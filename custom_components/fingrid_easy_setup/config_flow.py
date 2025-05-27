"""Config flow for Fingrid Easy Setup integration."""
import asyncio
import logging
import voluptuous as vol
import aiohttp

from homeassistant import config_entries
from homeassistant.core import callback # Ensure callback is imported if used for staticmethod decorator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_ENABLED_SENSORS,
    CONF_UPDATE_INTERVAL,
    AVAILABLE_SENSORS_DATA,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    MIN_UPDATE_INTERVAL_MINUTES,
    MAX_UPDATE_INTERVAL_MINUTES,
    DATASET_ID_POWER_SYSTEM_STATE,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({
    vol.Required("api_key"): str,
})

class FingridEasySetupConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fingrid Easy Setup."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            api_key = user_input["api_key"]
            session = async_get_clientsession(self.hass)
            headers = {"x-api-key": api_key, "Accept": "application/json"}
            # Using dataset 209 for validation as per blueprint
            url = "https://data.fingrid.fi/api/datasets/209/data?pageSize=1"

            try:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        # Optionally, try to parse JSON to be more certain
                        # await response.json()
                        await self.async_set_unique_id(api_key) # Using API key as unique_id
                        self._abort_if_unique_id_configured()
                        return self.async_create_entry(title="Fingrid", data=user_input)
                    elif response.status in [401, 403]:
                        errors["base"] = "invalid_api_key"
                    else:
                        # Catch-all for other HTTP errors during validation
                        _LOGGER.error(
                            "API validation failed with status %s: %s",
                            response.status,
                            await response.text()
                        )
                        errors["base"] = "cannot_connect" # Or a more specific error
            except (aiohttp.ClientError, asyncio.TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception as e: # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during API validation: %s", e)
                errors["base"] = "unknown" # Add a generic unknown error

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get the options flow for this handler."""
        return FingridOptionsFlowHandler(config_entry)


class FingridOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for Fingrid Easy Setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        # self.current_options = dict(config_entry.options) # For pre-filling form later

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            # Validate that at least one sensor is selected if that's a requirement
            # For now, we allow no sensors to be selected.
            # if not user_input.get(CONF_ENABLED_SENSORS):
            #     errors["base"] = "no_sensors_selected"
            #     # Re-show form with error (need to define error string)

            # Create the options entry
            return self.async_create_entry(title="", data=user_input)

        # Get current options to pre-fill the form
        current_enabled_sensors = self.config_entry.options.get(
            CONF_ENABLED_SENSORS, [DATASET_ID_POWER_SYSTEM_STATE] # Default to power state sensor
        )
        current_update_interval = self.config_entry.options.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_MINUTES
        )

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_ENABLED_SENSORS,
                    default=current_enabled_sensors,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": dataset_id, "label": name}
                            for dataset_id, name in AVAILABLE_SENSORS_DATA.items()
                        ],
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST, # Show as a list
                        # custom_value=False, # Not allowing custom values
                        # sort=True, # Optionally sort options by label
                    )
                ),
                vol.Required(
                    CONF_UPDATE_INTERVAL,
                    default=current_update_interval,
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_UPDATE_INTERVAL_MINUTES, max=MAX_UPDATE_INTERVAL_MINUTES),
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            # errors=errors # if adding validation like no_sensors_selected
        )