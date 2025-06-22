from django.contrib import admin

from .models import Day, TimeAnalysis


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
