
"""Configuration flow for ViCare Heating Curve Sync."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries

from .const import CONF_VICARE_ENTRY_ID, DOMAIN


class ViCareCurveSyncConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure synchronization with an existing ViCare integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Select the existing ViCare config entry."""
        vicare_entries = self.hass.config_entries.async_entries("vicare")

        if not vicare_entries:
            return self.async_abort(reason="no_vicare_entry")

        if user_input is not None:
            vicare_entry_id = user_input[CONF_VICARE_ENTRY_ID]

            await self.async_set_unique_id(vicare_entry_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="ViCare Heizkurven-Synchronisierung",
                data={
                    CONF_VICARE_ENTRY_ID: vicare_entry_id,
                },
            )

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


async_get_options_flow = None
