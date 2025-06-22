from datetime import datetime

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Day, TimeAnalysis
from .serializers import (
    DaySerializer,
    TimeAnalysisCreateSerializer,
    TimeAnalysisSerializer,
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
