from __future__ import annotations

from typing import Any, Dict, Optional

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from ps.rbac import ActingRole
from ps.selectors import (
    check_stock_availability_for_indent_id,
    get_department_depadmin,
    get_department_hod,
    get_department_by_code,
    get_first_holder_by_designation,
    get_indent_data,
    get_indent_for_hod_action,
    get_indent_for_stock_entry,
    get_indent_for_stock_check,
    validate_store_item_ids,
)
from ps.models import (
    CurrentStock,
    Indent,
    IndentAudit,
    IndentItem,
    StockEntry,
    StockEntryItem,
)
from ps.serializers import StockEntrySerializer


def create_indent(validated_data: Dict[str, Any], actor, request_user) -> dict:
    if actor.role != ActingRole.EMPLOYEE:
        raise ValidationError("Only employees can submit indents.")

    item_lines = validated_data["items"]
    item_ids = [int(i["item_id"]) for i in item_lines]
    validate_store_item_ids(item_ids)

    indenter = actor.extrainfo
    department = indenter.department

    indent = Indent.objects.create(
        indenter=indenter,
        department=department,
        purpose=validated_data["purpose"],
        justification=validated_data.get("justification", ""),
        estimated_cost=validated_data.get("estimated_cost"),
        status=Indent.Status.SUBMITTED,
    )

    for line in item_lines:
        IndentItem.objects.create(
            indent=indent,
            item_id=int(line["item_id"]),
            quantity=int(line["quantity"]),
            estimated_cost=line.get("estimated_cost"),
        )

    indent.stock_available = check_stock_availability_for_indent_id(indent.id)

    hod = get_department_hod(department)
    indent.current_approver = hod if hod else get_department_depadmin(department)
    indent.status = Indent.Status.SUBMITTED
    indent.save(
        update_fields=["stock_available", "current_approver", "status", "updated_at"]
    )

    IndentAudit.objects.create(
        indent=indent,
        user=request_user,
        acting_role=actor.role,
        action="SUBMIT",
        notes="",
    )

    return get_indent_data(indent.id)


def apply_hod_action(
    indent_id: int,
    actor,
    action_name: str,
    notes: str = "",
    forward_to_department_code: Optional[str] = None,
    request_user=None,
) -> dict:
    # Read-only permission + loading
    indent = get_indent_for_hod_action(indent_id, actor)

    # Write logic
    if action_name == "APPROVE":
        if actor.role == ActingRole.DEPADMIN:
            if indent.status != Indent.Status.STOCK_CHECKED:
                raise ValidationError(
                    {"detail": "Please check stock before approving."}
                )
            indent.status = (
                Indent.Status.INTERNAL_ISSUED
                if indent.stock_available
                else Indent.Status.EXTERNAL_PROCUREMENT
            )
            indent.current_approver = None
            indent.save(update_fields=["status", "current_approver", "updated_at"])

        elif actor.role == ActingRole.HOD:
            next_approver = get_department_depadmin(indent.department)
            if not next_approver:
                raise ValidationError(
                    {"detail": "No DepAdmin found for this department."}
                )
            indent.current_approver = next_approver
            indent.status = Indent.Status.FORWARDED
            indent.save(update_fields=["status", "current_approver", "updated_at"])

        elif actor.role in (ActingRole.REGISTRAR, ActingRole.DIRECTOR):
            indent.status = Indent.Status.APPROVED
            indent.current_approver = None
            indent.save(update_fields=["status", "current_approver", "updated_at"])
        else:
            raise ValidationError({"action": "Invalid approver role"})

    elif action_name == "REJECT":
        indent.status = Indent.Status.REJECTED
        indent.current_approver = None
        indent.save(update_fields=["status", "current_approver", "updated_at"])

    elif action_name == "FORWARD":
        dept_code = (forward_to_department_code or "").strip()
        if dept_code:
            target_dept = get_department_by_code(dept_code)
            target_hod = get_department_hod(target_dept)
            indent.department = target_dept
            indent.current_approver = target_hod
            indent.status = (
                Indent.Status.FORWARDED if target_hod else Indent.Status.SUBMITTED
            )
            indent.save(
                update_fields=["department", "current_approver", "status", "updated_at"]
            )
        else:
            if actor.role != ActingRole.DEPADMIN:
                raise PermissionDenied("Only DepAdmin can forward to Director.")
            next_approver = get_first_holder_by_designation("director")
            if not next_approver:
                raise ValidationError({"detail": "No Director found to forward to."})
            indent.current_approver = next_approver
            indent.status = Indent.Status.FORWARDED_TO_DIRECTOR
            indent.save(update_fields=["current_approver", "status", "updated_at"])
    else:
        raise ValidationError({"action": "Invalid action"})

    IndentAudit.objects.create(
        indent=indent,
        user=request_user,
        acting_role=actor.role,
        action=action_name,
        notes=notes,
    )

    return get_indent_data(indent.id)


def check_stock_action(indent_id: int, actor, request_user) -> dict:
    indent = get_indent_for_stock_check(indent_id, actor)

    indent.stock_available = check_stock_availability_for_indent_id(indent.id)
    indent.procurement_type = (
        Indent.ProcurementType.INTERNAL
        if indent.stock_available
        else Indent.ProcurementType.EXTERNAL
    )
    indent.status = Indent.Status.STOCK_CHECKED
    indent.save(
        update_fields=["stock_available", "procurement_type", "status", "updated_at"]
    )

    IndentAudit.objects.create(
        indent=indent,
        user=request_user,
        acting_role=actor.role,
        action="CHECK_STOCK",
        notes="",
    )

    return get_indent_data(indent.id)


def create_stock_entry(
    indent_id: int,
    actor,
    request_user,
    item_lines: list[dict],
    notes: str = "",
) -> dict:
    indent = get_indent_for_stock_entry(indent_id, actor)

    requested_map = {
        int(line.item_id): int(line.quantity) for line in indent.items.all()
    }
    payload_map = {int(line["item_id"]): int(line["quantity"]) for line in item_lines}

    if set(requested_map.keys()) != set(payload_map.keys()):
        raise ValidationError(
            {"items": "Payload items must exactly match indent items."}
        )

    for item_id, qty in payload_map.items():
        if qty <= 0:
            raise ValidationError(
                {"items": f"Quantity must be > 0 for item_id {item_id}."}
            )
        if qty != requested_map[item_id]:
            raise ValidationError(
                {"items": f"Quantity mismatch for item_id {item_id}."}
            )

    with transaction.atomic():
        entry = StockEntry.objects.create(
            indent=indent,
            created_by=request_user,
            acting_role=actor.role,
            notes=notes or "",
        )

        for item_id, qty in payload_map.items():
            StockEntryItem.objects.create(
                stock_entry=entry, item_id=item_id, quantity=qty
            )
            stock, _ = CurrentStock.objects.get_or_create(
                item_id=item_id, defaults={"quantity": 0}
            )
            stock.quantity += qty
            stock.save(update_fields=["quantity", "updated_at"])

        indent.status = Indent.Status.STOCKED
        indent.current_approver = None
        indent.save(update_fields=["status", "current_approver", "updated_at"])

        IndentAudit.objects.create(
            indent=indent,
            user=request_user,
            acting_role=actor.role,
            action="STOCK_ENTRY",
            notes=notes or "",
        )

    return {
        "indent": get_indent_data(indent.id),
        "stock_entry": StockEntrySerializer(entry).data,
    }


def apply_ps_admin_action(
    indent_id: int,
    actor,
    action_name: str,
    notes: str = "",
    request_user=None,
) -> dict:
    """Handle PS_ADMIN actions: BIDDING, PURCHASE and STOCK_ENTRY"""
    if actor.role != ActingRole.PS_ADMIN:
        raise PermissionDenied("Only PS_ADMIN can perform this action.")

    indent = Indent.objects.get(id=indent_id)

    if action_name == "BIDDING":
        # Move from PENDING to BIDDING
        if indent.status != Indent.Status.APPROVED:
            raise ValidationError(
                {"detail": "Only APPROVED indents can move to BIDDING status."}
            )
        indent.status = Indent.Status.BIDDING
        indent.save(update_fields=["status", "updated_at"])

    elif action_name == "PURCHASE":
        # Move from pending/bidding to purchased; stock update happens on STOCK_ENTRY.
        if indent.status not in (Indent.Status.APPROVED, Indent.Status.BIDDING):
            raise ValidationError(
                {
                    "detail": "Only APPROVED or BIDDING indents can be marked as PURCHASED."
                }
            )

        indent.status = Indent.Status.PURCHASED
        indent.current_approver = None
        indent.save(update_fields=["status", "current_approver", "updated_at"])

    elif action_name == "STOCK_ENTRY":
        if indent.status != Indent.Status.PURCHASED:
            raise ValidationError(
                {"detail": "Only PURCHASED indents can be moved to STOCKED."}
            )

        with transaction.atomic():
            entry = StockEntry.objects.create(
                indent=indent,
                created_by=request_user,
                acting_role=actor.role,
                notes=notes or "",
            )

            for item_line in indent.items.all():
                StockEntryItem.objects.create(
                    stock_entry=entry,
                    item_id=item_line.item_id,
                    quantity=item_line.quantity,
                )
                stock, _ = CurrentStock.objects.get_or_create(
                    item_id=item_line.item_id, defaults={"quantity": 0}
                )
                stock.quantity += item_line.quantity
                stock.save(update_fields=["quantity", "updated_at"])

            indent.status = Indent.Status.STOCKED
            indent.current_approver = None
            indent.save(update_fields=["status", "current_approver", "updated_at"])

    else:
        raise ValidationError({"action": "Invalid action"})

    IndentAudit.objects.create(
        indent=indent,
        user=request_user,
        acting_role=actor.role,
        action=action_name,
        notes=notes,
    )

    return get_indent_data(indent.id)
