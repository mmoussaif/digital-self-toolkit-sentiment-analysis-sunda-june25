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
            print(f"🚀 New TimeAnalysis created: {self.name}")
            print(f"📅 Date range: {self.start_date} to {self.end_date}")
            self.perform_sentiment_analysis()

    def perform_sentiment_analysis(self):
        """
        Perform sentiment analysis on all messages within the date range.
        Groups messages by day and calculates average sentiment using AWS Comprehend.
        """
        print("🔄 Starting sentiment analysis...")

        # Clear ALL existing Day objects (from all TimeAnalyses)
        existing_days_count = Day.objects.count()
        if existing_days_count > 0:
            print(f"🗑️  Clearing {existing_days_count} existing Day records...")
            Day.objects.all().delete()
            print("✅ All existing Day records cleared")
        else:
            print("ℹ️  No existing Day records to clear")

        self.status = "processing"
        self.save(update_fields=["status"])
        print(f"📊 Status updated to: {self.status}")

        # Initialize Supabase client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_ANON_KEY")

        print("🔗 Checking Supabase credentials...")
        if not supabase_url or not supabase_key:
            print("❌ Supabase credentials not configured")
            self.status = "error"
            self.error_message = "Supabase credentials not configured"
            self.save(update_fields=["status", "error_message"])
            return
        print("✅ Supabase credentials found")

        # Initialize AWS Comprehend client
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_region = os.getenv("AWS_REGION", "us-east-1")

        print("🔑 Checking AWS credentials...")
        if not aws_access_key or not aws_secret_key:
            print("❌ AWS credentials not configured")
            self.status = "error"
            self.error_message = "AWS credentials not configured"
            self.save(update_fields=["status", "error_message"])
            return
        print(f"✅ AWS credentials found for region: {aws_region}")

        supabase: Client = create_client(supabase_url, supabase_key)
        comprehend = boto3.client(
            "comprehend",
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region,
        )

        # Group messages by day
        daily_messages = defaultdict(list)

        print("📱 Fetching messages from different sources...")
        # Query iMessages
        print("  📩 Querying iMessages...")
        self._fetch_imessages(supabase, daily_messages)

        # Query WhatsApp messages
        print("  💬 Querying WhatsApp messages...")
        self._fetch_whatsapp_messages(supabase, daily_messages)

        # Query Gmail emails
        print("  ✉️  Querying Gmail emails...")
        self._fetch_gmail_emails(supabase, daily_messages)

        total_days_with_messages = len(daily_messages)
        total_messages = sum(len(messages) for messages in daily_messages.values())
        print(
            f"📊 Found {total_messages} messages across {total_days_with_messages} days"
        )

        # Process messages in batches using BatchDetectSentiment
        print("🔍 Processing messages for sentiment analysis...")
        daily_data = []
        for date_str, messages in daily_messages.items():
            if not messages:
                continue

            # Combine all messages for the day
            combined_text = " ".join(messages)

            # Skip if no text content
            if not combined_text.strip():
                continue

            # Truncate if too long for AWS Comprehend
            if len(combined_text.encode("utf-8")) > 5000:
                combined_text = combined_text[:4900] + "..."
                print(f"  ✂️  Truncated messages for {date_str} (too long)")

            daily_data.append(
                {
                    "date_str": date_str,
                    "text": combined_text,
                    "message_count": len(messages),
                }
            )
            print(f"  📅 {date_str}: {len(messages)} messages combined")

        print(f"🎯 Prepared {len(daily_data)} days for sentiment analysis")

        # Process in batches of 25 (AWS Comprehend BatchDetectSentiment limit)
        batch_size = 25
        total_batches = (len(daily_data) + batch_size - 1) // batch_size
        created_days = 0

        print(f"🔄 Processing {len(daily_data)} days in {total_batches} batches...")

        for i in range(0, len(daily_data), batch_size):
            batch_num = (i // batch_size) + 1
            batch = daily_data[i : i + batch_size]
            text_list = [item["text"] for item in batch]

            print(
                f"  📦 Processing batch {batch_num}/{total_batches} ({len(batch)} days)..."
            )

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
                            day = Day.objects.create(
                                time_analysis=self,
                                date=date_obj,
                                sentiment=result,
                                message_count=batch[j]["message_count"],
                            )
                            created_days += 1
                            print(
                                f"    ✅ Created Day: {date_obj} (sentiment: {result:.3f}, {batch[j]['message_count']} msgs)"
                            )
                        except Exception as e:
                            print(
                                f"    ❌ Error creating Day for {batch[j]['date_str']}: {e}"
                            )
                            logger.error(
                                f"Error creating Day object for {batch[j]['date_str']}: {e}"
                            )

            print(f"  ✅ Batch {batch_num}/{total_batches} completed")

        print(f"🎉 Analysis complete! Created {created_days} Day records")
        self.status = "completed"
        self.save(update_fields=["status"])
        print(f"📊 Status updated to: {self.status}")

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

            print(f"    📱 Found {len(response.data)} iMessages")
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

            print(f"    💬 Found {len(response.data)} WhatsApp messages")
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

            print(f"    ✉️  Found {len(response.data)} Gmail emails")
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
