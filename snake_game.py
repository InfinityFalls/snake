import asyncio
from dataclasses import dataclass


@dataclass
class Team:
    team_id: int


class SnakeGame:
    CHALLENGE_INTERVAL = 120
    
    def __init__(self):
        self._challenge_task = None
        self._game_lock = asyncio.Lock()  # HACK: Using a lock for everything to avoid any and all race conditions
    
    def start_game(self):
        self._challenge_task = asyncio.create_task(self._challenge_loop())
        raise NotImplementedError
    
    def end_game(self):
        raise NotImplementedError
    
    async def _challenge_loop(self):
        while True:
            await asyncio.sleep(self.CHALLENGE_INTERVAL)
            # TODO: generate challenge set
            raise NotImplementedError