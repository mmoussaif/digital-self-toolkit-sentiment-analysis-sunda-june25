from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DayViewSet,
    LocationViewSet,
    MessageViewSet,
    PersonAnalysisViewSet,
    PlaceAnalysisViewSet,
    TimeAnalysisViewSet,
    WebsiteAnalysisViewSet,
)

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r"time-analyses", TimeAnalysisViewSet, basename="timeanalysis")
router.register(r"days", DayViewSet, basename="day")
router.register(r"messages", MessageViewSet, basename="message")
router.register(r"locations", LocationViewSet, basename="location")
router.register(r"website-analyses", WebsiteAnalysisViewSet, basename="websiteanalysis")
router.register(r"person-analyses", PersonAnalysisViewSet, basename="personanalysis")
router.register(r"place-analyses", PlaceAnalysisViewSet, basename="placeanalysis")

# The API URLs are now determined automatically by the router
urlpatterns = [
    path("api/", include(router.urls)),
]
