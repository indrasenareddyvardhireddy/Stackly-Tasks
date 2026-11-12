from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import Category, Task

User = get_user_model()


def make_user(email="a@example.com"):
    return User.objects.create_user(email=email, password="StrongPass123", first_name="A", last_name="B")


class BaseTest(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.other = make_user("b@example.com")
        self.client.force_authenticate(self.user)
        self.today = timezone.localdate()

    def create(self, **data):
        payload = {"title": "Sample task", **data}
        return self.client.post(reverse("task-list"), payload, format="json")


class AuthRequiredTests(APITestCase):
    def test_endpoints_require_token(self):
        for name in ("task-list", "category-list", "task-dashboard"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 401)


class CategoryTests(BaseTest):
    def test_unique_per_user_and_isolated(self):
        self.assertEqual(self.client.post(reverse("category-list"), {"name": "Work", "color": "#112233"}).status_code, 201)
        dup = self.client.post(reverse("category-list"), {"name": "work", "color": "#112233"})
        self.assertEqual(dup.status_code, 400)
        self.assertIn("name", dup.data)
        Category.objects.create(user=self.other, name="Secret")
        names = [c["name"] for c in self.client.get(reverse("category-list")).data]
        self.assertEqual(names, ["Work"])

    def test_delete_keeps_tasks(self):
        cat = Category.objects.create(user=self.user, name="Work")
        task = Task.objects.create(user=self.user, title="Keep me", category=cat)
        self.assertEqual(self.client.delete(reverse("category-detail", args=[cat.id])).status_code, 204)
        task.refresh_from_db()
        self.assertIsNone(task.category)


class TaskTests(BaseTest):
    def test_user_set_from_login_not_body(self):
        res = self.create(user=self.other.id)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Task.objects.get(pk=res.data["id"]).user, self.user)

    def test_title_and_past_due_date_validation(self):
        self.assertIn("title", self.create(title="ab").data)
        past = self.create(due_date=str(self.today - timedelta(days=1)))
        self.assertEqual(past.status_code, 400)
        self.assertIn("due_date", past.data)

    def test_other_users_task_is_404(self):
        theirs = Task.objects.create(user=self.other, title="Not yours")
        url = reverse("task-detail", args=[theirs.id])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertEqual(self.client.patch(reverse("task-toggle-complete", args=[theirs.id])).status_code, 404)

    def test_cannot_use_other_users_category(self):
        cat = Category.objects.create(user=self.other, name="Theirs")
        res = self.create(category=cat.id)
        self.assertEqual(res.status_code, 400)
        self.assertIn("category", res.data)

    def test_completed_at_and_toggle(self):
        task_id = self.create().data["id"]
        res = self.client.patch(reverse("task-detail", args=[task_id]), {"status": "Done"}, format="json")
        self.assertIsNotNone(res.data["completed_at"])
        res = self.client.patch(reverse("task-detail", args=[task_id]), {"status": "In Progress"}, format="json")
        self.assertIsNone(res.data["completed_at"])
        url = reverse("task-toggle-complete", args=[task_id])
        self.assertEqual(self.client.patch(url).data["status"], "Done")
        self.assertEqual(self.client.patch(url).data["status"], "To Do")

    def test_filters_search_ordering_pagination(self):
        yesterday = self.today - timedelta(days=1)
        Task.objects.create(user=self.user, title="Overdue high", priority="High", due_date=yesterday)
        Task.objects.create(user=self.user, title="Done old", status="Done", due_date=yesterday)
        Task.objects.create(user=self.user, title="Today low", priority="Low", due_date=self.today)
        Task.objects.create(user=self.user, title="Future medium", due_date=self.today + timedelta(days=3))
        url = reverse("task-list")
        titles = lambda r: [t["title"] for t in r.data["results"]]  # noqa: E731
        self.assertEqual(titles(self.client.get(url, {"due": "overdue"})), ["Overdue high"])
        self.assertEqual(titles(self.client.get(url, {"due": "today"})), ["Today low"])
        self.assertEqual(titles(self.client.get(url, {"due": "upcoming"})), ["Future medium"])
        self.assertEqual(titles(self.client.get(url, {"status": "Done"})), ["Done old"])
        self.assertEqual(titles(self.client.get(url, {"search": "future"})), ["Future medium"])
        self.assertEqual(titles(self.client.get(url, {"ordering": "-priority"}))[0], "Overdue high")
        self.assertEqual(titles(self.client.get(url, {"ordering": "due_date"}))[0], "Done old")
        self.assertEqual(self.client.get(url, {"status": "Nope"}).status_code, 400)

    def test_pagination_ten_per_page(self):
        for i in range(12):
            Task.objects.create(user=self.user, title=f"Task {i:02d}")
        res = self.client.get(reverse("task-list"))
        self.assertEqual(res.data["count"], 12)
        self.assertEqual(len(res.data["results"]), 10)
        self.assertIsNotNone(res.data["next"])
        self.assertEqual(len(self.client.get(reverse("task-list"), {"page": 2}).data["results"]), 2)

    def test_dashboard(self):
        cat = Category.objects.create(user=self.user, name="Work")
        Task.objects.create(user=self.user, title="One", category=cat, due_date=self.today - timedelta(days=1))
        Task.objects.create(user=self.user, title="Two", status="Done")
        Task.objects.create(user=self.user, title="Three", status="In Progress", due_date=self.today)
        Task.objects.create(user=self.other, title="Not mine")
        data = self.client.get(reverse("task-dashboard")).data
        self.assertEqual(data["total"], 3)
        self.assertEqual((data["todo"], data["in_progress"], data["done"]), (1, 1, 1))
        self.assertEqual((data["overdue"], data["due_today"]), (1, 1))
        self.assertEqual(data["completion_percentage"], 33.3)
        self.assertEqual({c["name"]: c["count"] for c in data["categories"]}, {"Work": 1, "Uncategorized": 2})

    def test_subtasks(self):
        task_id = self.create().data["id"]
        sub = self.client.post(reverse("task-add-subtask", args=[task_id]), {"title": "Step 1"})
        self.assertEqual(sub.status_code, 201)
        url = reverse("task-subtask-detail", args=[task_id, sub.data["id"]])
        self.assertTrue(self.client.patch(url, {"is_done": True}).data["is_done"])
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_recurring_task_spawns_next_once(self):
        res = self.create(recurrence="weekly", due_date=str(self.today))
        url = reverse("task-toggle-complete", args=[res.data["id"]])
        self.client.patch(url)  # Done -> creates next
        self.client.patch(url)  # To Do
        self.client.patch(url)  # Done again -> no duplicate
        copies = Task.objects.filter(user=self.user, title="Sample task", status="To Do")
        self.assertEqual(copies.count(), 1)  # exactly one next occurrence, no duplicates
        self.assertTrue(Task.objects.filter(due_date=self.today + timedelta(days=7)).exists())


class ReminderCommandTests(BaseTest):
    def test_reminder_email(self):
        Task.objects.create(user=self.user, title="Due tomorrow", due_date=self.today + timedelta(days=1))
        Task.objects.create(user=self.user, title="Finished", status="Done", due_date=self.today + timedelta(days=1))
        call_command("send_task_reminders")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Due tomorrow", mail.outbox[0].body)
        self.assertNotIn("Finished", mail.outbox[0].body)
