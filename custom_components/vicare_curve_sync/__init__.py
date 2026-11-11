
"""ViCare Heating Curve Sync integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_VICARE_ENTRY_ID, DOMAIN
from .coordinator import ViCareCurveSync

_LOGGER = logging.getLogger(__name__)


def _get_supported_circuits(api):
    """Load and check the first two supported ViCare heating circuits."""
    try:
        circuits = api.circuits

        if circuits is None or len(circuits) < 2:
            return None

        for circuit in circuits[:2]:
            float(circuit.getHeatingCurveSlope())
            float(circuit.getHeatingCurveShift())

        return circuits

    except Exception:
        return None


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
    selected_circuits = None

    for device in devices:
        api = getattr(device, "api", None)

        if api is None:
            continue

        circuits = await hass.async_add_executor_job(
            _get_supported_circuits,
            api,
        )

        if circuits is not None:
            selected_device = device
            selected_circuits = circuits
            break

    if selected_device is None:
        _LOGGER.error(
            "No ViCare device with two supported heating curves was found"
        )
        return False

    synchronizer = ViCareCurveSync(
        hass, selected_device, selected_circuits
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
    """Unload the integration."""
    synchronizer = hass.data.get(DOMAIN, {}).get(entry.entry_id)

    if synchronizer is not None:
        await synchronizer.async_stop()
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return True
