# Sentiment Analysis Setup

This document explains how to set up and use the Django sentiment analysis functionality that queries Supabase data and performs sentiment analysis using AWS Comprehend.

## Prerequisites

1. **Supabase Database**: Ensure your Supabase database is set up with the required tables (see `databases/setup_supabase.py`)
2. **AWS Account**: You need an AWS account with access to AWS Comprehend service
3. **Environment Variables**: Configure the required environment variables

## Environment Variables

Create a `.env` file in your project root with the following variables:

```bash
# Supabase Configuration
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=your-supabase-anon-key

# AWS Comprehend Configuration
AWS_ACCESS_KEY_ID=your-aws-access-key-id
AWS_SECRET_ACCESS_KEY=your-aws-secret-access-key
AWS_REGION=us-east-1

# Django Settings (optional)
DEBUG=True
SECRET_KEY=your-django-secret-key
```

## Database Setup

1. **Run Django Migrations**:

   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

2. **Create Superuser** (optional, for Django admin access):
   ```bash
   python manage.py createsuperuser
   ```

## Usage

### Creating a Time Analysis

1. **Through Django Admin**:

   - Start the Django server: `python manage.py runserver`
   - Go to `http://localhost:8000/admin/`
   - Navigate to "Time Analyses" and click "Add"
   - Fill in the form:
     - **Name**: A descriptive name for your analysis
     - **Description**: Optional description
     - **Start Date**: Beginning of the analysis period
     - **End Date**: End of the analysis period

2. **Programmatically**:

   ```python
   from djangoapp.models import TimeAnalysis
   from datetime import date

   # Create a new analysis
   analysis = TimeAnalysis.objects.create(
       name="Weekly Sentiment Analysis",
       description="Analyze sentiment for the past week",
       start_date=date(2024, 1, 1),
       end_date=date(2024, 1, 7)
   )
   ```

### How It Works

1. **Automatic Processing**: When a `TimeAnalysis` is created, it automatically triggers the sentiment analysis process in the `save()` method.

2. **Data Collection**: The system queries your Supabase database for:

   - iMessages from the `imessages` table
   - WhatsApp messages from the `whatsapp_messages` table
   - Gmail emails from the `gmail_emails` table

3. **Data Grouping**: Messages are grouped by day within the specified date range.

4. **Sentiment Analysis**: For each day:

   - All messages are combined into a single text
   - Text is sent to AWS Comprehend for sentiment analysis
   - A sentiment score from -1.0 (very negative) to 1.0 (very positive) is calculated

5. **Result Storage**: A `Day` object is created for each day with:
   - The date
   - Sentiment score
   - Number of messages analyzed
   - Reference to the parent TimeAnalysis

### Viewing Results

1. **Django Admin**:

   - Go to "Days" section to see daily sentiment results
   - View individual TimeAnalysis to see status and associated days

2. **Programmatically**:

   ```python
   # Get analysis results
   analysis = TimeAnalysis.objects.get(name="Weekly Sentiment Analysis")

   # Check status
   print(f"Status: {analysis.status}")

   # Get daily results
   for day in analysis.days.all():
       print(f"{day.date}: {day.sentiment:.2f} ({day.sentiment_label}) - {day.message_count} messages")
   ```

## Data Sources

The system analyzes text from the following Supabase tables:

### iMessages (`imessages` table)

- Columns used: `text`, `timestamp`
- Filters messages within the date range

### WhatsApp Messages (`whatsapp_messages` table)

- Columns used: `text`, `timestamp`
- Filters messages within the date range

### Gmail Emails (`gmail_emails` table)

- Columns used: `body_text`, `internal_date`
- Filters emails within the date range
- Uses `internal_date` (millisecond timestamp format)

## Error Handling

- **Missing Credentials**: Analysis status will be set to 'error' with appropriate error message
- **API Failures**: Individual failures are logged, analysis continues with available data
- **Text Limits**: AWS Comprehend has a 5000-byte limit; text is automatically truncated if needed

## Sentiment Score Interpretation

- **Positive (> 0.3)**: Generally positive sentiment
- **Neutral (-0.3 to 0.3)**: Neutral or mixed sentiment
- **Negative (< -0.3)**: Generally negative sentiment

The score is calculated based on AWS Comprehend's confidence scores for POSITIVE, NEGATIVE, NEUTRAL, and MIXED sentiments.

## Troubleshooting

1. **"Supabase credentials not configured"**: Check your `SUPABASE_URL` and `SUPABASE_ANON_KEY` environment variables
2. **"AWS credentials not configured"**: Check your AWS credentials and region
3. **No data found**: Verify that your Supabase tables contain data within the specified date range
4. **Import errors**: Ensure all dependencies are installed: `pip install -r requirements.txt`

## Performance Considerations

- Large date ranges with many messages may take time to process
- AWS Comprehend has rate limits and costs per API call
- Consider running analysis during off-peak hours for large datasets
- The system processes one day at a time to manage memory usage
