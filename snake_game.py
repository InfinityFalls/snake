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

# TODO: Figure out how to store settings in a somewhat sensible way
class Settings:
    challenge_interval: int = 120
    num_challenges: int = 3


class GameState(Enum):
    INITIAL = auto()
    PLAYING = auto()
    PAUSED = auto()  # NOTE: Will not be used in initial implementation
    ENDED = auto()


class SnakeGame:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._state = GameState.INITIAL
        self._challenge_loop_task = None
        self._challenge_lock = asyncio.Lock()

    @property
    def is_active(self):
        return self._state in (GameState.PLAYING, GameState.PAUSED)

    def start_game(self):
        if not self._state is GameState.INITIAL:
            raise GameError("Cannot start a game that has not started")
        self._challenge_loop_task = asyncio.create_task(self._challenge_loop())

        raise NotImplementedError

    def end_game(self):
        if not self._state is not GameState.PLAYING:
            raise GameError("Cannot end a game that is not active")
        assert self._challenge_loop_task is not None
        self._challenge_loop_task.cancel()

        raise NotImplementedError

    async def _shift_challenges(self):
        # TODO: Shift down the next challenge set
        raise NotImplementedError
    
    async def complete_challenge(self, team_id: int, challenge_id: int):
        # TODO: Mark a challenge as complete
        raise NotImplementedError

    async def _challenge_loop(self):
        while True:
            # TODO: change this to a pausable timer (will not be done in initial implementation)
            await asyncio.sleep(self._settings.challenge_interval)
            await self._shift_challenges()
