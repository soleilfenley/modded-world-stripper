import sys
from typing import cast

import questionary

KNOWN_MODS: list[questionary.Choice | questionary.Separator] = [
        questionary.Choice("Supplementaries", value="supplementaries"),
        questionary.Separator(),
        questionary.Choice("Other (custom namespace) (NOT TESTED)", value="__other__"),
]


def _validate_namespaces(text: str) -> bool | str:
        if not text.strip():
                return "Required."

        parts = [part.strip() for part in text.split(",")]
        for part in parts:
                if not part:
                        return "empty entry between commas."
                if not part.replace("_", "").replace("-", "").isalnum():
                        return f"Invalid namespace: '{part}' (letters, numbers, underscores and dashes only.)"
        return True

def _ask_checkbox() -> list[str]:
        result = questionary.checkbox(message="Select the mods to strip.", choices=KNOWN_MODS).ask()
        if result is None:
                print("Cancelled. Have a great day!")
                sys.exit(1)
        if not isinstance(result, list):
                print("Unexpected response from mod selection.")
                sys.exit(1)
        type_conv_result = cast(list[object], result)

        result_strs: list[str] = []
        for v in type_conv_result:
                if isinstance(v, str):
                        result_strs.append(v)
        return result_strs


def _ask_custom_namespaces() -> str:
        result = questionary.text("Custom namespace(s) (comma-separated):", validate=_validate_namespaces,).ask()
        if result is None:
                print("Cancelled. Have a great day!")
                sys.exit(1)
        return str(result)



def select_mods_interaction() -> list[str]:
        selected = _ask_checkbox()
        if not selected:
                print("ERROR: No mods selected.")
                sys.exit(1)

        namespaces: list[str] = []
        for value in selected:
                if value == "__other__":
                        custom = _ask_custom_namespaces()
                        namespaces.extend(
                                namespace.strip()
                                for namespace in custom.split(",")
                                if namespace.strip()
                        )
                else:
                        namespaces.append(value)

        return namespaces
