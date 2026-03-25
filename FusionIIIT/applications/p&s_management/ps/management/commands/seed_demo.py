from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import DepartmentInfo, Designation, ExtraInfo, HoldsDesignation
from ps.models import CurrentStock, StoreItem


class Command(BaseCommand):
    help = "Seed demo data for WF-PS-001"

    def handle(self, *args, **options):
        User = get_user_model()

        cse, _ = DepartmentInfo.objects.get_or_create(
            code="CSE", defaults={"name": "Computer Science & Engineering"}
        )
        ece, _ = DepartmentInfo.objects.get_or_create(
            code="ECE", defaults={"name": "Electronics & Communication"}
        )

        hod_cse_desig, _ = Designation.objects.get_or_create(name="HOD CSE")
        hod_ece_desig, _ = Designation.objects.get_or_create(name="HOD ECE")
        depadmin_cse_desig, _ = Designation.objects.get_or_create(name="DepAdmin CSE")
        depadmin_ece_desig, _ = Designation.objects.get_or_create(name="DepAdmin ECE")
        registrar_desig, _ = Designation.objects.get_or_create(name="Registrar")
        director_desig, _ = Designation.objects.get_or_create(name="Director")
        accounts_desig, _ = Designation.objects.get_or_create(name="Accounts Admin")
        ps_admin_desig, _ = Designation.objects.get_or_create(name="PS Admin")

        def ensure_user(username, password, dept):
            user, created = User.objects.get_or_create(
                username=username, defaults={"email": f"{username}@example.com"}
            )
            if created:
                user.set_password(password)
                user.save(update_fields=["password"])
            extrainfo, _ = ExtraInfo.objects.get_or_create(
                user=user, defaults={"department": dept, "employee_id": username}
            )
            if extrainfo.department_id != dept.id:
                extrainfo.department = dept
                extrainfo.save(update_fields=["department"])
            return user, extrainfo

        _, emp_cse = ensure_user("emp_cse", "pass1234", cse)
        _, emp_ece = ensure_user("emp_ece", "pass1234", ece)
        _, depadmin_cse = ensure_user("depadmin_cse", "pass1234", cse)
        _, depadmin_ece = ensure_user("depadmin_ece", "pass1234", ece)
        _, hod_cse = ensure_user("hod_cse", "pass1234", cse)
        _, hod_ece = ensure_user("hod_ece", "pass1234", ece)
        _, registrar = ensure_user("registrar", "pass1234", cse)
        _, director = ensure_user("director", "pass1234", cse)
        _, accounts = ensure_user("accounts", "pass1234", cse)
        _, ps_admin = ensure_user("ps_admin", "pass1234", cse)

        HoldsDesignation.objects.get_or_create(
            designation=depadmin_cse_desig,
            working=depadmin_cse,
            defaults={"is_active": True},
        )
        HoldsDesignation.objects.get_or_create(
            designation=depadmin_ece_desig,
            working=depadmin_ece,
            defaults={"is_active": True},
        )
        HoldsDesignation.objects.get_or_create(
            designation=hod_cse_desig, working=hod_cse, defaults={"is_active": True}
        )
        HoldsDesignation.objects.get_or_create(
            designation=hod_ece_desig, working=hod_ece, defaults={"is_active": True}
        )
        HoldsDesignation.objects.get_or_create(
            designation=registrar_desig, working=registrar, defaults={"is_active": True}
        )
        HoldsDesignation.objects.get_or_create(
            designation=director_desig, working=director, defaults={"is_active": True}
        )
        HoldsDesignation.objects.get_or_create(
            designation=accounts_desig, working=accounts, defaults={"is_active": True}
        )
        HoldsDesignation.objects.get_or_create(
            designation=ps_admin_desig, working=ps_admin, defaults={"is_active": True}
        )

        pen, _ = StoreItem.objects.get_or_create(name="Pen", defaults={"unit": "nos"})
        paper, _ = StoreItem.objects.get_or_create(
            name="A4 Paper", defaults={"unit": "ream"}
        )
        CurrentStock.objects.get_or_create(item=pen, defaults={"quantity": 100})
        CurrentStock.objects.get_or_create(item=paper, defaults={"quantity": 2})

        self.stdout.write(self.style.SUCCESS("Seeded demo data."))
        self.stdout.write(
            "Demo users (password: pass1234): emp_cse, emp_ece, depadmin_cse, depadmin_ece, hod_cse, hod_ece, registrar, director, accounts, ps_admin"
        )
