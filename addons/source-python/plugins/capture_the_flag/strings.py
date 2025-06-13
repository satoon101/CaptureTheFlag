# ../capture_the_flag/strings.py

"""Contains all translation variables for the base plugin."""

# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from translations.strings import LangStrings

# Plugin
from .info import info

# =============================================================================
# >> ALL DECLARATION
# =============================================================================
__all__ = (
    "CONFIG_STRINGS",
    "MESSAGE_STRINGS",
)


# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
CONFIG_STRINGS = LangStrings(info.name + "/config_strings")
MESSAGE_STRINGS = LangStrings(info.name + "/strings")
