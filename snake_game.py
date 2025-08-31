import asyncio
from dataclasses import dataclass
from enum import Enum, auto


class GameError(RuntimeError):
    pass


@dataclass
class Team:
    team_id: int
    # TODO: Define teams


class Challenge:
    # TODO: Define challenges
    pass


class GameState(Enum):
    INITIAL = auto()
    PLAYING = auto()
    PAUSED = auto()  # Will not be used in initial implementation
    ENDED = auto()


class SnakeGame:
    CHALLENGE_INTERVAL = 120

    def __init__(self):
        self._state = GameState.INITIAL
        self._challenge_task = None
        # HACK: Using a lock for everything to avoid any and all race conditions
        self._game_lock = asyncio.Lock()

    @property
    def is_active(self): return self._state in (
        GameState.PLAYING, GameState.PAUSED)

    def start_game(self):
        if not self._state is GameState.INITIAL:
            raise GameError("Cannot start a game that has not started")
        self._challenge_task = asyncio.create_task(self._challenge_loop())

        raise NotImplementedError

    def end_game(self):
        if not self._state is not GameState.PLAYING:
            raise GameError("Cannot end a game that is not active")
        assert self._challenge_task is not None
        self._challenge_task.cancel()

        raise NotImplementedError

    async def _challenge_loop(self):
        while True:
            # TODO: change this to a pausable timer
            await asyncio.sleep(self.CHALLENGE_INTERVAL)

            # TODO: generate challenge set
            raise NotImplementedError
