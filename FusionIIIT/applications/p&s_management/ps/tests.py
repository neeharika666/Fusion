from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import DepartmentInfo, Designation, ExtraInfo, HoldsDesignation
from ps.models import (
    CurrentStock,
    Indent,
    IndentAudit,
    IndentItem,
    StockEntry,
    StoreItem,
)
from ps.rbac import ActingRole
from ps.services import create_stock_entry


class WorkflowPs002StockEntryTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.dept = DepartmentInfo.objects.create(code="CSE", name="Computer Science")
        self.other_dept = DepartmentInfo.objects.create(code="ECE", name="Electronics")

        self.depadmin_designation = Designation.objects.create(name="DepAdmin CSE")
        self.ps_admin_designation = Designation.objects.create(name="PS Admin")

        self.depadmin_user = User.objects.create_user(
            username="depadmin", password="pass1234"
        )
        self.ps_admin_user = User.objects.create_user(
            username="psadmin", password="pass1234"
        )
        self.employee_user = User.objects.create_user(
            username="employee", password="pass1234"
        )

        self.depadmin_info = ExtraInfo.objects.create(
            user=self.depadmin_user, department=self.dept, employee_id="depadmin"
        )
        self.ps_admin_info = ExtraInfo.objects.create(
            user=self.ps_admin_user, department=self.dept, employee_id="psadmin"
        )
        self.employee_info = ExtraInfo.objects.create(
            user=self.employee_user, department=self.dept, employee_id="employee"
        )

        HoldsDesignation.objects.create(
            designation=self.depadmin_designation,
            working=self.depadmin_info,
            is_active=True,
        )
        HoldsDesignation.objects.create(
            designation=self.ps_admin_designation,
            working=self.ps_admin_info,
            is_active=True,
        )

        self.item1 = StoreItem.objects.create(name="Pen", unit="nos")
        self.item2 = StoreItem.objects.create(name="A4 Paper", unit="ream")
        CurrentStock.objects.create(item=self.item1, quantity=10)
        CurrentStock.objects.create(item=self.item2, quantity=3)

        self.indent = Indent.objects.create(
            indenter=self.employee_info,
            department=self.dept,
            purpose="Procure stationery",
            status=Indent.Status.EXTERNAL_PROCUREMENT,
        )
        IndentItem.objects.create(indent=self.indent, item=self.item1, quantity=5)
        IndentItem.objects.create(indent=self.indent, item=self.item2, quantity=2)

    def _actor(self, role, extrainfo):
        return SimpleNamespace(role=role, extrainfo=extrainfo)

    def test_ps_admin_can_create_stock_entry_and_increase_inventory(self):
        actor = self._actor(ActingRole.PS_ADMIN, self.ps_admin_info)

        result = create_stock_entry(
            indent_id=self.indent.id,
            actor=actor,
            request_user=self.ps_admin_user,
            item_lines=[
                {"item_id": self.item1.id, "quantity": 5},
                {"item_id": self.item2.id, "quantity": 2},
            ],
            notes="Goods received from supplier",
        )

        self.indent.refresh_from_db()
        self.assertEqual(self.indent.status, Indent.Status.STOCKED)

        stock1 = CurrentStock.objects.get(item=self.item1)
        stock2 = CurrentStock.objects.get(item=self.item2)
        self.assertEqual(stock1.quantity, 15)
        self.assertEqual(stock2.quantity, 5)

        self.assertEqual(StockEntry.objects.count(), 1)
        entry = StockEntry.objects.first()
        self.assertEqual(entry.acting_role, ActingRole.PS_ADMIN)
        self.assertEqual(entry.items.count(), 2)
        self.assertEqual(
            IndentAudit.objects.filter(
                indent=self.indent, action="STOCK_ENTRY"
            ).count(),
            1,
        )
        self.assertEqual(result["indent"]["status"], Indent.Status.STOCKED)

    def test_depadmin_cannot_create_stock_entry_for_other_department(self):
        other_indent = Indent.objects.create(
            indenter=self.employee_info,
            department=self.other_dept,
            purpose="Other dept indent",
            status=Indent.Status.EXTERNAL_PROCUREMENT,
        )
        IndentItem.objects.create(indent=other_indent, item=self.item1, quantity=1)

        actor = self._actor(ActingRole.DEPADMIN, self.depadmin_info)

        with self.assertRaises(PermissionDenied):
            create_stock_entry(
                indent_id=other_indent.id,
                actor=actor,
                request_user=self.depadmin_user,
                item_lines=[{"item_id": self.item1.id, "quantity": 1}],
            )

    def test_reject_when_payload_item_ids_do_not_match_indent(self):
        actor = self._actor(ActingRole.PS_ADMIN, self.ps_admin_info)

        with self.assertRaises(ValidationError):
            create_stock_entry(
                indent_id=self.indent.id,
                actor=actor,
                request_user=self.ps_admin_user,
                item_lines=[{"item_id": self.item1.id, "quantity": 5}],
            )

        self.assertEqual(StockEntry.objects.count(), 0)

    def test_reject_when_quantity_mismatch(self):
        actor = self._actor(ActingRole.PS_ADMIN, self.ps_admin_info)

        with self.assertRaises(ValidationError):
            create_stock_entry(
                indent_id=self.indent.id,
                actor=actor,
                request_user=self.ps_admin_user,
                item_lines=[
                    {"item_id": self.item1.id, "quantity": 4},
                    {"item_id": self.item2.id, "quantity": 2},
                ],
            )

        self.assertEqual(CurrentStock.objects.get(item=self.item1).quantity, 10)
        self.assertEqual(StockEntry.objects.count(), 0)

    def test_reject_when_indent_status_not_procurement_ready(self):
        self.indent.status = Indent.Status.REJECTED
        self.indent.save(update_fields=["status", "updated_at"])

        actor = self._actor(ActingRole.PS_ADMIN, self.ps_admin_info)

        with self.assertRaises(ValidationError):
            create_stock_entry(
                indent_id=self.indent.id,
                actor=actor,
                request_user=self.ps_admin_user,
                item_lines=[
                    {"item_id": self.item1.id, "quantity": 5},
                    {"item_id": self.item2.id, "quantity": 2},
                ],
            )

    def test_employee_cannot_create_stock_entry(self):
        actor = self._actor(ActingRole.EMPLOYEE, self.employee_info)

        with self.assertRaises(PermissionDenied):
            create_stock_entry(
                indent_id=self.indent.id,
                actor=actor,
                request_user=self.employee_user,
                item_lines=[
                    {"item_id": self.item1.id, "quantity": 5},
                    {"item_id": self.item2.id, "quantity": 2},
                ],
            )
