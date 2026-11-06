from datetime import timedelta

import voluptuous as vol

DOMAIN = "first_bus"

DEFAULT_TITLE = "First Bus"
MANUFACTURER = "First Bus"

# How often the (unofficial) API is polled per stop. Kept deliberately low so we don't hammer the service.
UPDATE_INTERVAL = timedelta(minutes=5)
REQUEST_TIMEOUT_SECONDS = 15

SUBENTRY_TYPE_STOP = "stop"

CONFIG_NAME = "Name"
CONFIG_STOP = "Stop"
CONFIG_BUSES = "Buses"

REGEX_BUSES = "^[a-zA-Z0-9 ]+(,[a-zA-Z0-9 ]+)*$"
REGEX_TIME = "^([0-9]{2}):([0-9]{2})$"
REGEX_TIME_MINS = "([0-9]+) mins?"

DATA_SCHEMA_STOP = vol.Schema({
  vol.Required(CONFIG_NAME): str,
  vol.Required(CONFIG_STOP): str,
  vol.Optional(CONFIG_BUSES): str,
})

DATA_SCHEMA_RECONFIGURE_STOP = vol.Schema({
  vol.Required(CONFIG_NAME): str,
  vol.Optional(CONFIG_BUSES): str,
})
