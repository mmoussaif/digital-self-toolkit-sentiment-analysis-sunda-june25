from rest_framework import serializers

from .models import (
    Day,
    Location,
    Message,
    PersonAnalysis,
    TimeAnalysis,
    WebsiteAnalysis,
)


class LocationSerializer(serializers.ModelSerializer):
    """Serializer for clustered location data."""

    coordinates = serializers.ReadOnlyField()
    average_time_per_visit = serializers.ReadOnlyField()

    class Meta:
        model = Location
        fields = [
            "id",
            "name",
            "center_latitude",
            "center_longitude",
            "coordinates",
            "visit_count",
            "total_time_minutes",
            "average_time_per_visit",
            "first_visit",
            "last_visit",
            "address",
            "activity_types",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "coordinates",
            "average_time_per_visit",
        ]


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for individual message sentiment data."""

    sentiment_label = serializers.ReadOnlyField()

    class Meta:
        model = Message
        fields = [
            "id",
            "text",
            "sentiment",
            "sentiment_label",
            "source",
            "contact",
            "timestamp",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "sentiment_label"]


class DaySerializer(serializers.ModelSerializer):
    """Serializer for daily sentiment analysis results."""

    sentiment_label = serializers.ReadOnlyField()
    happiest_messages = MessageSerializer(many=True, read_only=True)
    saddest_messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = Day
        fields = [
            "id",
            "date",
            "sentiment",
            "sentiment_label",
            "message_count",
            "happiest_messages",
            "saddest_messages",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "sentiment_label",
            "happiest_messages",
            "saddest_messages",
        ]


class TimeAnalysisSerializer(serializers.ModelSerializer):
    """Serializer for time analysis with related days."""

    days = DaySerializer(many=True, read_only=True)

    class Meta:
        model = TimeAnalysis
        fields = [
            "id",
            "name",
            "description",
            "start_date",
            "end_date",
            "status",
            "error_message",
            "created_at",
            "updated_at",
            "days",
        ]
        read_only_fields = [
            "id",
            "status",
            "error_message",
            "created_at",
            "updated_at",
            "days",
        ]


class TimeAnalysisCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new time analysis."""

    class Meta:
        model = TimeAnalysis
        fields = ["name", "description", "start_date", "end_date"]

    def validate(self, data):
        """Validate that end_date is after start_date."""
        if data["start_date"] >= data["end_date"]:
            raise serializers.ValidationError("End date must be after start date.")
        return data


class WebsiteAnalysisSerializer(serializers.ModelSerializer):
    """Serializer for website-happiness correlation data."""

    class Meta:
        model = WebsiteAnalysis
        fields = [
            "id",
            "domain",
            "example_url",
            "correlation_coefficient",
            "days_visited",
            "days_not_visited",
            "avg_sentiment_when_visited",
            "avg_sentiment_when_not_visited",
            "total_visits",
            "significance_score",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class PersonAnalysisSerializer(serializers.ModelSerializer):
    """Serializer for person-happiness correlation data."""

    class Meta:
        model = PersonAnalysis
        fields = [
            "id",
            "contact_name",
            "correlation_coefficient",
            "days_interacted",
            "days_not_interacted",
            "avg_sentiment_when_interacted",
            "avg_sentiment_when_not_interacted",
            "total_messages",
            "significance_score",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
