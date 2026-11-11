
"""Coordinator for ViCare Heating Curve Sync."""

from __future__ import annotations

from homeassistant.core import HomeAssistant


class ViCareCurveSyncCoordinator:
    """Manage ViCare heating curve synchronization."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.data = {}

    async def async_update(self) -> dict:
        """Update heating curve data."""
        # ViCare API connection will be implemented
        # after verifying the installed integration API.
        return self.data
