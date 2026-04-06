"""Tests for the iOS Alarm Sync config flow."""

import pytest
from unittest.mock import patch, MagicMock

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.config_entries import ConfigEntry

from custom_components.ios_alarm_sync.const import DOMAIN


async def _create_mobile_app_entry(hass: HomeAssistant) -> str:
    """Register a fake mobile_app config entry and return its entry_id."""
    entry = config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain="mobile_app",
        title="Mobile App",
        data={},
        source=config_entries.SOURCE_USER,
        options={},
        entry_id="mobile_app_entry",
        unique_id="mobile_app_entry",
        discovery_keys={},
    )
    hass.config_entries._entries["mobile_app_entry"] = entry
    return entry.entry_id


async def test_config_flow_shows_mobile_devices(hass: HomeAssistant):
    """Test that the config flow lists mobile_app devices."""
    await _create_mobile_app_entry(hass)
    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id="mobile_app_entry",
        identifiers={("mobile_app", "iphone_123")},
        name="Jagannath's iPhone",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert "device_id" in result["data_schema"].schema


async def test_config_flow_creates_entry(hass: HomeAssistant):
    """Test successful config flow creates entry."""
    await _create_mobile_app_entry(hass)
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id="mobile_app_entry",
        identifiers={("mobile_app", "iphone_123")},
        name="Jagannath's iPhone",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"device_id": device.id},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "Jagannath's iPhone"
    assert result["data"]["device_id"] == device.id
    assert result["data"]["device_name"] == "Jagannath's iPhone"


async def test_config_flow_no_mobile_devices(hass: HomeAssistant):
    """Test config flow aborts when no mobile_app devices exist."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "abort"
    assert result["reason"] == "no_mobile_devices"
