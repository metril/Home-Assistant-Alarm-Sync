#!/usr/bin/env python3
"""Generate an iOS Shortcut file for syncing alarms to Home Assistant.

This script creates a .shortcut (plist) file that handles the alarm
extraction logic (Get All Alarms → Repeat → Format → Dictionary → payload).

The final step — calling the HA service — must be added manually using the
Home Assistant Companion App's "Call Service" Shortcuts action, because
third-party Siri Intents can't be encoded in generated shortcut files.

Usage:
    python generate_shortcut.py

    # On macOS, sign the shortcut for iOS 15+ import:
    shortcuts sign -i sync_alarms_to_ha.shortcut -o sync_alarms_to_ha_signed.shortcut

    # Then AirDrop the signed file to your iPhone/iPad
"""

import plistlib
import uuid
from pathlib import Path


def make_uuid() -> str:
    """Generate a UUID string for action references."""
    return str(uuid.uuid4()).upper()


def make_text_token(text: str, attachments: dict | None = None):
    """Create a WFTextTokenString with optional variable attachments.

    Args:
        text: The text content. Use \\ufffc (Object Replacement Character)
              where variable insertions should go.
        attachments: Dict mapping "{pos, len}" to variable reference dicts.
    """
    result = {
        "WFSerializationType": "WFTextTokenString",
        "Value": {
            "string": text,
        },
    }
    if attachments:
        result["Value"]["attachmentsByRange"] = attachments
    return result


def make_action_output_ref(
    action_uuid: str, output_name: str | None = None
) -> dict:
    """Create a reference to another action's output."""
    ref = {
        "OutputUUID": action_uuid,
        "Type": "ActionOutput",
    }
    if output_name:
        ref["OutputName"] = output_name
    return ref


def make_variable_ref(variable_name: str) -> dict:
    """Create a reference to a named variable."""
    return {
        "Type": "Variable",
        "VariableName": variable_name,
    }


def make_property_ref(
    action_uuid: str, property_name: str, output_name: str | None = None
) -> dict:
    """Create a reference to a property of an action's output."""
    ref = make_action_output_ref(action_uuid, output_name)
    ref["Aggrandizements"] = [
        {
            "Type": "WFPropertyVariableAggrandizement",
            "PropertyName": property_name,
        }
    ]
    return ref


def generate_shortcut() -> dict:
    """Generate the shortcut plist structure.

    Generates all alarm extraction logic. The HA "Call Service" step
    must be added manually after import (third-party Siri Intents can't
    be encoded in generated plist files).
    """

    # UUIDs for each action (used for variable references)
    uuids = {
        "get_alarms": make_uuid(),
        "repeat_each": make_uuid(),
        "format_date": make_uuid(),
        "dict_alarm": make_uuid(),
        "append_var": make_uuid(),
        "repeat_end": make_uuid(),
        "dict_payload": make_uuid(),
        "comment": make_uuid(),
    }

    actions = [
        # ─── Action 1: Get All Alarms ───
        # Uses the Clock app's intent to retrieve all alarms
        {
            "WFWorkflowActionIdentifier": "com.apple.mobiletimer-framework.MobileTimerIntents.MTGetAlarmsIntent",
            "WFWorkflowActionParameters": {
                "UUID": uuids["get_alarms"],
            },
        },
        # ─── Action 2: Repeat with Each (alarm) ───
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.repeat.each",
            "WFWorkflowActionParameters": {
                "UUID": uuids["repeat_each"],
                "WFInput": {
                    "WFSerializationType": "WFTextTokenAttachment",
                    "Value": make_action_output_ref(uuids["get_alarms"]),
                },
                "GroupingIdentifier": uuids["repeat_each"],
                "WFControlFlowMode": 0,  # 0 = start of loop
            },
        },
        # ─── Action 3: Format Date (extract time as HH:mm) ───
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.format.date",
            "WFWorkflowActionParameters": {
                "UUID": uuids["format_date"],
                "WFDateFormatStyle": "Custom",
                "WFDateFormat": "HH:mm",
                "WFDate": {
                    "WFSerializationType": "WFTextTokenAttachment",
                    "Value": make_property_ref(
                        uuids["repeat_each"], "Time"
                    ),
                },
            },
        },
        # ─── Action 4: Dictionary (build alarm object) ───
        # Creates: {"label": <name>, "time": <formatted_time>, "enabled": true}
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.dictionary",
            "WFWorkflowActionParameters": {
                "UUID": uuids["dict_alarm"],
                "WFItems": {
                    "Value": {
                        "WFDictionaryFieldValueItems": [
                            {
                                "WFItemType": 0,  # Text
                                "WFKey": make_text_token("label"),
                                "WFValue": {
                                    "WFSerializationType": "WFTextTokenAttachment",
                                    "Value": make_property_ref(
                                        uuids["repeat_each"], "Name"
                                    ),
                                },
                            },
                            {
                                "WFItemType": 0,  # Text
                                "WFKey": make_text_token("time"),
                                "WFValue": {
                                    "WFSerializationType": "WFTextTokenAttachment",
                                    "Value": make_action_output_ref(
                                        uuids["format_date"]
                                    ),
                                },
                            },
                            {
                                "WFItemType": 3,  # Boolean
                                "WFKey": make_text_token("enabled"),
                                "WFValue": {
                                    "WFSerializationType": "WFNumberSubstitutableState",
                                    "Value": True,
                                },
                            },
                        ],
                    },
                    "WFSerializationType": "WFDictionaryFieldValue",
                },
            },
        },
        # ─── Action 5: Add to Variable (alarm_list) ───
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.appendvariable",
            "WFWorkflowActionParameters": {
                "UUID": uuids["append_var"],
                "WFVariableName": "alarm_list",
                "WFInput": {
                    "WFSerializationType": "WFTextTokenAttachment",
                    "Value": make_action_output_ref(uuids["dict_alarm"]),
                },
            },
        },
        # ─── Action 6: End Repeat ───
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.repeat.each",
            "WFWorkflowActionParameters": {
                "UUID": uuids["repeat_end"],
                "GroupingIdentifier": uuids["repeat_each"],
                "WFControlFlowMode": 2,  # 2 = end of loop
            },
        },
        # ─── Action 7: Dictionary (build final payload) ───
        # Creates: {"alarms": <alarm_list>}
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.dictionary",
            "WFWorkflowActionParameters": {
                "UUID": uuids["dict_payload"],
                "WFItems": {
                    "Value": {
                        "WFDictionaryFieldValueItems": [
                            {
                                "WFItemType": 0,  # Text
                                "WFKey": make_text_token("alarms"),
                                "WFValue": {
                                    "WFSerializationType": "WFTextTokenAttachment",
                                    "Value": make_variable_ref("alarm_list"),
                                },
                            },
                        ],
                    },
                    "WFSerializationType": "WFDictionaryFieldValue",
                },
            },
        },
        # ─── Action 8: Comment (instructions for manual step) ───
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "UUID": uuids["comment"],
                "WFCommentActionText": (
                    "ADD THE FOLLOWING ACTION BELOW THIS COMMENT:\n"
                    "\n"
                    "1. Tap + below this comment\n"
                    "2. Search for 'Home Assistant'\n"
                    "3. Select 'Call Service'\n"
                    "4. Set Service to: ha_alarm_sync.sync_alarms\n"
                    "5. Set Service Data to: the Dictionary output above\n"
                    "\n"
                    "Then delete this comment."
                ),
            },
        },
    ]

    return {
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowClientVersion": "2302.0.4",
        "WFWorkflowClientRelease": "2302.0.4",
        "WFWorkflowIcon": {
            "WFWorkflowIconStartColor": 4282601983,  # Blue
            "WFWorkflowIconGlyphNumber": 59143,  # Alarm clock glyph
        },
        "WFWorkflowTypes": ["NCWidget", "WatchKit"],
        "WFWorkflowInputContentItemClasses": [],
        "WFWorkflowOutputContentItemClasses": [],
        "WFWorkflowHasOutputFallback": False,
        "WFWorkflowImportQuestions": [],
        "WFWorkflowActions": actions,
    }


def main():
    shortcut = generate_shortcut()

    output_dir = Path(__file__).parent.parent / "shortcuts"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "sync_alarms_to_ha.shortcut"

    with open(output_path, "wb") as f:
        plistlib.dump(shortcut, f, fmt=plistlib.FMT_BINARY)

    print(f"Generated: {output_path}")
    print()
    print("Next steps:")
    print("  1. If on macOS, sign the shortcut for iOS 15+ import:")
    print(f"     shortcuts sign -i {output_path} -o {output_dir / 'sync_alarms_to_ha_signed.shortcut'}")
    print()
    print("  2. Transfer to your iPhone/iPad via AirDrop or iCloud Drive")
    print()
    print("  3. After importing, add the final step manually:")
    print("     - Tap + at the bottom of the shortcut (after the comment)")
    print("     - Search for 'Home Assistant' → select 'Call Service'")
    print("     - Set Service to: ha_alarm_sync.sync_alarms")
    print("     - Set Service Data to: the Dictionary output from the step above")
    print("     - Delete the instruction comment")
    print()
    print("NOTE: If 'Get All Alarms' doesn't import correctly,")
    print("delete it and re-add it by searching 'Get All Alarms'")
    print("in the action picker. Reconnect it to 'Repeat with Each'.")


if __name__ == "__main__":
    main()
