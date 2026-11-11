
"""Configuration flow for ViCare Heating Curve Sync."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN


class ViCareCurveSyncConfigFlow(
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial setup step."""

        if user_input is not None:
            return self.async_create_entry(
                title="ViCare Heizkurven-Synchronisierung",
                data={},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
        )


class ViCareCurveSyncOptionsFlow(
    config_entries.OptionsFlow,
):
    """Handle options."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage integration options."""

        if user_input is not None:
            return self.async_create_entry(
                title="",
                data=user_input,
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
        )


async def async_get_options_flow(config_entry):
    """Get options flow."""
    return ViCareCurveSyncOptionsFlow(config_entry)
