from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DistanceResult:
    distance_km: float
    duration_minutes: int


class MapsProviderProtocol(Protocol):
    """
    Provider-independent interface for geospatial distance calculations
    and address geocoding.
    """

    async def calculate_distance(
        self, origin_coords: list[float], dest_coords: list[float]
    ) -> DistanceResult:
        """Calculate travel distance and duration between two [lon, lat] coordinates."""
        ...

    async def geocode_address(self, address_str: str) -> list[float]:
        """Geocode an address string into [longitude, latitude]."""
        ...
