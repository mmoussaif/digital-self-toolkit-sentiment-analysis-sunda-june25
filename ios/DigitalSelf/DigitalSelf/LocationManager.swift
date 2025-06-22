import CoreLocation
import UIKit

class LocationManager: NSObject, CLLocationManagerDelegate {
    static let shared = LocationManager()
    
    private let locationManager = CLLocationManager()
    private let supabaseService = SupabaseService.shared
    
    private override init() {
        super.init()
        setupLocationManager()
    }
    
    private func setupLocationManager() {
        locationManager.delegate = self
        locationManager.desiredAccuracy = kCLLocationAccuracyBest
        locationManager.distanceFilter = 10 // Update every 10 meters
        locationManager.pausesLocationUpdatesAutomatically = false
        
        // Don't set background location updates here - do it after authorization
    }
    
    func startLocationTracking() {
        guard CLLocationManager.locationServicesEnabled() else {
            print("Location services not enabled")
            return
        }
        
        switch locationManager.authorizationStatus {
        case .authorizedAlways:
            startLocationUpdates()
        case .authorizedWhenInUse:
            // Request always authorization if we only have when-in-use
            locationManager.requestAlwaysAuthorization()
        case .denied, .restricted:
            print("Location access denied or restricted")
            showLocationPermissionAlert()
        case .notDetermined:
            locationManager.requestAlwaysAuthorization()
        @unknown default:
            break
        }
    }
    
    private func startLocationUpdates() {
        guard locationManager.authorizationStatus == .authorizedAlways else {
            print("Cannot start location updates without proper authorization")
            return
        }
        
        // Enable background location updates only when we have proper authorization
        locationManager.allowsBackgroundLocationUpdates = true
        locationManager.startUpdatingLocation()
        print("Started location tracking with background updates enabled")
    }
    
    func stopLocationTracking() {
        locationManager.stopUpdatingLocation()
        print("Stopped location tracking")
    }
    
    private func showLocationPermissionAlert() {
        DispatchQueue.main.async {
            guard let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
                  let window = windowScene.windows.first else { return }
            
            let alert = UIAlertController(
                title: "Location Permission Required",
                message: "This app needs location access to track your location. Please enable location access in Settings.",
                preferredStyle: .alert
            )
            
            alert.addAction(UIAlertAction(title: "Settings", style: .default) { _ in
                if let settingsUrl = URL(string: UIApplication.openSettingsURLString) {
                    UIApplication.shared.open(settingsUrl)
                }
            })
            
            alert.addAction(UIAlertAction(title: "Cancel", style: .cancel))
            
            window.rootViewController?.present(alert, animated: true)
        }
    }
    
    // MARK: - CLLocationManagerDelegate
    
    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let location = locations.last else { return }
        
        print("Location updated: \(location.coordinate.latitude), \(location.coordinate.longitude)")
        
        // Upload location to Supabase
        supabaseService.uploadLocation(location: location)
    }
    
    func locationManager(_ manager: CLLocationManager, didChangeAuthorization status: CLAuthorizationStatus) {
        print("Location authorization changed to: \(authorizationStatusString(status))")
        
        switch status {
        case .authorizedAlways:
            startLocationUpdates()
        case .authorizedWhenInUse:
            print("Only 'when in use' permission granted - requesting 'always' for background tracking")
            locationManager.requestAlwaysAuthorization()
        case .denied, .restricted:
            print("Location authorization denied or restricted")
            showLocationPermissionAlert()
        case .notDetermined:
            print("Location authorization not determined")
        @unknown default:
            print("Unknown authorization status")
        }
    }
    
    private func authorizationStatusString(_ status: CLAuthorizationStatus) -> String {
        switch status {
        case .notDetermined: return "Not Determined"
        case .restricted: return "Restricted"
        case .denied: return "Denied"
        case .authorizedAlways: return "Always"
        case .authorizedWhenInUse: return "When In Use"
        @unknown default: return "Unknown"
        }
    }
    
    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        print("Location manager failed with error: \(error.localizedDescription)")
    }
} 