from django.utils import timezone
from rest_framework import serializers

from .models import Category, Subtask, Task


class CategorySerializer(serializers.ModelSerializer):
    task_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "color", "task_count", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Name cannot be blank.")
        qs = Category.objects.filter(user=self.context["request"].user, name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("You already have a category with this name.")
        return value


class CategoryMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "color"]


class SubtaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subtask
        fields = ["id", "title", "is_done"]

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Title cannot be blank.")
        return value


class TaskSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.none(), allow_null=True, required=False)
    category_detail = CategoryMiniSerializer(source="category", read_only=True)
    subtasks = SubtaskSerializer(many=True, read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Task
        fields = [
            "id", "title", "description", "category", "category_detail", "priority", "status",
            "due_date", "recurrence", "is_overdue", "subtasks", "completed_at", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "completed_at", "created_at", "updated_at"]

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            # A task may only use the logged-in user's own categories.
            fields["category"].queryset = Category.objects.filter(user=request.user)
            fields["category"].error_messages["does_not_exist"] = "Choose one of your own categories."
        return fields

    def validate_title(self, value):
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError("Title must be at least 3 characters.")
        if len(value) > 100:
            raise serializers.ValidationError("Title must be at most 100 characters.")
        return value

    def validate_due_date(self, value):
        # Only enforced on creation so old tasks can still be edited.
        if self.instance is None and value and value < timezone.localdate():
            raise serializers.ValidationError("Due date cannot be in the past.")
        return value
