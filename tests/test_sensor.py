"""Tests for the Home Assistant Alarm Sync sensor entity."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from custom_components.ha_alarm_sync.sensor import AlarmSyncSensor
from custom_components.ha_alarm_sync.const import DOMAIN


def _make_sensor(device_id="test_device_123", device_name="Test iPhone", alarms=None):
    """Create an AlarmSyncSensor for testing."""
    hass = MagicMock()
    entry_data = {
        "store": MagicMock(),
        "alarms": {},
    }
    if alarms is not None:
        entry_data["alarms"][device_id] = {
            "alarms": alarms,
            "last_sync": "2026-04-05T10:00:00",
        }
    return AlarmSyncSensor(
        hass=hass,
        entry_id="test_entry",
        device_id=device_id,
        device_name=device_name,
        data=entry_data,
    )


def test_sensor_state_next_alarm_time():
    """Test sensor state returns next enabled alarm time."""
    alarms = [
        {"label": "Early", "time": "05:00", "enabled": True, "repeat": []},
        {"label": "Late", "time": "09:00", "enabled": True, "repeat": []},
    ]
    sensor = _make_sensor(alarms=alarms)
    assert sensor.native_value == "05:00"


def test_sensor_state_skips_disabled():
    """Test sensor state ignores disabled alarms."""
    alarms = [
        {"label": "Disabled", "time": "04:00", "enabled": False, "repeat": []},
        {"label": "Enabled", "time": "07:00", "enabled": True, "repeat": []},
    ]
    sensor = _make_sensor(alarms=alarms)
    assert sensor.native_value == "07:00"


def test_sensor_state_no_enabled_alarms():
    """Test sensor state when no alarms are enabled."""
    alarms = [
        {"label": "Off", "time": "06:00", "enabled": False, "repeat": []},
    ]
    sensor = _make_sensor(alarms=alarms)
    assert sensor.native_value is None


def test_sensor_state_no_alarms():
    """Test sensor state with empty alarm list."""
    sensor = _make_sensor(alarms=[])
    assert sensor.native_value is None


def test_sensor_state_no_data_yet():
    """Test sensor state before any sync has happened."""
    sensor = _make_sensor(alarms=None)
    assert sensor.native_value is None


def test_sensor_attributes(sample_alarms_payload):
    """Test sensor extra state attributes."""
    sensor = _make_sensor(alarms=sample_alarms_payload["alarms"])
    attrs = sensor.extra_state_attributes

    assert attrs["total_count"] == 3
    assert attrs["enabled_count"] == 2
    assert attrs["next_alarm_label"] == "Morning Workout"
    assert attrs["next_alarm_time"] == "06:30"
    assert len(attrs["alarms"]) == 3
    assert attrs["last_sync"] == "2026-04-05T10:00:00"
    assert attrs["device_name"] == "Test iPhone"


def test_sensor_icon_with_enabled_alarms():
    """Test icon when alarms are enabled."""
    alarms = [{"label": "A", "time": "06:00", "enabled": True, "repeat": []}]
    sensor = _make_sensor(alarms=alarms)
    assert sensor.icon == "mdi:alarm"


def test_sensor_icon_no_enabled_alarms():
    """Test icon when no alarms are enabled."""
    alarms = [{"label": "A", "time": "06:00", "enabled": False, "repeat": []}]
    sensor = _make_sensor(alarms=alarms)
    assert sensor.icon == "mdi:alarm-off"


def test_sensor_unique_id():
    """Test unique ID format."""
    sensor = _make_sensor(device_id="my_device")
    assert sensor.unique_id == "ha_alarm_sync_my_device"
