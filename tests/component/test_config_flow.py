from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.first_bus.const import CONFIG_BUSES, CONFIG_NAME, CONFIG_STOP, DOMAIN, SUBENTRY_TYPE_STOP


async def test_user_flow_creates_single_entry_with_first_stop(hass: HomeAssistant, mock_bus_times):
  result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
  assert result["type"] is FlowResultType.FORM

  result = await hass.config_entries.flow.async_configure(
    result["flow_id"], {CONFIG_NAME: "Home", CONFIG_STOP: "0170SGB20116", CONFIG_BUSES: "19, 20"}
  )
  assert result["type"] is FlowResultType.CREATE_ENTRY
  assert result["title"] == "First Bus"

  entry = result["result"]
  subentries = list(entry.subentries.values())
  assert len(subentries) == 1
  assert subentries[0].title == "Home"
  assert subentries[0].unique_id == "0170SGB20116"
  assert subentries[0].data == {CONFIG_NAME: "Home", CONFIG_STOP: "0170SGB20116", CONFIG_BUSES: ["19", "20"]}
  await hass.async_block_till_done()

  # Only a single entry is allowed
  result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
  assert result["type"] is FlowResultType.ABORT


async def test_user_flow_invalid_stop(hass: HomeAssistant, mock_bus_times):
  result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
  result = await hass.config_entries.flow.async_configure(
    result["flow_id"], {CONFIG_NAME: "Home", CONFIG_STOP: "UNKNOWN"}
  )
  assert result["type"] is FlowResultType.FORM
  assert result["errors"] == {CONFIG_STOP: "invalid_stop"}


def _setup_entry(hass):
  entry = MockConfigEntry(
    domain=DOMAIN,
    version=2,
    unique_id=DOMAIN,
    data={},
    subentries_data=[
      {"data": {CONFIG_NAME: "Home", CONFIG_STOP: "0170SGB20116", CONFIG_BUSES: []}, "subentry_type": SUBENTRY_TYPE_STOP, "title": "Home", "unique_id": "0170SGB20116"},
    ],
  )
  entry.add_to_hass(hass)
  return entry


async def test_add_stop_subentry(hass: HomeAssistant, mock_bus_times):
  entry = _setup_entry(hass)
  assert await hass.config_entries.async_setup(entry.entry_id)
  await hass.async_block_till_done()

  result = await hass.config_entries.subentries.async_init(
    (entry.entry_id, SUBENTRY_TYPE_STOP), context={"source": config_entries.SOURCE_USER}
  )
  assert result["type"] is FlowResultType.FORM

  # Duplicate stop
  result = await hass.config_entries.subentries.async_configure(
    result["flow_id"], {CONFIG_NAME: "Home again", CONFIG_STOP: "0170SGB20116"}
  )
  assert result["type"] is FlowResultType.FORM
  assert result["errors"] == {CONFIG_STOP: "duplicate_stop"}

  result = await hass.config_entries.subentries.async_configure(
    result["flow_id"], {CONFIG_NAME: "Work", CONFIG_STOP: "3800C509801", CONFIG_BUSES: "X1"}
  )
  assert result["type"] is FlowResultType.CREATE_ENTRY
  await hass.async_block_till_done()

  assert len(entry.subentries) == 2
  # Entry is reloaded, so the new stop's sensors appear straight away
  assert hass.states.get("sensor.work_next_bus").state == "0"


async def test_reconfigure_stop_subentry(hass: HomeAssistant, mock_bus_times):
  entry = _setup_entry(hass)
  assert await hass.config_entries.async_setup(entry.entry_id)
  await hass.async_block_till_done()
  assert hass.states.get("sensor.home_next_bus").attributes["service_number"] == "19"

  subentry = next(iter(entry.subentries.values()))
  result = await entry.start_subentry_reconfigure_flow(hass, subentry.subentry_id)
  assert result["type"] is FlowResultType.FORM
  assert result["step_id"] == "reconfigure"

  result = await hass.config_entries.subentries.async_configure(
    result["flow_id"], {CONFIG_NAME: "Home", CONFIG_BUSES: "A-B"}
  )
  assert result["errors"] == {CONFIG_BUSES: "invalid_buses"}

  result = await hass.config_entries.subentries.async_configure(
    result["flow_id"], {CONFIG_NAME: "Home stop", CONFIG_BUSES: "20"}
  )
  assert result["type"] is FlowResultType.ABORT
  assert result["reason"] == "reconfigure_successful"
  await hass.async_block_till_done()

  subentry = entry.subentries[subentry.subentry_id]
  assert subentry.title == "Home stop"
  assert subentry.data == {CONFIG_NAME: "Home stop", CONFIG_STOP: "0170SGB20116", CONFIG_BUSES: ["20"]}
  assert hass.states.get("sensor.home_next_bus").attributes["service_number"] == "20"
