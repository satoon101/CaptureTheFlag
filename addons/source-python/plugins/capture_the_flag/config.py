# ../capture_the_flag/config.py

"""Creates server configuration and user settings."""

# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from config.manager import ConfigManager
from paths import CFG_PATH

# Site-package
from configobj import ConfigObj

# Plugin
from .info import info
from .strings import CONFIG_STRINGS

# =============================================================================
# >> ALL DECLARATION
# =============================================================================
__all__ = (
    "drop_command",
    "map_coordinates",
    "win_count",
)


# =============================================================================
# >> CONFIGURATION
# =============================================================================
# Create the capture_the_flag.cfg file and execute it upon __exit__
with ConfigManager(f"{info.name}/config", "ctf_") as config:
    drop_command = config.cvar(
        name="drop_command",
        default="",
        description=CONFIG_STRINGS["drop_command"],
    )
    win_count = config.cvar(
        name="win_count",
        default=3,
        description=CONFIG_STRINGS["win_count"],
    )


_map_coordinates_file = CFG_PATH / info.name / "map_coordinates.ini"
map_coordinates = ConfigObj(_map_coordinates_file)
if not map_coordinates:
    map_coordinates["de_dust"] = {
        "t": "1340 3377 -127",
        "ct": "125 -1562 64",
    }
    map_coordinates.write()
