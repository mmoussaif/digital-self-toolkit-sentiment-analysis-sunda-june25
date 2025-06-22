//
//  ViewController.swift
//  DigitalSelf
//
//  Created by Gabe Montague on 6/22/25.
//

import UIKit

class ViewController: UIViewController {
    
    private var statusLabel: UILabel!
    private var startButton: UIButton!
    private var stopButton: UIButton!
    
    override func viewDidLoad() {
        super.viewDidLoad()
        setupUI()
        updateStatus()
    }
    
    private func setupUI() {
        view.backgroundColor = .systemBackground
        
        // Create status label
        statusLabel = UILabel()
        statusLabel.text = "Location Tracking Status"
        statusLabel.textAlignment = .center
        statusLabel.font = UIFont.systemFont(ofSize: 18, weight: .medium)
        statusLabel.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(statusLabel)
        
        // Create start button
        startButton = UIButton(type: .system)
        startButton.setTitle("Start Location Tracking", for: .normal)
        startButton.backgroundColor = .systemGreen
        startButton.setTitleColor(.white, for: .normal)
        startButton.layer.cornerRadius = 8
        startButton.titleLabel?.font = UIFont.systemFont(ofSize: 16, weight: .medium)
        startButton.translatesAutoresizingMaskIntoConstraints = false
        startButton.addTarget(self, action: #selector(startButtonTapped), for: .touchUpInside)
        view.addSubview(startButton)
        
        // Create stop button
        stopButton = UIButton(type: .system)
        stopButton.setTitle("Stop Location Tracking", for: .normal)
        stopButton.backgroundColor = .systemRed
        stopButton.setTitleColor(.white, for: .normal)
        stopButton.layer.cornerRadius = 8
        stopButton.titleLabel?.font = UIFont.systemFont(ofSize: 16, weight: .medium)
        stopButton.translatesAutoresizingMaskIntoConstraints = false
        stopButton.addTarget(self, action: #selector(stopButtonTapped), for: .touchUpInside)
        view.addSubview(stopButton)
        
        // Setup constraints
        NSLayoutConstraint.activate([
            statusLabel.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            statusLabel.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 100),
            statusLabel.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 20),
            statusLabel.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -20),
            
            startButton.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            startButton.topAnchor.constraint(equalTo: statusLabel.bottomAnchor, constant: 50),
            startButton.widthAnchor.constraint(equalToConstant: 200),
            startButton.heightAnchor.constraint(equalToConstant: 44),
            
            stopButton.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            stopButton.topAnchor.constraint(equalTo: startButton.bottomAnchor, constant: 20),
            stopButton.widthAnchor.constraint(equalToConstant: 200),
            stopButton.heightAnchor.constraint(equalToConstant: 44)
        ])
    }
    
    @objc private func startButtonTapped() {
        LocationManager.shared.startLocationTracking()
        updateStatus()
    }
    
    @objc private func stopButtonTapped() {
        LocationManager.shared.stopLocationTracking()
        updateStatus()
    }
    
    private func updateStatus() {
        statusLabel.text = "Location tracking is active.\nData is being uploaded to Supabase."
    }
}

