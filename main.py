import discord
from discord.ext import commands
from discord.ui import Button, View
import os
from dotenv import load_dotenv
import sqlite3
from datetime import datetime, timedelta

load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- DATABASE ----------------
conn = sqlite3.connect('delmarbot.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS warns (
    user_id INTEGER,
    reason TEXT,
    moderator TEXT
)''')
c.execute('''CREATE TABLE IF NOT EXISTS xp (
    user_id INTEGER,
    points INTEGER
)''')
c.execute('''CREATE TABLE IF NOT EXISTS roblox (
    discord_id INTEGER,
    roblox_username TEXT
)''')
conn.commit()

# ---------------- CONFIG ----------------
WELCOME_MESSAGE = """☕ 🌴Bienvenue au Café Del Mar, {user} !

Installe-toi confortablement et profite de l'ambiance 
Et choisis ton rôle pour commencer ton aventure !

 📜 Passe par le règlement
 🎶 Rejoins la terrasse vocale

Bon séjour au Café Del Mar !"""

AUTO_ROLE_ID = 1460216169930690793  # Rôle automatique
STAFF_ROLE_ID = 123456789012345678  # Remplace avec ton rôle staff


# ---------------- WELCOME & ANTI-RAID ----------------
@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name="bienvenue")
    if channel:
        await channel.send(WELCOME_MESSAGE.format(user=member.mention))
    # Ajouter rôle automatique
    role = member.guild.get_role(AUTO_ROLE_ID)
    if role:
        await member.add_roles(role)
    # Anti-raid basique
    if (datetime.utcnow() - member.created_at) < timedelta(days=3):
        await member.kick(reason="Anti-raid : compte trop récent")
        if channel:
            await channel.send(f"{member} a été kick (compte trop récent).")


# ---------------- TICKETS ----------------
class TicketView(View):

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(
            Button(label="Ouvrir un ticket",
                   style=discord.ButtonStyle.green,
                   custom_id="open_ticket"))


@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component:
        if interaction.data["custom_id"] == "open_ticket":
            guild = interaction.guild
            category = discord.utils.get(guild.categories, name="🎟️・Tickets")
            if not category:
                category = await guild.create_category("🎟️・Tickets")
            ticket_channel = await guild.create_text_channel(
                f"ticket-{interaction.user.name}", category=category)
            await ticket_channel.set_permissions(interaction.user,
                                                 read_messages=True,
                                                 send_messages=True)
            # Permissions staff
            staff_role = guild.get_role(STAFF_ROLE_ID)
            if staff_role:
                await ticket_channel.set_permissions(staff_role,
                                                     read_messages=True,
                                                     send_messages=True)
                await ticket_channel.send(
                    f"{staff_role.mention}, un nouveau ticket a été créé par {interaction.user.mention} !"
                )
            await ticket_channel.send(
                f"{interaction.user.mention}, votre ticket est ouvert !")
            await interaction.response.send_message("Ticket créé !",
                                                    ephemeral=True)


# ---------------- WARN SYSTEM ----------------
@bot.tree.command(name="warn", description="Avertir un membre")
async def warn(interaction: discord.Interaction, member: discord.Member,
               reason: str):
    c.execute("INSERT INTO warns VALUES (?, ?, ?)",
              (member.id, reason, interaction.user.name))
    conn.commit()
    await member.send(f"⚠️ Vous avez reçu un avertissement : {reason}")
    await interaction.response.send_message(
        f"{member.mention} a été averti pour : {reason}", ephemeral=True)


@bot.tree.command(name="warns", description="Voir les warns d'un membre")
async def warns(interaction: discord.Interaction, member: discord.Member):
    c.execute("SELECT reason, moderator FROM warns WHERE user_id=?",
              (member.id, ))
    results = c.fetchall()
    if not results:
        await interaction.response.send_message(
            f"{member.mention} n'a aucun warn.", ephemeral=True)
    else:
        msg = "\n".join(
            [f"{i+1}. {r[0]} (par {r[1]})" for i, r in enumerate(results)])
        await interaction.response.send_message(
            f"Warns de {member.mention} :\n{msg}", ephemeral=True)


# ---------------- MODERATION COMMANDS ----------------
@bot.tree.command(name="kick", description="Expulser un membre")
async def kick(interaction: discord.Interaction, member: discord.Member,
               reason: str):
    await member.kick(reason=reason)
    await interaction.response.send_message(
        f"{member.mention} a été expulsé pour : {reason}")


@bot.tree.command(name="ban", description="Bannir un membre")
async def ban(interaction: discord.Interaction, member: discord.Member,
              reason: str):
    await member.ban(reason=reason)
    await interaction.response.send_message(
        f"{member.mention} a été banni pour : {reason}")


# ---------------- XP SYSTEM ----------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    c.execute("SELECT points FROM xp WHERE user_id=?", (message.author.id, ))
    result = c.fetchone()
    if result:
        c.execute("UPDATE xp SET points = points + 1 WHERE user_id=?",
                  (message.author.id, ))
    else:
        c.execute("INSERT INTO xp VALUES (?, ?)", (message.author.id, 1))
    conn.commit()
    await bot.process_commands(message)


@bot.tree.command(name="xp", description="Voir votre XP")
async def xp(interaction: discord.Interaction, member: discord.Member = None):
    if not member:
        member = interaction.user
    c.execute("SELECT points FROM xp WHERE user_id=?", (member.id, ))
    result = c.fetchone()
    points = result[0] if result else 0
    await interaction.response.send_message(
        f"{member.mention} a {points} points XP.", ephemeral=True)


# ---------------- ROBLOX INTEGRATION ----------------
@bot.tree.command(name="roblox", description="Vérifier votre pseudo Roblox")
async def roblox(interaction: discord.Interaction, username: str):
    c.execute("INSERT OR REPLACE INTO roblox VALUES (?, ?)",
              (interaction.user.id, username))
    conn.commit()
    role = discord.utils.get(interaction.guild.roles, name="🎮 Membre Roblox")
    if role:
        await interaction.user.add_roles(role)
    await interaction.response.send_message(
        f"{interaction.user.mention} est maintenant lié à Roblox : {username}",
        ephemeral=True)


# ---------------- HELP COMMAND ----------------
@bot.tree.command(name="help", description="Liste toutes les commandes")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🌴☕ Commandes DelMarBot",
        description=
        "Voici toutes les commandes disponibles pour le staff et la communauté !",
        color=0xF4A261)
    embed.add_field(name="⚔️ Modération",
                    value="""
/warn <membre> <raison> - Avertir un membre
/warns <membre> - Voir les warns
/kick <membre> <raison> - Expulser un membre
/ban <membre> <raison> - Bannir un membre
""",
                    inline=False)
    embed.add_field(name="🎟️ Tickets",
                    value="""
/ticket - Ouvrir un ticket
/close_ticket - Fermer un ticket
""",
                    inline=False)
    embed.add_field(name="🌴 Communauté",
                    value="""
/xp [membre] - Voir votre XP
/roblox <pseudo> - Lier votre pseudo Roblox
""",
                    inline=False)
    embed.set_footer(text="🌅 Café Del Mar – Staff Guide")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------------- SETUP ----------------
@bot.event
async def setup_hook():
    bot.add_view(TicketView())
    await bot.tree.sync()


bot.run(TOKEN)
