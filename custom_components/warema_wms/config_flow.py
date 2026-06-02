"""Config flow for Warema WMS WebControl pro."""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .api import WMSWebControlAPI, WMSConnectionError
from .const import DOMAIN, CONF_HOST, CONF_PORT, COVER_ANIMATION_TYPES

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): str,
    vol.Optional(CONF_PORT, default=80): int,
})


class WMSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input.get(CONF_PORT, 80)

            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            api = WMSWebControlAPI(host=host, port=port)
            try:
                await api.ping()
                config = await api.get_configuration()
                await api.close()
                covers = [
                    d for d in config.get("destinations", [])
                    if d.get("animationType") in COVER_ANIMATION_TYPES
                ]
                _LOGGER.info("WMS: %d Gerät(e) gefunden", len(covers))
            except WMSConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"WMS WebControl pro ({host})",
                    data={CONF_HOST: host, CONF_PORT: port},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

