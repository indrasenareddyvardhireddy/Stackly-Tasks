from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from tasks.models import Category, Subtask, Task

User = get_user_model()


class Command(BaseCommand):
    help = "Create the demo user (demo@example.com / Demo@12345) with sample data."

    def handle(self, *args, **options):
        user, created = User.objects.get_or_create(
            email="demo@example.com", defaults={"first_name": "Demo", "last_name": "User"}
        )
        user.set_password("Demo@12345")
        user.save()
        if not created and user.tasks.exists():
            self.stdout.write("Demo user already has data; password reset only.")
            return

        work = Category.objects.create(user=user, name="Work", color="#4F46E5")
        personal = Category.objects.create(user=user, name="Personal", color="#059669")
        study = Category.objects.create(user=user, name="Study", color="#D97706")
        today = timezone.localdate()
        T = Task.Status
        rows = [
            ("Finish quarterly report", work, "High", T.IN_PROGRESS, today + timedelta(days=2)),
            ("Email the design team", work, "Medium", T.TODO, today),
            ("Pay electricity bill", personal, "High", T.TODO, today - timedelta(days=2)),
            ("Buy groceries", personal, "Low", T.TODO, today + timedelta(days=1)),
            ("Read Django REST docs", study, "Medium", T.DONE, today - timedelta(days=1)),
            ("Practice React hooks", study, "Medium", T.TODO, today + timedelta(days=5)),
            ("Book dentist appointment", personal, "Low", T.TODO, None),
        ]
        for title, cat, prio, status, due in rows:
            Task.objects.create(user=user, title=title, category=cat, priority=prio, status=status, due_date=due)
        first = Task.objects.get(user=user, title="Finish quarterly report")
        for title, done in [("Collect numbers", True), ("Write summary", False), ("Send for review", False)]:
            Subtask.objects.create(task=first, title=title, is_done=done)
        self.stdout.write(self.style.SUCCESS("Demo data created: demo@example.com / Demo@12345"))
