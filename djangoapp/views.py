from datetime import datetime

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .filters import MessageFilter
from .models import (
    Day,
    Location,
    Message,
    PersonAnalysis,
    PlaceAnalysis,
    TimeAnalysis,
    WebsiteAnalysis,
)
from .serializers import (
    DaySerializer,
    LocationSerializer,
    MessageSerializer,
    PersonAnalysisSerializer,
    PlaceAnalysisSerializer,
    TimeAnalysisCreateSerializer,
    TimeAnalysisSerializer,
    WebsiteAnalysisSerializer,
)

# Create your views here.


class TimeAnalysisViewSet(viewsets.ModelViewSet):
    """
    ViewSet for TimeAnalysis model.
    Supports filtering by date range and status.
    """

    queryset = TimeAnalysis.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status"]

    def get_serializer_class(self):
        if self.action == "create":
            return TimeAnalysisCreateSerializer
        return TimeAnalysisSerializer

    def get_queryset(self):
        queryset = TimeAnalysis.objects.all()

        # Filter by date range if provided
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")

        if start_date:
            try:
                start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
                queryset = queryset.filter(start_date__gte=start_date)
            except ValueError:
                pass

        if end_date:
            try:
                end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
                queryset = queryset.filter(end_date__lte=end_date)
            except ValueError:
                pass

        return queryset.prefetch_related("days").order_by("-created_at")

    @action(detail=True, methods=["post"])
    def rerun_analysis(self, request, pk=None):
        """Rerun sentiment analysis for a specific TimeAnalysis."""
        time_analysis = self.get_object()

        if time_analysis.status == "processing":
            return Response(
                {"error": "Analysis is already in progress"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Clear existing days and rerun analysis
        time_analysis.days.all().delete()
        time_analysis.status = "pending"
        time_analysis.error_message = ""
        time_analysis.save()

        # Trigger the analysis
        time_analysis.perform_sentiment_analysis()

        serializer = self.get_serializer(time_analysis)
        return Response(serializer.data)


class DayViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Day model.
    Read-only viewset with filtering by date range and time_analysis.
    """

    queryset = Day.objects.all()
    serializer_class = DaySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["time_analysis"]

    def get_queryset(self):
        queryset = Day.objects.all()

        # Filter by date range if provided
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        time_analysis_id = self.request.query_params.get("time_analysis")

        if start_date:
            try:
                start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
                queryset = queryset.filter(date__gte=start_date)
            except ValueError:
                pass

        if end_date:
            try:
                end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
                queryset = queryset.filter(date__lte=end_date)
            except ValueError:
                pass

        if time_analysis_id:
            queryset = queryset.filter(time_analysis_id=time_analysis_id)

        return queryset.select_related("time_analysis").order_by("date")


class MessageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing individual messages.
    Provides filtering by sentiment, source, date, etc.
    """

    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = MessageFilter
    search_fields = ["text", "contact"]
    ordering_fields = ["sentiment", "created_at", "day__date"]
    ordering = ["-sentiment"]  # Default to happiest first

    @action(detail=False, methods=["get"])
    def happiest(self, request):
        """Get the happiest messages across all days."""
        limit = int(request.query_params.get("limit", 10))
        time_analysis_id = request.query_params.get("time_analysis")
        day_date = request.query_params.get("date")

        queryset = self.get_queryset().order_by("-sentiment")

        if time_analysis_id:
            queryset = queryset.filter(day__time_analysis_id=time_analysis_id)
        if day_date:
            queryset = queryset.filter(day__date=day_date)

        messages = queryset[:limit]
        serializer = self.get_serializer(messages, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def saddest(self, request):
        """Get the saddest messages across all days."""
        limit = int(request.query_params.get("limit", 10))
        time_analysis_id = request.query_params.get("time_analysis")
        day_date = request.query_params.get("date")

        queryset = self.get_queryset().order_by("sentiment")

        if time_analysis_id:
            queryset = queryset.filter(day__time_analysis_id=time_analysis_id)
        if day_date:
            queryset = queryset.filter(day__date=day_date)

        messages = queryset[:limit]
        serializer = self.get_serializer(messages, many=True)
        return Response(serializer.data)


class LocationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Location model.
    Read-only viewset for viewing clustered locations.
    """

    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["time_analysis"]
    ordering_fields = ["visit_count", "total_time_minutes", "first_visit", "last_visit"]
    ordering = ["-visit_count"]  # Default to most visited locations first

    def get_queryset(self):
        queryset = Location.objects.all()
        time_analysis_id = self.request.query_params.get("time_analysis")

        if time_analysis_id:
            queryset = queryset.filter(time_analysis_id=time_analysis_id)

        return queryset.select_related("time_analysis").order_by("-visit_count")

    @action(detail=False, methods=["get"])
    def most_visited(self, request):
        """Get the most visited locations."""
        limit = int(request.query_params.get("limit", 10))
        time_analysis_id = request.query_params.get("time_analysis")

        queryset = self.get_queryset().order_by("-visit_count")
        if time_analysis_id:
            queryset = queryset.filter(time_analysis_id=time_analysis_id)

        locations = queryset[:limit]
        serializer = self.get_serializer(locations, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def longest_stays(self, request):
        """Get locations with the longest total time spent."""
        limit = int(request.query_params.get("limit", 10))
        time_analysis_id = request.query_params.get("time_analysis")

        queryset = self.get_queryset().order_by("-total_time_minutes")
        if time_analysis_id:
            queryset = queryset.filter(time_analysis_id=time_analysis_id)

        locations = queryset[:limit]
        serializer = self.get_serializer(locations, many=True)
        return Response(serializer.data)


class WebsiteAnalysisViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for WebsiteAnalysis model.
    Read-only viewset for viewing website-happiness correlations.
    """

    queryset = WebsiteAnalysis.objects.all()
    serializer_class = WebsiteAnalysisSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["time_analysis"]
    ordering_fields = [
        "correlation_coefficient",
        "significance_score",
        "days_visited",
        "total_visits",
    ]
    ordering = ["-correlation_coefficient"]  # Default to highest correlation first

    def get_queryset(self):
        queryset = WebsiteAnalysis.objects.all()
        time_analysis_id = self.request.query_params.get("time_analysis")

        if time_analysis_id:
            queryset = queryset.filter(time_analysis_id=time_analysis_id)

        return queryset.select_related("time_analysis").order_by(
            "-correlation_coefficient"
        )

    @action(detail=False, methods=["get"])
    def positive_correlations(self, request):
        """Get websites with positive correlations (make you happier)."""
        limit = int(request.query_params.get("limit", 10))
        time_analysis_id = request.query_params.get("time_analysis")

        queryset = (
            self.get_queryset()
            .filter(correlation_coefficient__gt=0)
            .order_by("-correlation_coefficient")
        )
        if time_analysis_id:
            queryset = queryset.filter(time_analysis_id=time_analysis_id)

        websites = queryset[:limit]
        serializer = self.get_serializer(websites, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def negative_correlations(self, request):
        """Get websites with negative correlations (make you sadder)."""
        limit = int(request.query_params.get("limit", 10))
        time_analysis_id = request.query_params.get("time_analysis")

        queryset = (
            self.get_queryset()
            .filter(correlation_coefficient__lt=0)
            .order_by("correlation_coefficient")
        )
        if time_analysis_id:
            queryset = queryset.filter(time_analysis_id=time_analysis_id)

        websites = queryset[:limit]
        serializer = self.get_serializer(websites, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def most_significant(self, request):
        """Get websites with the highest significance scores."""
        limit = int(request.query_params.get("limit", 10))
        time_analysis_id = request.query_params.get("time_analysis")

        queryset = self.get_queryset().order_by("-significance_score")
        if time_analysis_id:
            queryset = queryset.filter(time_analysis_id=time_analysis_id)

        websites = queryset[:limit]
        serializer = self.get_serializer(websites, many=True)
        return Response(serializer.data)


class PersonAnalysisViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for PersonAnalysis model.
    Read-only viewset for viewing person-happiness correlations.
    """

    queryset = PersonAnalysis.objects.all()
    serializer_class = PersonAnalysisSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
        filters.SearchFilter,
    ]
    filterset_fields = ["time_analysis"]
    ordering_fields = [
        "correlation_coefficient",
        "significance_score",
        "days_interacted",
        "total_messages",
    ]
    ordering = ["-correlation_coefficient"]  # Default to highest correlation first
    search_fields = ["contact_name"]

    def get_queryset(self):
        queryset = PersonAnalysis.objects.all()
        time_analysis_id = self.request.query_params.get("time_analysis")

        if time_analysis_id:
            queryset = queryset.filter(time_analysis_id=time_analysis_id)

        return queryset.select_related("time_analysis").order_by(
            "-correlation_coefficient"
        )

    @action(detail=False, methods=["get"])
    def positive_correlations(self, request):
        """Get people with positive correlations (make you happier)."""
        limit = int(request.query_params.get("limit", 10))
        time_analysis_id = request.query_params.get("time_analysis")

        queryset = (
            self.get_queryset()
            .filter(correlation_coefficient__gt=0)
            .order_by("-correlation_coefficient")
        )
        if time_analysis_id:
            queryset = queryset.filter(time_analysis_id=time_analysis_id)

        people = queryset[:limit]
        serializer = self.get_serializer(people, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def negative_correlations(self, request):
        """Get people with negative correlations (make you sadder)."""
        limit = int(request.query_params.get("limit", 10))
        time_analysis_id = request.query_params.get("time_analysis")

        queryset = (
            self.get_queryset()
            .filter(correlation_coefficient__lt=0)
            .order_by("correlation_coefficient")
        )
        if time_analysis_id:
            queryset = queryset.filter(time_analysis_id=time_analysis_id)

        people = queryset[:limit]
        serializer = self.get_serializer(people, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def most_significant(self, request):
        """Get people with the highest significance scores."""
        limit = int(request.query_params.get("limit", 10))
        time_analysis_id = request.query_params.get("time_analysis")

        queryset = self.get_queryset().order_by("-significance_score")
        if time_analysis_id:
            queryset = queryset.filter(time_analysis_id=time_analysis_id)

        people = queryset[:limit]
        serializer = self.get_serializer(people, many=True)
        return Response(serializer.data)


class PlaceAnalysisViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for PlaceAnalysis model.
    Read-only viewset for viewing place-happiness correlations.
    """

    queryset = PlaceAnalysis.objects.all()
    serializer_class = PlaceAnalysisSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
        filters.SearchFilter,
    ]
    filterset_fields = ["time_analysis"]
    ordering_fields = [
        "correlation_coefficient",
        "significance_score",
        "days_present",
        "total_visits",
    ]
    ordering = ["-correlation_coefficient"]  # Default to highest correlation first
    search_fields = ["location__name", "location__address"]

    def get_queryset(self):
        queryset = PlaceAnalysis.objects.all()
        time_analysis_id = self.request.query_params.get("time_analysis")

        if time_analysis_id:
            queryset = queryset.filter(time_analysis_id=time_analysis_id)

        return queryset.select_related("time_analysis", "location").order_by(
            "-correlation_coefficient"
        )

    @action(detail=False, methods=["get"])
    def positive_correlations(self, request):
        """Get places with positive correlations (make you happier)."""
        limit = int(request.query_params.get("limit", 10))
        time_analysis_id = request.query_params.get("time_analysis")

        queryset = (
            self.get_queryset()
            .filter(correlation_coefficient__gt=0)
            .order_by("-correlation_coefficient")
        )
        if time_analysis_id:
            queryset = queryset.filter(time_analysis_id=time_analysis_id)

        places = queryset[:limit]
        serializer = self.get_serializer(places, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def negative_correlations(self, request):
        """Get places with negative correlations (make you sadder)."""
        limit = int(request.query_params.get("limit", 10))
        time_analysis_id = request.query_params.get("time_analysis")

        queryset = (
            self.get_queryset()
            .filter(correlation_coefficient__lt=0)
            .order_by("correlation_coefficient")
        )
        if time_analysis_id:
            queryset = queryset.filter(time_analysis_id=time_analysis_id)

        places = queryset[:limit]
        serializer = self.get_serializer(places, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def most_significant(self, request):
        """Get places with the highest significance scores."""
        limit = int(request.query_params.get("limit", 10))
        time_analysis_id = request.query_params.get("time_analysis")

        queryset = self.get_queryset().order_by("-significance_score")
        if time_analysis_id:
            queryset = queryset.filter(time_analysis_id=time_analysis_id)

        places = queryset[:limit]
        serializer = self.get_serializer(places, many=True)
        return Response(serializer.data)
