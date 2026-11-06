import logging
import re
from datetime import (datetime, timedelta)

from .const import (
  REGEX_TIME,
  REGEX_TIME_MINS,
)

_LOGGER = logging.getLogger(__name__)

LATE_BUS_TOLERANCE = timedelta(hours=1)


def normalise_bus(bus: str) -> str:
  return bus.strip().upper()


def _is_target_bus(service_number: str, target_buses: list[str] | None) -> bool:
  if target_buses is None or len(target_buses) == 0:
    return True

  return normalise_bus(service_number) in {normalise_bus(bus) for bus in target_buses}


def _parse_due(raw_due: str, current_timestamp: datetime) -> datetime | None:
  current_minute = current_timestamp.replace(second=0, microsecond=0)

  matches = re.search(REGEX_TIME, raw_due)
  if matches is not None:
    due = current_minute.replace(hour=int(matches[1]), minute=int(matches[2]))
    # The API only returns a time. The API lists upcoming buses, so assume the bus is due within
    # the next day, but allow for buses running a little late (e.g. a 23:55 bus still listed at 00:05)
    if due < current_minute - LATE_BUS_TOLERANCE:
      due = due + timedelta(days=1)
    elif due >= current_minute + timedelta(days=1) - LATE_BUS_TOLERANCE:
      due = due - timedelta(days=1)

    return due

  matches = re.search(REGEX_TIME_MINS, raw_due)
  if matches is not None:
    return current_minute + timedelta(minutes=int(matches[1]))

  if raw_due.strip().lower() == "due now":
    return current_minute

  return None


def get_buses(bus_times: list | None, current_timestamp: datetime, target_buses: list[str] | None):
  """Convert the raw bus times into buses with absolute due timestamps, filtered to the target buses"""
  _LOGGER.debug(f'buses: {bus_times}')

  if bus_times is None:
    return None

  buses_to_return = []
  for bus_time in bus_times:
    if _is_target_bus(bus_time["service_number"], target_buses) == False:
      continue

    due = _parse_due(bus_time["due"], current_timestamp)
    if due is None:
      _LOGGER.warning(f'Unable to extract due time, skipping bus: {bus_time}')
      continue

    buses_to_return.append({**bus_time, "due": due})

  buses_to_return.sort(key=lambda bus: bus["due"])
  return buses_to_return


def get_next_bus(bus_times: list | None, target_buses: list[str] | None, current_timestamp: datetime):
  next_bus = None
  if bus_times is not None:
    current_minute = current_timestamp.replace(second=0, microsecond=0)
    for bus_time in bus_times:
      if _is_target_bus(bus_time["service_number"], target_buses):
        if bus_time["due"] >= current_minute and (next_bus is None or next_bus["due"] > bus_time["due"]):
          next_bus = bus_time

  return next_bus


def calculate_minutes_remaining(target_timestamp: datetime | None, current_timestamp: datetime | None):
  if target_timestamp is None or current_timestamp is None:
    return None

  seconds = (target_timestamp - current_timestamp).total_seconds()
  minutes = int(abs(seconds) // 60)
  return minutes if seconds >= 0 else minutes * -1
