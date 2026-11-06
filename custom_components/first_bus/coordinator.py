import logging

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import now

from .api_client import FirstBusApiClient, FirstBusApiError
from .const import CONFIG_BUSES, CONFIG_NAME, CONFIG_STOP, DOMAIN, UPDATE_INTERVAL
from .utils import get_buses

_LOGGER = logging.getLogger(__name__)


class FirstBusStopCoordinator(DataUpdateCoordinator[list[dict]]):
  """Retrieves the bus times for a single stop"""

  def __init__(
    self,
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    subentry: ConfigSubentry,
    client: FirstBusApiClient,
  ) -> None:
    super().__init__(
      hass,
      _LOGGER,
      config_entry=config_entry,
      name=f"{DOMAIN}_{subentry.data[CONFIG_STOP]}",
      update_interval=UPDATE_INTERVAL,
    )
    self.subentry = subentry
    self.stop: str = subentry.data[CONFIG_STOP]
    self.stop_name: str = subentry.data.get(CONFIG_NAME, subentry.title)
    self.target_buses: list[str] = list(subentry.data.get(CONFIG_BUSES) or [])
    self.data_last_updated = None
    self._client = client

  async def _async_update_data(self) -> list[dict]:
    try:
      bus_times = await self._client.async_get_bus_times(self.stop)
    except FirstBusApiError as ex:
      raise UpdateFailed(str(ex)) from ex

    if bus_times is None:
      raise UpdateFailed(f"Stop {self.stop} was not recognised by First Bus")

    self.data_last_updated = now()
    return get_buses(bus_times, self.data_last_updated, self.target_buses)
