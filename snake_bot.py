import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Optional
from snake_game import Challenge, SnakeGame, Settings, InterfaceMethods, GameError
from dotenv import load_dotenv
import os

import discord


load_dotenv()


@dataclass
class Team:
    id: int
    team_role: discord.Role
    thread: Optional[discord.Thread] = None
    members: list[discord.Member] = field(default_factory=list)
    
    async def remove_roles(self):
        async with asyncio.TaskGroup() as tg:
            for member in self.members:
                tg.create_task(member.remove_roles(self.team_role))


class ChallengeView(discord.ui.View):
    def __init__(self, game: "DiscordGame", challenge_id: int, cycle_id: int, timeout: int):
        super().__init__(timeout=timeout, disable_on_timeout=True)
        self._game = game
        self.challenge_id = challenge_id
        self.cycle_id = cycle_id

    @discord.ui.button(label="Complete Challenge", style=discord.ButtonStyle.green)
    async def complete_challenge(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self._game._complete_challenge(interaction, self.challenge_id, self.cycle_id)
        
    async def on_timeout(self) -> None:
        await self.disable_view()
    
    async def disable_view(self) -> None:
        assert self.message is not None
        self.disable_all_items()
        await self.message.edit(content=self.message.content, view=self)


class DiscordGame:
    def __init__(self, thread: discord.Thread, game_id: int, team_roles: Sequence[discord.Role]) -> None:
        self._game_id = game_id  # NOTE: Currently unused
        self._general_thread: discord.Thread = thread
        self._challenge_countdown_done = asyncio.Event()
        self._challenge_countdown_done.set()

        self._challenge_view_lock = asyncio.Lock()
        self._active_challenge_views: list[ChallengeView] = []

        self._pre_game_lock = asyncio.Lock()
        self._players = {}
        self._teams = [Team(0, team_roles[0]),
                       Team(1, team_roles[1])]
        self._settings = Settings()

        self._interface = InterfaceMethods(
            broadcast_challenges=self._broadcast_challenges,
            warning_ping=self._warning_ping
        )
        self._game = SnakeGame(settings=self._settings,
                               interface=self._interface)

    async def _create_team_thread(self, ctx: discord.ApplicationContext, team: Team):
        assert isinstance(ctx.channel, discord.Thread)
        assert isinstance(ctx.channel.parent, discord.TextChannel)
        
        team.thread = await ctx.channel.parent.create_thread(name=f"Snake Team {team.id + 1}", invitable=False)
        assert team.thread is not None
        
        async with asyncio.TaskGroup() as tg:
            for user in team.members:
                tg.create_task(self._general_thread.add_user(user))
                tg.create_task(team.thread.add_user(user))

    async def _create_threads(self, ctx: discord.ApplicationContext):
        async with asyncio.TaskGroup() as tg:
            for team in self._teams:
                tg.create_task(self._create_team_thread(ctx, team))

    async def _countdown(self, message_str: str, time: int):
        if self._game.has_ended:
            return
        
        message = await self._general_thread.send(f"## {message_str} in {time}...")
        for i in range(time - 1, 0, -1):
            await asyncio.sleep(1)
            
            if self._game.has_ended:
                await message.delete()
                return
            
            await message.edit(content=f"## {message_str} in {i}...")
        await asyncio.sleep(1)
        await message.delete()
        
    def _is_player(self, user: discord.abc.Snowflake):
        return user.id in self._players

    async def join_game(self, ctx: discord.ApplicationContext, team_id: int):
        assert isinstance(ctx.user, discord.Member)
        
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
            team = self._teams[true_team_id]

            self._players[ctx.user.id] = true_team_id
            team.members.append(ctx.user)
            await ctx.user.add_roles(self._teams[true_team_id].team_role)
            await ctx.respond(f"You have joined Team {team_id}", ephemeral=True)

    def _get_team(self, user: discord.abc.Snowflake) -> Team:
        return self._teams[self._players[user.id]]

    async def start_game(self, ctx: discord.ApplicationContext):
        async with self._pre_game_lock:
            if self._game.has_started:
                await ctx.respond("The game has already started", ephemeral=True)
                return
            await self._game.enter_starting_state()
        
        await ctx.respond("Starting game...", ephemeral=True)
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._create_threads(ctx))
            tg.create_task(self._countdown("Game starts", 5))
        
        await self._game.start_game()
        await self._broadcast_challenges(0)

    async def _disable_views(self):
        assert self._challenge_view_lock.locked()
        async with asyncio.TaskGroup() as tg:
            for view in self._active_challenge_views:
                tg.create_task(view.disable_view())
        self._active_challenge_views.clear()


    async def end_game(self, ctx: discord.ApplicationContext):
        async def locking_disable_views():
            async with self._challenge_view_lock:
                await self._disable_views()
        
        await self._game.end_game()
        await ctx.respond("Ending game...", ephemeral=True)

        async with asyncio.TaskGroup() as tg:
            tg.create_task(locking_disable_views())
            tg.create_task(self._general_thread.send("# Game Over!"))
            for team in self._teams:
                tg.create_task(team.remove_roles())

    async def settings(self, ctx: discord.ApplicationContext, setting_name: str, new_val: Any):
        async with self._pre_game_lock:
            if self._game.has_started:
                await ctx.respond("Cannot change settings for a in-progress game", ephemeral=True)
                return
            raise NotImplementedError("Settings command not implemented yet")

    async def _send_freeze(self, team: Team, next_challenges: list[Challenge]):
        assert team.thread is not None
        await team.thread.send(f"## {team.team_role.mention} You have been frozen!\nThe upcoming challenges are:")
        for c in next_challenges:
            await team.thread.send(format_challenge(c))

    async def _complete_challenge(self, interaction: discord.Interaction, challenge_id: int, cycle_id: int):
        assert interaction.user is not None
        if not self._is_player(interaction.user):
            await interaction.respond("You are not playing in this game. You cannot complete the challenge.", ephemeral=True)
            return
        
        async with self._challenge_view_lock:
            try:
                challenge, next_challenges = await self._game.complete_challenge(challenge_id, cycle_id)
            except GameError as e:
                await interaction.response.send_message(f"{e}", ephemeral=True)
                return
            else:
                await self._disable_views()

        completed_team = self._get_team(interaction.user)
        victim_teams = [v for i, v in enumerate(
            self._teams) if i != completed_team.id]

        async with asyncio.TaskGroup() as tg:
            tg.create_task(interaction.respond(f"{completed_team.team_role.mention} has completed the challenge: {challenge.title}!\nAll other teams have been frozen!"))
            for team in victim_teams:
                tg.create_task(self._send_freeze(team, next_challenges))

    async def _broadcast_challenges(self, cycle_id: int):
        await self._challenge_countdown_done.wait()
        async with self._challenge_view_lock, self._general_thread.typing():
            assert self._game.has_started
            if not self._game.is_playing:
                return
            
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self._disable_views())
                challenges = await tg.create_task(self._game.get_current_challenges())

            await self._general_thread.send("## Challenges")
            for i, c in enumerate(challenges):
                view = ChallengeView(self, i, cycle_id, self._settings.cycle_length + 10)
                self._active_challenge_views.append(view)
                await self._general_thread.send(format_challenge(c), view=view)

    async def _warning_ping(self):
        assert self._game.has_started
        self._challenge_countdown_done.clear()
        await self._countdown("New challenges", self._settings.warning_time)
        self._challenge_countdown_done.set()


def format_challenge(challenge: Challenge) -> str:
    return f"### {challenge.title}\n{challenge.description}"


GUILD_IDS = [1412516526447268075]  # NOTE: Currently only supports one guild at a time
TEAM_ROLES_IDS = [1412516839711576144, 1412516873534308446]


# TODO: Make this work with multiple games
# TODO: Make this work with multiple threads per game
class GameManager:
    def __init__(self) -> None:
        self._game_threads = {}

    async def create_game(self, ctx: discord.ApplicationContext):
        if isinstance(ctx.channel, discord.Thread):
            await ctx.respond("Cannot create a Game in a thread")
            return
        if len(self._game_threads) >= 1:
            await ctx.respond("Oops, this game only supports one at the time atm.", ephemeral=True)
            return
        
        await ctx.respond("Creating game...", ephemeral=True)
        
        thread = await ctx.channel.create_thread(name="Snake General", type=discord.ChannelType.public_thread)
        game = DiscordGame(thread, 0, [ctx.guild.get_role(i) for i in TEAM_ROLES_IDS])
        self._game_threads[thread.id] = game

    async def end_game(self, ctx: discord.ApplicationContext):
        game = self._game_threads[ctx.channel.id]
        if game is None:
            await ctx.respond("No game has been found", ephemeral=True)
            return
        try:
            await game.end_game(ctx)
        except GameError as e:
            await ctx.respond(f"{e}")
        else:
            del self._game_threads[ctx.channel.id]

    # TODO: Change this to a decorator instead of a function
    def __getitem__(self, thread_id: int) -> DiscordGame:
        return self._game_threads[thread_id]

game_manager = GameManager()
bot = discord.Bot()


@bot.command()
async def create_game(ctx: discord.ApplicationContext):
    await game_manager.create_game(ctx)


@bot.command()
async def start_game(ctx: discord.ApplicationContext):
    game = game_manager[ctx.channel.id]
    await game.start_game(ctx)

@bot.command()
async def join_game(ctx: discord.ApplicationContext, team_id: int):
    game = game_manager[ctx.channel.id]
    await game.join_game(ctx, team_id)


@bot.command()
async def end_game(ctx: discord.ApplicationContext):
    await game_manager.end_game(ctx)

if __name__ == "__main__":
    bot.run(os.environ["DISCORD_TOKEN"])