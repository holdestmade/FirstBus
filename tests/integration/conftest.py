"""Global fixtures for custom integration."""
import pytest
import pytest_socket


@pytest.fixture(autouse=True)
def enable_external_sockets():
  """Integration tests talk to the live First Bus API.

  pytest-homeassistant-custom-component blocks all sockets (other than localhost) before each test,
  so re-enable them for the First Bus host.
  """
  pytest_socket.socket_allow_hosts(["www.firstbus.co.uk"], allow_unix_socket=True)
  pytest_socket.enable_socket()
  yield
