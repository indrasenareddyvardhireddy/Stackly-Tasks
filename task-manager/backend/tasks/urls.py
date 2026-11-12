from rest_framework.routers import SimpleRouter

from .views import CategoryViewSet, TaskViewSet

router = SimpleRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("tasks", TaskViewSet, basename="task")

urlpatterns = router.urls
