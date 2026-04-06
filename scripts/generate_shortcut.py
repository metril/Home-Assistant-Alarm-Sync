#!/usr/bin/env python3
"""Generate an iOS Shortcut file for syncing alarms to Home Assistant.

This script creates a .shortcut (plist) file that:
1. Gets all alarms from the iOS Clock app
2. Iterates through each alarm, extracting name and time
3. Builds a JSON payload
4. POSTs it to the Home Assistant REST API

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
        text: The text content. Use \ufffc (Object Replacement Character)
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
    """Generate the complete shortcut plist structure."""

    # UUIDs for each action (used for variable references)
    uuids = {
        "get_alarms": make_uuid(),
        "repeat_each": make_uuid(),
        "format_date": make_uuid(),
        "dict_alarm": make_uuid(),
        "append_var": make_uuid(),
        "repeat_end": make_uuid(),
        "dict_payload": make_uuid(),
        "url_request": make_uuid(),
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
        # ─── Action 8: Get Contents of URL (POST to HA API) ───
        # POSTs the alarm payload to Home Assistant REST API
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
            "WFWorkflowActionParameters": {
                "UUID": uuids["url_request"],
                "WFHTTPMethod": "POST",
                "WFURL": make_text_token(
                    "\ufffc/api/services/ios_alarm_sync/sync_alarms",
                    {
                        "{0, 1}": make_variable_ref("ha_url"),
                    },
                ),
                "WFHTTPHeaders": {
                    "Value": {
                        "WFDictionaryFieldValueItems": [
                            {
                                "WFItemType": 0,
                                "WFKey": make_text_token("Authorization"),
                                "WFValue": make_text_token(
                                    "Bearer \ufffc",
                                    {
                                        "{7, 1}": make_variable_ref("ha_token"),
                                    },
                                ),
                            },
                            {
                                "WFItemType": 0,
                                "WFKey": make_text_token("Content-Type"),
                                "WFValue": make_text_token("application/json"),
                            },
                        ],
                    },
                    "WFSerializationType": "WFDictionaryFieldValue",
                },
                "WFHTTPBodyType": "Json",
                "WFJSONValues": {
                    "WFSerializationType": "WFTextTokenAttachment",
                    "Value": make_action_output_ref(uuids["dict_payload"]),
                },
            },
        },
    ]

    # Import questions — asked when the user installs the shortcut
    import_questions = [
        {
            "ActionIndex": 7,  # URL action index
            "Category": "Parameter",
            "DefaultValue": "http://homeassistant.local:8123",
            "ParameterKey": "ha_url_import",
            "Text": "What is your Home Assistant URL? (e.g., http://homeassistant.local:8123)",
        },
        {
            "ActionIndex": 7,
            "Category": "Parameter",
            "DefaultValue": "",
            "ParameterKey": "ha_token_import",
            "Text": "Paste your Home Assistant Long-Lived Access Token (Settings > Your Profile > Security > Long-Lived Access Tokens > Create Token)",
        },
    ]

    # Prepend variable setup actions for import question values
    setup_actions = [
        # Set ha_url from import question or default
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": make_uuid(),
                "WFTextActionText": make_text_token(
                    "http://homeassistant.local:8123"
                ),
            },
        },
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": "ha_url",
            },
        },
        # Set ha_token
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": make_uuid(),
                "WFTextActionText": make_text_token(
                    "YOUR_LONG_LIVED_ACCESS_TOKEN_HERE"
                ),
            },
        },
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": "ha_token",
            },
        },
    ]

    all_actions = setup_actions + actions

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
        "WFWorkflowImportQuestions": import_questions,
        "WFWorkflowActions": all_actions,
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
    print("  1. If on macOS, sign the shortcut:")
    print(f"     shortcuts sign -i {output_path} -o {output_dir / 'sync_alarms_to_ha_signed.shortcut'}")
    print()
    print("  2. Transfer to your iPhone/iPad:")
    print("     - AirDrop the signed .shortcut file")
    print("     - Or open it from iCloud Drive / Files app")
    print()
    print("  3. After importing, edit the shortcut to:")
    print("     - Replace 'YOUR_LONG_LIVED_ACCESS_TOKEN_HERE' with your actual HA token")
    print("     - Replace 'http://homeassistant.local:8123' with your actual HA URL")
    print()
    print("  4. To create a Long-Lived Access Token in HA:")
    print("     Settings > Your Profile > Security > Long-Lived Access Tokens > Create Token")
    print()
    print("NOTE: If the 'Get All Alarms' action doesn't import correctly,")
    print("delete it and re-add it manually by searching for 'Get All Alarms'")
    print("in the Shortcuts editor. Then reconnect it to the 'Repeat with Each' input.")


if __name__ == "__main__":
    main()
