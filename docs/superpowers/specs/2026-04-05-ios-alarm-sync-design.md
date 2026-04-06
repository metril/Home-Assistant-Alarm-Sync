# iOS Alarm Sync — Design Spec

## Context

There is no reliable way to sync iOS Clock app alarms to Home Assistant. The built-in "Next Alarm" sensor in the HA Companion app is unreliable and only shows the next alarm time — not full alarm details. Community workarounds use input helpers manually, which don't scale.

This project creates a custom Home Assistant integration + iOS Shortcuts that sync all alarms from multiple iPhones/iPads to HA, with full alarm details (time, label, repeat days, enabled state).

## Architecture

Two components working together:

```
iPhone Clock App
  → iOS Shortcut ("Get All Alarms")
  → HA Companion App "Call Service" action
  → ios_alarm_sync.sync_alarms service
  → Custom Integration manages entities
```

No custom webhooks — we leverage the existing HA Companion app infrastructure (mobile_app integration) that's already authenticated and registered per device.

## Component 1: Home Assistant Custom Integration (`ios_alarm_sync`)

### Setup

- Installed as a custom integration (HACS-compatible)
- Configured via HA config flow UI (no YAML)
- Config flow: User adds integration → selects which registered mobile devices to track alarms from
- Multi-user: each family member's device is configured independently

### Service: `ios_alarm_sync.sync_alarms`

Accepts a full alarm sync payload. Caller identity is determined from `context.user_id` provided automatically by the companion app's service call, which is then mapped to a configured mobile device.

If called without device context (e.g., from Developer Tools), a `device_id` field in the payload can be used as fallback. If neither is available, the call is rejected.

**Input schema:**
```json
{
  "alarms": [
    {
      "id": "unique-alarm-id",
      "label": "Morning Workout",
      "time": "06:30",
      "enabled": true,
      "repeat": ["mon", "tue", "wed", "thu", "fri"]
    },
    {
      "id": "another-alarm-id",
      "label": "Weekend Sleep In",
      "time": "09:00",
      "enabled": false,
      "repeat": ["sat", "sun"]
    }
  ]
}
```

**Behavior:**
- Receives the full alarm list from a device
- Diffs against stored state for that device
- Updates the device's alarm sensor entity and attributes
- Persists state to survive HA restarts

### Entity Model

**One sensor entity per device** (not per alarm):

- **Entity ID:** `sensor.ios_alarms_{device_name}` (e.g., `sensor.ios_alarms_jagannath_iphone`)
- **State:** Next upcoming alarm time (e.g., `06:30`) or `unknown` if no enabled alarms
- **Device class:** None (state is `HH:MM` string, not a full datetime)
- **Icon:** `mdi:alarm` (changes to `mdi:alarm-off` when no enabled alarms)

**Attributes:**
| Attribute | Type | Description |
|-----------|------|-------------|
| `alarms` | list[dict] | Full list of all alarms with id, label, time, enabled, repeat |
| `next_alarm_label` | str | Label of the next upcoming alarm |
| `next_alarm_time` | str | Time of the next alarm (HH:MM) |
| `enabled_count` | int | Number of enabled alarms |
| `total_count` | int | Total number of alarms |
| `last_sync` | datetime | Timestamp of the last successful sync |
| `device_name` | str | Friendly name of the source device |

### Storage

Uses HA's `helpers.storage.Store` to persist alarm data across restarts. Storage key: `ios_alarm_sync.{device_id}`.

### File Structure

```
custom_components/ios_alarm_sync/
  __init__.py          # Integration setup, service registration
  manifest.json        # Integration metadata, dependencies
  config_flow.py       # UI-based configuration flow
  const.py             # Constants (domain, service names, etc.)
  sensor.py            # Sensor entity platform
  services.yaml        # Service definitions for HA UI
  strings.json         # UI strings for config flow
  translations/
    en.json            # English translations
```

## Component 2: iOS Shortcut

### Shortcut Flow

One Shortcut per user, shareable via iCloud link:

1. **Get All Alarms** — retrieves all alarms from the Clock app
2. **For each alarm**, extract: ID, label, time, enabled state, repeat schedule
3. **Build JSON dictionary** with the alarm list
4. **Call Service** via HA Companion App → `ios_alarm_sync.sync_alarms` with JSON payload

### Sync Triggers (iOS Automations)

Set up as Personal Automations in the Shortcuts app:

| Trigger | When | Confirmation Required |
|---------|------|-----------------------|
| Alarm stopped | After any alarm is dismissed | iOS 16+: can run without confirmation |
| Alarm snoozed | After any alarm is snoozed | iOS 16+: can run without confirmation |
| Clock app opened | When user opens Clock app | May require confirmation |
| Time-based | Every 30 minutes | Can run without confirmation |
| HA app opened | When HA companion app opens | May require confirmation |

### Shortcut Limitations

- **No unique alarm ID** — alarms are identified by composite of time + label
- **No documented `enabled` property** — "Get All Alarms" exposes Name, Time, Repeat but enabled state is not reliably accessible. Integration accepts `enabled` field but defaults to `true` if absent.
- **iOS 16+ required** for alarm event triggers
- **"Get All Alarms"** field availability may vary by iOS version
- Personal Automations with "app opened" triggers may require user tap to confirm on some iOS versions
- HA Companion app must be installed, configured, and logged in
- Shortcut must have permission to access the Clock app

## Deliverables

1. Custom HA integration (`custom_components/ios_alarm_sync/`)
2. iOS Shortcut file or step-by-step creation guide
3. Setup documentation (README)
4. HACS repository configuration for easy installation

## Verification

1. **Unit tests:** Test service call handling, alarm diffing, entity creation/removal
2. **Manual integration test:**
   - Install integration in HA dev environment
   - Call `ios_alarm_sync.sync_alarms` with test payloads via HA Developer Tools > Services
   - Verify entity creation, attribute updates, and alarm removal
3. **End-to-end test:**
   - Install Shortcut on iPhone
   - Add/remove/toggle alarms in Clock app
   - Verify HA entities update correctly
   - Test with multiple devices for multi-user support
4. **Edge cases:**
   - Empty alarm list (all deleted)
   - Unnamed alarms (no label)
   - Duplicate alarm times
   - HA restart with persisted state
