from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from tasks.models import Task


class Command(BaseCommand):
    help = "Email each user a reminder for their unfinished tasks that are due tomorrow."

    def handle(self, *args, **options):
        tomorrow = timezone.localdate() + timedelta(days=1)
        tasks = (
            Task.objects.filter(due_date=tomorrow)
            .exclude(status=Task.Status.DONE)
            .select_related("user")
            .order_by("title")
        )
        by_user = defaultdict(list)
        for task in tasks:
            by_user[task.user].append(task)

        for user, user_tasks in by_user.items():
            lines = "\n".join(f"- {t.title} [{t.priority}]" for t in user_tasks)
            send_mail(
                subject=f"{len(user_tasks)} task(s) due tomorrow",
                message=f"Hi {user.first_name or 'there'},\n\nThese tasks are due tomorrow ({tomorrow}):\n\n{lines}\n",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
            )
        self.stdout.write(self.style.SUCCESS(f"Sent reminders to {len(by_user)} user(s)."))
