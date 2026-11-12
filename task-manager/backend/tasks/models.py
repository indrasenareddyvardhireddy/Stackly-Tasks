from datetime import timedelta

from django.conf import settings
from django.core.validators import MinLengthValidator, RegexValidator
from django.db import models
from django.utils import timezone


class Category(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=50)
    color = models.CharField(
        max_length=7,
        default="#4F46E5",
        validators=[RegexValidator(r"^#[0-9a-fA-F]{6}$", "Enter a valid hex colour such as #4F46E5.")],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"
        constraints = [models.UniqueConstraint(fields=["user", "name"], name="unique_category_name_per_user")]

    def __str__(self):
        return self.name


class Task(models.Model):
    class Priority(models.TextChoices):
        LOW = "Low", "Low"
        MEDIUM = "Medium", "Medium"
        HIGH = "High", "High"

    class Status(models.TextChoices):
        TODO = "To Do", "To Do"
        IN_PROGRESS = "In Progress", "In Progress"
        DONE = "Done", "Done"

    class Recurrence(models.TextChoices):  # bonus
        NONE = "none", "Does not repeat"
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=100, validators=[MinLengthValidator(3)])
    description = models.TextField(blank=True)
    # Deleting a category keeps the task; it just has no category.
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="tasks")
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.TODO)
    due_date = models.DateField(null=True, blank=True)
    recurrence = models.CharField(max_length=10, choices=Recurrence.choices, default=Recurrence.NONE)
    next_created = models.BooleanField(default=False, editable=False)
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        return bool(self.due_date and self.due_date < timezone.localdate() and self.status != self.Status.DONE)

    def save(self, *args, **kwargs):
        # completed_at follows status automatically (API, admin, anywhere).
        if self.status == self.Status.DONE:
            if self.completed_at is None:
                self.completed_at = timezone.now()
        else:
            self.completed_at = None
        super().save(*args, **kwargs)
        if self.status == self.Status.DONE and self.recurrence != self.Recurrence.NONE and not self.next_created:
            self._spawn_next_occurrence()

    def _spawn_next_occurrence(self):
        step = timedelta(days=1 if self.recurrence == self.Recurrence.DAILY else 7)
        base = self.due_date or timezone.localdate()
        new_task = Task.objects.create(
            user=self.user,
            title=self.title,
            description=self.description,
            category=self.category,
            priority=self.priority,
            status=self.Status.TODO,
            due_date=base + step,
            recurrence=self.recurrence,
        )
        Subtask.objects.bulk_create([Subtask(task=new_task, title=s.title) for s in self.subtasks.all()])
        Task.objects.filter(pk=self.pk).update(next_created=True)
        self.next_created = True


class Subtask(models.Model):  # bonus: checklist inside a task
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="subtasks")
    title = models.CharField(max_length=200)
    is_done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.title
