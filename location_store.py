"""
In-memory location store for token-based location requests.
Maps token (UUID string) -> {"lat": float, "lng": float}

This can be swapped for Redis or a database for scaling later.
"""

# Global in-memory store: token -> {"lat": ..., "lng": ...}
LOCATION_STORE: dict[str, dict[str, float]] = {}

