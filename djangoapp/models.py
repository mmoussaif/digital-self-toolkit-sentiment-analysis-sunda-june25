import logging
import os
from collections import defaultdict
from datetime import datetime

import boto3
from dateutil.parser import parse as parse_date
from django.db import models
from supabase import Client, create_client

logger = logging.getLogger(__name__)


class TimeAnalysis(models.Model):
    """Model for storing time-based sentiment analysis results."""

    name = models.CharField(max_length=200, help_text="Name for this analysis")
    description = models.TextField(blank=True, help_text="Description of this analysis")
    start_date = models.DateField(help_text="Start date for analysis period")
    end_date = models.DateField(help_text="End date for analysis period")
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("completed", "Completed"),
            ("error", "Error"),
        ],
        default="pending",
    )
    error_message = models.TextField(
        blank=True, help_text="Error message if analysis failed"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Time Analysis"
        verbose_name_plural = "Time Analyses"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.start_date} to {self.end_date})"

    def save(self, *args, **kwargs):
        """Override save to trigger sentiment analysis when a new analysis is created."""
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new and self.status == "pending":
            self.perform_sentiment_analysis()

    def perform_sentiment_analysis(self):
        """
        Perform sentiment analysis on all messages within the date range.
        Groups messages by day and calculates average sentiment using AWS Comprehend.
        """
        self.status = "processing"
        self.save(update_fields=["status"])

        # Initialize Supabase client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_ANON_KEY")

        if not supabase_url or not supabase_key:
            self.status = "error"
            self.error_message = "Supabase credentials not configured"
            self.save(update_fields=["status", "error_message"])
            return

        # Initialize AWS Comprehend client
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_region = os.getenv("AWS_REGION", "us-east-1")

        if not aws_access_key or not aws_secret_key:
            self.status = "error"
            self.error_message = "AWS credentials not configured"
            self.save(update_fields=["status", "error_message"])
            return

        supabase: Client = create_client(supabase_url, supabase_key)
        comprehend = boto3.client(
            "comprehend",
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region,
        )

        # Group messages by day
        daily_messages = defaultdict(list)

        # Query iMessages
        self._fetch_imessages(supabase, daily_messages)

        # Query WhatsApp messages
        self._fetch_whatsapp_messages(supabase, daily_messages)

        # Query Gmail emails
        self._fetch_gmail_emails(supabase, daily_messages)

        # Process messages in batches using BatchDetectSentiment
        daily_data = []
        for date_str, messages in daily_messages.items():
            if not messages:
                continue

            # Combine all messages for the day
            combined_text = " ".join(messages)

            # Skip if no text content
            if not combined_text.strip():
                continue

            if len(combined_text.encode("utf-8")) > 5000:
                combined_text = combined_text[:4900] + "..."

            daily_data.append(
                {
                    "date_str": date_str,
                    "text": combined_text,
                    "message_count": len(messages),
                }
            )

        # Process in batches of 25 (AWS Comprehend BatchDetectSentiment limit)
        batch_size = 25
        for i in range(0, len(daily_data), batch_size):
            batch = daily_data[i : i + batch_size]
            text_list = [item["text"] for item in batch]

            # Analyze sentiment for the batch
            sentiment_results = self._analyze_sentiment_batch(comprehend, text_list)

            if sentiment_results:
                # Create Day objects for successful analyses
                for j, result in enumerate(sentiment_results):
                    if result is not None:
                        try:
                            date_obj = datetime.strptime(
                                batch[j]["date_str"], "%Y-%m-%d"
                            ).date()
                            Day.objects.create(
                                time_analysis=self,
                                date=date_obj,
                                sentiment=result,
                                message_count=batch[j]["message_count"],
                            )
                        except Exception as e:
                            logger.error(
                                f"Error creating Day object for {batch[j]['date_str']}: {e}"
                            )

        self.status = "completed"
        self.save(update_fields=["status"])

    def _fetch_imessages(self, supabase: Client, daily_messages: dict):
        """Fetch iMessages from Supabase and group by day."""
        try:
            response = (
                supabase.table("imessages")
                .select("text, timestamp")
                .gte("timestamp", self.start_date.isoformat())
                .lte("timestamp", self.end_date.isoformat())
                .execute()
            )

            for message in response.data:
                if message.get("text"):
                    # Parse timestamp and extract date
                    try:
                        if message.get("timestamp"):
                            # Handle different timestamp formats
                            timestamp = message["timestamp"]
                            if isinstance(timestamp, str):
                                # Try parsing different formats
                                parsed_date = parse_date(timestamp).date()
                            else:
                                parsed_date = datetime.fromtimestamp(timestamp).date()

                            date_str = parsed_date.isoformat()
                            if self.start_date <= parsed_date <= self.end_date:
                                daily_messages[date_str].append(message["text"])
                    except Exception as e:
                        logger.warning(f"Error parsing iMessage timestamp: {e}")

        except Exception as e:
            logger.error(f"Error fetching iMessages: {e}")

    def _fetch_whatsapp_messages(self, supabase: Client, daily_messages: dict):
        """Fetch WhatsApp messages from Supabase and group by day."""
        try:
            response = (
                supabase.table("whatsapp_messages")
                .select("text, timestamp")
                .gte("timestamp", self.start_date.isoformat())
                .lte("timestamp", self.end_date.isoformat())
                .execute()
            )

            for message in response.data:
                if message.get("text"):
                    try:
                        timestamp = parse_date(message["timestamp"]).date()
                        date_str = timestamp.isoformat()
                        if self.start_date <= timestamp <= self.end_date:
                            daily_messages[date_str].append(message["text"])
                    except Exception as e:
                        logger.warning(f"Error parsing WhatsApp timestamp: {e}")

        except Exception as e:
            logger.error(f"Error fetching WhatsApp messages: {e}")

    def _fetch_gmail_emails(self, supabase: Client, daily_messages: dict):
        """Fetch Gmail emails from Supabase and group by day."""
        try:
            response = (
                supabase.table("gmail_emails")
                .select("body_text, internal_date")
                .gte("internal_date", int(self.start_date.strftime("%s")) * 1000)
                .lte("internal_date", int(self.end_date.strftime("%s")) * 1000)
                .execute()
            )

            for email in response.data:
                if email.get("body_text"):
                    try:
                        # Gmail internal_date is in milliseconds
                        timestamp = datetime.fromtimestamp(
                            email["internal_date"] / 1000
                        ).date()
                        date_str = timestamp.isoformat()
                        if self.start_date <= timestamp <= self.end_date:
                            daily_messages[date_str].append(email["body_text"])
                    except Exception as e:
                        logger.warning(f"Error parsing Gmail timestamp: {e}")

        except Exception as e:
            logger.error(f"Error fetching Gmail emails: {e}")

    def _analyze_sentiment_batch(
        self, comprehend, text_list: list[str]
    ) -> list[float | None]:
        """
        Analyze sentiment using AWS Comprehend BatchDetectSentiment API.
        Returns a list of scores from -1.0 (very negative) to 1.0 (very positive), or None if error.
        """
        try:
            response = comprehend.batch_detect_sentiment(
                TextList=text_list, LanguageCode="en"
            )

            results: list[float | None] = [None] * len(text_list)

            # Process successful results
            for result in response.get("ResultList", []):
                index = result["Index"]
                sentiment = result["Sentiment"]
                scores = result["SentimentScore"]

                # Convert sentiment to numerical score
                if sentiment == "POSITIVE":
                    results[index] = scores["Positive"] - scores["Negative"]
                elif sentiment == "NEGATIVE":
                    results[index] = -(scores["Negative"] - scores["Positive"])
                elif sentiment == "NEUTRAL":
                    results[index] = scores["Positive"] - scores["Negative"]
                else:  # MIXED
                    results[index] = (scores["Positive"] - scores["Negative"]) * 0.5

            # Log errors for failed items
            for error in response.get("ErrorList", []):
                logger.error(
                    f"Error analyzing sentiment for item {error['Index']}: {error['ErrorMessage']}"
                )

            return results

        except Exception as e:
            logger.error(f"Error in batch sentiment analysis: {e}")
            return [None] * len(text_list)


class Day(models.Model):
    """Model for storing daily sentiment analysis results."""

    time_analysis = models.ForeignKey(
        TimeAnalysis, on_delete=models.CASCADE, related_name="days"
    )
    date = models.DateField(help_text="Date for this day's analysis")
    sentiment = models.FloatField(
        help_text="Sentiment score from -1.0 (negative) to 1.0 (positive)"
    )
    message_count = models.PositiveIntegerField(
        default=0, help_text="Number of messages analyzed for this day"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Day"
        verbose_name_plural = "Days"
        ordering = ["date"]
        unique_together = ["time_analysis", "date"]

    def __str__(self):
        return f"{self.date} - Sentiment: {self.sentiment:.2f}"

    @property
    def sentiment_label(self):
        """Return human-readable sentiment label."""
        if self.sentiment > 0.3:
            return "Positive"
        elif self.sentiment < -0.3:
            return "Negative"
        else:
            return "Neutral"
