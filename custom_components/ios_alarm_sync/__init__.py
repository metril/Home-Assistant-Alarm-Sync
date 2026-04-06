"""iOS Alarm Sync integration for Home Assistant."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.util import dt as dt_util

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store

from .const import (
    CONF_DEVICE_ID,
    DOMAIN,
    EVENT_ALARMS_UPDATED,
    SERVICE_SYNC_ALARMS,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

ALARM_SCHEMA = vol.Schema(
    {
        vol.Optional("label", default=""): cv.string,
        vol.Required("time"): cv.string,
        vol.Optional("enabled", default=True): cv.boolean,
        vol.Optional("repeat", default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
    }
)

SYNC_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("alarms"): vol.All(cv.ensure_list, [ALARM_SCHEMA]),
        vol.Optional("device_id"): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up iOS Alarm Sync from a config entry."""
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    stored_data = await store.async_load() or {}

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "store": store,
        "alarms": stored_data,
    }

    device_id = entry.data[CONF_DEVICE_ID]

    async def handle_sync_alarms(call: ServiceCall) -> None:
        """Handle the sync_alarms service call."""
        call_device_id = call.data.get("device_id", device_id)

        alarms = call.data["alarms"]
        now = dt_util.utcnow().isoformat()

        current_data = await store.async_load() or {}
        current_data[call_device_id] = {
            "alarms": alarms,
            "last_sync": now,
        }

        await store.async_save(current_data)

        # Update in-memory reference for sensor
        stored_data.update(current_data)

        # Signal sensor to update
        hass.bus.async_fire(
            EVENT_ALARMS_UPDATED,
            {"device_id": call_device_id},
        )

        _LOGGER.debug(
            "Synced %d alarms for device %s", len(alarms), call_device_id
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SYNC_ALARMS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SYNC_ALARMS,
            handle_sync_alarms,
            schema=SYNC_SERVICE_SCHEMA,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_SYNC_ALARMS)

    return unload_ok
