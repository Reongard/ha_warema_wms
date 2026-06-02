"""API client for Warema WMS WebControl pro."""
from __future__ import annotations

import asyncio
import logging

import aiohttp

from .const import PROTOCOL_VERSION, SOURCE_ID

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=10)


class WMSConnectionError(Exception):
    """Raised when connection to WMS WebControl pro fails."""


class WMSWebControlAPI:
    def __init__(self, host: str, port: int = 80) -> None:
        self._host = host
        self._port = port
        self._base_url = f"http://{host}:{port}/WMS/WMSRequest"
        self._session = None

    def _get_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=DEFAULT_TIMEOUT)
        return self._session

    async def _request(self, payload: dict) -> dict:
        session = self._get_session()
        try:
            async with session.post(self._base_url, json=payload) as resp:
                if resp.status != 200:
                    raise WMSConnectionError(f"HTTP {resp.status}")
                return await resp.json(content_type=None)
        except aiohttp.ClientConnectorError as err:
            raise WMSConnectionError(f"Cannot connect: {err}") from err
        except asyncio.TimeoutError as err:
            raise WMSConnectionError("Timeout") from err

    def _base(self, command: str) -> dict:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "command": command,
            "source": SOURCE_ID,
        }

    async def ping(self) -> bool:
        result = await self._request(self._base("ping"))
        return result.get("command") == "ping"

    async def get_configuration(self) -> dict:
        return await self._request(self._base("getConfiguration"))

    async def get_status(self, destination_id: int) -> dict:
        payload = {**self._base("getStatus"), "destinations": [destination_id]}
        result = await self._request(payload)
        for detail in result.get("details", []):
            if detail.get("destinationId") == destination_id:
                return detail.get("data", {})
        return {}

    async def action(self, destination_id: int, actions: list) -> bool:
        payload = {
            **self._base("action"),
            "responseType": 0,
            "actions": [
                {
                    "destinationId": destination_id,
                    "actionId": a["actionId"],
                    "parameters": a.get("parameters", {}),
                }
                for a in actions
            ],
        }
        await self._request(payload)
        return True

    async def set_position(self, destination_id: int, action_id: int, percentage: float) -> bool:
        return await self.action(destination_id, [
            {"actionId": action_id, "parameters": {"percentage": round(percentage, 1)}}
        ])

    async def set_rotation(self, destination_id: int, action_id: int, rotation: float) -> bool:
        return await self.action(destination_id, [
            {"actionId": action_id, "parameters": {"rotation": round(rotation, 1)}}
        ])

    async def stop(self, destination_id: int, stop_action_id: int) -> bool:
        return await self.action(destination_id, [
            {"actionId": stop_action_id, "parameters": {}}
        ])

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

