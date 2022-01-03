import os
import re
import discord
from typing import Union
from discord.ext import commands
from discord import Colour, Member, Role, PermissionOverwrite
from keep_alive import keep_alive

intents = discord.Intents.default()
intents.members = True

client = commands.Bot(command_prefix="!", case_insensitive=True, intents=intents)
players = {}

########## COMMANDS ############

@client.command(brief="Fais sonner le clocher")
async def ding(ctx):
    await ctx.send("Dong !")

@client.command(hidden=True)
async def print_players(ctx):
    players = get_member_from_role(ctx.guild, "Player")
    await ctx.send(str(len(players)) + " Players: ")
    for player in players:
        await ctx.send("<@!" + str(player.id) + ">")

@client.command(brief="Création du village", 
    help="""Construit une maison pour chaque membre avec le Role 'Player'.
    Ne pas appeler plusieurs fois de suite.""")
async def setup_maisons(ctx):
    category = await ctx.guild.create_category("Maisons")
    role_player = get_role(ctx, "Player")
    await ctx.send("Je construis des maisons pour: ")
    for player in get_member_from_role(ctx.guild, "Player"):

        role = await ctx.guild.create_role(name=player.name, color=Colour.lighter_grey(), mentionable=True)
        await player.add_roles(role)

        maison = await ctx.guild.create_text_channel("Maison de " + player.name, category=category)
        await maison.set_permissions(role, read_messages=True, send_messages=True)
        await maison.set_permissions(role_player, read_messages=False)

        vaison = await ctx.guild.create_voice_channel("Maison de " + player.name, category=category)
        await vaison.set_permissions(role, view_channel=True)
        await vaison.set_permissions(role_player, view_channel=False)

        await ctx.send(player.name)

        players[player.id] = {
            "member": player,
            "role": role,
            "maison": maison,
            "vaison": vaison
        }
    await save(ctx)

@client.command(brief="Inviter quelqu'un dans sa maison",
    help="""Invite un joueur dans sa maison.
    Ne peut pas être utilisé ailleurs que chez soi.
    !kick pour faire partir le joueur""")
async def invite(ctx, player: Union[Member, Role]):
    if await check_authorization(ctx):
        if type(player) == Member:
            player = players[player.id]["role"]
        await players[ctx.author.id]["maison"].set_permissions(player, read_messages=True, send_messages=True, read_message_history=False)
        await players[ctx.author.id]["vaison"].set_permissions(player, view_channel=True)
        await ctx.send("J'invite " + player.name + " ici :)")

@client.command(brief="Faire sortir quelqu'un de sa maison",
    help="""Kick un joueur dans sa maison.
    Ne peut pas être utilisé ailleurs que chez soi.""")
async def kick(ctx, player: Union[Member, Role]):
    if await check_authorization(ctx):
        if type(player) == Member:
            player = players[player.id]["role"]
        await players[ctx.author.id]["maison"].set_permissions(player, read_messages=False)
        await players[ctx.author.id]["vaison"].set_permissions(player, view_channel=False)
        await ctx.send("Dehors " + player.name + " !")


@client.command(brief="Renommer sa maison",
    help="""Renomme sa maison.
    Il faut mettre le nom entre guillemets s'il y a des espaces.
    Ne peut pas être utilisé en dehors de sa propre maison.
    Attention, ne peut pas être utilisé plus de 2 fois en 10 minutes.
    """)
async def renommer(ctx, nouveau_nom):
    if await check_authorization(ctx):
        player_data = get_player_from_maison(ctx.channel)
        await player_data["maison"].edit(name=nouveau_nom)
        await player_data["vaison"].edit(name=nouveau_nom)
        await ctx.send("Maison renommée en : " + nouveau_nom)

########### CLEAR ##############


@client.command(hidden=True)
async def clear_setup(ctx):
    for player in players.values():
        await player["maison"].delete()
        await player["vaison"].delete()
        await player["role"].delete()

@client.command(hidden=True)
async def full_clear(ctx):
    for channel in ctx.guild.channels:
        if channel != ctx.channel:
            await channel.delete()
    await ctx.send("J'efface les roles :")
    for role in ctx.guild.roles:
        if len(role.members) <= 1 and role.name != "Le Village":
            await ctx.send(role.name)
            await role.delete()
    global players
    players = {}

###### LOAD/SAVE ###########

@client.command(hidden=True)
async def save(ctx):
    admin_role = discord.utils.get(ctx.guild.roles, name="MJ")
    overwrites = {
        ctx.guild.default_role: PermissionOverwrite(read_messages=False),
        admin_role: PermissionOverwrite(read_messages=True)
    }
    channel = await ctx.guild.create_text_channel("memory", topic="Ne pas modifier ce channel", overwrites=overwrites)
    await channel.send("**Maisons**")
    for player in players:
        await channel.send("<@" + str(player) + "> - "
                         + "<@&" + str(players[player]["role"].id) + "> - "
                         + "<#" + str(players[player]["maison"].id) + "> - "
                         + "<#" + str(players[player]["vaison"].id) + ">")

@client.command(hidden=True)
async def load(ctx):
    global players
    pattern = re.compile("^<@([0-9]+)> - <@&([0-9]+)> - <#([0-9]+)> - <#([0-9]+)>$")
    players = {}
    channel = discord.utils.get(ctx.guild.channels, name="memory")
    async for elem in channel.history():
        match = pattern.match(elem.content)
        if match:
            players[int(match.group(1))] = {
                "member": discord.utils.get(ctx.guild.members, id=int(match.group(1))),
                "role": ctx.guild.get_role(int(match.group(2))),
                "maison": ctx.guild.get_channel(int(match.group(3))),
                "vaison": ctx.guild.get_channel(int(match.group(4)))
            }

######## UTILITY #########

def get_member_from_role(guild, role_name):
    result = []
    for member in guild.members:
        for role in member.roles:
            if role.name == role_name:
                result.append(member)
    return result

def get_role(ctx, role_name):
    for role in ctx.guild.roles:
        if role.name == role_name:
            return role

async def check_authorization(ctx):
    if not players:
        await load(ctx)
    if ctx.channel != players[ctx.author.id]["maison"]:
        await ctx.send("Vous n'avez pas le droit de faire ça ici")
        return False
    return True

def get_player_from_maison(maison):
    for player in players:
        if players[player]["maison"] == maison:
            return players[player]

def get_player_from_role(role):
    for player in players:
        if players[player]["role"] == role:
            return players[player]

######### ERRORS #########

class ErrorHandler(commands.Cog):

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        await ctx.send(str(error))
        raise error

client.add_cog(ErrorHandler())


######### EVENTS #########

@client.event
async def on_ready():
    async for guild in client.fetch_guilds(limit=150):
        print("ready " + guild.name)


keep_alive()
client.run(os.environ['TOKEN'])
