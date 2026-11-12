from django.contrib import admin

from .models import Category, Subtask, Task


class SubtaskInline(admin.TabularInline):
    model = Subtask
    extra = 0


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "color")
    search_fields = ("name", "user__email")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "priority", "status", "due_date")
    list_filter = ("status", "priority")
    search_fields = ("title",)
    readonly_fields = ("completed_at", "created_at", "updated_at")
    inlines = [SubtaskInline]
