from datetime import datetime
import logging

from homeassistant.components.sensor import (
  SensorDeviceClass,
  SensorEntity,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
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
  normalise_bus,
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
  entity_registry = er.async_get(hass)

  for subentry_id, coordinator in entry.runtime_data.items():
    async_add_entities(
      [
        FirstBusNextBus(coordinator),
        FirstBusNextBusDue(coordinator),
      ],
      config_subentry_id=subentry_id,
    )

    _async_setup_route_sensors(entry, entity_registry, subentry_id, coordinator, async_add_entities)


def route_unique_id(stop: str, service: str) -> str:
  return f"first_bus_{stop}_route_{normalise_bus(service)}"


@callback
def _async_setup_route_sensors(
  entry: FirstBusConfigEntry,
  entity_registry: er.EntityRegistry,
  subentry_id: str,
  coordinator: FirstBusStopCoordinator,
  async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
  """Add a sensor per bus service (route) at the stop.

  The services at a stop aren't known up front, so sensors are created for any configured buses,
  any services previously seen (so they survive restarts when no bus is currently due) and any new
  services that appear in later updates.
  """
  known_services: set[str] = set()
  unique_id_prefix = route_unique_id(coordinator.stop, "")

  def _async_add_services(services) -> None:
    new_entities = []
    for service in services:
      if service is None or normalise_bus(service) == "" or normalise_bus(service) in known_services:
        continue

      known_services.add(normalise_bus(service))
      new_entities.append(FirstBusRouteNextBus(coordinator, service.strip()))

    if len(new_entities) > 0:
      async_add_entities(new_entities, config_subentry_id=subentry_id)

  previously_seen = [
    entity.unique_id[len(unique_id_prefix):]
    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    if entity.config_subentry_id == subentry_id and entity.unique_id.startswith(unique_id_prefix)
  ]

  @callback
  def _async_coordinator_updated() -> None:
    _async_add_services(bus["service_number"] for bus in coordinator.data or [])

  _async_add_services([*coordinator.target_buses, *previously_seen])
  _async_coordinator_updated()
  entry.async_on_unload(coordinator.async_add_listener(_async_coordinator_updated))


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


class FirstBusRouteNextBus(FirstBusStopEntity, SensorEntity):
  """Sensor for the number of minutes until the next bus on a specific service (route)."""

  _attr_translation_key = "route_next_bus"
  _attr_icon = "mdi:bus-marker"
  _attr_device_class = SensorDeviceClass.DURATION
  _attr_native_unit_of_measurement = UnitOfTime.MINUTES
  _unrecorded_attributes = frozenset({"buses"})

  def __init__(self, coordinator: FirstBusStopCoordinator, service: str) -> None:
    super().__init__(coordinator)
    self.service = service
    self._attr_unique_id = route_unique_id(coordinator.stop, service)
    self._attr_translation_placeholders = {"service": service}

  @property
  def next_bus(self) -> dict | None:
    return get_next_bus(self.coordinator.data, [self.service], now())

  @property
  def native_value(self):
    next_bus = self.next_bus
    return calculate_minutes_remaining(next_bus["due"], now()) if next_bus is not None else None

  @property
  def extra_state_attributes(self):
    current_minute = now().replace(second=0, microsecond=0)
    attributes = dict(self.next_bus or {})
    attributes["service_number"] = attributes.get("service_number", self.service)
    attributes["stop"] = self.coordinator.stop
    attributes["buses"] = [
      bus
      for bus in self.coordinator.data or []
      if normalise_bus(bus["service_number"]) == normalise_bus(self.service) and bus["due"] >= current_minute
    ]
    return attributes
