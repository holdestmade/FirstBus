from datetime import datetime
import logging

from homeassistant.components.sensor import (
  SensorDeviceClass,
  SensorEntity,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import now

from . import FirstBusConfigEntry
from .const import DOMAIN, MANUFACTURER
from .coordinator import FirstBusStopCoordinator
from .utils import (
  calculate_minutes_remaining,
  get_next_bus,
)

_LOGGER = logging.getLogger(__name__)

# Entities are updated by the coordinators
PARALLEL_UPDATES = 0


async def async_setup_entry(
  hass: HomeAssistant,
  entry: FirstBusConfigEntry,
  async_add_entities: AddConfigEntryEntitiesCallback,
):
  """Setup sensors for each configured stop"""
  for subentry_id, coordinator in entry.runtime_data.items():
    async_add_entities(
      [
        FirstBusNextBus(coordinator),
        FirstBusNextBusDue(coordinator),
      ],
      config_subentry_id=subentry_id,
    )


class FirstBusStopEntity(CoordinatorEntity[FirstBusStopCoordinator]):
  """Base entity for a stop. Each stop is represented as its own service in Home Assistant."""

  _attr_has_entity_name = True

  def __init__(self, coordinator: FirstBusStopCoordinator) -> None:
    super().__init__(coordinator)
    self._attr_device_info = DeviceInfo(
      identifiers={(DOMAIN, coordinator.stop)},
      name=coordinator.stop_name,
      manufacturer=MANUFACTURER,
      model="Bus stop",
      serial_number=coordinator.stop,
      entry_type=DeviceEntryType.SERVICE,
    )

  @property
  def next_bus(self) -> dict | None:
    return get_next_bus(self.coordinator.data, self.coordinator.target_buses, now())

  async def async_added_to_hass(self) -> None:
    await super().async_added_to_hass()

    # Data is only refreshed every few minutes, but the "next bus" moves on every minute
    self.async_on_remove(
      async_track_time_change(self.hass, self._async_minute_tick, second=0)
    )

  @callback
  def async_entity_id_changed(self, old_entity_id: str) -> None:
    """Run when the entity_id has been changed in the entity registry (HA 2026.11+).

    Nothing we set up is keyed on the entity_id (the minute timer and coordinator listener aren't),
    so the entity can be renamed in place rather than being removed and re-added.
    """
    parent = getattr(super(), "async_entity_id_changed", None)
    if parent is not None:
      parent(old_entity_id)

  @callback
  def _async_minute_tick(self, _: datetime) -> None:
    self.async_write_ha_state()


class FirstBusNextBus(FirstBusStopEntity, SensorEntity):
  """Sensor for the number of minutes until the next bus."""

  _attr_translation_key = "next_bus"
  _attr_icon = "mdi:bus"
  _attr_device_class = SensorDeviceClass.DURATION
  _attr_native_unit_of_measurement = UnitOfTime.MINUTES
  # The full list of buses changes constantly, so don't bloat the recorder with it
  _unrecorded_attributes = frozenset({"buses", "data_last_updated"})

  def __init__(self, coordinator: FirstBusStopCoordinator) -> None:
    super().__init__(coordinator)
    # Kept the same as previous versions so existing entities (and their history) are preserved
    self._attr_unique_id = f"first_bus_{coordinator.stop}_next_bus"

  @property
  def native_value(self):
    next_bus = self.next_bus
    return calculate_minutes_remaining(next_bus["due"], now()) if next_bus is not None else None

  @property
  def extra_state_attributes(self):
    attributes = dict(self.next_bus or {})
    attributes["stop"] = self.coordinator.stop
    attributes["buses"] = self.coordinator.data or []

    if self.coordinator.data_last_updated is not None:
      attributes["data_last_updated"] = self.coordinator.data_last_updated

    return attributes


class FirstBusNextBusDue(FirstBusStopEntity, SensorEntity):
  """Sensor for the timestamp of the next bus."""

  _attr_translation_key = "next_bus_due"
  _attr_icon = "mdi:bus-clock"
  _attr_device_class = SensorDeviceClass.TIMESTAMP

  def __init__(self, coordinator: FirstBusStopCoordinator) -> None:
    super().__init__(coordinator)
    self._attr_unique_id = f"first_bus_{coordinator.stop}_next_bus_due"

  @property
  def native_value(self):
    next_bus = self.next_bus
    return next_bus["due"] if next_bus is not None else None

  @property
  def extra_state_attributes(self):
    next_bus = self.next_bus
    if next_bus is None:
      return None

    return {
      "service_number": next_bus["service_number"],
      "destination": next_bus["destination"],
      "is_live": next_bus["is_live"],
    }
