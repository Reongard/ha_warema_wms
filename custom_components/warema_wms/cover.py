"""Cover platform for Warema WMS WebControl pro."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ANIMATION_TYPE_AWNING,
    ANIMATION_TYPE_ROLLER_SHUTTER,
    ANIMATION_TYPE_SLAT_ROOF,
    ANIMATION_TYPE_VENETIAN_BLIND,
    ANIMATION_TYPE_WINDOW,
    TILT_ANIMATION_TYPES,
    ACTION_TYPE_PERCENTAGE,
    ACTION_TYPE_ROTATION,
    ACTION_TYPE_STOP,
)
from .coordinator import WMSDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

DEVICE_CLASS_MAP = {
    ANIMATION_TYPE_VENETIAN_BLIND: CoverDeviceClass.BLIND,
    ANIMATION_TYPE_AWNING: CoverDeviceClass.AWNING,
    ANIMATION_TYPE_ROLLER_SHUTTER: CoverDeviceClass.SHUTTER,
    ANIMATION_TYPE_SLAT_ROOF: CoverDeviceClass.BLIND,
    ANIMATION_TYPE_WINDOW: CoverDeviceClass.WINDOW,
}


def _find_action(actions, action_type):
    for a in actions:
        if a.get("actionType") == action_type:
            return a
    return None


def _wms_to_ha_position(pct):
    if pct is None or pct > 100:
        return None
    return round(pct)


def _wms_to_ha_tilt(rotation, min_val, max_val):
    span = max_val - min_val
    if span == 0:
        return 0
    return round(max(0, min(100, (rotation - min_val) / span * 100)))


def _ha_to_wms_rotation(tilt, min_val, max_val):
    return round(min_val + (tilt / 100) * (max_val - min_val), 1)


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    entities = [
        WMSCoverEntity(coordinator, entry, dest)
        for dest in coordinator.cover_destinations
    ]
    async_add_entities(entities)


class WMSCoverEntity(CoordinatorEntity, CoverEntity):
    def __init__(self, coordinator, entry, destination):
        super().__init__(coordinator)
        self._destination = destination
        self._dest_id = destination["id"]
        self._animation_type = destination.get("animationType", 999)
        self._actions = destination.get("actions", [])

        self._position_action = _find_action(self._actions, ACTION_TYPE_PERCENTAGE)
        self._rotation_action = _find_action(self._actions, ACTION_TYPE_ROTATION)
        self._stop_action = _find_action(self._actions, ACTION_TYPE_STOP)

        if self._rotation_action:
            self._tilt_min = float(self._rotation_action.get("minValue", -127))
            self._tilt_max = float(self._rotation_action.get("maxValue", 127))
        else:
            self._tilt_min = -127.0
            self._tilt_max = 127.0

        self._attr_unique_id = f"{entry.entry_id}_{self._dest_id}"
        names = destination.get("names", [""])
        self._attr_name = next((n for n in names if n), f"WMS {self._dest_id}")
        self._attr_device_class = DEVICE_CLASS_MAP.get(self._animation_type)

        features = CoverEntityFeature(0)
        if self._position_action:
            features |= CoverEntityFeature.OPEN
            features |= CoverEntityFeature.CLOSE
            features |= CoverEntityFeature.SET_COVER_POSITION
        if self._stop_action:
            features |= CoverEntityFeature.STOP
        if self._rotation_action and self._animation_type in TILT_ANIMATION_TYPES:
            features |= CoverEntityFeature.OPEN_TILT
            features |= CoverEntityFeature.CLOSE_TILT
            features |= CoverEntityFeature.SET_COVER_TILT_POSITION
            features |= CoverEntityFeature.STOP_TILT
        self._attr_supported_features = features

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(entry.entry_id))},
            name=f"WMS WebControl pro ({entry.data['host']})",
            manufacturer="WAREMA",
            model="WMS WebControl pro",
        )

    def _status(self):
        if self.coordinator.data:
            return self.coordinator.data.get(self._dest_id, {})
        return {}

    def _product_value(self, action_id, key):
        for item in self._status().get("productData", []):
            if item.get("actionId") == action_id:
                return item.get("value", {}).get(key)
        return None

    @property
    def is_closed(self):
        pos = self.current_cover_position
        if pos is None:
            return None
        return pos == 0

    @property
    def is_opening(self):
        return False

    @property
    def is_closing(self):
        return False

    @property
    def current_cover_position(self):
        if not self._position_action:
            return None
        return _wms_to_ha_position(
            self._product_value(self._position_action["id"], "percentage")
        )

    @property
    def current_cover_tilt_position(self):
        if not self._rotation_action:
            return None
        if self._animation_type not in TILT_ANIMATION_TYPES:
            return None
        raw = self._product_value(self._rotation_action["id"], "rotation")
        if raw is None:
            return None
        return _wms_to_ha_tilt(raw, self._tilt_min, self._tilt_max)

    async def async_open_cover(self, **kwargs):
        if self._position_action:
            await self.coordinator.api.set_position(
                self._dest_id, self._position_action["id"], 100.0
            )
            await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs):
        if self._position_action:
            await self.coordinator.api.set_position(
                self._dest_id, self._position_action["id"], 0.0
            )
            await self.coordinator.async_request_refresh()

    async def async_set_cover_position(self, **kwargs):
        if self._position_action:
            await self.coordinator.api.set_position(
                self._dest_id, self._position_action["id"], float(kwargs[ATTR_POSITION])
            )
            await self.coordinator.async_request_refresh()

    async def async_stop_cover(self, **kwargs):
        if self._stop_action:
            await self.coordinator.api.stop(self._dest_id, self._stop_action["id"])

    async def async_open_cover_tilt(self, **kwargs):
        if self._rotation_action:
            await self.coordinator.api.set_rotation(
                self._dest_id, self._rotation_action["id"], self._tilt_max
            )
            await self.coordinator.async_request_refresh()

    async def async_close_cover_tilt(self, **kwargs):
        if self._rotation_action:
            await self.coordinator.api.set_rotation(
                self._dest_id, self._rotation_action["id"], self._tilt_min
            )
            await self.coordinator.async_request_refresh()

    async def async_set_cover_tilt_position(self, **kwargs):
        if self._rotation_action:
            rotation = _ha_to_wms_rotation(
                kwargs[ATTR_TILT_POSITION], self._tilt_min, self._tilt_max
            )
            await self.coordinator.api.set_rotation(
                self._dest_id, self._rotation_action["id"], rotation
            )
            await self.coordinator.async_request_refresh()

    async def async_stop_cover_tilt(self, **kwargs):
        await self.async_stop_cover(**kwargs)

