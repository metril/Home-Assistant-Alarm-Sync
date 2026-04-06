"""Shared test fixtures."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from custom_components.ios_alarm_sync.const import DOMAIN, CONF_DEVICE_ID, CONF_DEVICE_NAME


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    return enable_custom_integrations


@pytest.fixture(autouse=True)
def mock_forward_entry_setups():
    """Patch async_forward_entry_setups to avoid loading sensor platform in unit tests."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        return_value=True,
    ) as mock_forward:
        yield mock_forward


@pytest.fixture
def mock_config_entry() -> ConfigEntry:
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.domain = DOMAIN
    entry.data = {
        CONF_DEVICE_ID: "test_device_123",
        CONF_DEVICE_NAME: "Test iPhone",
    }
    entry.title = "Test iPhone"
    entry.runtime_data = None
    return entry


@pytest.fixture
def sample_alarms_payload():
    """Sample alarm sync payload."""
    return {
        "alarms": [
            {
                "label": "Morning Workout",
                "time": "06:30",
                "enabled": True,
                "repeat": ["mon", "tue", "wed", "thu", "fri"],
            },
            {
                "label": "Weekend Sleep In",
                "time": "09:00",
                "enabled": True,
                "repeat": ["sat", "sun"],
            },
            {
                "label": "",
                "time": "07:00",
                "enabled": False,
                "repeat": [],
            },
        ]
    }


@pytest.fixture
def empty_alarms_payload():
    """Empty alarm payload (all alarms deleted)."""
    return {"alarms": []}
