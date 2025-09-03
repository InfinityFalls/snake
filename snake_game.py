import asyncio
from collections import deque
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Awaitable
from warnings import warn


class GameError(RuntimeError):
    pass


@dataclass
class Challenge:
    title: str
    description: str

# TODO: Figure out how to store settings in a somewhat sensible way
@dataclass
class Settings:
    cycle_length: int = 30  # TODO: Change to 120
    warning_time: int = 5
    num_challenges: int = 3


async def _no_method_warning(*_, **__):
    warn("A method has not been defined")


@dataclass
class InterfaceMethods:
    broadcast_challenges: Callable[[int], Coroutine[Any, Any, None]] = _no_method_warning
    warning_ping: Callable[[], Coroutine[Any, Any, None]] = _no_method_warning


class GameState(Enum):
    INITIAL = auto()
    STARTING = auto()
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
        self._challenge_lock = asyncio.Lock()
        self._cycle_id = 0
        self._set_complete = False

        self._challenge_loop_task = None

    @property
    def has_started(self):
        return self._state is not GameState.INITIAL

    @property
    def is_playing(self):
        return self._state is GameState.PLAYING

    @property
    def is_active(self):
        return self._state in (GameState.PLAYING, GameState.PAUSED)
    
    @property
    def has_ended(self):
        return self._state is GameState.ENDED

    async def get_current_challenges(self) -> list[Challenge]:
        async with self._challenge_lock:
            return self._challenge_queue[0]

    async def get_next_challenges(self):
        async with self._challenge_lock:
            return self._challenge_queue[1]

    async def enter_starting_state(self):
        """Enters the STARTING state of the Game. This sets has_started to False.
        This is intended to indicate when Settings should not be changed before the Game starts.

        Raises:
            GameError: Cannot enter starting state from a state other than INITIAL
        """
        async with self._state_lock:
            if self._state is not GameState.INITIAL:
                raise GameError("Cannot enter starting state from a state other than INITIAL")
            self._state = GameState.STARTING

    async def start_game(self):
        async with self._state_lock:
            if self._state not in (GameState.INITIAL, GameState.STARTING):
                raise GameError("Cannot start a game that has not started")
            
            self._challenge_queue.append(self._generate_challenges())
            self._challenge_queue.append(self._generate_challenges())
            
            self._challenge_loop_task = asyncio.create_task(
                self._challenge_loop())
            self._state = GameState.PLAYING

    async def end_game(self):
        async with self._state_lock:
            if self._state is not GameState.PLAYING:
                raise GameError("Cannot end a game that is not active")
            assert self._challenge_loop_task is not None
            self._challenge_loop_task.cancel()
            self._state = GameState.ENDED

    async def complete_challenge(self, challenge_id: int, cycle_id: int) -> tuple[Challenge, list[Challenge]]:
        async with self._challenge_lock:
            if self._state is not GameState.PLAYING:
                raise GameError("Game is currently not in progress")
            if self._cycle_id != cycle_id:
                raise GameError(
                    "Cannot complete a challenge from an expired cycle")
            if self._set_complete:
                raise GameError(
                    "A challenge has already been completed for this cycle")
            if not 0 <= challenge_id < self._settings.num_challenges:
                raise GameError("Invalid challenge ID")

            completed_challenge = self._challenge_queue[0][challenge_id]
            next_challenges = self._challenge_queue[1]
            self._set_complete = True
            return completed_challenge, next_challenges

    def _generate_challenges(self) -> list[Challenge]:
        # TODO: Generate a challenge cycle
        warn("Using dummy challenges")
        return [Challenge(f"Challenge {i + 1}", "Do something lol") for i in range(self._settings.num_challenges)]

    async def _shift_challenges(self):
        async with self._challenge_lock:
            self._challenge_queue.append(self._generate_challenges())
            self._cycle_id += 1
            self._set_complete = False

    async def _challenge_loop(self):
        while True:
            # TODO: change this to a pausable timer (will not be done in initial implementation)
            if self._settings.cycle_length > self._settings.warning_time:
                await asyncio.sleep(self._settings.cycle_length - self._settings.warning_time)
                asyncio.create_task(self._interface.warning_ping())
                await asyncio.sleep(self._settings.warning_time)
            else:
                await asyncio.sleep(self._settings.cycle_length)
            await self._shift_challenges()
            await self._interface.broadcast_challenges(self._cycle_id)
