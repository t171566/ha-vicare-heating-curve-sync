
"""ViCare Heating Curve Sync integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_VICARE_ENTRY_ID, DOMAIN
from .coordinator import ViCareCurveSync

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up ViCare Heating Curve Sync from a config entry."""
    vicare_entry_id = entry.data.get(CONF_VICARE_ENTRY_ID)

    vicare_entry = hass.config_entries.async_get_entry(
        vicare_entry_id
    )

    if vicare_entry is None or vicare_entry.domain != "vicare":
        _LOGGER.error("Selected ViCare configuration entry was not found")
        return False

    vicare_data = getattr(vicare_entry, "runtime_data", None)

    if vicare_data is None:
        _LOGGER.error("ViCare runtime data is not available")
        return False

    devices = getattr(vicare_data, "devices", [])

    selected_device = None

    for device in devices:
        api = getattr(device, "api", None)

        if api is None:
            continue

        try:
            circuits = api.circuits
        except Exception:
            continue

        if circuits is not None and len(circuits) >= 2:
            selected_device = device
            break

    if selected_device is None:
        _LOGGER.error(
            "No ViCare device with at least two heating circuits was found"
        )
        return False

    synchronizer = ViCareCurveSync(hass, selected_device)

    try:
        await synchronizer.async_start()
    except Exception:
        _LOGGER.exception("Could not start ViCare curve synchronization")
        await synchronizer.async_stop()
        return False

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = synchronizer

    _LOGGER.info("ViCare heating curve synchronization started")
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Unload the integration."""
    synchronizer = hass.data.get(DOMAIN, {}).get(entry.entry_id)

    if synchronizer is not None:
        await synchronizer.async_stop()
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return True
