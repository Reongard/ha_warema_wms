"""Warema WMS WebControl pro Integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import WMSWebControlAPI, WMSConnectionError
from .coordinator import WMSDataUpdateCoordinator
from .const import DOMAIN, CONF_HOST, CONF_PORT, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, 80)

    api = WMSWebControlAPI(host=host, port=port)

    try:
        await api.ping()
        config = await api.get_configuration()
    except WMSConnectionError as err:
        raise ConfigEntryNotReady(f"Cannot connect to WMS at {host}:{port} — {err}") from err

    coordinator = WMSDataUpdateCoordinator(
        hass=hass,
        api=api,
        config=config,
        update_interval=timedelta(seconds=SCAN_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "config": config,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

