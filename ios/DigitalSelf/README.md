# DigitalSelf - Location Tracking App

This iOS app tracks user location continuously (even in background) and uploads location data to Supabase.

## Features

- **Continuous Location Tracking**: Tracks user location at all times, including when the app is in the background
- **Supabase Integration**: Automatically uploads location data to your Supabase database
- **Permission Handling**: Properly requests and manages location permissions
- **Offline Support**: Stores failed uploads locally and retries when connection is restored
- **Background Processing**: Continues tracking even when the app is not in the foreground

## Setup Instructions

### 1. Supabase Configuration

1. Update the Supabase credentials in `SupabaseService.swift`:

   ```swift
   private let supabaseURL = "YOUR_SUPABASE_URL"
   private let supabaseAnonKey = "YOUR_SUPABASE_ANON_KEY"
   ```

2. Create a `locations` table in your Supabase database with the following schema:
   ```sql
   CREATE TABLE locations (
       id BIGSERIAL PRIMARY KEY,
       latitude DOUBLE PRECISION NOT NULL,
       longitude DOUBLE PRECISION NOT NULL,
       altitude DOUBLE PRECISION,
       accuracy DOUBLE PRECISION,
       timestamp TIMESTAMPTZ NOT NULL,
       speed DOUBLE PRECISION,
       course DOUBLE PRECISION,
       device_id TEXT,
       created_at TIMESTAMPTZ DEFAULT NOW()
   );
   ```

### 2. Xcode Project Configuration

You mentioned you can add the right keys to the Xcode project. Make sure to:

1. **Add Location Permissions**: The Info.plist has been updated with the required location usage descriptions.

2. **Enable Background Modes**: The Info.plist includes background modes for location tracking.

3. **Code Signing**: Ensure your app has the proper provisioning profile for location services.

### 3. Testing

1. **Simulator**: Location tracking won't work in the iOS Simulator. Use a physical device for testing.

2. **Background Testing**:
   - Run the app on a physical device
   - Grant location permissions when prompted
   - Put the app in background and move around
   - Check your Supabase database to verify location uploads

## App Architecture

### LocationManager

- Handles all Core Location functionality
- Manages location permissions
- Provides continuous location updates
- Handles background location tracking

### SupabaseService

- Manages communication with Supabase
- Handles location data uploads
- Implements retry logic for failed uploads
- Stores failed uploads locally for offline support

### ViewController

- Simple UI for controlling location tracking
- Start/stop location tracking buttons
- Status display

## Privacy Considerations

This app tracks location continuously, which raises privacy concerns:

1. **User Consent**: Always inform users about location tracking and get explicit consent
2. **Data Security**: Ensure your Supabase database is properly secured
3. **Data Retention**: Consider implementing data retention policies
4. **Compliance**: Ensure compliance with local privacy laws (GDPR, CCPA, etc.)

## Battery Optimization

Continuous location tracking can drain battery. Consider:

1. **Adjusting Accuracy**: Modify `desiredAccuracy` in LocationManager based on your needs
2. **Distance Filter**: The app updates every 10 meters - adjust as needed
3. **Significant Location Changes**: For less frequent updates, consider using `startMonitoringSignificantLocationChanges()`

## Next Steps

1. Replace the placeholder Supabase credentials
2. Set up your Supabase database table
3. Test on a physical device
4. Implement additional features as needed (data visualization, analytics, etc.)
