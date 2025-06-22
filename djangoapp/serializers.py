from rest_framework import serializers

from .models import Day, TimeAnalysis


class DaySerializer(serializers.ModelSerializer):
    sentiment_label = serializers.ReadOnlyField()

    class Meta:
        model = Day
        fields = [
            "id",
            "date",
            "sentiment",
            "sentiment_label",
            "message_count",
            "created_at",
        ]


class TimeAnalysisSerializer(serializers.ModelSerializer):
    days = DaySerializer(many=True, read_only=True)
    days_count = serializers.SerializerMethodField()

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
            "days_count",
        ]
        read_only_fields = ["status", "error_message", "created_at", "updated_at"]

    def get_days_count(self, obj):
        return obj.days.count()


class TimeAnalysisCreateSerializer(serializers.ModelSerializer):
    """Simplified serializer for creating TimeAnalysis instances."""

    class Meta:
        model = TimeAnalysis
        fields = ["name", "description", "start_date", "end_date"]

    def validate(self, data):
        if data["start_date"] > data["end_date"]:
            raise serializers.ValidationError("Start date must be before end date.")
        return data
