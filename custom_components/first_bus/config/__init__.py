import logging
import re

from ..api_client import FirstBusApiClient, FirstBusApiError
from ..const import CONFIG_BUSES, CONFIG_STOP, REGEX_BUSES

_LOGGER = logging.getLogger(__name__)


def parse_buses(buses) -> list[str]:
  """Convert the configured buses (string or list) into a clean list"""
  if buses is None:
    return []

  if isinstance(buses, str):
    buses = buses.split(",")

  return [bus.strip() for bus in buses if bus is not None and bus.strip() != ""]


async def async_validate_main_config(
  config: dict,
  existing_atco_codes: list[str] | None = None,
  client: FirstBusApiClient | None = None,
):
  new_config = dict(config)
  errors = {}
  client = client if client is not None else FirstBusApiClient()

  if CONFIG_STOP in new_config:
    new_config[CONFIG_STOP] = new_config[CONFIG_STOP].strip()
    if existing_atco_codes is not None and new_config[CONFIG_STOP] in existing_atco_codes:
      errors[CONFIG_STOP] = "duplicate_stop"
    else:
      try:
        buses = await client.async_get_bus_times(new_config[CONFIG_STOP])
        if buses is None:
          errors[CONFIG_STOP] = "invalid_stop"
      except FirstBusApiError as ex:
        _LOGGER.warning(ex)
        errors["base"] = "cannot_connect"

  if CONFIG_BUSES in new_config and isinstance(new_config[CONFIG_BUSES], list):
    new_config[CONFIG_BUSES] = parse_buses(new_config[CONFIG_BUSES])
  elif CONFIG_BUSES in new_config and new_config[CONFIG_BUSES] is not None and len(new_config[CONFIG_BUSES]) > 0:
    matches = re.search(REGEX_BUSES, new_config[CONFIG_BUSES])
    if (matches is None):
      errors[CONFIG_BUSES] = "invalid_buses"
    else:
      new_config[CONFIG_BUSES] = parse_buses(new_config[CONFIG_BUSES])
  else:
    new_config[CONFIG_BUSES] = []

  return (errors, new_config)
