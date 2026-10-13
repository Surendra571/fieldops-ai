import math

from app.integrations.maps.protocol import DistanceResult, MapsProviderProtocol


class MockMapsAdapter(MapsProviderProtocol):
    """
    Deterministic, offline Maps adapter using the Haversine formula
    for distance calculation and realistic urban travel time estimations.
    """

    def __init__(self, average_speed_kmh: float = 40.0):
        self.average_speed_kmh = average_speed_kmh
        # Known geocoded addresses for testing
        self._address_cache = {
            "1428 elm street": [-84.3840, 33.7890],
            "742 evergreen terrace": [-84.3500, 33.7800],
            "221b baker street": [-84.4100, 33.7750],
            "100 peachtree st": [-84.3880, 33.7560],
        }

    async def calculate_distance(
        self, origin_coords: list[float], dest_coords: list[float]
    ) -> DistanceResult:
        """
        Calculate geodesic distance between [lon1, lat1] and [lon2, lat2] in kilometers.
        """
        lon1, lat1 = origin_coords
        lon2, lat2 = dest_coords

        # Earth radius in kilometers
        r = 6371.0

        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_phi / 2.0) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        distance_km = round(r * c, 2)

        # Estimate duration in minutes based on urban driving speed (minimum 5 mins)
        duration_minutes = max(5, int(round((distance_km / self.average_speed_kmh) * 60)))

        return DistanceResult(
            distance_km=distance_km,
            duration_minutes=duration_minutes,
        )

    async def geocode_address(self, address_str: str) -> list[float]:
        """
        Resolve address string into [longitude, latitude].
        Falls back to Metro Atlanta coordinates if unknown.
        """
        cleaned = address_str.lower().strip()
        for key, coords in self._address_cache.items():
            if key in cleaned:
                return coords
        # Default Atlanta coordinate
        return [-84.3880, 33.7490]
