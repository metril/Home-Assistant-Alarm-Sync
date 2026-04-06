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
