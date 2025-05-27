"""The Fingrid Easy Setup integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import FingridDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Define the platforms that this integration will support.
# For now, we are preparing for sensors. Others can be added later.
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fingrid Easy Setup from a config entry."""
    _LOGGER.debug("Setting up Fingrid Easy Setup for config entry %s", entry.entry_id)

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    # api_key = entry.data[CONF_API_KEY] # No longer needed here, coordinator handles it

    coordinator = FingridDataUpdateCoordinator(hass=hass, entry=entry)

    # Perform the first data refresh. If this fails (e.g., bad API key,
    # network issues), Home Assistant will automatically retry setup later.
    # ConfigEntryNotReady will be raised by coordinator's first refresh if critical.
    await coordinator.async_config_entry_first_refresh()
    
    # Store the coordinator in hass.data for platforms to access.
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward the setup to platforms.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Add listener for options updates
    entry.async_on_unload(entry.add_update_listener(async_options_update_listener))

    _LOGGER.info("Fingrid Easy Setup successfully set up for config entry %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Fingrid Easy Setup for config entry %s", entry.entry_id)
    
    # Unload platforms.
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Clean up hass.data.
        # The coordinator itself might have cleanup tasks (e.g. closing sessions)
        # if it managed its own session, but here we use the shared one.
        if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
            del hass.data[DOMAIN][entry.entry_id]
            if not hass.data[DOMAIN]: # If no more entries for this domain
                del hass.data[DOMAIN]
        _LOGGER.info("Fingrid Easy Setup successfully unloaded for config entry %s", entry.entry_id)

    return unload_ok

async def async_options_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.debug("Fingrid options updated, reloading entry %s", entry.entry_id)
    # The coordinator and sensor setup will pick up new options on reload.
    await hass.config_entries.async_reload(entry.entry_id)