from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DayViewSet, TimeAnalysisViewSet

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r"time-analyses", TimeAnalysisViewSet, basename="timeanalysis")
router.register(r"days", DayViewSet, basename="day")

# The API URLs are now determined automatically by the router
urlpatterns = [
    path("api/", include(router.urls)),
]
