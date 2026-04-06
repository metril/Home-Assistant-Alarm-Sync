"""Tests for ios_alarm_sync integration setup and service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.core import HomeAssistant, ServiceCall, Context

from custom_components.ios_alarm_sync.const import (
    DOMAIN,
    SERVICE_SYNC_ALARMS,
    STORAGE_KEY,
    STORAGE_VERSION,
)


async def test_async_setup_entry_registers_service(hass: HomeAssistant, mock_config_entry):
    """Test that setup registers the sync_alarms service."""
    with patch(
        "custom_components.ios_alarm_sync.Store",
        return_value=MagicMock(async_load=AsyncMock(return_value=None), async_save=AsyncMock()),
    ):
        from custom_components.ios_alarm_sync import async_setup_entry

        result = await async_setup_entry(hass, mock_config_entry)

        assert result is True
        assert hass.services.has_service(DOMAIN, SERVICE_SYNC_ALARMS)


async def test_sync_alarms_service_stores_data(
    hass: HomeAssistant, mock_config_entry, sample_alarms_payload
):
    """Test that calling sync_alarms stores alarm data."""
    mock_store = MagicMock()
    mock_store.async_load = AsyncMock(return_value=None)
    mock_store.async_save = AsyncMock()

    with patch(
        "custom_components.ios_alarm_sync.Store",
        return_value=mock_store,
    ):
        from custom_components.ios_alarm_sync import async_setup_entry

        await async_setup_entry(hass, mock_config_entry)

        # Simulate a service call with device_id in data
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SYNC_ALARMS,
            {**sample_alarms_payload, "device_id": "test_device_123"},
            blocking=True,
        )

        mock_store.async_save.assert_called_once()
        saved_data = mock_store.async_save.call_args[0][0]
        assert "test_device_123" in saved_data
        assert len(saved_data["test_device_123"]["alarms"]) == 3


async def test_sync_alarms_empty_payload(
    hass: HomeAssistant, mock_config_entry, empty_alarms_payload
):
    """Test syncing an empty alarm list clears stored alarms."""
    mock_store = MagicMock()
    mock_store.async_load = AsyncMock(
        return_value={
            "test_device_123": {
                "alarms": [{"label": "Old", "time": "08:00", "enabled": True, "repeat": []}]
            }
        }
    )
    mock_store.async_save = AsyncMock()

    with patch(
        "custom_components.ios_alarm_sync.Store",
        return_value=mock_store,
    ):
        from custom_components.ios_alarm_sync import async_setup_entry

        await async_setup_entry(hass, mock_config_entry)

        await hass.services.async_call(
            DOMAIN,
            SERVICE_SYNC_ALARMS,
            {**empty_alarms_payload, "device_id": "test_device_123"},
            blocking=True,
        )

        saved_data = mock_store.async_save.call_args[0][0]
        assert saved_data["test_device_123"]["alarms"] == []
