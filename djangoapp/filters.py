import django_filters

from .models import Day, Message, TimeAnalysis


class TimeAnalysisFilter(django_filters.FilterSet):
    """Filter for TimeAnalysis model."""

    status = django_filters.ChoiceFilter(
        choices=TimeAnalysis._meta.get_field("status").choices
    )
    start_date = django_filters.DateFilter(lookup_expr="gte")
    end_date = django_filters.DateFilter(lookup_expr="lte")
    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )

    class Meta:
        model = TimeAnalysis
        fields = ["status", "start_date", "end_date", "created_after", "created_before"]


class DayFilter(django_filters.FilterSet):
    """Filter for Day model."""

    date = django_filters.DateFilter()
    date_after = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_before = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    sentiment_min = django_filters.NumberFilter(
        field_name="sentiment", lookup_expr="gte"
    )
    sentiment_max = django_filters.NumberFilter(
        field_name="sentiment", lookup_expr="lte"
    )
    message_count_min = django_filters.NumberFilter(
        field_name="message_count", lookup_expr="gte"
    )
    message_count_max = django_filters.NumberFilter(
        field_name="message_count", lookup_expr="lte"
    )
    time_analysis = django_filters.NumberFilter(field_name="time_analysis__id")

    class Meta:
        model = Day
        fields = [
            "date",
            "date_after",
            "date_before",
            "sentiment_min",
            "sentiment_max",
            "message_count_min",
            "message_count_max",
            "time_analysis",
        ]


class MessageFilter(django_filters.FilterSet):
    """Filter for Message model."""

    source = django_filters.ChoiceFilter(
        choices=Message._meta.get_field("source").choices
    )
    sentiment_min = django_filters.NumberFilter(
        field_name="sentiment", lookup_expr="gte"
    )
    sentiment_max = django_filters.NumberFilter(
        field_name="sentiment", lookup_expr="lte"
    )
    contact = django_filters.CharFilter(lookup_expr="icontains")
    text = django_filters.CharFilter(field_name="text", lookup_expr="icontains")
    day = django_filters.NumberFilter(field_name="day__id")
    day_date = django_filters.DateFilter(field_name="day__date")
    day_date_after = django_filters.DateFilter(
        field_name="day__date", lookup_expr="gte"
    )
    day_date_before = django_filters.DateFilter(
        field_name="day__date", lookup_expr="lte"
    )
    time_analysis = django_filters.NumberFilter(field_name="day__time_analysis__id")

    class Meta:
        model = Message
        fields = [
            "source",
            "sentiment_min",
            "sentiment_max",
            "contact",
            "text",
            "day",
            "day_date",
            "day_date_after",
            "day_date_before",
            "time_analysis",
        ]
