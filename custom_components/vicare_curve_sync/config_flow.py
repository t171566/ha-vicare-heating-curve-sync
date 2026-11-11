
"""Configuration flow for ViCare Heating Curve Sync."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries

from .const import CONF_VICARE_DEVICE, CONF_VICARE_ENTRY_ID, DOMAIN


def _has_supported_curves(api) -> bool:
    """Check whether the device provides two readable heating curves."""
    try:
        circuits = api.circuits

        if circuits is None or len(circuits) < 2:
            return False

        for circuit in circuits[:2]:
            float(circuit.getHeatingCurveSlope())
            float(circuit.getHeatingCurveShift())

        return True

    except Exception:
        return False


class ViCareCurveSyncConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure synchronization with an existing ViCare device."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Select the existing ViCare integration."""
        vicare_entries = self.hass.config_entries.async_entries("vicare")

        if not vicare_entries:
            return self.async_abort(reason="no_vicare_entry")

        if user_input is not None:
            self._vicare_entry_id = user_input[CONF_VICARE_ENTRY_ID]
            return await self.async_step_device()

        options = {
            entry.entry_id: entry.title
            for entry in vicare_entries
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_VICARE_ENTRY_ID): vol.In(options)
                }
            ),
        )

    async def async_step_device(self, user_input=None):
        """Select a ViCare device with two readable heating curves."""
        vicare_entry = self.hass.config_entries.async_get_entry(
            self._vicare_entry_id
        )

        if vicare_entry is None:
            return self.async_abort(reason="no_vicare_entry")

        vicare_data = getattr(vicare_entry, "runtime_data", None)

        if vicare_data is None:
            return self.async_abort(reason="vicare_not_ready")

        devices = getattr(vicare_data, "devices", [])
        options = {}

        for index, device in enumerate(devices):
            api = getattr(device, "api", None)

            if api is None:
                continue

            supported = await self.hass.async_add_executor_job(
                _has_supported_curves,
                api,
            )

            if not supported:
                continue

            device_id = device.serial or str(index)
            model = device.config.getModel()

            options[device_id] = (
                f"{model} – {device.serial or 'Gerät ' + str(index + 1)}"
            )

        if not options:
            return self.async_abort(reason="no_vicare_device")

        if user_input is not None:
            await self.async_set_unique_id(
                f"{self._vicare_entry_id}_{user_input[CONF_VICARE_DEVICE]}"
            )
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="ViCare Heizkurven-Synchronisierung",
                data={
                    CONF_VICARE_ENTRY_ID: self._vicare_entry_id,
                    CONF_VICARE_DEVICE: user_input[CONF_VICARE_DEVICE],
                },
            )

        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_VICARE_DEVICE): vol.In(options)
                }
            ),
        )
