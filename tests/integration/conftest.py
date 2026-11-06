"""Global fixtures for custom integration."""
import pytest
import pytest_socket


@pytest.fixture(autouse=True)
def enable_external_sockets():
  """Integration tests talk to the live First Bus API.

  pytest-homeassistant-custom-component blocks all sockets (other than localhost) before each test,
  so re-enable them for the First Bus host.

  The order matters: socket_allow_hosts patches connect() on the current socket.socket class,
  so sockets must be enabled first, otherwise the patch lands on pytest-socket's blocking wrapper.
  """
  pytest_socket.enable_socket()
  pytest_socket.socket_allow_hosts(["www.firstbus.co.uk"], allow_unix_socket=True)
  yield
