import logging
from typing import Any

from homeassistant.config_entries import (
  ConfigEntry,
  ConfigFlow,
  ConfigFlowResult,
  ConfigSubentryFlow,
  SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api_client import FirstBusApiClient
from .config import async_validate_main_config
from .const import (
  CONFIG_BUSES,
  CONFIG_NAME,
  CONFIG_STOP,
  DATA_SCHEMA_RECONFIGURE_STOP,
  DATA_SCHEMA_STOP,
  DEFAULT_TITLE,
  DOMAIN,
  SUBENTRY_TYPE_STOP,
)

_LOGGER = logging.getLogger(__name__)

description_placeholders = {
  "faq_atco_code_url": "https://bottlecapdave.github.io/HomeAssistant-FirstBus/faq/#how-do-i-find-my-atco-code",
}


def _stop_subentry_data(config: dict) -> dict:
  return {
    CONFIG_NAME: config[CONFIG_NAME],
    CONFIG_STOP: config[CONFIG_STOP],
    CONFIG_BUSES: config[CONFIG_BUSES],
  }


class FirstBusConfigFlow(ConfigFlow, domain=DOMAIN):
  """Config flow. Creates the single First Bus entry along with the first stop."""

  VERSION = 2

  @classmethod
  @callback
  def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
    """Return subentries supported by this integration."""
    return {SUBENTRY_TYPE_STOP: StopSubentryFlowHandler}

  async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
    """Setup based on user config"""
    await self.async_set_unique_id(DOMAIN)
    self._abort_if_unique_id_configured()

    errors = {}
    if user_input is not None:
      client = FirstBusApiClient(async_get_clientsession(self.hass))
      (errors, config) = await async_validate_main_config(user_input, [], client)

      if len(errors) < 1:
        return self.async_create_entry(
          title=DEFAULT_TITLE,
          data={},
          subentries=[
            {
              "subentry_type": SUBENTRY_TYPE_STOP,
              "data": _stop_subentry_data(config),
              "title": config[CONFIG_NAME],
              "unique_id": config[CONFIG_STOP],
            }
          ],
        )

    return self.async_show_form(
      step_id="user",
      data_schema=self.add_suggested_values_to_schema(DATA_SCHEMA_STOP, user_input or {}),
      errors=errors,
      description_placeholders=description_placeholders,
    )


class StopSubentryFlowHandler(ConfigSubentryFlow):
  """Handles adding and reconfiguring individual bus stops."""

  async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
    """Add a new bus stop"""
    errors = {}
    if user_input is not None:
      entry = self._get_entry()
      existing_stops = [subentry.unique_id for subentry in entry.subentries.values()]
      client = FirstBusApiClient(async_get_clientsession(self.hass))
      (errors, config) = await async_validate_main_config(user_input, existing_stops, client)

      if len(errors) < 1:
        return self.async_create_entry(
          title=config[CONFIG_NAME],
          data=_stop_subentry_data(config),
          unique_id=config[CONFIG_STOP],
        )

    return self.async_show_form(
      step_id="user",
      data_schema=self.add_suggested_values_to_schema(DATA_SCHEMA_STOP, user_input or {}),
      errors=errors,
      description_placeholders=description_placeholders,
    )

  async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
    """Update the name/buses of an existing stop"""
    subentry = self._get_reconfigure_subentry()

    errors = {}
    if user_input is not None:
      (errors, config) = await async_validate_main_config(user_input)

      if len(errors) < 1:
        return self.async_update_and_abort(
          self._get_entry(),
          subentry,
          title=config[CONFIG_NAME],
          data=_stop_subentry_data({**subentry.data, **config}),
        )

    suggested_values = user_input if user_input is not None else {
      CONFIG_NAME: subentry.data.get(CONFIG_NAME, subentry.title),
      CONFIG_BUSES: ','.join(subentry.data.get(CONFIG_BUSES) or []),
    }

    return self.async_show_form(
      step_id="reconfigure",
      data_schema=self.add_suggested_values_to_schema(DATA_SCHEMA_RECONFIGURE_STOP, suggested_values),
      errors=errors,
      description_placeholders={**description_placeholders, "stop": subentry.data[CONFIG_STOP]},
    )
