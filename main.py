import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional
from snake_game import SnakeGame, Settings, InterfaceMethods, GameError

import discord


@dataclass
class Team:
    team_id: int
    thread: Optional[discord.Thread] = None
    members: list[discord.abc.Snowflake] = field(default_factory=list)


class ChallengeView(discord.ui.View):
    def __init__(self, challenge_id: int, cycle_id: int):
        self.challenge_id = challenge_id
        self.cycle_id = cycle_id


class DiscordGame:
    def __init__(self) -> None:
        self._general_thread = None
        self._teams = [Team(0), Team(1)]
        self._challenge_views: list[ChallengeView] = []
        self._settings = Settings()
        self._interface = InterfaceMethods()  # TODO: Fill
        self._game = SnakeGame(settings=self._settings, interface=self._interface)

    async def _create_threads(self, ctx: discord.ApplicationContext):
        self._general_thread = await ctx.channel.create_thread(name="Snake Chat", invitable=False)
        for team in self._teams:
            team.thread = await ctx.channel.create_thread(name=f"Snake Team {team.team_id + 1}", invitable=False)
            assert team.thread is not None
            for user in team.members:
                await self._general_thread.add_user(user)
                await team.thread.add_user(user)
    
    async def _countdown(self, message: str, time: int):
        assert self._general_thread is not None
        await self._general_thread.send(f"## {message} in {time}...")
        for i in range(time - 1, 0, -1):
            await asyncio.sleep(1)
            await self._general_thread.send(f"{i}...")
        await asyncio.sleep(1)

    async def start_game(self, ctx: discord.ApplicationContext):
        if self._game.has_started:
            await ctx.respond("The game has already started", ephemeral=True)
            return
        await ctx.respond("Starting game...", ephemeral=True)
        await self._create_threads(ctx)
        await self._countdown("Game starts", 5)
        await self._game.start_game()
    
    async def end_game(self, ctx: discord.ApplicationContext):
        await ctx.respond("Ending game...", ephemeral=True)
        await self._game.end_game()
        for view in self._challenge_views:
            view.disable_all_items()
    
    async def settings(self, ctx: discord.ApplicationContext, setting_name: str, new_val: Any):
        if self._game.has_started:
            await ctx.respond("Cannot change settings for a in-progress game", ephemeral=True)
            return
        raise NotImplementedError("Settings command not implemented yet")
    
    async def _complete_challenge(self, challenge_id: int, cycle_id: int):
        raise NotImplementedError("Complete challenge not implemented yet")
    
    async def _broadcast_challenges(self):
        assert self._game.has_started
        for view in self._challenge_views:
            view.disable_all_items()
        challenges = await self._game.get_current_challenges()
        raise NotImplementedError("Broadcast challenges not implemented yet")

    async def _warning_ping(self):
        assert self._game.has_started
        await self._countdown("New challenges", self._settings.warning_time)