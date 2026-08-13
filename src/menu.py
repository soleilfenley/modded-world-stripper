import sys

import questionary

KNOWN_MODS = [
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


def select_mods_interaction() -> list[str]:
        selected = questionary.checkbox(
                message="Select the mods to strip.", choices=KNOWN_MODS
        ).ask()

        if selected is None:
                print("Cancelled. Have a great day!")
                sys.exit(1)

        if not selected:
                print("ERROR: No mods selected.")
                sys.exit(1)

        namespaces: list[str] = []
        for value in selected:
                if value == "__other__":
                        custom = questionary.text(
                                "Custom namespace(s) (comma-separated):",
                                validate=_validate_namespaces,
                        ).ask()
                        if custom is None:
                                print("Cancelled.")
                                sys.exit(1)
                        namespaces.extend(
                                namespace.strip()
                                for namespace in custom.split(",")
                                if namespace.strip()
                        )
                else:
                        namespaces.append(value)

        return namespaces
