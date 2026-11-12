from django.db.models import Case, Count, IntegerField, When
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .filters import TaskFilter, TaskOrderingFilter
from .models import Category, Subtask, Task
from .serializers import CategorySerializer, SubtaskSerializer, TaskSerializer


class TaskPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"  # Kanban board asks for more
    max_page_size = 100


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    pagination_class = None
    http_method_names = ["get", "post", "put", "delete", "head", "options"]

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user).annotate(task_count=Count("tasks"))

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    pagination_class = TaskPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, TaskOrderingFilter]
    filterset_class = TaskFilter
    search_fields = ["title", "description"]
    ordering_fields = ["due_date", "priority", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        # Scoping to the user means another user's task simply returns 404.
        return (
            Task.objects.filter(user=self.request.user)
            .select_related("category")
            .prefetch_related("subtasks")
            .annotate(
                priority_rank=Case(
                    When(priority=Task.Priority.HIGH, then=3),
                    When(priority=Task.Priority.MEDIUM, then=2),
                    default=1,
                    output_field=IntegerField(),
                )
            )
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)  # never from the request body

    @action(detail=True, methods=["patch"], url_path="toggle-complete")
    def toggle_complete(self, request, pk=None):
        task = self.get_object()
        task.status = Task.Status.TODO if task.status == Task.Status.DONE else Task.Status.DONE
        task.save()
        return Response(self.get_serializer(task).data)

    @action(detail=False, methods=["get"])
    def dashboard(self, request):
        qs = Task.objects.filter(user=request.user)
        today = timezone.localdate()
        total = qs.count()
        done = qs.filter(status=Task.Status.DONE).count()
        overdue_qs = qs.filter(due_date__lt=today).exclude(status=Task.Status.DONE)
        due_today_qs = qs.filter(due_date=today).exclude(status=Task.Status.DONE)
        per_category = (
            qs.values("category__id", "category__name", "category__color")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        ctx = {"request": request}
        return Response(
            {
                "total": total,
                "todo": qs.filter(status=Task.Status.TODO).count(),
                "in_progress": qs.filter(status=Task.Status.IN_PROGRESS).count(),
                "done": done,
                "overdue": overdue_qs.count(),
                "due_today": due_today_qs.count(),
                "completion_percentage": round(done / total * 100, 1) if total else 0,
                "categories": [
                    {
                        "id": row["category__id"],
                        "name": row["category__name"] or "Uncategorized",
                        "color": row["category__color"] or "#94A3B8",
                        "count": row["count"],
                    }
                    for row in per_category
                ],
                "overdue_tasks": TaskSerializer(
                    overdue_qs.select_related("category").prefetch_related("subtasks").order_by("due_date")[:10],
                    many=True, context=ctx,
                ).data,
                "due_today_tasks": TaskSerializer(
                    due_today_qs.select_related("category").prefetch_related("subtasks")[:10],
                    many=True, context=ctx,
                ).data,
            }
        )

    # ---- Subtasks (bonus) ----
    @action(detail=True, methods=["post"], url_path="subtasks")
    def add_subtask(self, request, pk=None):
        task = self.get_object()
        serializer = SubtaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(task=task)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch", "delete"], url_path=r"subtasks/(?P<subtask_id>\d+)")
    def subtask_detail(self, request, pk=None, subtask_id=None):
        task = self.get_object()
        subtask = get_object_or_404(Subtask.objects.filter(task=task), pk=subtask_id)
        if request.method == "DELETE":
            subtask.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        serializer = SubtaskSerializer(subtask, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
