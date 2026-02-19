import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta, timezone
import asyncio
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Часовой пояс МСК (UTC+3)
MSK = timezone(timedelta(hours=3))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ================= НАСТРОЙКИ ЛОГГЕРА =================
LOG_CHANNEL_ID = 1457692274694684774   # Канал для логов удалённых сообщений
MOD_LOG_CHANNEL_ID = 1457692308840517695  # ← ВСТАВЬ ID КАНАЛА ДЛЯ ЛОГОВ МОДЕРАЦИИ
IGNORED_CHANNELS = []
IGNORE_BOTS = True
# =====================================================


@bot.event
async def on_ready():
    print(f"Бот {bot.user} успешно запущен!")
    print(f"ID: {bot.user.id}")
    print("Синхронизируем slash-команды...")
    synced = await bot.tree.sync()
    print(f"Синхронизировано {len(synced)} команд.")
    print("Бот полностью готов к работе")


# ================= ЛОГИРОВАНИЕ УДАЛЁННЫХ СООБЩЕНИЙ =================
@bot.event
async def on_message_delete(message):
    if not LOG_CHANNEL_ID or message.channel.id in IGNORED_CHANNELS:
        return
    if IGNORE_BOTS and message.author.bot:
        return
    if message.type != discord.MessageType.default:
        return

    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if not log_channel:
        return

    content = message.content or "*(нет текста, только вложение)*"
    if len(content) > 1024:
        content = content[:1021] + "..."

    embed = discord.Embed(
        title="🗑️ Сообщение удалено",
        description=f"**Автор:** {message.author.mention} (`{message.author.id}`)\n"
                    f"**Канал:** {message.channel.mention}\n"
                    f"**Время:** <t:{int(message.created_at.timestamp())}:F>",
        color=discord.Color.red(),
        timestamp=datetime.now(MSK)
    )
    embed.add_field(name="📝 Содержимое:", value=content, inline=False)
    embed.set_footer(text=f"ID сообщения: {message.id}")

    if message.attachments:
        file_info = "\n".join([f"[📎 {att.filename}]({att.url})" for att in message.attachments])
        embed.add_field(name="📎 Вложения:", value=file_info, inline=False)

    try:
        await log_channel.send(embed=embed)
    except discord.Forbidden:
        print(f"⚠️ Нет прав на отправку сообщений в канал логов #{LOG_CHANNEL_ID}")
    except Exception as e:
        logging.error(f"Ошибка при логировании удаления: {e}")
# ===================================================================


# ================= 🛡️ ЛОГИРОВАНИЕ ДЕЙСТВИЙ МОДЕРАТОРОВ =================
async def send_mod_log(interaction: discord.Interaction, action: str, target: discord.Member, duration: str = None, reason: str = "Не указана", extra_fields: dict = None):
    """Отправка лога модерации в отдельный канал"""
    if not MOD_LOG_CHANNEL_ID:
        return
    
    mod_log_channel = bot.get_channel(MOD_LOG_CHANNEL_ID)
    if not mod_log_channel:
        return

    # Цвета для разных действий
    colors = {
        "mute": discord.Color.orange(),
        "unmute": discord.Color.green(),
        "ban": discord.Color.red(),
        "clean": discord.Color.blue()
    }
    icons = {
        "mute": "🔇",
        "unmute": "🔊",
        "ban": "🔨",
        "clean": "🧹"
    }

    embed = discord.Embed(
        title=f"{icons.get(action, '⚙️')} Действие модератора: {action.upper()}",
        color=colors.get(action, discord.Color.greyple()),
        timestamp=datetime.now(MSK)
    )
    embed.add_field(name="👤 Модератор", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
    embed.add_field(name="🎯 Цель", value=f"{target.mention} (`{target.id}`)", inline=False)
    
    if duration:
        embed.add_field(name="⏱ Длительность", value=duration, inline=True)
    embed.add_field(name="📝 Причина", value=reason, inline=True)
    
    if extra_fields:
        for name, value in extra_fields.items():
            embed.add_field(name=name, value=value, inline=False)
    
    embed.set_footer(text=f"Сервер: {interaction.guild.name} | ID: {interaction.guild.id}")

    try:
        await mod_log_channel.send(embed=embed)
    except discord.Forbidden:
        print(f"⚠️ Нет прав на отправку в канал модерации #{MOD_LOG_CHANNEL_ID}")
    except Exception as e:
        logging.error(f"Ошибка при логировании модерации: {e}")
# ===================================================================


# /cleanuser — удалить сообщения пользователя за период
@bot.tree.command(name="cleanuser", description="Удалить сообщения пользователя за период")
@app_commands.describe(member="Пользователь", period="Период: 30m, 2h, 1d")
@app_commands.checks.has_permissions(manage_messages=True)
async def clean_user(interaction: discord.Interaction, member: discord.Member, period: str):
    await interaction.response.defer(ephemeral=True)

    try:
        period = period.lower()
        if "m" in period:
            minutes = int(period.replace("m", ""))
            time_delta = timedelta(minutes=minutes)
        elif "h" in period:
            hours = int(period.replace("h", ""))
            time_delta = timedelta(hours=hours)
        elif "d" in period:
            days = int(period.replace("d", ""))
            time_delta = timedelta(days=days)
        else:
            await interaction.followup.send("Формат: 30m / 2h / 1d", ephemeral=True)
            return

        after_time = datetime.now(MSK) - time_delta
        deleted_count = 0

        async for msg in interaction.channel.history(limit=1000, after=after_time):
            if msg.author.id == member.id and not msg.pinned:
                await msg.delete()
                deleted_count += 1
                await asyncio.sleep(0.35)

        msg = (
            f"Удалено **{deleted_count}** сообщений от {member.mention} за {period}."
            if deleted_count > 0
            else f"У {member.mention} ничего не найдено за последние {period}."
        )
        await interaction.followup.send(msg, ephemeral=True)

        # 🛡️ Логирование действия
        await send_mod_log(
            interaction=interaction,
            action="clean",
            target=member,
            reason=f"Очистка за {period}",
            extra_fields={"🗑️ Удалено сообщений": str(deleted_count), "📍 Канал": interaction.channel.mention}
        )

    except Exception as e:
        logging.error(f"Ошибка в /cleanuser: {e}")
        await interaction.followup.send("Ошибка при очистке сообщений", ephemeral=True)


# /mute — замутить пользователя
@bot.tree.command(name="mute", description="Замутить пользователя")
@app_commands.describe(
    member="Кого мутить",
    duration="Длительность: 30m, 2h, 1d",
    reason="Причина (необязательно)"
)
@app_commands.checks.has_permissions(moderate_members=True)
async def mute_user(interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "Не указана"):
    await interaction.response.defer(ephemeral=True)

    try:
        duration = duration.lower()
        if "m" in duration:
            minutes = int(duration.replace("m", ""))
            time_delta = timedelta(minutes=minutes)
        elif "h" in duration:
            hours = int(duration.replace("h", ""))
            time_delta = timedelta(hours=hours)
        elif "d" in duration:
            days = int(duration.replace("d", ""))
            time_delta = timedelta(days=days)
        else:
            await interaction.followup.send("Формат: 30m / 2h / 1d", ephemeral=True)
            return

        end_time = datetime.now(MSK) + time_delta
        await member.timeout(end_time, reason=reason)

        moderator = interaction.user

        try:
            await member.send(
                f"**Вы получили таймаут на сервере {interaction.guild.name}**\n"
                f"От: {moderator} ({moderator.mention})\n"
                f"Длительность: {duration}\n"
                f"Причина: {reason}\n"
                f"Окончание (МСК): {end_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        except:
            pass

        await interaction.followup.send(
            f"{member.mention} замучен на {duration} | Причина: {reason}\n"
            f"Окончание (МСК): {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
            ephemeral=True
        )

        # 🛡️ Логирование действия
        await send_mod_log(
            interaction=interaction,
            action="mute",
            target=member,
            duration=duration,
            reason=reason,
            extra_fields={"⏰ Окончание (МСК)": end_time.strftime('%Y-%m-%d %H:%M:%S')}
        )

    except discord.Forbidden:
        await interaction.followup.send("Нет прав на moderate members", ephemeral=True)
    except ValueError:
        await interaction.followup.send("Неверный формат длительности", ephemeral=True)
    except Exception as e:
        logging.error(f"Ошибка в /mute: {e}")
        await interaction.followup.send("Ошибка при выдаче мута", ephemeral=True)


# /unmute — снять мут
@bot.tree.command(name="unmute", description="Снять таймаут (размутить) пользователя")
@app_commands.describe(member="Кого размутить", reason="Причина (необязательно)")
@app_commands.checks.has_permissions(moderate_members=True)
async def unmute_user(interaction: discord.Interaction, member: discord.Member, reason: str = "Не указана"):
    await interaction.response.defer(ephemeral=True)

    try:
        await member.timeout(None, reason=reason)

        moderator = interaction.user

        await interaction.followup.send(
            f"{member.mention} размучен | Причина: {reason}",
            ephemeral=True
        )

        try:
            await member.send(
                f"**Вам сняли таймаут на сервере {interaction.guild.name}**\n"
                f"Кто снял: {moderator} ({moderator.mention})\n"
                f"Причина снятия: {reason}\n"
                f"Время (МСК): {datetime.now(MSK).strftime('%Y-%m-%d %H:%M:%S')}"
            )
        except:
            pass

        # 🛡️ Логирование действия
        await send_mod_log(
            interaction=interaction,
            action="unmute",
            target=member,
            reason=reason
        )

    except discord.Forbidden:
        await interaction.followup.send("Нет прав на moderate members", ephemeral=True)
    except Exception as e:
        logging.error(f"Ошибка в /unmute: {e}")
        await interaction.followup.send("Ошибка при снятии мута", ephemeral=True)


# /ban — забанить пользователя
@bot.tree.command(name="ban", description="Забанить пользователя")
@app_commands.describe(member="Кого банить", reason="Причина (необязательно)")
@app_commands.checks.has_permissions(ban_members=True)
async def ban_user(interaction: discord.Interaction, member: discord.Member, reason: str = "Не указана"):
    await interaction.response.defer(ephemeral=True)

    try:
        moderator = interaction.user

        try:
            await member.send(
                f"**Вы получили бан на сервере {interaction.guild.name}**\n"
                f"От: {moderator} ({moderator.mention})\n"
                f"Причина: {reason}\n"
                f"Бан перманентный.\n"
                f"Время (МСК): {datetime.now(MSK).strftime('%Y-%m-%d %H:%M:%S')}"
            )
        except:
            pass

        await member.ban(reason=f"{reason} | от {moderator}")

        await interaction.followup.send(
            f"{member.mention} забанен | Причина: {reason}",
            ephemeral=True
        )

        # 🛡️ Логирование действия
        await send_mod_log(
            interaction=interaction,
            action="ban",
            target=member,
            reason=reason,
            extra_fields={"🔒 Тип": "Перманентный бан"}
        )

    except discord.Forbidden:
        await interaction.followup.send("Нет прав на бан", ephemeral=True)
    except Exception as e:
        logging.error(f"Ошибка в /ban: {e}")
        await interaction.followup.send("Ошибка при бане", ephemeral=True)


import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)