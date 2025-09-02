"""
This is a very bodged implemention of the bot which is just enough to get the game to work.
This should be significantly refactored (or completely rewritten) later to properly handle the game.
"""
import asyncio
from dataclasses import dataclass, field
from typing import Optional
import discord
from discord.ui.item import Item
from snake_game import SnakeGame, Settings, InterfaceMethods

with open("token.txt") as f:
    token = f.read().strip()
bot = discord.Bot()
guild_id = 1332689704361001001
command_lock = asyncio.Lock()


@dataclass
class Team:
    team_id: int
    thread: Optional[discord.Thread] = None
    members: list[discord.abc.Snowflake] = field(default_factory=list)


current_game = None
general_thread: Optional[discord.Thread] = None

teams = [Team(0), Team(1)]
# TODO: Assign roles to teams
team_roles = [1412368130054950944, 1412368173784891484]


@bot.application_command(guild_id=guild_id)
async def join_game(ctx: discord.ApplicationContext, team_id: int):
    assert isinstance(ctx.author, discord.Member)
    true_team_id = team_id - 1
    teams[true_team_id].members.append(ctx.author)
    await ctx.author.add_roles(ctx.guild.get_role(team_roles[true_team_id]))
    await ctx.respond(f"You have joined team {team_id}", ephemeral=True)


@bot.application_command(guild_id=guild_id)
async def start_game(ctx: discord.ApplicationContext, cycle_length: int = 120, num_challenges: int = 3):
    async with command_lock:
        global current_game
        if current_game is not None:
            await ctx.respond("A game is currently in progress", ephemeral=True)
            return

        settings = Settings(
            cycle_length=cycle_length,
            num_challenges=num_challenges
        )

        interface = InterfaceMethods(
            broadcast_challenges=broadcast_challenges,
            warning_ping=send_warning_ping
        )

        await ctx.respond("Starting game...", ephemeral=True)

        # Create threads
        general_thread = await ctx.channel.create_thread(name="Snake General", invitable=False)
        for team in teams:
            team.thread = await ctx.channel.create_thread(name=f"Team {team.team_id + 1}", invitable=False)
            assert team.thread is not None
            for user in team.members:
                await general_thread.add_user(user)
                await team.thread.add_user(user)

        current_game = SnakeGame(settings, interface)

        for i in range(5):
            await general_thread.send(f"Countdown: {5 - i}")
            await asyncio.sleep(1)

        await current_game.start_game()

    await broadcast_challenges()


@bot.application_command(guild_id=guild_id)
async def end_game(ctx: discord.ApplicationContext):
    global teams
    async with command_lock:
        global current_game
        if current_game is None:
            await ctx.respond("No game is currently in progress", ephemeral=True)
            return

        teams = [Team(0), Team(1)]

        await current_game.end_game()
        current_game = None


async def send_warning_ping():
    assert current_game is not None
    assert general_thread is not None

    warning_time = current_game._settings.warning_time
    await general_thread.send(f"{warning_time} seconds until next set of challenges!")


class ChallengeView(discord.ui.View):
    def __init__(self, challenge_id: int, cycle_id: int):
        super().__init__(timeout=120)
        self.challenge_id = challenge_id
        self.cycle_id = cycle_id

    @discord.ui.button(label="Complete Challenge", style=discord.ButtonStyle.green)
    async def complete_challenge(self, button: discord.ui.Button, interaction: discord.Interaction):
        assert current_game is not None
        assert general_thread is not None

        for view in challenge_views:
            view.disable_all_items()
        await interaction.response.send_message("Not implemented error", ephemeral=True)


challenge_views: list[ChallengeView] = []


async def broadcast_challenges():
    assert current_game is not None
    assert general_thread is not None
    raise NotImplementedError("Send out a set of challenges")


if __name__ == "__main__":
    bot.run(token)
