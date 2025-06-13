# ../capture_the_flag/capture_the_flag.py

"""."""

# ==============================================================================
# >> IMPORTS
# ==============================================================================
# Python
from enum import IntEnum

# Source.Python
from colors import BLUE, RED, WHITE
from commands.client import ClientCommand
from commands.say import SayCommand
from engines.precache import Model
from engines.server import global_vars
from engines.sound import Sound
from entities.constants import SolidType
from entities.entity import Entity
from entities.helpers import index_from_pointer
from entities.hooks import EntityCondition, EntityPreHook, EntityPostHook
from events import Event
from filters.entities import EntityIter
from listeners import OnLevelInit
from mathlib import Vector
from memory.hooks import use_pre_registers
from messages import SayText2
from players.entity import Player
from players.helpers import index_from_userid, userid_from_index
from players.teams import teams_by_name, team_managers

# Plugin
from .config import drop_command, map_coordinates, win_count
from .custom_events import (
    Flag_Captured,
    Flag_Dropped,
    Flag_Returned,
    Flag_Taken,
)
from .strings import MESSAGE_STRINGS


# ==============================================================================
# >> GLOBAL VARIABLES
# ==============================================================================
_start_touch_dict = {}
# TODO: set the model
FLAG_MODEL = Model("models/props/cs_militia/caseofbeer01.mdl")
TEAM_COLORS = {
    2: {
        "name": "Red",
        "value": RED,
    },
    3: {
        "name": "Blue",
        "value": BLUE,
    },
}
TEAM_SOUNDS = {}
for _team_index, _color in ((2, "red"), (3, "blue")):
    current = TEAM_SOUNDS[_team_index] = {}
    for _event in ("dropped", "returned", "taken"):
        current[f"flag_{_event}"] = Sound(
            f"source-python/capture_the_flag/{_color}_flag_{_event}.mp3",
            download=True,
        )


# ==============================================================================
# >> CLASSES
# ==============================================================================
class FlagState(IntEnum):
    HOME = 0
    TAKEN = 1
    DROPPED = 2


class Flag:
    entity = None
    state = FlagState.HOME
    carrier = None

    def __init__(self, team_index, origin):
        self.team_index = team_index
        self.start_origin = origin

    def create(self, origin=None):
        origin = origin or self.start_origin
        self.entity = Entity.create("prop_dynamic")
        ctf.indexes.add(self.entity.index)
        self.entity.model = FLAG_MODEL
        self.entity.color = TEAM_COLORS[self.team_index]["value"]
        self.entity.solid_type = SolidType.VPHYSICS
        self.entity.teleport(origin)
        self.entity.spawn()
        return self

    def take_flag(self, index):
        self.carrier = index
        player = Player(index)
        ctf.indexes.remove(self.entity.index)
        self.entity.remove()
        self.entity = None
        player.color = TEAM_COLORS[self.team_index]["value"]
        self.state = FlagState.TAKEN
        with Flag_Taken() as event:
            event.userid = player.userid
            event.flag_team = self.team_index

    def drop_flag(self, player, attacker=0, location=None):
        location = location or player.origin
        self.create(origin=location)
        self.state = FlagState.DROPPED
        with Flag_Dropped() as event:
            event.userid = player.userid
            event.attacker = attacker
            event.location = " ".join(map(str, location))
            event.flag_team = self.team_index

    def return_flag(self, index):
        self.entity.teleport(self.start_origin)
        self.state = FlagState.HOME
        with Flag_Returned() as event:
            event.userid = userid_from_index(index)
            event.flag_team = self.team_index

    def capture_flag(self):
        player = Player(self.carrier)
        player.color = WHITE
        self.create()
        self.state = FlagState.HOME
        with Flag_Captured() as event:
            event.userid = player.userid
            event.team = player.team_index
            event.flag_team = self.team_index

        self.carrier = None


class CaptureTheFlag(dict):
    indexes = set()
    scores = {
        2: 0,
        3: 0,
    }

    def clear(self):
        self.indexes.clear()
        self.scores = {k: 0 for k in self.scores.keys()}
        super().clear()

    def create_flags(self):
        self.clear()
        coordinates = map_coordinates.get(global_vars.map_name)
        if coordinates is None:
            # TODO: raise/warn
            return

        if coordinates.keys() != teams_by_name.keys():
            # TODO: raise/warn
            pass

        for team, origin in coordinates.items():
            origin = Vector(*map(float, origin.split()))
            team_index = teams_by_name[team]
            flag = self[team_index] = Flag(team_index, origin)
            flag.create()

    def check_player_touched_flag(self, touched_entity, touching_entity):
        if touched_entity.index not in self.indexes:
            return False

        if touching_entity.classname != "player":
            return False

        return True

    def get_flag(self, entity):
        for flag in self.values():
            if flag.entity is not None and flag.entity.index == entity.index:
                return flag
        return None

    def drop_flag(self, index, use_player_location=True):
        player = Player(index)
        flag = self.get(5 - player.team_index)
        if flag is None:
            return

        if player.index != flag.carrier:
            return

        location = player.origin
        if not use_player_location:
            # TODO: fix this
            location = player.origin
        flag.drop_flag(player, location=location)


ctf = CaptureTheFlag()


# ==============================================================================
# >> COMMANDS
# ==============================================================================
_drop_command = str(drop_command)
if _drop_command:
    @SayCommand(_drop_command)
    @ClientCommand(_drop_command)
    def drop(command, index, teamonly=None):
        ctf.drop_flag(
            index=index,
            use_player_location=False,
        )


# ==============================================================================
# >> LISTENERS
# ==============================================================================
@OnLevelInit
def load(map_name=None):
    """Reset the cash dictionary."""
    ctf.create_flags()


# ==============================================================================
# >> HOOKS
# ==============================================================================
@EntityPreHook(
    EntityCondition.equals_entity_classname("prop_dynamic"),
    "start_touch",
)
def pre_start_touch(stack_data):
    _start_touch_dict[stack_data[0].address] = (
        index_from_pointer(stack_data[0]),
        index_from_pointer(stack_data[1]),
    )


@EntityPostHook(
    EntityCondition.equals_entity_classname("prop_dynamic"),
    "start_touch",
)
def post_start_touch(stack_data, return_value):
    with use_pre_registers(stack_data):
        address = stack_data[0].address

    trigger_index, other_index = _start_touch_dict.pop(address)
    if not all([trigger_index, other_index]):
        return

    touched_entity = Entity(trigger_index)
    touching_entity = Entity(other_index)
    if not ctf.check_player_touched_flag(
        touched_entity=touched_entity,
        touching_entity=touching_entity,
    ):
        return

    flag = ctf.get_flag(touched_entity)
    if flag is None:
        return

    team_index = touching_entity.team_index
    # did the player take the flag?
    if flag.state is FlagState.HOME and flag.team_index != team_index:
        flag.take_flag(touching_entity.index)
        return

    # did the player return the flag?
    if flag.state is FlagState.DROPPED and flag.team_index == team_index:
        flag.return_flag(other_index)
        return

    # did the player capture?
    if (
        flag.state is FlagState.HOME and
        flag.team_index == team_index
    ):
        other_flag = ctf[5 - flag.team_index]
        if other_flag.carrier == touching_entity.index:
            other_flag.capture_flag()


# ==============================================================================
# >> GAME EVENTS
# ==============================================================================
@Event("player_death")
def player_death(game_event):
    ctf.drop_flag(
        index=index_from_userid(game_event["userid"]),
    )


@Event("flag_captured")
def _flag_captured(game_event):
    team_index = int(game_event["team"])
    # TODO: sounds and messages
    #       takes lead
    #       increases lead
    #       scores
    #       wins the match
    ctf.scores[team_index] += 1
    set_team_scores()
    if ctf.scores[team_index] >= int(win_count):
        entity = Entity.find_or_create("game_end")
        entity.end_game()


@Event("flag_dropped")
@Event("flag_returned")
@Event("flag_taken")
def _flag_event(game_event):
    event_name = game_event.name
    team_index = game_event["flag_team"]
    TEAM_SOUNDS[team_index][event_name].play()
    player = Player.from_userid(game_event["userid"])
    SayText2(
        message=MESSAGE_STRINGS[event_name],
        index=player.index,
    ).send(
        name=player.name,
        team=TEAM_COLORS[team_index]["name"],
    )


@Event("round_start")
def set_team_scores(game_event=None):
    if game_event is not None:
        ctf.create_flags()
    for class_name in team_managers:
        for entity in EntityIter(class_name):
            if entity.team not in ctf.scores:
                continue
            entity.score = ctf.scores[entity.team]
