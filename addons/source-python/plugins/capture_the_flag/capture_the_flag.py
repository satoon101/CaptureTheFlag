# ../capture_the_flag/capture_the_flag.py

"""Plugin to provide Capture the Flag gameplay."""

# =============================================================================
# >> IMPORTS
# =============================================================================
# Python
from enum import IntEnum

# Source.Python
from colors import BLUE, RED, WHITE
from commands.client import ClientCommand
from commands.say import SayCommand
from cvars.tags import sv_tags
from engines.precache import Model
from engines.server import global_vars
from engines.sound import Sound
from entities.constants import CollisionGroup, SolidType
from entities.entity import Entity
from entities.helpers import index_from_pointer
from entities.hooks import EntityCondition, EntityPreHook, EntityPostHook
from events import Event
from filters.entities import EntityIter
from listeners import OnLevelInit
from listeners.tick import Repeat
from mathlib import Vector
from memory.hooks import use_pre_registers
from messages import HudMsg, SayText2
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
from .info import info
from .strings import MESSAGE_STRINGS


# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
_start_touch_dict = {}
# TODO: set the model
FLAG_MODEL = Model("models/props/cs_militia/caseofbeer01.mdl")
TEAM_COLORS = {
    2: {
        "message": f"{RED}Red\x01",
        "color": RED,
    },
    3: {
        "message": f"{BLUE}Blue\x01",
        "color": BLUE,
    },
}


# =============================================================================
# >> ENUMS
# =============================================================================
class FlagState(IntEnum):
    HOME = 0
    TAKEN = 1
    DROPPED = 2


class FlagTeam(IntEnum):
    RED = 2
    BLUE = 3


# =============================================================================
# >> SOUNDS
# =============================================================================
TEAM_SOUNDS = {}
for _team in FlagTeam:
    current = TEAM_SOUNDS[_team] = {}
    for _event in ("dropped", "returned", "taken"):
        current[f"flag_{_event}"] = Sound(
            f"source-python/{info.name}/{_team.name.lower()}_flag_{_event}.mp3",
            download=True,
        )
    for _item in (
        "dominating",
        "increase",
        "scores",
        "takes",
        "wins_match",
    ):
        current[_item] = Sound(
            f"source-python/{info.name}/{_team.name.lower()}_{_item}.mp3",
            download=True,
        )


# =============================================================================
# >> CLASSES
# =============================================================================
class Flag:
    entity = None
    state = FlagState.HOME
    carrier = None
    collision_group = None

    def __init__(self, team_index, origin):
        self.team_index = team_index
        self.start_origin = origin

    def create(self, location=None):
        origin = location if location is not None else self.start_origin
        self.entity = Entity.create("prop_dynamic")
        ctf.indexes.add(self.entity.index)
        self.entity.model = FLAG_MODEL
        self.entity.color = TEAM_COLORS[self.team_index]["color"]
        self.entity.solid_type = SolidType.VPHYSICS
        self.collision_group = self.entity.collision_group
        self.entity.collision_group = CollisionGroup.PUSHAWAY
        self.entity.teleport(origin=origin)
        self.entity.spawn()
        self.entity.delay(0.2, self.set_entity_collision_group)
        return self

    def set_entity_collision_group(self):
        if self.collision_group is None:
            return

        self.entity.collision_group = self.collision_group
        self.collision_group = None

    def take_flag(self, index):
        self.carrier = index
        player = Player(index)
        ctf.indexes.remove(self.entity.index)
        self.entity.remove()
        self.entity = None
        player.color = TEAM_COLORS[self.team_index]["color"]
        self.state = FlagState.TAKEN
        with Flag_Taken() as event:
            event.userid = player.userid
            event.flag_team = self.team_index

    def drop_flag(self, player, attacker=0):
        location = player.origin
        self.create(location=location)
        self.state = FlagState.DROPPED
        self.carrier = None
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
    scores = {i.value: 0 for i in FlagTeam}

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

    def drop_flag(self, index, attacker=0):
        player = Player(index)
        flag = self.get(5 - player.team_index)
        if flag is None:
            return

        if player.index != flag.carrier:
            return

        flag.drop_flag(player, attacker=attacker)


ctf = CaptureTheFlag()


# =============================================================================
# >> LOAD & UNLOAD
# =============================================================================
def load():
    sv_tags.add("ctf")
    ctf.create_flags()


def unload():
    sv_tags.remove("ctf")


# =============================================================================
# >> COMMANDS
# =============================================================================
_drop_command = str(drop_command)
if _drop_command:
    @SayCommand(_drop_command)
    @ClientCommand(_drop_command)
    def drop(command, index, teamonly=None):
        ctf.drop_flag(index=index)


# =============================================================================
# >> LISTENERS
# =============================================================================
@OnLevelInit
def _level_init(map_name):
    """Reset the cash dictionary."""
    ctf.create_flags()


# =============================================================================
# >> HOOKS
# =============================================================================
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
    if (
        flag.state in (FlagState.HOME, FlagState.DROPPED)
        and flag.team_index != team_index
    ):
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


# =============================================================================
# >> GAME EVENTS
# =============================================================================
@Event("player_death")
def player_death(game_event):
    ctf.drop_flag(
        index=index_from_userid(game_event["userid"]),
        attacker=game_event["attacker"],
    )


@Event("flag_captured")
def _flag_captured(game_event):
    team_index = int(game_event["team"])
    sounds = TEAM_SOUNDS[team_index]
    # TODO: sounds and messages
    #       takes lead
    #       increases lead
    #       scores
    #       wins the match
    ctf.scores[team_index] += 1
    set_team_scores()
    if ctf.scores[team_index] >= int(win_count):
        sounds["wins_match"].play()
        entity = Entity.find_or_create("game_end")
        return entity.end_game()

    score = ctf.scores[team_index]
    other_score = ctf.scores[5 - team_index]
    if score <= other_score:
        return sounds["scores"].play()

    if score == other_score + 1:
        return sounds["takes"].play()

    if score >= other_score + 5:
        return sounds["dominating"].play()

    return sounds["increase"].play()


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
        team=TEAM_COLORS[team_index]["message"],
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


# =============================================================================
# >> REPEATS
# =============================================================================
@Repeat
def repeat_flag_stat_display():
    if not ctf:
        return

    for team, y, channel in (
        (2, -0.7, 10),
        (3, -0.75, 11),
    ):
        HudMsg(
            message=MESSAGE_STRINGS["flag_state"],
            color1=TEAM_COLORS[team]["color"].with_alpha(255),
            x=1.5,
            y=y,
            effect=0,
            fade_in=0,
            fade_out=0,
            hold_time=2,
            fx_time=0,
            channel=channel,
        ).send(
            team=FlagTeam(team).name,
            state=ctf[team].state.name,
        )

repeat_flag_stat_display.start(1.0)
