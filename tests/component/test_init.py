from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.first_bus.const import CONFIG_BUSES, CONFIG_NAME, CONFIG_STOP, DOMAIN, SUBENTRY_TYPE_STOP


def _stop_subentry(name, stop, buses=None):
  return ConfigSubentry(
    data={CONFIG_NAME: name, CONFIG_STOP: stop, CONFIG_BUSES: buses or []},
    subentry_type=SUBENTRY_TYPE_STOP,
    title=name,
    unique_id=stop,
  )


async def test_each_stop_is_a_service_with_sensors(hass: HomeAssistant, mock_bus_times):
  entry = MockConfigEntry(
    domain=DOMAIN,
    version=2,
    title="First Bus",
    unique_id=DOMAIN,
    data={},
    subentries_data=[
      {"data": {CONFIG_NAME: "Home", CONFIG_STOP: "0170SGB20116", CONFIG_BUSES: ["20"]}, "subentry_type": SUBENTRY_TYPE_STOP, "title": "Home", "unique_id": "0170SGB20116"},
      {"data": {CONFIG_NAME: "Work", CONFIG_STOP: "3800C509801", CONFIG_BUSES: []}, "subentry_type": SUBENTRY_TYPE_STOP, "title": "Work", "unique_id": "3800C509801"},
    ],
  )
  entry.add_to_hass(hass)

  assert await hass.config_entries.async_setup(entry.entry_id)
  await hass.async_block_till_done()
  assert entry.state is ConfigEntryState.LOADED

  home = hass.states.get("sensor.home_next_bus")
  assert home is not None
  assert home.state in ("11", "12")
  assert home.attributes["service_number"] == "20"
  assert home.attributes["stop"] == "0170SGB20116"
  assert len(home.attributes["buses"]) == 1

  assert hass.states.get("sensor.work_next_bus").state == "0"
  assert hass.states.get("sensor.work_next_bus_due") is not None

  device_registry = dr.async_get(hass)
  devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
  assert len(devices) == 2
  assert all(device.entry_type is dr.DeviceEntryType.SERVICE for device in devices)

  entity_registry = er.async_get(hass)
  home_entity = entity_registry.async_get("sensor.home_next_bus")
  assert home_entity.unique_id == "first_bus_0170SGB20116_next_bus"
  assert home_entity.config_subentry_id is not None

  assert await hass.config_entries.async_unload(entry.entry_id)
  assert entry.state is ConfigEntryState.NOT_LOADED


async def test_one_failing_stop_does_not_block_the_others(hass: HomeAssistant, mock_bus_times):
  entry = MockConfigEntry(
    domain=DOMAIN,
    version=2,
    data={},
    subentries_data=[
      {"data": {CONFIG_NAME: "Home", CONFIG_STOP: "0170SGB20116", CONFIG_BUSES: []}, "subentry_type": SUBENTRY_TYPE_STOP, "title": "Home", "unique_id": "0170SGB20116"},
      {"data": {CONFIG_NAME: "Gone", CONFIG_STOP: "UNKNOWN", CONFIG_BUSES: []}, "subentry_type": SUBENTRY_TYPE_STOP, "title": "Gone", "unique_id": "UNKNOWN"},
    ],
  )
  entry.add_to_hass(hass)

  assert await hass.config_entries.async_setup(entry.entry_id)
  await hass.async_block_till_done()

  assert hass.states.get("sensor.home_next_bus").state in ("4", "5")
  assert hass.states.get("sensor.gone_next_bus").state == "unavailable"


async def test_v1_entries_are_merged_into_a_single_entry(hass: HomeAssistant, mock_bus_times):
  home = MockConfigEntry(
    domain=DOMAIN,
    version=1,
    title="Bus Stop Home",
    data={CONFIG_NAME: "Home", CONFIG_STOP: "0170SGB20116", CONFIG_BUSES: ["19"]},
    options={CONFIG_NAME: "Home", CONFIG_STOP: "0170SGB20116", CONFIG_BUSES: ["20"]},
  )
  work = MockConfigEntry(
    domain=DOMAIN,
    version=1,
    title="Bus Stop Work",
    data={CONFIG_NAME: "Work", CONFIG_STOP: "3800C509801", CONFIG_BUSES: []},
  )
  home.add_to_hass(hass)
  work.add_to_hass(hass)

  entity_registry = er.async_get(hass)
  entity_registry.async_get_or_create(
    "sensor", DOMAIN, "first_bus_0170SGB20116_next_bus",
    config_entry=home, suggested_object_id="first_bus_home_next_bus",
  )
  entity_registry.async_get_or_create(
    "sensor", DOMAIN, "first_bus_3800C509801_next_bus",
    config_entry=work, suggested_object_id="first_bus_work_next_bus",
  )

  assert await hass.config_entries.async_setup(home.entry_id)
  await hass.async_block_till_done()

  entries = hass.config_entries.async_entries(DOMAIN)
  assert len(entries) == 1
  entry = entries[0]
  assert entry.version == 2
  assert entry.title == "First Bus"
  assert entry.data == {}
  assert entry.state is ConfigEntryState.LOADED

  subentries = {subentry.unique_id: subentry for subentry in entry.subentries.values()}
  assert set(subentries) == {"0170SGB20116", "3800C509801"}
  # Options took priority over data
  assert subentries["0170SGB20116"].data[CONFIG_BUSES] == ["20"]

  # Existing entity ids (and therefore history/automations) are kept
  home_entity = entity_registry.async_get("sensor.first_bus_home_next_bus")
  assert home_entity.config_entry_id == entry.entry_id
  assert home_entity.config_subentry_id == subentries["0170SGB20116"].subentry_id
  work_entity = entity_registry.async_get("sensor.first_bus_work_next_bus")
  assert work_entity.config_entry_id == entry.entry_id
  assert work_entity.config_subentry_id == subentries["3800C509801"].subentry_id

  assert hass.states.get("sensor.first_bus_home_next_bus").attributes["service_number"] == "20"
  assert hass.states.get("sensor.first_bus_work_next_bus").state == "0"
