from django.contrib import admin

from .models import Day, Location, Message, TimeAnalysis


@admin.register(TimeAnalysis)
class TimeAnalysisAdmin(admin.ModelAdmin):
    """Admin configuration for TimeAnalysis model."""

    list_display = ("name", "start_date", "end_date", "status", "created_at")
    list_filter = ("status", "created_at", "start_date", "end_date")
    search_fields = ("name", "description")
    readonly_fields = ("status", "error_message", "created_at", "updated_at")
    date_hierarchy = "created_at"

    fieldsets = (
        (None, {"fields": ("name", "description", "start_date", "end_date")}),
        ("Status", {"fields": ("status", "error_message"), "classes": ("collapse",)}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(Day)
class DayAdmin(admin.ModelAdmin):
    """Admin configuration for Day model."""

    list_display = (
        "date",
        "time_analysis",
        "sentiment",
        "sentiment_label",
        "message_count",
        "created_at",
    )
    list_filter = ("time_analysis", "created_at")
    search_fields = ("time_analysis__name",)
    readonly_fields = ("sentiment_label", "created_at")
    date_hierarchy = "date"
    ordering = ("-date",)

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "time_analysis",
                    "date",
                    "sentiment",
                    "sentiment_label",
                    "message_count",
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at",), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related("time_analysis")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Admin configuration for Message model."""

    list_display = (
        "get_short_text",
        "sentiment",
        "sentiment_label",
        "source",
        "contact",
        "day",
        "created_at",
    )
    list_filter = ("source", "day__time_analysis", "created_at")
    search_fields = ("text", "contact", "day__time_analysis__name")
    readonly_fields = ("sentiment_label", "created_at")
    date_hierarchy = "created_at"
    ordering = ("-sentiment",)

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "day",
                    "text",
                    "sentiment",
                    "sentiment_label",
                    "source",
                    "contact",
                    "timestamp",
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at",), "classes": ("collapse",)}),
    )

    def get_short_text(self, obj):
        """Return truncated text for list display."""
        if len(obj.text) > 100:
            return obj.text[:100] + "..."
        return obj.text

    get_short_text.short_description = "Text Preview"

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related("day", "day__time_analysis")


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    """Admin configuration for Location model."""

    list_display = (
        "get_display_name",
        "time_analysis",
        "visit_count",
        "total_time_minutes",
        "average_time_per_visit",
        "first_visit",
        "last_visit",
        "created_at",
    )
    list_filter = ("time_analysis", "created_at", "first_visit")
    search_fields = ("name", "address", "time_analysis__name")
    readonly_fields = ("average_time_per_visit", "coordinates", "created_at")
    date_hierarchy = "created_at"
    ordering = ("-visit_count",)

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "time_analysis",
                    "name",
                    "address",
                    "center_latitude",
                    "center_longitude",
                    "coordinates",
                )
            },
        ),
        (
            "Visit Information",
            {
                "fields": (
                    "visit_count",
                    "total_time_minutes",
                    "average_time_per_visit",
                    "first_visit",
                    "last_visit",
                    "activity_types",
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at",), "classes": ("collapse",)}),
    )

    def get_display_name(self, obj):
        """Return name or coordinates for list display."""
        return obj.name or f"{obj.center_latitude}, {obj.center_longitude}"

    get_display_name.short_description = "Location"

    def average_time_per_visit(self, obj):
        """Return formatted average time per visit."""
        avg_time = obj.average_time_per_visit
        if avg_time == 0:
            return "0 min"
        if avg_time >= 60:
            hours = int(avg_time // 60)
            minutes = int(avg_time % 60)
            return f"{hours}h {minutes}m"
        return f"{int(avg_time)}m"

    average_time_per_visit.short_description = "Avg Time/Visit"

    def coordinates(self, obj):
        """Return formatted coordinates."""
        return f"{obj.center_latitude}, {obj.center_longitude}"

    coordinates.short_description = "Coordinates"

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related("time_analysis")
