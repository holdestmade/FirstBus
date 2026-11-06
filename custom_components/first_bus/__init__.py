import asyncio
import logging

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api_client import FirstBusApiClient
from .config import parse_buses
from .const import (
  CONFIG_BUSES,
  CONFIG_NAME,
  CONFIG_STOP,
  DEFAULT_TITLE,
  DOMAIN,
  SUBENTRY_TYPE_STOP,
)
from .coordinator import FirstBusStopCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type FirstBusConfigEntry = ConfigEntry[dict[str, FirstBusStopCoordinator]]


async def async_setup(hass: HomeAssistant, config) -> bool:
  """Set up the integration."""
  await async_migrate_integration(hass)
  return True


async def async_setup_entry(hass: HomeAssistant, entry: FirstBusConfigEntry) -> bool:
  """Set up the single First Bus entry, with a coordinator per configured stop."""
  client = FirstBusApiClient(async_get_clientsession(hass))

  coordinators: dict[str, FirstBusStopCoordinator] = {}
  for subentry in entry.subentries.values():
    if subentry.subentry_type != SUBENTRY_TYPE_STOP:
      continue

    coordinators[subentry.subentry_id] = FirstBusStopCoordinator(hass, entry, subentry, client)

  # Refresh all stops in parallel. A failing stop shouldn't stop the others from loading,
  # so we don't use async_config_entry_first_refresh here. Failing stops will retry on their next interval.
  await asyncio.gather(*(coordinator.async_refresh() for coordinator in coordinators.values()))

  entry.runtime_data = coordinators

  await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

  # Reload when stops are added, changed or removed
  entry.async_on_unload(entry.add_update_listener(async_update_listener))

  return True


async def async_update_listener(hass: HomeAssistant, entry: FirstBusConfigEntry) -> None:
  """Handle entry/subentry updates."""
  await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: FirstBusConfigEntry) -> bool:
  """Unload a config entry."""
  return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
  """Migrate old entry."""
  # Version 1 entries (one entry per stop) are merged together in async_migrate_integration,
  # which runs before any entry is set up. Anything newer than we know about can't be downgraded.
  return entry.version <= 2


async def async_migrate_integration(hass: HomeAssistant) -> None:
  """Merge the old 'one config entry per stop' layout into a single entry with a subentry per stop."""

  # Make sure we pick an enabled entry as the parent if there is one
  entries = sorted(
    hass.config_entries.async_entries(DOMAIN),
    key=lambda e: e.disabled_by is not None,
  )
  if not any(entry.version == 1 for entry in entries):
    return

  entity_registry = er.async_get(hass)
  device_registry = dr.async_get(hass)

  parent_entry = next((entry for entry in entries if entry.version >= 2), None)
  existing_stops = (
    {subentry.unique_id for subentry in parent_entry.subentries.values()}
    if parent_entry is not None
    else set()
  )

  for entry in entries:
    if entry.version != 1:
      continue

    config = {**entry.data, **entry.options}
    stop = config[CONFIG_STOP]
    name = config.get(CONFIG_NAME, stop)
    is_new_parent = parent_entry is None

    if is_new_parent:
      parent_entry = entry

    subentry = None
    if stop not in existing_stops:
      subentry = ConfigSubentry(
        data={
          CONFIG_NAME: name,
          CONFIG_STOP: stop,
          CONFIG_BUSES: parse_buses(config.get(CONFIG_BUSES)),
        },
        subentry_type=SUBENTRY_TYPE_STOP,
        title=name,
        unique_id=stop,
      )
      hass.config_entries.async_add_subentry(parent_entry, subentry)
      existing_stops.add(stop)

    # Move the existing entities over so that entity ids and history are kept
    for entity_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
      if subentry is None:
        continue

      disabled_by = entity_entry.disabled_by
      if disabled_by is er.RegistryEntryDisabler.CONFIG_ENTRY and parent_entry.disabled_by is None:
        # The registry clears CONFIG_ENTRY when moving to an enabled entry, but the user disabled this stop
        disabled_by = er.RegistryEntryDisabler.USER

      entity_registry.async_update_entity(
        entity_entry.entity_id,
        config_entry_id=parent_entry.entry_id,
        config_subentry_id=subentry.subentry_id,
        disabled_by=disabled_by,
      )

    if is_new_parent:
      hass.config_entries.async_update_entry(
        parent_entry,
        title=DEFAULT_TITLE,
        data={},
        options={},
        unique_id=DOMAIN,
        version=2,
      )
    else:
      # Old entries didn't create devices, but clean up any that may exist before removing the entry
      for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        device_registry.async_update_device(device.id, remove_config_entry_id=entry.entry_id)

      await hass.config_entries.async_remove(entry.entry_id)

  _LOGGER.info("Migrated First Bus stops into a single integration entry")
