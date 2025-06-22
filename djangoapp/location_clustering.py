"""
Location clustering module for processing GPS trails into meaningful places.

This module implements a sophisticated clustering approach that:
1. Detects stay points where users remain in one location for a meaningful time
2. Clusters those stay points using DBSCAN
3. Summarizes clusters into commonly visited places
"""

import logging
import math
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

import numpy as np
from dateutil.parser import parse as parse_date
from sklearn.cluster import DBSCAN

logger = logging.getLogger(__name__)


class GPSPoint:
    """Represents a single GPS point with timestamp."""

    def __init__(
        self, latitude: float, longitude: float, timestamp: datetime, **metadata
    ):
        self.latitude = float(latitude)
        self.longitude = float(longitude)
        self.timestamp = timestamp
        self.metadata = metadata

    def __repr__(self):
        return f"GPSPoint({self.latitude}, {self.longitude}, {self.timestamp})"


class StayPoint:
    """Represents a detected stay point."""

    def __init__(
        self,
        latitude: float,
        longitude: float,
        start_time: datetime,
        end_time: datetime,
        point_count: int,
        **metadata,
    ):
        self.latitude = float(latitude)
        self.longitude = float(longitude)
        self.start_time = start_time
        self.end_time = end_time
        self.point_count = point_count
        self.duration_minutes = (end_time - start_time).total_seconds() / 60
        self.metadata = metadata

    def __repr__(self):
        return f"StayPoint({self.latitude}, {self.longitude}, {self.duration_minutes:.1f}min)"


class LocationCluster:
    """Represents a clustered location with visit statistics."""

    def __init__(
        self,
        center_latitude: float,
        center_longitude: float,
        stay_points: List[StayPoint],
        name: str = "",
        address: str = "",
    ):
        self.center_latitude = float(center_latitude)
        self.center_longitude = float(center_longitude)
        self.stay_points = stay_points
        self.name = name
        self.address = address

        # Calculate statistics
        self.visit_count = len(stay_points)
        self.total_time_minutes = sum(sp.duration_minutes for sp in stay_points)

        if stay_points:
            self.first_visit = min(sp.start_time for sp in stay_points)
            self.last_visit = max(sp.end_time for sp in stay_points)
        else:
            self.first_visit = None
            self.last_visit = None

        # Aggregate activity types from metadata
        self.activity_types = defaultdict(int)
        for sp in stay_points:
            activity = sp.metadata.get("activity_type")
            if activity:
                self.activity_types[activity] += 1

    @property
    def average_time_per_visit(self) -> float:
        """Return average time per visit in minutes."""
        if self.visit_count > 0:
            return self.total_time_minutes / self.visit_count
        return 0.0

    def __repr__(self):
        name = self.name or f"{self.center_latitude:.6f}, {self.center_longitude:.6f}"
        return f"LocationCluster({name}, {self.visit_count} visits, {self.total_time_minutes:.1f}min)"


class LocationClusterer:
    """Main class for processing GPS trails into meaningful places."""

    def __init__(
        self,
        stay_distance_threshold_meters: int = 100,
        stay_time_threshold_minutes: int = 10,
        cluster_distance_threshold_meters: int = 200,
        min_cluster_visits: int = 2,
    ):
        """
        Initialize the location clusterer.

        Args:
            stay_distance_threshold_meters: Max distance for stay point detection
            stay_time_threshold_minutes: Min time for stay point detection
            cluster_distance_threshold_meters: Max distance for clustering stay points
            min_cluster_visits: Minimum visits required to form a cluster
        """
        self.stay_distance_threshold = stay_distance_threshold_meters
        self.stay_time_threshold = stay_time_threshold_minutes
        self.cluster_distance_threshold = cluster_distance_threshold_meters
        self.min_cluster_visits = min_cluster_visits

    def process_gps_trail(self, gps_data: List[Dict]) -> List[LocationCluster]:
        """
        Process a GPS trail into meaningful location clusters.

        Args:
            gps_data: List of GPS records with lat, lng, timestamp, and metadata

        Returns:
            List of LocationCluster objects sorted by visit frequency
        """
        print(f"🔍 Processing {len(gps_data)} GPS points into location clusters...")

        # Step 1: Convert to GPSPoint objects and sort chronologically
        gps_points = self._convert_to_gps_points(gps_data)
        if not gps_points:
            print("❌ No valid GPS points to process")
            return []

        print(f"📍 Converted to {len(gps_points)} GPS points")

        # Step 2: Detect stay points
        stay_points = self._detect_stay_points(gps_points)
        print(f"⏱️  Detected {len(stay_points)} stay points")

        if not stay_points:
            print("❌ No stay points detected")
            return []

        # Step 3: Cluster stay points
        clusters = self._cluster_stay_points(stay_points)
        print(f"🏠 Created {len(clusters)} location clusters")

        # Step 4: Sort by importance (visit count, then total time)
        clusters.sort(key=lambda c: (-c.visit_count, -c.total_time_minutes))

        return clusters

    def _convert_to_gps_points(self, gps_data: List[Dict]) -> List[GPSPoint]:
        """Convert raw GPS data to GPSPoint objects."""
        points = []

        for record in gps_data:
            if not record.get("latitude") or not record.get("longitude"):
                continue

            try:
                timestamp = parse_date(record["timestamp"])
                point = GPSPoint(
                    latitude=record["latitude"],
                    longitude=record["longitude"],
                    timestamp=timestamp,
                    **{
                        k: v
                        for k, v in record.items()
                        if k not in ["latitude", "longitude", "timestamp"]
                    },
                )
                points.append(point)
            except Exception as e:
                logger.warning(f"Error parsing GPS record: {e}")

        # Sort chronologically
        points.sort(key=lambda p: p.timestamp)
        return points

    def _detect_stay_points(self, gps_points: List[GPSPoint]) -> List[StayPoint]:
        """
        Detect stay points using the sliding window approach.

        A stay point is a location where the user stayed within a certain distance
        for more than a minimum time threshold.
        """
        stay_points = []
        i = 0

        print(
            f"      Detecting stay points with {self.stay_distance_threshold}m distance and {self.stay_time_threshold}min time thresholds..."
        )

        while i < len(gps_points):
            j = i + 1

            # Find all consecutive points within distance threshold
            while j < len(gps_points):
                distance = self._calculate_distance(
                    gps_points[i].latitude,
                    gps_points[i].longitude,
                    gps_points[j].latitude,
                    gps_points[j].longitude,
                )
                if distance > self.stay_distance_threshold:
                    break
                j += 1

            # Check if time spent is above threshold
            if j > i + 1:  # At least 2 points
                time_diff = (
                    gps_points[j - 1].timestamp - gps_points[i].timestamp
                ).total_seconds() / 60

                if time_diff >= self.stay_time_threshold:
                    # Calculate centroid of the stay point
                    segment_points = gps_points[i:j]
                    center_lat = sum(p.latitude for p in segment_points) / len(
                        segment_points
                    )
                    center_lng = sum(p.longitude for p in segment_points) / len(
                        segment_points
                    )

                    # Aggregate metadata
                    metadata = {}
                    activity_types = defaultdict(int)
                    for p in segment_points:
                        activity = p.metadata.get("activity_type")
                        if activity:
                            activity_types[activity] += 1

                    if activity_types:
                        # Use most common activity type
                        metadata["activity_type"] = max(
                            activity_types.items(), key=lambda x: x[1]
                        )[0]

                    # Use metadata from the first point for other fields
                    for key in ["location_name", "address", "source"]:
                        if gps_points[i].metadata.get(key):
                            metadata[key] = gps_points[i].metadata[key]

                    stay_point = StayPoint(
                        latitude=center_lat,
                        longitude=center_lng,
                        start_time=gps_points[i].timestamp,
                        end_time=gps_points[j - 1].timestamp,
                        point_count=len(segment_points),
                        **metadata,
                    )
                    stay_points.append(stay_point)

                    print(f"        Found stay point: {stay_point}")

            # Move to next non-overlapping segment
            i = max(i + 1, j)

        return stay_points

    def _cluster_stay_points(
        self, stay_points: List[StayPoint]
    ) -> List[LocationCluster]:
        """
        Cluster stay points using DBSCAN to find commonly visited places.
        """
        if len(stay_points) < self.min_cluster_visits:
            print(
                f"      Not enough stay points ({len(stay_points)}) for clustering (min: {self.min_cluster_visits})"
            )
            return []

        # Convert to coordinate array for DBSCAN
        coordinates = np.array([[sp.latitude, sp.longitude] for sp in stay_points])

        # Convert distance threshold to approximate degrees
        # Rough approximation: 1 degree ≈ 111,000 meters
        eps_degrees = self.cluster_distance_threshold / 111000.0

        print(
            f"      Clustering with eps={eps_degrees:.6f} degrees (~{self.cluster_distance_threshold}m), min_samples={self.min_cluster_visits}"
        )

        # Apply DBSCAN clustering
        dbscan = DBSCAN(
            eps=eps_degrees, min_samples=self.min_cluster_visits, metric="euclidean"
        )
        cluster_labels = dbscan.fit_predict(coordinates)

        # Group stay points by cluster
        clusters_dict = defaultdict(list)
        for i, label in enumerate(cluster_labels):
            if label != -1:  # -1 indicates noise/outlier
                clusters_dict[label].append(stay_points[i])

        print(
            f"      DBSCAN found {len(clusters_dict)} clusters from {len(stay_points)} stay points"
        )

        # Create LocationCluster objects
        clusters = []
        for cluster_id, cluster_stay_points in clusters_dict.items():
            # Calculate cluster centroid
            center_lat = sum(sp.latitude for sp in cluster_stay_points) / len(
                cluster_stay_points
            )
            center_lng = sum(sp.longitude for sp in cluster_stay_points) / len(
                cluster_stay_points
            )

            # Try to get a meaningful name from the stay points
            name = ""
            address = ""
            for sp in cluster_stay_points:
                if sp.metadata.get("location_name") and not name:
                    name = sp.metadata["location_name"]
                if sp.metadata.get("address") and not address:
                    address = sp.metadata["address"]
                if name and address:
                    break

            cluster = LocationCluster(
                center_latitude=center_lat,
                center_longitude=center_lng,
                stay_points=cluster_stay_points,
                name=name,
                address=address,
            )
            clusters.append(cluster)

            print(f"        Cluster {cluster_id}: {cluster}")

        return clusters

    def _calculate_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Calculate distance between two points in meters using Haversine formula."""
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))
        r = 6371000  # Earth's radius in meters

        return c * r


def process_location_data(
    gps_data: List[Dict],
    stay_distance_threshold: int = 100,
    stay_time_threshold: int = 10,
    cluster_distance_threshold: int = 200,
    min_cluster_visits: int = 2,
) -> List[LocationCluster]:
    """
    Convenience function to process GPS data into location clusters.

    Args:
        gps_data: List of GPS records with lat, lng, timestamp, and metadata
        stay_distance_threshold: Max distance for stay point detection (meters)
        stay_time_threshold: Min time for stay point detection (minutes)
        cluster_distance_threshold: Max distance for clustering stay points (meters)
        min_cluster_visits: Minimum visits required to form a cluster

    Returns:
        List of LocationCluster objects sorted by visit frequency
    """
    clusterer = LocationClusterer(
        stay_distance_threshold_meters=stay_distance_threshold,
        stay_time_threshold_minutes=stay_time_threshold,
        cluster_distance_threshold_meters=cluster_distance_threshold,
        min_cluster_visits=min_cluster_visits,
    )

    return clusterer.process_gps_trail(gps_data)
