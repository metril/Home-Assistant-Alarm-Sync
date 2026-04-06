# Home Assistant Alarm Sync for Home Assistant

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
4. Search for "Home Assistant Alarm Sync" and install
5. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/ha_alarm_sync` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Setup

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **Home Assistant Alarm Sync**
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
