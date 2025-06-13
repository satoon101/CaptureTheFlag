# ../gungame/core/events/included/leveling.py

"""Leveling based events."""

# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from events.custom import CustomEvent
from events.variable import ByteVariable, ShortVariable, StringVariable

# GunGame
from events.resource import ResourceFile

# =============================================================================
# >> ALL DECLARATION
# =============================================================================
__all__ = (
    "Flag_Captured",
    "Flag_Dropped",
    "Flag_Returned",
    "Flag_Taken",
)


# =============================================================================
# >> CLASSES
# =============================================================================
# ruff: noqa: N801
class Flag_Captured(CustomEvent):
    """Called when a player levels up."""

    userid = ShortVariable("The userid of the flag capturer")
    team = ShortVariable("The team of the flag capturer")
    flag_team = ShortVariable("The team of the flag that was captured")


class Flag_Dropped(CustomEvent):
    """Called when a player loses a level."""

    userid = ShortVariable("The userid of the player that dropped the flag")
    attacker = ShortVariable(
        "The userid of the player that killed the flag carrier",
    )
    location = StringVariable(
        "The comma separated location where the flag was dropped",
    )
    flag_team = ShortVariable("The team of the flag that was dropped")


class Flag_Returned(CustomEvent):
    """Called when a player levels up."""

    userid = ShortVariable("The userid of the player who returned the flag")
    flag_team = ShortVariable("The team of the flag that was returned")


class Flag_Taken(CustomEvent):
    """Called when a player levels up."""

    userid = ShortVariable("The userid of the player who took the flag")
    flag_team = ShortVariable("The team of the flag that was taken")


# =============================================================================
# >> RESOURCE FILE
# =============================================================================
resource_file = ResourceFile(
    "capture_the_flag",
    Flag_Captured,
    Flag_Dropped,
    Flag_Returned,
    Flag_Taken,
)
resource_file.write()
resource_file.load_events()
