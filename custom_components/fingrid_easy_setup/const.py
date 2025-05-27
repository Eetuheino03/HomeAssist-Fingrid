"""Constants for the Fingrid Easy Setup integration."""
from datetime import timedelta

DOMAIN = "fingrid_easy_setup"

# Fingrid API Dataset IDs
DATASET_ID_POWER_SYSTEM_STATE = "209"
DATASET_ID_GRID_FREQUENCY = "177"
DATASET_ID_ELECTRICITY_SHORTAGE_STATUS = "336"
# DATASET_ID_ELECTRICITY_PRICE_FI = "TBD" # To be determined if reliably available

# Default names for sensors (can be overridden by entity descriptions later if needed)
SENSOR_NAME_POWER_SYSTEM_STATE = "Power System State"
SENSOR_NAME_GRID_FREQUENCY = "Grid Frequency"
SENSOR_NAME_ELECTRICITY_SHORTAGE_STATUS = "Electricity Shortage Status"
# SENSOR_NAME_ELECTRICITY_PRICE_FI = "Electricity Price Finland"

# Options Flow
CONF_ENABLED_SENSORS = "enabled_sensors"
CONF_UPDATE_INTERVAL = "update_interval"

DEFAULT_UPDATE_INTERVAL_MINUTES = 5

# API Key configuration
CONF_API_KEY = "api_key"
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=DEFAULT_UPDATE_INTERVAL_MINUTES)

# Min/Max for polling interval in options flow (in minutes)
MIN_UPDATE_INTERVAL_MINUTES = 1
MAX_UPDATE_INTERVAL_MINUTES = 60

# Map dataset IDs to their default names for use in Options Flow
AVAILABLE_SENSORS_DATA = {
    DATASET_ID_POWER_SYSTEM_STATE: SENSOR_NAME_POWER_SYSTEM_STATE,
    DATASET_ID_GRID_FREQUENCY: SENSOR_NAME_GRID_FREQUENCY,
    DATASET_ID_ELECTRICITY_SHORTAGE_STATUS: SENSOR_NAME_ELECTRICITY_SHORTAGE_STATUS,
    # If price sensor is added:
    # "TBD_PRICE_ID": SENSOR_NAME_ELECTRICITY_PRICE_FI,
}