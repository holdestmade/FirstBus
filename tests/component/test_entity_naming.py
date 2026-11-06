import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity as entity_helper
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.first_bus.const import CONFIG_BUSES, CONFIG_NAME, CONFIG_STOP, DOMAIN, SUBENTRY_TYPE_STOP
from custom_components.first_bus.sensor import FirstBusNextBus, FirstBusNextBusDue


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
  entry = MockConfigEntry(
    domain=DOMAIN,
    version=2,
    data={},
    subentries_data=[
      {"data": {CONFIG_NAME: "Home", CONFIG_STOP: "0170SGB20116", CONFIG_BUSES: []}, "subentry_type": SUBENTRY_TYPE_STOP, "title": "Home", "unique_id": "0170SGB20116"},
    ],
  )
  entry.add_to_hass(hass)
  assert await hass.config_entries.async_setup(entry.entry_id)
  await hass.async_block_till_done()
  return entry


async def test_entities_are_named_from_device_and_translation(hass: HomeAssistant, mock_bus_times):
  entry = await _setup(hass)
  entity_registry = er.async_get(hass)

  next_bus = entity_registry.async_get("sensor.home_next_bus")
  assert next_bus.has_entity_name is True
  assert next_bus.translation_key == "next_bus"
  assert next_bus.original_name == "Next bus"
  assert hass.states.get("sensor.home_next_bus").attributes["friendly_name"] == "Home Next bus"

  next_bus_due = entity_registry.async_get("sensor.home_next_bus_due")
  assert next_bus_due.translation_key == "next_bus_due"
  assert hass.states.get("sensor.home_next_bus_due").attributes["friendly_name"] == "Home Next bus due"

  device = dr.async_get(hass).async_get(next_bus.device_id)
  assert device.name == "Home"
  assert device.entry_type is dr.DeviceEntryType.SERVICE

  if hasattr(next_bus, "object_id_base"):
    # HA 2026.x+: the entity id is derived by the registry from the device and entity names
    assert next_bus.object_id_base == "Next bus"
    assert next_bus.suggested_object_id is None

    area = ar.async_get(hass).async_create("Hallway")
    dr.async_get(hass).async_update_device(device.id, area_id=area.id)
    assert entity_registry.async_regenerate_entity_id(next_bus) == "sensor.hallway_home_next_bus"


async def test_entity_id_can_be_renamed(hass: HomeAssistant, mock_bus_times):
  await _setup(hass)
  entity_registry = er.async_get(hass)

  entity_registry.async_update_entity("sensor.home_next_bus", new_entity_id="sensor.my_bus")
  await hass.async_block_till_done()

  assert hass.states.get("sensor.home_next_bus") is None
  assert hass.states.get("sensor.my_bus") is not None
  assert hass.states.get("sensor.my_bus").attributes["stop"] == "0170SGB20116"


@pytest.mark.parametrize("entity_class", [FirstBusNextBus, FirstBusNextBusDue])
def test_entities_are_renamed_in_place(entity_class):
  requires_readd = getattr(entity_helper, "_entity_class_requires_readd", None)
  if requires_readd is None:
    pytest.skip("In place entity id changes were added in HA 2026.11")

  assert requires_readd(entity_class) is False
