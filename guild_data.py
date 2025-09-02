from dataclasses import dataclass
import discord

@dataclass
class GuildInfo:
    guild_id: int
    team_roles: tuple[discord.Role, ...]
