# DigitalSelf - Location Tracking App

This iOS app tracks user location continuously (even in background) and uploads location data to Supabase.

**WARNING**: Do NOT publish this app on the app store or distribute it via TestFlight. It contains hard-coded your Supabase key to the project of your personal data.

## Setup

- Copy `Secret.swift.template` to `Secret.swift` and fill in the details of your Supabase.
- Set your signing team in the Xcode project settings. Automatically manage signing.
- Build for iPhone
