//
//  AppDelegate.swift
//  DigitalSelf
//
//  Created by Gabe Montague on 6/22/25.
//

import UIKit

@main
class AppDelegate: UIResponder, UIApplicationDelegate {

    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        // Initialize location tracking
        LocationManager.shared.startLocationTracking()
        
        // Retry any failed uploads
        SupabaseService.shared.retryFailedUploads()
        
        return true
    }
    
    func applicationDidEnterBackground(_ application: UIApplication) {
        // Continue location tracking in background
        print("App entered background - location tracking continues")
    }
    
    func applicationWillEnterForeground(_ application: UIApplication) {
        // Retry failed uploads when app comes to foreground
        SupabaseService.shared.retryFailedUploads()
        print("App entering foreground - retrying failed uploads")
    }

    // MARK: UISceneSession Lifecycle

    func application(_ application: UIApplication, configurationForConnecting connectingSceneSession: UISceneSession, options: UIScene.ConnectionOptions) -> UISceneConfiguration {
        // Called when a new scene session is being created.
        // Use this method to select a configuration to create the new scene with.
        return UISceneConfiguration(name: "Default Configuration", sessionRole: connectingSceneSession.role)
    }

    func application(_ application: UIApplication, didDiscardSceneSessions sceneSessions: Set<UISceneSession>) {
        // Called when the user discards a scene session.
        // If any sessions were discarded while the application was not running, this will be called shortly after application:didFinishLaunchingWithOptions.
        // Use this method to release any resources that were specific to the discarded scenes, as they will not return.
    }


}

