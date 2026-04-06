"""Sensor platform for iOS Alarm Sync."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DEVICE_ID, CONF_DEVICE_NAME, DOMAIN, EVENT_ALARMS_UPDATED

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor from config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    device_id = entry.data[CONF_DEVICE_ID]
    device_name = entry.data[CONF_DEVICE_NAME]

    sensor = AlarmSyncSensor(
        hass=hass,
        entry_id=entry.entry_id,
        device_id=device_id,
        device_name=device_name,
        data=data,
    )
    async_add_entities([sensor])


class AlarmSyncSensor(SensorEntity):
    """Sensor representing all alarms for a single iOS device."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        device_id: str,
        device_name: str,
        data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        self._hass_ref = hass
        self._entry_id = entry_id
        self._device_id = device_id
        self._device_name = device_name
        self._data = data
        self._attr_unique_id = f"ios_alarm_sync_{device_id}"
        self._attr_name = f"iOS Alarms {device_name}"

    def _get_device_data(self) -> dict[str, Any] | None:
        """Get stored alarm data for this device."""
        return self._data.get("alarms", {}).get(self._device_id)

    def _get_alarms(self) -> list[dict[str, Any]]:
        """Get alarm list for this device."""
        device_data = self._get_device_data()
        if device_data is None:
            return []
        return device_data.get("alarms", [])

    def _get_enabled_alarms(self) -> list[dict[str, Any]]:
        """Get only enabled alarms, sorted by time."""
        return sorted(
            [a for a in self._get_alarms() if a.get("enabled", True)],
            key=lambda a: a.get("time", "99:99"),
        )

    def _get_next_alarm(self) -> dict[str, Any] | None:
        """Get the next enabled alarm (earliest time)."""
        enabled = self._get_enabled_alarms()
        return enabled[0] if enabled else None

    @property
    def native_value(self) -> str | None:
        """Return the next alarm time as the sensor state."""
        next_alarm = self._get_next_alarm()
        if next_alarm is None:
            return None
        return next_alarm.get("time")

    @property
    def icon(self) -> str:
        """Return icon based on alarm state."""
        if self._get_enabled_alarms():
            return "mdi:alarm"
        return "mdi:alarm-off"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return full alarm data as attributes."""
        alarms = self._get_alarms()
        device_data = self._get_device_data()
        next_alarm = self._get_next_alarm()

        return {
            "alarms": alarms,
            "next_alarm_label": next_alarm.get("label", "") if next_alarm else None,
            "next_alarm_time": next_alarm.get("time") if next_alarm else None,
            "enabled_count": len(self._get_enabled_alarms()),
            "total_count": len(alarms),
            "last_sync": device_data.get("last_sync") if device_data else None,
            "device_name": self._device_name,
        }

    async def async_added_to_hass(self) -> None:
        """Register event listener when added to hass."""
        await super().async_added_to_hass()

        @callback
        def _handle_update(event) -> None:
            """Handle alarm data update event."""
            if event.data.get("device_id") == self._device_id:
                self.async_write_ha_state()

        self.async_on_remove(
            self._hass_ref.bus.async_listen(
                EVENT_ALARMS_UPDATED, _handle_update
            )
        )
