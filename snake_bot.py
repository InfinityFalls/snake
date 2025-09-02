import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional
from guild_data import GuildInfo
from snake_game import Challenge, SnakeGame, Settings, InterfaceMethods, GameError

import discord


@dataclass
class Team:
    id: int
    team_role: discord.Role
    thread: Optional[discord.Thread] = None
    members: list[discord.abc.Snowflake] = field(default_factory=list)


class ChallengeView(discord.ui.View):
    def __init__(self, game: "DiscordGame", challenge_id: int, cycle_id: int, timeout: int):
        self._game = game
        self.challenge_id = challenge_id
        self.cycle_id = cycle_id
        self.timeout = timeout

    @discord.ui.button(label="Complete Challenge", style=discord.ButtonStyle.green)
    async def complete_challenge(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self._game._complete_challenge(interaction, self.challenge_id, self.cycle_id)


class DiscordGame:
    def __init__(self, game_id: int, guild_info: GuildInfo) -> None:
        self._game_id = game_id  # NOTE: Currently unused
        self._general_thread: Optional[discord.Thread] = None
        self._challenge_countdown_done = asyncio.Event()

        self._challenge_view_lock = asyncio.Lock()
        self._active_challenge_views: list[ChallengeView] = []

        self._pre_game_lock = asyncio.Lock()
        self._players = {}
        self._teams = [Team(0, guild_info.team_roles[0]),
                       Team(1, guild_info.team_roles[1])]
        self._settings = Settings()

        self._interface = InterfaceMethods(
            broadcast_challenges=self._broadcast_challenges,
            warning_ping=self._warning_ping
        )
        self._game = SnakeGame(settings=self._settings,
                               interface=self._interface)

    async def _create_threads(self, ctx: discord.ApplicationContext):
        self._general_thread = await ctx.channel.create_thread(name="Snake Chat", invitable=False)
        assert self._general_thread is not None
        for team in self._teams:
            team.thread = await ctx.channel.create_thread(name=f"Snake Team {team.id + 1}", invitable=False)
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

    async def join_game(self, ctx: discord.ApplicationContext, team_id: int):
        async with self._pre_game_lock:
            if self._game.has_started:
                await ctx.respond("The game has already started", ephemeral=True)
                return
            if ctx.user.id in self._players:
                await ctx.respond("You have already joined the game", ephemeral=True)
                return

            true_team_id = team_id - 1
            if not 0 <= true_team_id < len(self._teams):
                await ctx.respond(f"Invalid team ID", ephemeral=True)
                return

            self._players[ctx.user.id] = true_team_id
            self._teams[true_team_id].members.append(ctx.user)
            await ctx.respond(f"You have joined Team {team_id}", ephemral=True)

    def _get_team(self, user: discord.abc.Snowflake) -> Team:
        return self._teams[self._players[user.id]]

    async def start_game(self, ctx: discord.ApplicationContext):
        async with self._pre_game_lock:
            if self._game.has_started:
                await ctx.respond("The game has already started", ephemeral=True)
                return
            await self._game.enter_starting_state()
        await ctx.respond("Starting game...", ephemeral=True)
        await self._create_threads(ctx)
        await self._countdown("Game starts", 5)
        await self._game.start_game()

    def _disable_views(self):
        assert self._challenge_view_lock.locked()
        for view in self._active_challenge_views:
            view.disable_all_items()
        self._active_challenge_views.clear()

    async def end_game(self, ctx: discord.ApplicationContext):
        await ctx.respond("Ending game...", ephemeral=True)
        await self._game.end_game()

        async with self._challenge_view_lock:
            self._disable_views()

        assert self._general_thread is not None
        await self._general_thread.send("# Game Over!")

    async def settings(self, ctx: discord.ApplicationContext, setting_name: str, new_val: Any):
        async with self._pre_game_lock:
            if self._game.has_started:
                await ctx.respond("Cannot change settings for a in-progress game", ephemeral=True)
                return
            raise NotImplementedError("Settings command not implemented yet")

    async def _complete_challenge(self, interaction: discord.Interaction, challenge_id: int, cycle_id: int):
        async with self._challenge_view_lock:
            assert self._general_thread is not None
            try:
                challenge, next_challenges = await self._game.complete_challenge(challenge_id, cycle_id)
            except GameError as e:
                await interaction.response.send_message(f"{e}", ephemeral=True)
                return
            self._disable_views()

        assert interaction.user is not None
        completed_team = self._get_team(interaction.user)
        victim_teams = [v for i, v in enumerate(
            self._teams) if i != completed_team.id]

        # TODO: Make all of these happen at the same time
        await interaction.respond(f"<@&{completed_team.team_role.id}> has completed the challenge: {challenge.title}!\nAll other teams have been frozen!")
        for team in victim_teams:
            assert team.thread is not None
            await team.thread.send(f"<@&{team.team_role.id}> You have been frozen!\nThe upcoming challenges are:")
            for c in next_challenges:
                await team.thread.send(format_challenge(c))

    async def _broadcast_challenges(self, cycle_id: int):
        assert self._general_thread is not None
        
        await self._challenge_countdown_done.wait()
        async with self._challenge_view_lock:
            assert self._game.has_started
            if not self._game.is_playing:
                return
            self._disable_views()
            challenges = await self._game.get_current_challenges()
            
            
            for i, c in enumerate(challenges):
                view = ChallengeView(self, i, cycle_id, self._settings.cycle_length + 5)
                self._active_challenge_views.append(view)
                await self._general_thread.send(format_challenge(c), view=view)

    async def _warning_ping(self):
        assert self._game.has_started
        self._challenge_countdown_done.clear()
        await self._countdown("New challenges", self._settings.warning_time)
        self._challenge_countdown_done.set()


def format_challenge(challenge: Challenge) -> str:
    return f"### {challenge.title}\n{challenge.description}"
