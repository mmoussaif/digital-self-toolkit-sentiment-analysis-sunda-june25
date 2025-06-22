import Foundation
import CoreLocation
import UIKit
import Supabase

class SupabaseService {
    static let shared = SupabaseService()
    
    private let supabase: SupabaseClient
    
    private init() {
        // Initialize Supabase client
        self.supabase = SupabaseClient(
            supabaseURL: URL(string: Secret.supabaseURL)!,
            supabaseKey: Secret.supabaseAnonKey
        )
    }
    
    func uploadLocation(location: CLLocation) {
        let locationData = LocationData(
            latitude: location.coordinate.latitude,
            longitude: location.coordinate.longitude,
            altitude: location.altitude,
            accuracy: location.horizontalAccuracy,
            timestamp: location.timestamp,
            speed: location.speed >= 0 ? location.speed : nil,
            course: location.course >= 0 ? location.course : nil
        )
        
        uploadLocationData(locationData)
    }
    
    private func uploadLocationData(_ locationData: LocationData) {
        // Perform async operations
        Task {
            await uploadLocationDataAsync(locationData)
        }
    }
    
    private func uploadLocationDataAsync(_ locationData: LocationData) async {
        guard !Secret.supabaseURL.contains("YOUR_SUPABASE_URL") else {
            print("⚠️ Supabase URL not configured - please update Secret.swift")
            return
        }
        
        do {
            print("📍 Uploading location: \(locationData.latitude), \(locationData.longitude)")
            
            // Use Supabase Swift SDK to insert location data
            try await supabase
                .from("location_history")
                .insert(locationData)
                .execute()
            
            print("✅ Location uploaded successfully")
            
        } catch {
            print("❌ Failed to upload location: \(error.localizedDescription)")
            
            // Handle specific Supabase errors
            if let error = error as? PostgrestError {
                print("🔍 Supabase error: \(error)")
            }
            
            // Store failed upload for retry
            storeFailedUpload(locationData)
        }
    }
    
    private func storeFailedUpload(_ locationData: LocationData) {
        // Store failed uploads in UserDefaults for retry later
        let key = "failedUploads"
        var failedUploads = UserDefaults.standard.array(forKey: key) as? [Data] ?? []
        
        do {
            let encoder = JSONEncoder()
            encoder.dateEncodingStrategy = .iso8601
            let data = try encoder.encode(locationData)
            failedUploads.append(data)
            UserDefaults.standard.set(failedUploads, forKey: key)
            print("📦 Stored failed upload for retry")
        } catch {
            print("❌ Error storing failed upload: \(error.localizedDescription)")
        }
    }
    
    func retryFailedUploads() {
        let key = "failedUploads"
        guard let failedUploads = UserDefaults.standard.array(forKey: key) as? [Data] else {
            return
        }
        
        print("🔄 Retrying \(failedUploads.count) failed uploads")
        
        Task {
            for data in failedUploads {
                do {
                    let decoder = JSONDecoder()
                    decoder.dateDecodingStrategy = .iso8601
                    let locationData = try decoder.decode(LocationData.self, from: data)
                    await uploadLocationDataAsync(locationData)
                } catch {
                    print("❌ Error decoding failed upload: \(error.localizedDescription)")
                }
            }
            
            // Clear failed uploads after retry attempt
            UserDefaults.standard.removeObject(forKey: key)
            print("🧹 Cleared failed uploads after retry")
        }
    }
}

struct LocationData: Codable {
    let timestamp: Date
    let latitude: Double
    let longitude: Double
    let accuracy: Double?
    let altitude: Double?
    let speed: Double?
    let heading: Double?
    let activityType: String?
    let locationName: String?
    let address: String?
    let source: String
    
    init(latitude: Double, longitude: Double, altitude: Double, accuracy: Double, timestamp: Date, speed: Double?, course: Double?) {
        self.timestamp = timestamp
        self.latitude = latitude
        self.longitude = longitude
        self.accuracy = accuracy
        self.altitude = altitude
        self.speed = speed
        self.heading = course
        self.activityType = nil // Can be enhanced later with motion detection
        self.locationName = nil // Can be enhanced later with reverse geocoding
        self.address = nil // Can be enhanced later with reverse geocoding
        self.source = "ios"
    }
} 
