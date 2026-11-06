from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.first_bus.const import CONFIG_BUSES, CONFIG_NAME, CONFIG_STOP, DOMAIN, SUBENTRY_TYPE_STOP

from .conftest import BUS_TIMES

STOP = "0170SGB20116"


async def _setup(hass: HomeAssistant, buses: list[str] | None = None) -> MockConfigEntry:
  entry = MockConfigEntry(
    domain=DOMAIN,
    version=2,
    data={},
    subentries_data=[
      {"data": {CONFIG_NAME: "Home", CONFIG_STOP: STOP, CONFIG_BUSES: buses or []}, "subentry_type": SUBENTRY_TYPE_STOP, "title": "Home", "unique_id": STOP},
    ],
  )
  entry.add_to_hass(hass)
  assert await hass.config_entries.async_setup(entry.entry_id)
  await hass.async_block_till_done()
  return entry


async def test_a_sensor_is_created_for_each_route(hass: HomeAssistant, mock_bus_times):
  await _setup(hass)

  route_19 = hass.states.get("sensor.home_route_19_next_bus")
  assert route_19 is not None
  assert route_19.state in ("4", "5")
  assert route_19.attributes["friendly_name"] == "Home Route 19 next bus"
  assert route_19.attributes["service_number"] == "19"
  assert route_19.attributes["destination"] == "Town"
  assert route_19.attributes["stop"] == STOP
  assert [bus["service_number"] for bus in route_19.attributes["buses"]] == ["19"]

  route_20 = hass.states.get("sensor.home_route_20_next_bus")
  assert route_20 is not None
  assert route_20.state in ("11", "12")
  assert route_20.attributes["destination"] == "Station"

  entity = er.async_get(hass).async_get("sensor.home_route_19_next_bus")
  assert entity.unique_id == f"first_bus_{STOP}_route_19"
  assert entity.translation_key == "route_next_bus"


async def test_only_filtered_routes_are_created(hass: HomeAssistant, mock_bus_times):
  await _setup(hass, ["20"])

  assert hass.states.get("sensor.home_route_19_next_bus") is None
  assert hass.states.get("sensor.home_route_20_next_bus") is not None


async def test_configured_route_without_buses_is_created_as_unknown(hass: HomeAssistant, mock_bus_times):
  await _setup(hass, ["20", "X5"])

  route = hass.states.get("sensor.home_route_x5_next_bus")
  assert route is not None
  assert route.state == "unknown"
  assert route.attributes["service_number"] == "X5"
  assert route.attributes["buses"] == []


async def test_new_routes_are_added_when_they_appear(hass: HomeAssistant, mock_bus_times, monkeypatch):
  entry = await _setup(hass)
  assert hass.states.get("sensor.home_route_7_next_bus") is None

  monkeypatch.setitem(BUS_TIMES, STOP, [
    *BUS_TIMES[STOP],
    {"due": "20 mins", "service_ref": "4", "service_number": "7", "destination": "Hospital", "is_live": True},
  ])
  coordinator = next(iter(entry.runtime_data.values()))
  await coordinator.async_refresh()
  await hass.async_block_till_done()

  route_7 = hass.states.get("sensor.home_route_7_next_bus")
  assert route_7 is not None
  assert route_7.attributes["destination"] == "Hospital"
  # Existing routes aren't duplicated
  assert len([state for state in hass.states.async_entity_ids("sensor") if "route_19" in state]) == 1


async def test_previously_seen_routes_survive_a_reload(hass: HomeAssistant, mock_bus_times, monkeypatch):
  entry = await _setup(hass)
  assert hass.states.get("sensor.home_route_20_next_bus") is not None

  # Route 20 has no more buses today
  monkeypatch.setitem(BUS_TIMES, STOP, [bus for bus in BUS_TIMES[STOP] if bus["service_number"] != "20"])
  assert await hass.config_entries.async_reload(entry.entry_id)
  await hass.async_block_till_done()

  route_20 = hass.states.get("sensor.home_route_20_next_bus")
  assert route_20 is not None
  assert route_20.state == "unknown"
  assert hass.states.get("sensor.home_route_19_next_bus").state in ("4", "5")
