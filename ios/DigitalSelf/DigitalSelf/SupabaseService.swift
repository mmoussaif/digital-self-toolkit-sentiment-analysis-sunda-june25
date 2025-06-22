import Foundation
import CoreLocation
import UIKit

class SupabaseService {
    static let shared = SupabaseService()
    
    private let supabaseURL = Secret.supabaseURL
    private let supabaseAnonKey = Secret.supabaseAnonKey
    
    private let session = URLSession.shared
    
    private init() {}
    
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
        // Perform network operations on background queue
        DispatchQueue.global(qos: .utility).async { [weak self] in
            guard let self = self else { return }
            
            guard !self.supabaseURL.contains("YOUR_SUPABASE_URL") else {
                print("⚠️ Supabase URL not configured - please update Secret.swift")
                return
            }
            
            guard let url = URL(string: "\(self.supabaseURL)/rest/v1/locations") else {
                print("❌ Invalid Supabase URL: \(self.supabaseURL)")
                return
            }
            
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.addValue("application/json", forHTTPHeaderField: "Content-Type")
            request.addValue("Bearer \(self.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
            request.addValue(self.supabaseAnonKey, forHTTPHeaderField: "apikey")
            request.addValue("return=minimal", forHTTPHeaderField: "Prefer")
            
            do {
                let encoder = JSONEncoder()
                encoder.dateEncodingStrategy = .iso8601
                let jsonData = try encoder.encode(locationData)
                request.httpBody = jsonData
                
                print("📍 Uploading location: \(locationData.latitude), \(locationData.longitude)")
                
                let task = self.session.dataTask(with: request) { data, response, error in
                    if let error = error {
                        print("❌ Network error uploading location: \(error.localizedDescription)")
                        self.storeFailedUpload(locationData)
                        return
                    }
                    
                    if let httpResponse = response as? HTTPURLResponse {
                        if httpResponse.statusCode >= 200 && httpResponse.statusCode < 300 {
                            print("✅ Location uploaded successfully (Status: \(httpResponse.statusCode))")
                        } else {
                            print("❌ Failed to upload location. Status: \(httpResponse.statusCode)")
                            
                            // Log response for debugging
                            if let data = data, let responseString = String(data: data, encoding: .utf8) {
                                print("Response: \(responseString)")
                            }
                            
                            // Common HTTP status codes
                            switch httpResponse.statusCode {
                            case 401:
                                print("🔑 Authentication failed - check your Supabase anon key")
                            case 403:
                                print("🚫 Access forbidden - check your database policies")
                            case 404:
                                print("🔍 Table not found - make sure 'locations' table exists")
                            case 405:
                                print("❌ Method not allowed - check your Supabase configuration and table policies")
                            default:
                                break
                            }
                            
                            self.storeFailedUpload(locationData)
                        }
                    }
                }
                
                task.resume()
            } catch {
                print("❌ Error encoding location data: \(error.localizedDescription)")
            }
        }
    }
    
    private func storeFailedUpload(_ locationData: LocationData) {
        // Store failed uploads in UserDefaults for retry later
        let key = "failedUploads"
        var failedUploads = UserDefaults.standard.array(forKey: key) as? [Data] ?? []
        
        do {
            let data = try JSONEncoder().encode(locationData)
            failedUploads.append(data)
            UserDefaults.standard.set(failedUploads, forKey: key)
            print("Stored failed upload for retry")
        } catch {
            print("Error storing failed upload: \(error.localizedDescription)")
        }
    }
    
    func retryFailedUploads() {
        let key = "failedUploads"
        guard let failedUploads = UserDefaults.standard.array(forKey: key) as? [Data] else {
            return
        }
        
        print("Retrying \(failedUploads.count) failed uploads")
        
        for data in failedUploads {
            do {
                let locationData = try JSONDecoder().decode(LocationData.self, from: data)
                uploadLocationData(locationData)
            } catch {
                print("Error decoding failed upload: \(error.localizedDescription)")
            }
        }
        
        // Clear failed uploads after retry attempt
        UserDefaults.standard.removeObject(forKey: key)
    }
}

struct LocationData: Codable {
    let latitude: Double
    let longitude: Double
    let altitude: Double
    let accuracy: Double
    let timestamp: Date
    let speed: Double?
    let course: Double?
    let deviceId: String
    
    init(latitude: Double, longitude: Double, altitude: Double, accuracy: Double, timestamp: Date, speed: Double?, course: Double?) {
        self.latitude = latitude
        self.longitude = longitude
        self.altitude = altitude
        self.accuracy = accuracy
        self.timestamp = timestamp
        self.speed = speed
        self.course = course
        self.deviceId = UIDevice.current.identifierForVendor?.uuidString ?? "unknown"
    }
} 
