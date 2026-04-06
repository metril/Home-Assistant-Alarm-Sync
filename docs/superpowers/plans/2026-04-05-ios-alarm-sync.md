# iOS Alarm Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a custom Home Assistant integration that syncs iOS Clock app alarms to HA entities via the companion app's Call Service infrastructure, with multi-device support.

**Architecture:** iOS Shortcut extracts alarm data via "Get All Alarms", serializes to JSON, and calls `ios_alarm_sync.sync_alarms` through the HA Companion App. The custom integration receives the payload, diffs alarm state, and maintains one sensor entity per device with full alarm data in attributes. Data persists across HA restarts via Store.

**Tech Stack:** Python 3.12+, Home Assistant Core APIs (config_entries, helpers.storage, services), voluptuous for schema validation, pytest + pytest-homeassistant-custom-component for testing.

**Important iOS Limitation:** The Shortcuts "Get All Alarms" action exposes Name, Time, and Repeat properties. There is no documented `enabled` property and no unique alarm ID. The integration accepts an `enabled` field in the payload (the Shortcut will attempt to extract it), but treats all alarms in the payload as "present" regardless. Alarms are keyed by a composite of time + label.

---

## File Structure

```
ios_alarm_sync/
├── custom_components/
│   └── ios_alarm_sync/
│       ├── __init__.py          # Integration setup, service registration, storage
│       ├── manifest.json        # Integration metadata
│       ├── config_flow.py       # UI config flow — select mobile device
│       ├── const.py             # Domain, service names, storage keys
│       ├── sensor.py            # AlarmSyncSensor entity
│       ├── services.yaml        # Service definitions for HA UI
│       ├── strings.json         # Config flow UI strings
│       └── translations/
│           └── en.json          # English translations
├── tests/
│   ├── conftest.py              # Shared fixtures (hass, config entries, mock data)
│   ├── test_init.py             # Service registration & handling tests
│   ├── test_sensor.py           # Sensor entity behavior tests
│   └── test_config_flow.py      # Config flow tests
├── docs/
│   └── ios-shortcut-guide.md    # Step-by-step Shortcut creation guide
├── hacs.json                    # HACS metadata
├── README.md                    # Setup & usage documentation
└── pyproject.toml               # Dev dependencies (pytest, etc.)
```

---

## Task 1: Project Scaffolding & Constants

**Files:**
- Create: `custom_components/ios_alarm_sync/const.py`
- Create: `custom_components/ios_alarm_sync/manifest.json`
- Create: `hacs.json`
- Create: `pyproject.toml`

- [ ] **Step 1: Create `const.py`**

```python
"""Constants for the iOS Alarm Sync integration."""

DOMAIN = "ios_alarm_sync"
STORAGE_VERSION = 1
STORAGE_KEY = "ios_alarm_sync_alarms"
SERVICE_SYNC_ALARMS = "sync_alarms"
CONF_DEVICE_ID = "device_id"
CONF_DEVICE_NAME = "device_name"
```

- [ ] **Step 2: Create `manifest.json`**

```json
{
  "domain": "ios_alarm_sync",
  "name": "iOS Alarm Sync",
  "codeowners": [],
  "config_flow": true,
  "documentation": "https://github.com/yourusername/ios_alarm_sync",
  "integration_type": "hub",
  "iot_class": "local_push",
  "issue_tracker": "https://github.com/yourusername/ios_alarm_sync/issues",
  "requirements": [],
  "version": "0.1.0",
  "after_dependencies": ["mobile_app"]
}
```

- [ ] **Step 3: Create `hacs.json`**

```json
{
  "name": "iOS Alarm Sync",
  "content_in_root": false,
  "homeassistant": "2024.1.0",
  "documentation": "https://github.com/yourusername/ios_alarm_sync",
  "issues": "https://github.com/yourusername/ios_alarm_sync/issues"
}
```

- [ ] **Step 4: Create `pyproject.toml`**

```toml
[project]
name = "ios-alarm-sync"
version = "0.1.0"
description = "Sync iOS Clock app alarms to Home Assistant"
requires-python = ">=3.12"

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-homeassistant-custom-component>=0.13",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 5: Commit**

```bash
git add custom_components/ios_alarm_sync/const.py custom_components/ios_alarm_sync/manifest.json hacs.json pyproject.toml
git commit -m "feat: scaffold project with constants, manifest, and dev config"
```

---

## Task 2: Alarm Data Model & Storage

**Files:**
- Create: `custom_components/ios_alarm_sync/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_init.py`

- [ ] **Step 1: Create test fixtures in `tests/conftest.py`**

```python
"""Shared test fixtures."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from custom_components.ios_alarm_sync.const import DOMAIN, CONF_DEVICE_ID, CONF_DEVICE_NAME


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
```

- [ ] **Step 2: Write failing test for alarm storage and service handling**

Create `tests/test_init.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /home/OLYMPOS/jagannath/projects/ios_alarm_sync && pip install -e ".[dev]" && pytest tests/test_init.py -v`
Expected: FAIL (module `custom_components.ios_alarm_sync` has no `async_setup_entry`)

- [ ] **Step 4: Implement `__init__.py`**

```python
"""iOS Alarm Sync integration for Home Assistant."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store

from .const import (
    CONF_DEVICE_ID,
    DOMAIN,
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
    store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)
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
        now = datetime.now().isoformat()

        stored_data[call_device_id] = {
            "alarms": alarms,
            "last_sync": now,
        }

        await store.async_save(stored_data)

        # Signal sensor to update
        hass.bus.async_fire(
            f"{DOMAIN}_updated",
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_init.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add custom_components/ios_alarm_sync/__init__.py tests/conftest.py tests/test_init.py
git commit -m "feat: add integration setup with sync_alarms service and storage"
```

---

## Task 3: Sensor Entity

**Files:**
- Create: `custom_components/ios_alarm_sync/sensor.py`
- Create: `tests/test_sensor.py`

- [ ] **Step 1: Write failing test for sensor entity**

Create `tests/test_sensor.py`:

```python
"""Tests for the iOS Alarm Sync sensor entity."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from custom_components.ios_alarm_sync.sensor import AlarmSyncSensor
from custom_components.ios_alarm_sync.const import DOMAIN


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
    assert sensor.unique_id == "ios_alarm_sync_my_device"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sensor.py -v`
Expected: FAIL (cannot import `AlarmSyncSensor`)

- [ ] **Step 3: Implement `sensor.py`**

```python
"""Sensor platform for iOS Alarm Sync."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DEVICE_ID, CONF_DEVICE_NAME, DOMAIN

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
                f"{DOMAIN}_updated", _handle_update
            )
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_sensor.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/ios_alarm_sync/sensor.py tests/test_sensor.py
git commit -m "feat: add alarm sync sensor entity with attributes"
```

---

## Task 4: Config Flow

**Files:**
- Create: `custom_components/ios_alarm_sync/config_flow.py`
- Create: `custom_components/ios_alarm_sync/strings.json`
- Create: `custom_components/ios_alarm_sync/translations/en.json`
- Create: `tests/test_config_flow.py`

- [ ] **Step 1: Write failing test for config flow**

Create `tests/test_config_flow.py`:

```python
"""Tests for the iOS Alarm Sync config flow."""

import pytest
from unittest.mock import patch, MagicMock

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from custom_components.ios_alarm_sync.const import DOMAIN


async def test_config_flow_shows_mobile_devices(hass: HomeAssistant):
    """Test that the config flow lists mobile_app devices."""
    # Create a mock mobile_app device in the registry
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
    # Schema should contain device selection
    assert "device_id" in result["data_schema"].schema


async def test_config_flow_creates_entry(hass: HomeAssistant):
    """Test successful config flow creates entry."""
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config_flow.py -v`
Expected: FAIL (no config flow module)

- [ ] **Step 3: Implement `config_flow.py`**

```python
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

            # Prevent duplicate entries for the same device
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
```

- [ ] **Step 4: Create `strings.json`**

```json
{
  "title": "iOS Alarm Sync",
  "config": {
    "step": {
      "user": {
        "title": "Select Mobile Device",
        "description": "Choose the iPhone or iPad to sync alarms from.",
        "data": {
          "device_id": "Mobile Device"
        }
      }
    },
    "abort": {
      "no_mobile_devices": "No mobile devices found. Install the Home Assistant Companion app on your iPhone/iPad first.",
      "already_configured": "This device is already configured."
    }
  }
}
```

- [ ] **Step 5: Create `translations/en.json`**

```json
{
  "title": "iOS Alarm Sync",
  "config": {
    "step": {
      "user": {
        "title": "Select Mobile Device",
        "description": "Choose the iPhone or iPad to sync alarms from.",
        "data": {
          "device_id": "Mobile Device"
        }
      }
    },
    "abort": {
      "no_mobile_devices": "No mobile devices found. Install the Home Assistant Companion app on your iPhone/iPad first.",
      "already_configured": "This device is already configured."
    }
  }
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_config_flow.py -v`
Expected: All 3 tests PASS

- [ ] **Step 7: Commit**

```bash
git add custom_components/ios_alarm_sync/config_flow.py custom_components/ios_alarm_sync/strings.json custom_components/ios_alarm_sync/translations/en.json tests/test_config_flow.py
git commit -m "feat: add config flow for mobile device selection"
```

---

## Task 5: Service YAML & Full Integration Test

**Files:**
- Create: `custom_components/ios_alarm_sync/services.yaml`

- [ ] **Step 1: Create `services.yaml`**

```yaml
sync_alarms:
  name: Sync Alarms
  description: "Sync iOS Clock app alarms from a device. Called by iOS Shortcuts via the HA Companion App."
  fields:
    alarms:
      name: Alarms
      description: "List of alarm objects with label, time, enabled, and repeat fields."
      required: true
      selector:
        object:
    device_id:
      name: Device ID
      description: "Optional device ID override. If not provided, uses the configured device for this entry."
      required: false
      selector:
        text:
```

- [ ] **Step 2: Run the full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS (3 init + 9 sensor + 3 config flow = 15 tests)

- [ ] **Step 3: Commit**

```bash
git add custom_components/ios_alarm_sync/services.yaml
git commit -m "feat: add service YAML for HA UI service description"
```

---

## Task 6: iOS Shortcut Guide & README

**Files:**
- Create: `docs/ios-shortcut-guide.md`
- Create: `README.md`

- [ ] **Step 1: Create `docs/ios-shortcut-guide.md`**

```markdown
# iOS Shortcut Setup Guide

This guide walks you through creating the iOS Shortcut that syncs your Clock app alarms to Home Assistant.

## Prerequisites

- iPhone or iPad running iOS 16 or later
- Home Assistant Companion app installed and signed in
- iOS Alarm Sync integration installed and configured in Home Assistant

## Create the Shortcut

### Step 1: Open the Shortcuts App

Open the **Shortcuts** app on your iPhone or iPad.

### Step 2: Create a New Shortcut

Tap the **+** button in the top right to create a new shortcut. Name it **"Sync Alarms to HA"**.

### Step 3: Add "Get All Alarms" Action

1. Tap **Add Action**
2. Search for **"Get All Alarms"**
3. Select it — this retrieves all alarms from the Clock app

### Step 4: Build the Alarm Data

1. Add a **Repeat with Each** action (set it to repeat with the output of "Get All Alarms")
2. Inside the loop, add a **Dictionary** action with these keys:
   - `label` → Repeat Item (select **Name** property)
   - `time` → Repeat Item (select **Time** property, format as **HH:mm** using "Format Date" action first)
   - `enabled` → Set to `true` (see note below)
   - `repeat` → Repeat Item (select **Repeat** property)
3. Add an **Add to Variable** action, variable name: `alarm_list`

### Step 5: Build the Final Payload

1. After the Repeat loop, add a **Dictionary** action:
   - `alarms` → Variable `alarm_list`

### Step 6: Call the HA Service

1. Add the **Home Assistant** action: **Call Service**
2. Set Service to: `ios_alarm_sync.sync_alarms`
3. Set Service Data to: the Dictionary from Step 5

### Note on Enabled State

iOS Shortcuts does not reliably expose the enabled/disabled state of alarms. The Shortcut sends all alarms — the integration treats all received alarms as present. If you find a way to detect enabled state on your iOS version, add it to the dictionary in Step 4.

## Set Up Automations

Create these Personal Automations in the Shortcuts app for automatic syncing:

### Automation 1: When Any Alarm Goes Off

1. Go to **Automations** tab → **+** → **Personal Automation**
2. Select **Alarm** → **Any Alarm** → **Is Stopped**
3. Add action: **Run Shortcut** → select "Sync Alarms to HA"
4. Turn OFF "Ask Before Running"

### Automation 2: Periodic Sync

1. Create a new Personal Automation
2. Select **Time of Day** → set to repeat every 30 minutes (or your preference)
3. Add action: **Run Shortcut** → select "Sync Alarms to HA"
4. Turn OFF "Ask Before Running"

### Automation 3: When Clock App Opens (Optional)

1. Create a new Personal Automation
2. Select **App** → **Clock** → **Is Opened**
3. Add action: **Run Shortcut** → select "Sync Alarms to HA"
4. Note: This may require confirmation tap depending on iOS version
```

- [ ] **Step 2: Create `README.md`**

```markdown
# iOS Alarm Sync for Home Assistant

A custom Home Assistant integration that syncs all your iOS Clock app alarms to Home Assistant. Supports multiple devices (family members).

## Features

- Syncs all alarms from iPhone/iPad Clock app to Home Assistant
- One sensor per device showing next alarm time with full alarm list in attributes
- Multi-device support — each family member's device tracked separately
- Automatic sync via iOS Shortcuts automations
- Persists alarm data across Home Assistant restarts

## Requirements

- Home Assistant 2024.1.0 or later
- iPhone/iPad running iOS 16 or later
- Home Assistant Companion app installed on each device

## Installation

### Via HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Go to **Integrations** → **Custom repositories**
3. Add this repository URL
4. Search for "iOS Alarm Sync" and install
5. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/ios_alarm_sync` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Setup

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **iOS Alarm Sync**
3. Select the mobile device to sync alarms from
4. Repeat for each family member's device

## iOS Shortcut Setup

Follow the [iOS Shortcut Guide](docs/ios-shortcut-guide.md) to set up the Shortcut and automations on each device.

## Entity

Each configured device creates one sensor:

- **Entity:** `sensor.ios_alarms_<device_name>`
- **State:** Next alarm time (HH:MM) or unknown
- **Attributes:**
  - `alarms` — Full list of all alarms
  - `next_alarm_label` — Label of next alarm
  - `next_alarm_time` — Time of next alarm
  - `enabled_count` — Number of enabled alarms
  - `total_count` — Total alarms
  - `last_sync` — Last sync timestamp
  - `device_name` — Device friendly name

## Example Automation

```yaml
automation:
  - alias: "Turn on bedroom lights before alarm"
    trigger:
      - platform: template
        value_template: >
          {{ now().strftime('%H:%M') == state_attr('sensor.ios_alarms_jagannath_iphone', 'next_alarm_time') }}
    action:
      - service: light.turn_on
        target:
          entity_id: light.bedroom
```

## Known Limitations

- iOS Shortcuts "Get All Alarms" may not expose the enabled/disabled state on all iOS versions
- No unique alarm IDs from iOS — alarms are identified by time + label
- Sync requires the HA Companion app to be functional on the device
- Some iOS automation triggers may require user confirmation to run

## License

MIT
```

- [ ] **Step 3: Commit**

```bash
git add docs/ios-shortcut-guide.md README.md
git commit -m "docs: add README and iOS Shortcut setup guide"
```

---

## Task 7: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 2: Verify file structure is complete**

Run: `find custom_components/ -type f | sort`

Expected output:
```
custom_components/ios_alarm_sync/__init__.py
custom_components/ios_alarm_sync/config_flow.py
custom_components/ios_alarm_sync/const.py
custom_components/ios_alarm_sync/manifest.json
custom_components/ios_alarm_sync/sensor.py
custom_components/ios_alarm_sync/services.yaml
custom_components/ios_alarm_sync/strings.json
custom_components/ios_alarm_sync/translations/en.json
```

- [ ] **Step 3: Test service call manually (when HA available)**

In HA Developer Tools → Services:
```yaml
service: ios_alarm_sync.sync_alarms
data:
  device_id: "your_device_id_here"
  alarms:
    - label: "Test Alarm"
      time: "07:30"
      enabled: true
      repeat:
        - mon
        - tue
        - wed
        - thu
        - fri
```

Verify: `sensor.ios_alarms_<device>` shows state `07:30` with correct attributes.

- [ ] **Step 4: Final commit with any fixes**

```bash
git add -A
git commit -m "chore: final cleanup and verification"
```
