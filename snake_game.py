"""
Specification:
- Has two teams
- A set of three challenges are generated every 2 minutes
- First team to complete a challenge will notify opponent to freeze.
- Other team team will learn upcoming challenges while they are frozen.

Implementation Notes:
- Challenges are going to be strings and not much else.
- A message will need to be sent to opponent team, so needs an method to do that
- Race conditions will need to prevented when completing challenges
- Two teams might claim at the same time
- A team might claim just when challenges are rerolling!
"""
import asyncio
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from logging import warning
from types import FunctionType


class GameError(RuntimeError):
    pass


@dataclass
class Team:
    team_id: int
    # TODO: Define teams


class Challenge:
    # TODO: Define challenges
    pass

# TODO: Figure out how to store settings in a somewhat sensible way


@dataclass
class Settings:
    cycle_length: int = 120
    warning_time: int = 5
    num_challenges: int = 3


async def _no_method(*args, **kwargs):
    warning("A method has not been defined")


@dataclass
class InterfaceMethods:
    broadcast_challenges: FunctionType = _no_method
    warning_ping: FunctionType = _no_method


class GameState(Enum):
    INITIAL = auto()
    PLAYING = auto()
    PAUSED = auto()  # NOTE: Will not be used in initial implementation
    ENDED = auto()


class SnakeGame:
    def __init__(self, settings: Settings, interface: InterfaceMethods):
        self._settings = settings
        self._interface = interface

        self._state = GameState.INITIAL
        self._state_lock = asyncio.Lock()

        self._challenge_queue = deque(maxlen=2)
        self._challenge_queue.append(self._generate_challenges())
        self._challenge_queue.append(self._generate_challenges())
        self._challenge_lock = asyncio.Lock()
        self._current_set_id = 0
        self._set_complete = False

        self._challenge_loop_task = None

    @property
    def is_active(self):
        return self._state in (GameState.PLAYING, GameState.PAUSED)

    async def get_current_challenges(self):
        async with self._challenge_lock:
            return self._challenge_queue[0]

    async def get_next_challenges(self):
        async with self._challenge_lock:
            return self._challenge_queue[1]

    async def start_game(self) -> list[Challenge]:
        async with self._state_lock:
            if not self._state is GameState.INITIAL:
                raise GameError("Cannot start a game that has not started")
            self._challenge_loop_task = asyncio.create_task(
                self._challenge_loop())
            return self._challenge_queue[0]

    async def end_game(self):
        async with self._state_lock:
            if not self._state is not GameState.PLAYING:
                raise GameError("Cannot end a game that is not active")
            assert self._challenge_loop_task is not None
            self._challenge_loop_task.cancel()
            self._state = GameState.ENDED

    async def complete_challenge(self, challenge_id: int, set_id: int) -> tuple[Challenge, list[Challenge]]:
        async with self._challenge_lock:
            if self._current_set_id != set_id:
                raise GameError(
                    "Cannot complete a challenge from an expired set")
            if self._set_complete:
                raise GameError(
                    "A challenge has already been completed for this set")
            if not 0 <= challenge_id < self._settings.num_challenges:
                raise GameError("Invalid challenge ID")

            completed_challenge = self._challenge_queue[0][challenge_id]
            next_challenges = self._challenge_queue[1]
            self._set_complete = True
            return completed_challenge, next_challenges

    @staticmethod
    def _generate_challenges() -> list[Challenge]:
        # TODO: Generate a challenge set
        raise NotImplementedError

    async def _shift_challenges(self):
        async with self._challenge_lock:
            self._challenge_queue.append(self._generate_challenges())
            self._current_set_id += 1
            self._set_complete = False
        await self._interface.broadcast_challenges()

    async def _challenge_loop(self):
        while True:
            # TODO: change this to a pausable timer (will not be done in initial implementation)
            if self._settings.cycle_length > self._settings.warning_time:
                await asyncio.sleep(self._settings.cycle_length - self._settings.warning_time)
                await self._interface.warning_ping()
                await asyncio.sleep(self._settings.warning_time)
            else:
                await asyncio.sleep(self._settings.cycle_length)
            await self._shift_challenges()
