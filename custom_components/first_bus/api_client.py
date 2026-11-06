import asyncio
import logging

import aiohttp

from .const import REQUEST_TIMEOUT_SECONDS

_LOGGER = logging.getLogger(__name__)


class FirstBusApiError(Exception):
  """Raised when the First Bus API could not be reached or returned something unexpected."""


class FirstBusApiClient:

  def __init__(self, session: aiohttp.ClientSession | None = None):
    self._base_url = 'https://www.firstbus.co.uk'
    self._session = session

  async def async_get_bus_times(self, stop: str):
    """Get the bus times for a given stop.

    Returns a list of bus times, or None if the stop is not recognised.
    Raises FirstBusApiError if the service could not be reached.
    """
    if self._session is not None:
      return await self._async_get_bus_times(self._session, stop)

    async with aiohttp.ClientSession() as session:
      return await self._async_get_bus_times(session, stop)

  async def _async_get_bus_times(self, session: aiohttp.ClientSession, stop: str):
    url = f'{self._base_url}/getNextBus'
    try:
      async with session.get(
        url,
        params={"stop": stop},
        timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS),
      ) as response:
        response.raise_for_status()
        # Disable content type check as sometimes it can report text/html
        data = await response.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as ex:
      raise FirstBusApiError(f"Failed to retrieve bus times for stop {stop}: {ex}") from ex

    if isinstance(data, dict) and "times" in data and "atcocode" in data:
      return [
        {
          "due": time["Due"],
          "service_ref": time["ServiceRef"],
          "service_number": time["ServiceNumber"],
          "destination": time["Destination"],
          "is_live": str(time["IsLive"]).lower() == 'y',
        }
        for time in (data["times"] or [])
      ]

    _LOGGER.debug("Unexpected response for stop %s: %s", stop, data)
    return None
