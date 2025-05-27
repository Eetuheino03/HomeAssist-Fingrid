"""DataUpdateCoordinator for the Fingrid Easy Setup integration."""
import asyncio
import logging
from datetime import timedelta

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry # Add this
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import (
    DOMAIN,
    CONF_API_KEY, # Added for clarity, used in __init__
    CONF_ENABLED_SENSORS,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DATASET_ID_POWER_SYSTEM_STATE,
)
from .exceptions import (
    FingridApiAuthError,
    FingridApiRateLimitError,
    FingridApiError,
)

_LOGGER = logging.getLogger(__name__)


class FingridDataUpdateCoordinator(DataUpdateCoordinator):
    """Manages fetching Fingrid data for the integration."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.config_entry = entry # Store the config entry
        self.api_key = entry.data[CONF_API_KEY] # Get API key from entry.data
        self.session = async_get_clientsession(hass)

        # Get enabled sensors from options, default to power system state if not set
        self.enabled_dataset_ids = entry.options.get(
            CONF_ENABLED_SENSORS, [DATASET_ID_POWER_SYSTEM_STATE]
        )
        
        # Get update interval from options, default to constant
        update_interval_minutes = entry.options.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL.seconds // 60
        )
        resolved_update_interval = timedelta(minutes=update_interval_minutes)

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({entry.entry_id})",
            update_interval=resolved_update_interval,
        )
        _LOGGER.debug(
            "Coordinator initialized with enabled_datasets: %s, update_interval: %s",
            self.enabled_dataset_ids,
            resolved_update_interval
        )

    async def _async_fetch_dataset(self, dataset_id: str) -> dict | None:
        """Fetch a single dataset from the Fingrid API."""
        url = f"https://data.fingrid.fi/api/datasets/{dataset_id}/data"
        headers = {"x-api-key": self.api_key, "Accept": "application/json"}
        # Parameters to get the latest value, may need adjustment based on API specifics
        # For many datasets, fetching with pageSize=1 and sorting by endTime desc might be needed
        # or specific startTime/endTime windows.
        # For now, a simple pageSize=1 for the latest entry.
        params = {"pageSize": 1} 

        _LOGGER.debug("Fetching dataset %s from %s", dataset_id, url)
        try:
            async with self.session.get(url, headers=headers, params=params, timeout=20) as response:
                if response.status == 200:
                    api_response = await response.json()
                    # Expecting a dict with a 'data' key containing a list
                    if (
                        isinstance(api_response, dict)
                        and "data" in api_response
                        and isinstance(api_response["data"], list)
                        and len(api_response["data"]) > 0
                    ):
                        latest_entry = api_response["data"][0]
                        _LOGGER.debug("Successfully fetched dataset %s: %s", dataset_id, latest_entry)
                        return latest_entry
                    _LOGGER.warning("No data or unexpected format for dataset %s: %s", dataset_id, api_response)
                    return None
                if response.status in [401, 403]:
                    _LOGGER.error("Authentication error for dataset %s: %s", dataset_id, response.status)
                    raise FingridApiAuthError(f"Authentication failed for dataset {dataset_id} (HTTP {response.status})")
                if response.status == 429:
                    _LOGGER.warning("Rate limit hit for dataset %s", dataset_id)
                    raise FingridApiRateLimitError(f"Rate limit hit for dataset {dataset_id}")
                
                response_text = await response.text()
                _LOGGER.error(
                    "Error fetching dataset %s: HTTP %s - %s",
                    dataset_id,
                    response.status,
                    response_text[:150] # Log snippet of error
                )
                raise FingridApiError(f"Error fetching dataset {dataset_id}: HTTP {response.status}")

        except aiohttp.ClientError as err:
            _LOGGER.error("Network error fetching dataset %s: %s", dataset_id, err)
            raise FingridApiError(f"Network error fetching dataset {dataset_id}: {err}") from err
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout fetching dataset %s", dataset_id)
            raise FingridApiError(f"Timeout fetching dataset {dataset_id}") from asyncio.TimeoutError
        except Exception as err: # Catch any other unexpected error during fetch
            _LOGGER.exception("Unexpected error fetching dataset %s: %s", dataset_id, err)
            raise FingridApiError(f"Unexpected error fetching dataset {dataset_id}: {err}") from err


    async def _async_update_data(self) -> dict[str, dict | None]:
        """Fetch data from Fingrid API for enabled datasets."""
        data_results: dict[str, dict | None] = {}
        
        # Warn if polling interval is too short for Fingrid API limits
        if self.update_interval.total_seconds() < 180:
            _LOGGER.warning(
                "Polling interval is set to less than 3 minutes. This may cause API rate limiting. "
                "Increase the update interval in integration options."
            )

        # Fetch datasets sequentially with a delay to avoid rate limits
        data_results: dict[str, dict | None] = {}
        auth_failure_raised = False
        for dataset_id in self.enabled_dataset_ids:
            try:
                result = await self._async_fetch_dataset(dataset_id)
            except FingridApiAuthError as e:
                _LOGGER.error("Authentication error processing dataset %s: %s", dataset_id, e)
                if not auth_failure_raised:
                    raise ConfigEntryAuthFailed(e) from e
                auth_failure_raised = True
                data_results[dataset_id] = None
            except (FingridApiRateLimitError, FingridApiError) as e:
                _LOGGER.warning("API error processing dataset %s: %s", dataset_id, e)
                data_results[dataset_id] = None
            except Exception as e:
                _LOGGER.error("Unexpected exception for dataset %s during fetch: %s", dataset_id, e)
                data_results[dataset_id] = None
            else:
                if result is not None:
                    data_results[dataset_id] = result
                else:
                    _LOGGER.warning("No data returned or malformed for dataset %s after fetch.", dataset_id)
                    data_results[dataset_id] = None
            # Delay between requests to avoid hitting rate limits (10/minute allowed)
            await asyncio.sleep(7)

            if isinstance(result, FingridApiAuthError):
                _LOGGER.error("Authentication error processing dataset %s: %s", dataset_id, result)
                if not auth_failure_raised:
                     # This will trigger re-auth flow in Home Assistant
                    raise ConfigEntryAuthFailed(result) from result
                auth_failure_raised = True
                data_results[dataset_id] = None 
            elif isinstance(result, (FingridApiRateLimitError, FingridApiError)):
                _LOGGER.warning("API error processing dataset %s: %s", dataset_id, result)
                # For rate limit or other API errors, we might still return partial data
                # or raise UpdateFailed if all fail.
                data_results[dataset_id] = None
            elif isinstance(result, Exception): # Other unexpected exceptions from gather
                _LOGGER.error("Unexpected exception for dataset %s during gather: %s", dataset_id, result)
                data_results[dataset_id] = None
            elif result is not None:
                data_results[dataset_id] = result
            else: # Result is None (successful call but no data or malformed)
                _LOGGER.warning("No data returned or malformed for dataset %s after fetch.", dataset_id)
                data_results[dataset_id] = None
        
        if not data_results and self.enabled_dataset_ids: # No data fetched at all for enabled sensors
            # If an auth error already raised ConfigEntryAuthFailed, HA handles it.
            # Otherwise, if all fetches failed for other reasons:
            if not auth_failure_raised:
                last_error = results[-1] if results and isinstance(results[-1], Exception) else "Unknown error"
                raise UpdateFailed(f"Failed to fetch any data from Fingrid API. Last error: {last_error}")
        
        _LOGGER.debug("Coordinator update finished, data: %s", data_results)
        return data_results