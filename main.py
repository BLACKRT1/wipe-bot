import discord
from discord import app_commands
from discord.ext import commands
import os

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

LINKS = [
    {"label": "GitHub", "emoji": "🐙", "url": "https://github.com"},
    {"label": "Discord", "emoji": "💬", "url": "https://discord.gg/example"},
]

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ {bot.user} онлайн!")

@bot.tree.command(name="link", description="Приватные ссылки")
async def link(interaction: discord.Interaction):
    embed = discord.Embed(title="📌 Полезные ссылки", color=0x0bee38)
    view = discord.ui.View(timeout=30.0)
    for link in LINKS:
        view.add_item(discord.ui.Button(
            label=link["label"], emoji=link["emoji"], url=link["url"], style=discord.ButtonStyle.link
        ))
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    await discord.utils.sleep_until(discord.utils.utcnow().timestamp() + 30)
    try:
        await interaction.delete_original_response()
    except:
        pass

bot.run(TOKEN)