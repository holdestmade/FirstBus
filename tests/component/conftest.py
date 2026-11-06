"""Fixtures for tests that run the integration inside Home Assistant."""
from unittest.mock import patch

import pytest

from custom_components.first_bus.api_client import FirstBusApiClient


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
  yield


BUS_TIMES = {
  "0170SGB20116": [
    {"due": "5 mins", "service_ref": "1", "service_number": "19", "destination": "Town", "is_live": True},
    {"due": "12 mins", "service_ref": "2", "service_number": "20", "destination": "Station", "is_live": False},
  ],
  "3800C509801": [
    {"due": "Due now", "service_ref": "3", "service_number": "X1", "destination": "Airport", "is_live": True},
  ],
  "2200YEA00934": [],
}


@pytest.fixture
def mock_bus_times():
  async def async_get_bus_times(self, stop):
    times = BUS_TIMES.get(stop)
    return [dict(time) for time in times] if times is not None else None

  with patch.object(FirstBusApiClient, "async_get_bus_times", async_get_bus_times):
    yield
