# iOS Shortcut Setup Guide

This guide covers two methods for creating the iOS Shortcut that syncs your Clock app alarms to Home Assistant.

## Prerequisites

- iPhone or iPad running iOS 16 or later
- Home Assistant Companion app installed and signed in
- Home Assistant Alarm Sync integration installed and configured in Home Assistant

---

## Method 1: Import Generated Shortcut (Recommended)

### Step 1: Generate the Shortcut File

On your computer, run the generator script:

```bash
cd ha_alarm_sync
python3 scripts/generate_shortcut.py
```

This creates `shortcuts/sync_alarms_to_ha.shortcut`.

### Step 2: Sign the Shortcut (macOS only)

iOS 15+ requires signed shortcut files. On a Mac:

```bash
shortcuts sign -i shortcuts/sync_alarms_to_ha.shortcut \
               -o shortcuts/sync_alarms_to_ha_signed.shortcut
```

### Step 3: Transfer to Your Device

- **AirDrop** the signed `.shortcut` file to your iPhone/iPad
- Or save it to **iCloud Drive** and open from the Files app

### Step 4: Add the HA "Call Service" Step

After importing, open the shortcut in the Shortcuts editor. You'll see a comment at the bottom with instructions:

1. Tap **+** below the comment
2. Search for **Home Assistant**
3. Select **Call Service**
4. Set Service to: `ha_alarm_sync.sync_alarms`
5. Set Service Data to: the **Dictionary** output from the step above it
6. Delete the instruction comment

### Step 5: Fix "Get All Alarms" (if needed)

If the **Get All Alarms** action shows an error after import, delete it and re-add it by searching "Get All Alarms" in the action picker. Then reconnect it to the **Repeat with Each** input.

### Step 6: Test the Shortcut

Tap the play button to run it. Check your HA entity for updated alarm data.

---

## Method 2: Manual Creation

If the import doesn't work, create the shortcut manually:

### Step 1: Open the Shortcuts App

Open the **Shortcuts** app on your iPhone or iPad. Tap **+** to create a new shortcut. Name it **"Sync Alarms to HA"**.

### Step 2: Get All Alarms

1. Tap **Add Action**
2. Search for **Get All Alarms** and add it

### Step 3: Build the Alarm Data

1. Add a **Repeat with Each** action — set input to the output of "Get All Alarms"
2. Inside the loop:
   - Add **Format Date** → set to **Custom Format** → `HH:mm` → set input to **Repeat Item**'s Time property
   - Add **Dictionary** with these entries:
     - Key `label` → Value: **Repeat Item** (select **Name** property)
     - Key `time` → Value: output of **Format Date**
     - Key `enabled` → Value: `true` (Boolean)
   - Add **Add to Variable** → variable name: `alarm_list`

### Step 4: Build the Final Payload

After the Repeat loop:
1. Add a **Dictionary** action:
   - Key `alarms` → Value: variable `alarm_list`

### Step 5: Call the HA Service

1. Tap **+** to add a new action
2. Search for **Home Assistant**
3. Select **Call Service**
4. Set Service to: `ha_alarm_sync.sync_alarms`
5. Set Service Data to: the **Dictionary** from Step 4

---

## Set Up Automations

Create these Personal Automations in the Shortcuts app for automatic syncing:

### Automation 1: When Any Alarm Goes Off

1. Go to **Automations** tab → **+** → **Personal Automation**
2. Select **Alarm** → **Any Alarm** → **Is Stopped**
3. Add action: **Run Shortcut** → select "Sync Alarms to HA"
4. Turn OFF "Ask Before Running"

### Automation 2: Periodic Sync

1. Create a new Personal Automation
2. Select **Time of Day** → choose a time, repeat daily
3. Add action: **Run Shortcut** → select "Sync Alarms to HA"
4. Turn OFF "Ask Before Running"

### Automation 3: When Clock App Opens (Optional)

1. Create a new Personal Automation
2. Select **App** → **Clock** → **Is Opened**
3. Add action: **Run Shortcut** → select "Sync Alarms to HA"
4. Note: This may require confirmation tap depending on iOS version

---

## Troubleshooting

- **"Get All Alarms" not found:** Make sure you're on iOS 16+. The action is provided by the Clock app.
- **"Home Assistant" not found in actions:** Make sure the HA Companion app is installed and signed in.
- **Service call fails:** Verify the `ha_alarm_sync` integration is installed and the service name is exactly `ha_alarm_sync.sync_alarms`.
- **Shortcut won't import:** Make sure the file is signed (macOS: `shortcuts sign`). Or create manually using Method 2.
- **Alarms not updating in HA:** Check the HA logs for `ha_alarm_sync` debug messages. Enable debug logging in `configuration.yaml`:
  ```yaml
  logger:
    logs:
      custom_components.ha_alarm_sync: debug
  ```
