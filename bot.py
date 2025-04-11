from keep_alive import keep_alive
keep_alive()

import discord
from discord.ext import commands
import json
import os
import time
from dotenv import load_dotenv  # type: ignore

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

PROMOTION_CHANNEL_ID = 1360173320426885261  # 🔁 Replace with your text channel ID

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.messages = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

message_data_file = "message_data.json"
voice_data_file = "voice_data.json"

def load_data(file):
    if os.path.exists(file):
        with open(file, "r") as f:
            return json.load(f)
    return {}

def save_data(file, data):
    with open(file, "w") as f:
        json.dump(data, f)

message_data = load_data(message_data_file)
voice_data = load_data(voice_data_file)
active_voice_sessions = {}

# Thresholds for messages and voice (in minutes)
message_thresholds = {
    1: 200,
    2: 400,
    3: 800,
    4: 1600,
    5: 3200,
    6: 6400,
    7: 12800
}

voice_thresholds = {
    1: 9,
    2: 18,
    3: 36,
    4: 75,
    5: 150,
    6: 300,
    7: 620
}

rank_roles = {
    1: "Lieutenant",
    2: "Captain",
    3: "Major",
    4: "Lieutenant Colonel",
    5: "Colonel",
    6: "Brigadier",
    7: "Major General",
}

@bot.event
async def on_ready():
    print(f'✅ Bot is online as {bot.user.name}')

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    uid = str(message.author.id)
    message_data[uid] = message_data.get(uid, 0) + 1
    save_data(message_data_file, message_data)

    await update_combined_rank(message.author)
    await bot.process_commands(message)

@bot.event
async def on_voice_state_update(member, before, after):
    uid = str(member.id)

    # User joined voice
    if after.channel and not before.channel:
        active_voice_sessions[uid] = time.time()

    # User left voice
    elif before.channel and not after.channel:
        join_time = active_voice_sessions.pop(uid, None)
        if join_time:
            duration = int(time.time() - join_time)
            voice_data[uid] = voice_data.get(uid, 0) + duration
            save_data(voice_data_file, voice_data)
            await update_combined_rank(member)

async def update_combined_rank(member):
    uid = str(member.id)
    message_points = message_data.get(uid, 0)
    voice_seconds = voice_data.get(uid, 0)
    voice_minutes = voice_seconds // 60

    highest_rank = 0
    for level in range(1, 8):
        has_voice = voice_minutes >= voice_thresholds[level]
        has_message = message_points >= message_thresholds[level]
        if has_voice or has_message:
            highest_rank = level

    guild_roles = {r.name: r for r in member.guild.roles}
    updated = False
    new_role = None

    for level in range(1, 8):
        role = guild_roles.get(rank_roles[level])
        if role:
            if level == highest_rank:
                print(f"{member} eligible for rank {highest_rank} ({rank_roles.get(highest_rank)})")
                if role not in member.roles:
                    await member.add_roles(role)
                    updated = True
                    new_role = role
            else:
                if role in member.roles:
                    await member.remove_roles(role)

    if updated and new_role:
        reason = []
        if message_points >= message_thresholds.get(highest_rank, 0):
            reason.append("TEXT DUTY")
        if voice_minutes >= voice_thresholds.get(highest_rank, 0):
            reason.append("VOICE COMMAND")

        reason_text = " and ".join(reason)

        channel = member.guild.get_channel(PROMOTION_CHANNEL_ID)
        print(f"Channel fetched: {channel}")
        print(f"Bot permissions: {channel.permissions_for(member.guild.me).send_messages}")
        if channel and channel.permissions_for(member.guild.me).send_messages:
            await channel.send(
                f"**PROMOTION ORDER**\n"
                f"Soldier {member.mention} has been promoted to **{new_role.name}**\n"
                f"🎖️ Reason: Exceptional performance in **{reason_text}**\n"
                f"Carry your stripes with honour. Dismissed!"
            )
        else:
            print(f"⚠️ Could not find or send message to channel ID: {PROMOTION_CHANNEL_ID}")


@bot.command(name="myrank")
async def my_rank(ctx):
    uid = str(ctx.author.id)
    msg_count = message_data.get(uid, 0)
    voice_seconds = voice_data.get(uid, 0)
    voice_minutes = voice_seconds // 60

    highest_rank = 0
    for level in range(1, 8):
        if msg_count >= message_thresholds[level] or voice_minutes >= voice_thresholds[level]:
            highest_rank = level

    current_rank = rank_roles.get(highest_rank, "Unranked")

    await ctx.send(
        f"📊 **Stats for {ctx.author.mention}**\n"
        f"📝 Messages Sent: `{msg_count}`\n"
        f"🎙️ Voice Time: `{voice_minutes}` minutes\n"
        f"🎖️ Rank: **{current_rank}**"
    )


# Keep-alive & Run
bot.run(TOKEN)
