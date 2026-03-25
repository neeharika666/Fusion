from django.conf import settings
from django.db import models


class DepartmentInfo(models.Model):
    code = models.CharField(max_length=20, unique=True)  # e.g., CSE
    name = models.CharField(max_length=255)

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class ExtraInfo(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="extrainfo")
    department = models.ForeignKey(DepartmentInfo, on_delete=models.PROTECT, related_name="members")
    employee_id = models.CharField(max_length=50, blank=True, default="")

    def __str__(self) -> str:
        return f"{self.user.username} ({self.department.code})"


class Designation(models.Model):
    name = models.CharField(max_length=255, unique=True)  # e.g., "HOD CSE"

    def __str__(self) -> str:
        return self.name


class HoldsDesignation(models.Model):
    designation = models.ForeignKey(Designation, on_delete=models.PROTECT, related_name="holds")
    working = models.ForeignKey(ExtraInfo, on_delete=models.CASCADE, related_name="designations")
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["designation", "working"],
                name="uniq_designation_per_person",
            )
        ]

    def __str__(self) -> str:
        return f"{self.working} -> {self.designation}"

