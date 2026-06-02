"""Data Update Coordinator for Warema WMS."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WMSWebControlAPI, WMSConnectionError
from .const import DOMAIN, COVER_ANIMATION_TYPES

_LOGGER = logging.getLogger(__name__)


class WMSDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api, config, update_interval):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)
        self.api = api
        self.wms_config = config
        self._destinations = {d["id"]: d for d in config.get("destinations", [])}

    @property
    def destinations(self):
        return self._destinations

    @property
    def cover_destinations(self):
        return [
            d for d in self._destinations.values()
            if d.get("animationType") in COVER_ANIMATION_TYPES
        ]

    async def _async_update_data(self):
        data = {}
        for dest in self.cover_destinations:
            dest_id = dest["id"]
            try:
                status = await self.api.get_status(dest_id)
                data[dest_id] = status
            except WMSConnectionError as err:
                _LOGGER.warning("Status fehler für %s: %s", dest_id, err)
                data[dest_id] = {}
        return data

