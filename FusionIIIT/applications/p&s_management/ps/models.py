from django.conf import settings
from django.db import models

from accounts.models import DepartmentInfo, ExtraInfo


class StoreItem(models.Model):
    name = models.CharField(max_length=255, unique=True)
    unit = models.CharField(max_length=50, default="nos")  # e.g., nos/kg/ltr

    def __str__(self) -> str:
        return self.name


class CurrentStock(models.Model):
    item = models.OneToOneField(
        StoreItem, on_delete=models.CASCADE, related_name="stock"
    )
    quantity = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.item}: {self.quantity}"


class Indent(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        UNDER_HOD_REVIEW = "UNDER_HOD_REVIEW", "Under HOD Review"
        STOCK_CHECKED = "STOCK_CHECKED", "Stock Checked"
        INTERNAL_ISSUED = "INTERNAL_ISSUED", "Internal Issued"
        EXTERNAL_PROCUREMENT = "EXTERNAL_PROCUREMENT", "External Procurement"
        FORWARDED_TO_DIRECTOR = "FORWARDED_TO_DIRECTOR", "Forwarded to Director"
        APPROVED_BY_DEP_ADMIN = "APPROVED_BY_DEP_ADMIN", "Approved by Dept Admin"
        APPROVED = "APPROVED", "Approved"
        STOCKED = "STOCKED", "Stocked"
        REJECTED = "REJECTED", "Rejected"
        FORWARDED = "FORWARDED", "Forwarded"
        BIDDING = "BIDDING", "Bidding"
        PURCHASED = "PURCHASED", "Purchased"

    class ProcurementType(models.TextChoices):
        INTERNAL = "INTERNAL", "Internal Stock"
        EXTERNAL = "EXTERNAL", "External Procurement"

    indenter = models.ForeignKey(
        ExtraInfo, on_delete=models.PROTECT, related_name="indents"
    )
    department = models.ForeignKey(
        DepartmentInfo, on_delete=models.PROTECT, related_name="indents"
    )
    purpose = models.CharField(max_length=255)
    justification = models.TextField(blank=True, default="")
    estimated_cost = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    status = models.CharField(
        max_length=30, choices=Status.choices, default=Status.DRAFT
    )
    stock_available = models.BooleanField(default=False)
    procurement_type = models.CharField(
        max_length=20,
        choices=ProcurementType.choices,
        null=True,
        blank=True,
    )
    current_approver = models.ForeignKey(
        ExtraInfo,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pending_indents",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Indent #{self.id} by {self.indenter}"


class IndentItem(models.Model):
    indent = models.ForeignKey(Indent, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(
        StoreItem, on_delete=models.PROTECT, related_name="indent_lines"
    )
    quantity = models.PositiveIntegerField()
    estimated_cost = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["indent", "item"], name="uniq_item_per_indent"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.indent_id}: {self.item} x {self.quantity}"


class IndentAudit(models.Model):
    indent = models.ForeignKey(
        Indent, on_delete=models.CASCADE, related_name="audit_events"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    acting_role = models.CharField(max_length=50)  # EMPLOYEE/HOD
    action = models.CharField(max_length=50)  # SUBMIT/APPROVE/REJECT/FORWARD
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.indent_id} {self.action} by {self.user_id}"


class StockEntry(models.Model):
    indent = models.ForeignKey(
        Indent, on_delete=models.PROTECT, related_name="stock_entries"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="stock_entries"
    )
    acting_role = models.CharField(max_length=50)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"StockEntry #{self.id} for indent {self.indent_id}"


class StockEntryItem(models.Model):
    stock_entry = models.ForeignKey(
        StockEntry, on_delete=models.CASCADE, related_name="items"
    )
    item = models.ForeignKey(
        StoreItem, on_delete=models.PROTECT, related_name="stock_entry_lines"
    )
    quantity = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["stock_entry", "item"], name="uniq_item_per_stock_entry"
            ),
        ]

    def __str__(self) -> str:
        return f"StockEntry {self.stock_entry_id}: {self.item_id} x {self.quantity}"
