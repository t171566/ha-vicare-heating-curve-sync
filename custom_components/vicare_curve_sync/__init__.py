
"""ViCare Heating Curve Sync integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_VICARE_DEVICE,
    CONF_VICARE_ENTRY_ID,
    DOMAIN,
)
from .coordinator import ViCareCurveSync

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


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
    selected_device_id = entry.data.get(CONF_VICARE_DEVICE)

    if not vicare_entry_id or not selected_device_id:
        _LOGGER.error("ViCare configuration entry or device ID is missing")
        return False

    vicare_entry = hass.config_entries.async_get_entry(
        vicare_entry_id
    )

    if vicare_entry is None or vicare_entry.domain != "vicare":
        _LOGGER.error("Selected ViCare configuration entry was not found")
        return False

    synchronizer = ViCareCurveSync(
        hass,
        vicare_entry_id,
        selected_device_id,
    )

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
    """Unload ViCare Heating Curve Sync."""
    synchronizer = hass.data.get(DOMAIN, {}).get(entry.entry_id)

    if synchronizer is not None:
        await synchronizer.async_stop()
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return True
