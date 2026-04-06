"""Config flow for iOS Alarm Sync."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import device_registry as dr

from .const import CONF_DEVICE_ID, CONF_DEVICE_NAME, DOMAIN


class IOSAlarmSyncConfigFlow(
    config_entries.ConfigFlow, domain=DOMAIN
):
    """Handle a config flow for iOS Alarm Sync."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the user step — select a mobile device."""
        dev_reg = dr.async_get(self.hass)
        mobile_devices = {
            device.id: device.name or device.id
            for device in dev_reg.devices.values()
            if any(
                identifier[0] == "mobile_app"
                for identifier in device.identifiers
            )
        }

        if not mobile_devices:
            return self.async_abort(reason="no_mobile_devices")

        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID]
            device_name = mobile_devices.get(device_id, device_id)

            await self.async_set_unique_id(f"ios_alarm_sync_{device_id}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=device_name,
                data={
                    CONF_DEVICE_ID: device_id,
                    CONF_DEVICE_NAME: device_name,
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ID): vol.In(mobile_devices),
                }
            ),
        )
