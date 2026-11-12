import django_filters
from django.db.models import F
from django.utils import timezone
from rest_framework.filters import OrderingFilter

from .models import Category, Task


class TaskFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=Task.Status.choices)
    priority = django_filters.ChoiceFilter(choices=Task.Priority.choices)
    category = django_filters.ModelChoiceFilter(
        queryset=lambda request: Category.objects.filter(user=request.user)
    )
    due = django_filters.ChoiceFilter(
        choices=[("today", "Today"), ("overdue", "Overdue"), ("upcoming", "Upcoming")],
        method="filter_due",
    )

    class Meta:
        model = Task
        fields = ["status", "priority", "category", "due"]

    def filter_due(self, queryset, name, value):
        today = timezone.localdate()
        if value == "today":
            return queryset.filter(due_date=today)
        if value == "overdue":  # past due AND not Done
            return queryset.filter(due_date__lt=today).exclude(status=Task.Status.DONE)
        if value == "upcoming":
            return queryset.filter(due_date__gt=today)
        return queryset


class TaskOrderingFilter(OrderingFilter):
    """ordering=due_date|priority|created_at, '-' for descending.

    'priority' is sorted by meaning (Low < Medium < High), not alphabetically,
    and tasks without a due date always come last.
    """

    def filter_queryset(self, request, queryset, view):
        ordering = self.get_ordering(request, queryset, view)
        if not ordering:
            return queryset
        expressions = []
        for item in ordering:
            desc = item.startswith("-")
            name = item.lstrip("-")
            if name == "priority":
                name = "priority_rank"
            expr = F(name)
            expressions.append(expr.desc(nulls_last=True) if desc else expr.asc(nulls_last=True))
        expressions.append(F("id").desc())  # stable pagination
        return queryset.order_by(*expressions)
