"""Sensor platform for Fingrid Easy Setup integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass, # Add this
    SensorStateClass,  # Add this
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfFrequency # Add this
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo, DeviceEntryType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    DATASET_ID_POWER_SYSTEM_STATE,
    DATASET_ID_GRID_FREQUENCY, # Add this
    DATASET_ID_ELECTRICITY_SHORTAGE_STATUS, # Add this
)
from .coordinator import FingridDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Define a mapping for power system states (dataset 209)
# This can be expanded or moved to const.py if it grows
POWER_SYSTEM_STATE_MAP: dict[int, str] = {
    1: "Normal",
    2: "Endangered",
    3: "Disturbed",
    4: "Blackout",
    5: "Restoration",
}
# Fallback description if state is unknown
POWER_SYSTEM_STATE_UNKNOWN = "Unknown"

# Add this near POWER_SYSTEM_STATE_MAP
ELECTRICITY_SHORTAGE_STATUS_MAP: dict[int, str] = {
    0: "Normal",
    1: "Electricity shortage possible",
    2: "High risk of electricity shortage",
    3: "Electricity shortage",
}
ELECTRICITY_SHORTAGE_STATUS_UNKNOWN = "Unknown"


class FingridSensor(CoordinatorEntity[FingridDataUpdateCoordinator], SensorEntity):
    """Base class for Fingrid sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FingridDataUpdateCoordinator,
        config_entry_id: str,
        dataset_id: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._dataset_id = dataset_id
        self._config_entry_id = config_entry_id # To make unique_id truly unique per config entry

        # Set unique ID based on config entry ID and dataset ID
        self._attr_unique_id = f"{self._config_entry_id}_{self._dataset_id}"

        # Associate with a device for better organization in HA
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._config_entry_id)},
            name="Fingrid Open Data", # User-friendly name for the device
            manufacturer="Fingrid",
            model="API Data", # Can be more specific if versions/types emerge
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        """Return True if coordinator is available and dataset has data."""
        return (
            super().available
            and self.coordinator.data is not None
            and self._dataset_id in self.coordinator.data
            and self.coordinator.data[self._dataset_id] is not None
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data and self._dataset_id in self.coordinator.data:
            dataset_data = self.coordinator.data[self._dataset_id]
            if dataset_data and "value" in dataset_data:
                self._update_state(dataset_data)
            else:
                # Mark as unavailable if specific data point is missing after successful fetch
                # This case might indicate an unexpected API response structure for this sensor
                _LOGGER.warning(
                    "Dataset %s for entity %s has no 'value' or is None. Data: %s",
                    self._dataset_id,
                    self.entity_id,
                    dataset_data
                )
                # Keep previous state or set to None? For now, let super().available handle it.
                # If we want to force unavailable if 'value' is missing:
                # self._attr_native_value = None
        self.async_write_ha_state()

    def _update_state(self, dataset_data: dict[str, Any]) -> None:
        """Update the sensor's state from dataset data. To be overridden by subclasses."""
        self._attr_native_value = dataset_data.get("value")
        # Store the raw API timestamp if available
        if "endTime" in dataset_data: # Fingrid uses 'endTime' for the data point's timestamp
             self._attr_extra_state_attributes = {
                 **self._attr_extra_state_attributes, # preserve existing attributes
                "api_timestamp": dataset_data["endTime"],
             }
        elif "startTime" in dataset_data: # Or startTime as a fallback
             self._attr_extra_state_attributes = {
                 **self._attr_extra_state_attributes,
                "api_timestamp": dataset_data["startTime"],
             }


class FingridPowerSystemStateSensor(FingridSensor):
    """Sensor for Fingrid Power System State (Dataset 209)."""

    def __init__(
        self,
        coordinator: FingridDataUpdateCoordinator,
        config_entry_id: str,
        dataset_id: str, # Should be "209"
    ) -> None:
        """Initialize the power system state sensor."""
        description = SensorEntityDescription(
            key=dataset_id, # Use dataset_id as key
            name="Power System State", # User-friendly name part
            icon="mdi:transmission-tower",
            # No device_class or unit_of_measurement for this categorical sensor
            # state_class can be None if it's not a numeric measurement
        )
        super().__init__(coordinator, config_entry_id, dataset_id, description)
        self._attr_extra_state_attributes = {} # Initialize extra attributes

    def _update_state(self, dataset_data: dict[str, Any]) -> None:
        """Update the sensor's state and attributes."""
        # Set the mapped description as the state, not the raw number
        current_value = dataset_data.get("value")
        if isinstance(current_value, (int, float)):
            numeric_value = int(current_value)
            description = POWER_SYSTEM_STATE_MAP.get(numeric_value, POWER_SYSTEM_STATE_UNKNOWN)
            self._attr_native_value = description
            self._attr_extra_state_attributes["raw_value"] = numeric_value
        else:
            self._attr_native_value = POWER_SYSTEM_STATE_UNKNOWN


class FingridGridFrequencySensor(FingridSensor):
    """Sensor for Fingrid Grid Frequency (Dataset 177)."""

    def __init__(
        self,
        coordinator: FingridDataUpdateCoordinator,
        config_entry_id: str,
        dataset_id: str, # Should be DATASET_ID_GRID_FREQUENCY
    ) -> None:
        """Initialize the grid frequency sensor."""
        description = SensorEntityDescription(
            key=dataset_id,
            name="Grid Frequency", # From SENSOR_NAME_GRID_FREQUENCY in const.py
            icon="mdi:sine-wave",
            native_unit_of_measurement=UnitOfFrequency.HERTZ,
            device_class=SensorDeviceClass.FREQUENCY,
            state_class=SensorStateClass.MEASUREMENT,
        )
        super().__init__(coordinator, config_entry_id, dataset_id, description)
        self._attr_extra_state_attributes = {} # Initialize


class FingridElectricityShortageSensor(FingridSensor):
    """Sensor for Fingrid Electricity Shortage Status (Dataset 336)."""

    def __init__(
        self,
        coordinator: FingridDataUpdateCoordinator,
        config_entry_id: str,
        dataset_id: str, # Should be DATASET_ID_ELECTRICITY_SHORTAGE_STATUS
    ) -> None:
        """Initialize the electricity shortage status sensor."""
        description = SensorEntityDescription(
            key=dataset_id,
            name="Electricity Shortage Status", # From SENSOR_NAME_ELECTRICITY_SHORTAGE_STATUS
            icon="mdi:power-plug-off-outline", # Consider dynamic icon later if desired
        )
        super().__init__(coordinator, config_entry_id, dataset_id, description)
        self._attr_extra_state_attributes = {} # Initialize

    def _update_state(self, dataset_data: dict[str, Any]) -> None:
        """Update the sensor's state and attributes."""
        # Set the mapped description as the state, not the raw number
        current_value = dataset_data.get("value")
        if isinstance(current_value, (int, float)):
            numeric_value = int(current_value)
            description_text = ELECTRICITY_SHORTAGE_STATUS_MAP.get(
                numeric_value, ELECTRICITY_SHORTAGE_STATUS_UNKNOWN
            )
            self._attr_native_value = description_text
            self._attr_extra_state_attributes["raw_value"] = numeric_value
        else:
            self._attr_native_value = ELECTRICITY_SHORTAGE_STATUS_UNKNOWN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Fingrid sensors from a config entry."""
    coordinator: FingridDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities_to_add: list[SensorEntity] = []

    # Get enabled datasets from the coordinator (which gets them from options)
    enabled_datasets = coordinator.enabled_dataset_ids
    _LOGGER.debug("Setting up sensors for enabled datasets: %s", enabled_datasets)

    if DATASET_ID_POWER_SYSTEM_STATE in enabled_datasets:
        entities_to_add.append(
            FingridPowerSystemStateSensor(
                coordinator=coordinator,
                config_entry_id=entry.entry_id,
                dataset_id=DATASET_ID_POWER_SYSTEM_STATE,
            )
        )
        _LOGGER.info(
            "Adding Fingrid Power System State sensor (%s)",
            DATASET_ID_POWER_SYSTEM_STATE
        )

    # Add new sensors:
    if DATASET_ID_GRID_FREQUENCY in enabled_datasets:
        entities_to_add.append(
            FingridGridFrequencySensor(
                coordinator=coordinator,
                config_entry_id=entry.entry_id,
                dataset_id=DATASET_ID_GRID_FREQUENCY,
            )
        )
        _LOGGER.info(
            "Adding Fingrid Grid Frequency sensor (%s)",
            DATASET_ID_GRID_FREQUENCY
        )

    if DATASET_ID_ELECTRICITY_SHORTAGE_STATUS in enabled_datasets:
        entities_to_add.append(
            FingridElectricityShortageSensor(
                coordinator=coordinator,
                config_entry_id=entry.entry_id,
                dataset_id=DATASET_ID_ELECTRICITY_SHORTAGE_STATUS,
            )
        )
        _LOGGER.info(
            "Adding Fingrid Electricity Shortage Status sensor (%s)",
            DATASET_ID_ELECTRICITY_SHORTAGE_STATUS
        )

    if entities_to_add:
        async_add_entities(entities_to_add)
    else:
        _LOGGER.info("No Fingrid sensors currently enabled via options to set up.")