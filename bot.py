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

PROMOTION_CHANNEL_ID=1360204923848884244  # 🔁 Replace with your text channel ID

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.messages = True
intents.guilds = True

# Create a custom help command by removing the default one
bot = commands.Bot(command_prefix='>', intents=intents, help_command=None)

message_data_file = "message_data.json"
voice_data_file = "voice_data.json"

def load_data(file):
    if os.path.exists(file):
        try:
            with open(file, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Error loading {file}. Creating new data.")
            return {}
    return {}

def save_data(file, data):
    with open(file, "w") as f:
        json.dump(data, f)

message_data = load_data(message_data_file)
voice_data = load_data(voice_data_file)
active_voice_sessions = {}

# Thresholds for messages and voice
message_thresholds = {
    1: 200,
    2: 400,
    3: 800,
    4: 1600,
    5: 3200,
    6: 6400,
    7: 12800
}

# Voice thresholds in HOURS - will be converted to minutes internally
voice_thresholds_hours = {
    1: 9,
    2: 18,
    3: 36,
    4: 75,
    5: 150,
    6: 300,
    7: 620
}

# Convert hours to minutes for internal calculations
voice_thresholds = {level: hours * 60 for level, hours in voice_thresholds_hours.items()}

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
    print(f'Bot ID: {bot.user.id}')
    print(f'Connected to {len(bot.guilds)} guilds')
    for guild in bot.guilds:
        print(f'- {guild.name} (ID: {guild.id})')
        
    # Verify role configuration
    for guild in bot.guilds:
        print(f"\nChecking roles for {guild.name}:")
        guild_roles = {r.name: r for r in guild.roles}
        for level, role_name in rank_roles.items():
            if role_name in guild_roles:
                print(f"✅ Rank {level} role '{role_name}' exists")
            else:
                print(f"❌ Rank {level} role '{role_name}' is missing")
                
    # Print threshold information
    print("\n=== Rank Threshold Information ===")
    for level in sorted(rank_roles.keys()):
        role_name = rank_roles[level]
        msg_threshold = message_thresholds[level]
        voice_hours = voice_thresholds_hours[level]
        voice_minutes = voice_thresholds[level]
        print(f"Rank {level} ({role_name}): Messages: {msg_threshold}, Voice: {voice_hours}h ({voice_minutes}m)")
                
    # Verify promotion channel
    for guild in bot.guilds:
        promo_channel = guild.get_channel(PROMOTION_CHANNEL_ID)
        if promo_channel:
            print(f"✅ Promotion channel found: #{promo_channel.name}")
            perm = promo_channel.permissions_for(guild.me)
            if perm.send_messages:
                print("✅ Bot has permission to send messages in promotion channel")
            else:
                print("❌ Bot lacks permission to send messages in promotion channel")
        else:
            print(f"❌ Promotion channel with ID {PROMOTION_CHANNEL_ID} not found")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    uid = str(message.author.id)
    message_data[uid] = message_data.get(uid, 0) + 1
    save_data(message_data_file, message_data)
    
    print(f"Message recorded for {message.author} (ID: {uid}). Total: {message_data[uid]}")

    await update_combined_rank(message.author)
    await bot.process_commands(message)

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return
        
    uid = str(member.id)

    # User joined voice
    if after.channel and not before.channel:
        active_voice_sessions[uid] = time.time()
        print(f"{member} joined voice channel {after.channel.name}")

    # User left voice or switched channels
    if before.channel and (not after.channel or before.channel != after.channel):
        try:
            join_time = active_voice_sessions.pop(uid, None)
            if join_time:
                duration = int(time.time() - join_time)
                voice_data[uid] = voice_data.get(uid, 0) + duration
                save_data(voice_data_file, voice_data)
                
                minutes = duration // 60
                seconds = duration % 60
                total_minutes = voice_data[uid] // 60
                total_hours = total_minutes // 60
                remaining_minutes = total_minutes % 60
                
                print(f"{member} left voice after {minutes}m {seconds}s.")
                print(f"Total voice time: {total_hours}h {remaining_minutes}m ({total_minutes}m)")
                await update_combined_rank(member)
        except Exception as e:
            print(f"Error processing voice update for {member}: {e}")

    # User joined a new voice channel
    if after.channel and (not before.channel or before.channel != after.channel):
        active_voice_sessions[uid] = time.time()
        print(f"{member} joined voice channel {after.channel.name}")

async def calculate_rank(message_points, voice_minutes):
    """Calculate the highest rank a user qualifies for based on their stats."""
    highest_rank = 0
    
    # Check each rank level from highest to lowest
    for level in sorted(rank_roles.keys(), reverse=True):
        msg_threshold = message_thresholds[level]
        voice_threshold = voice_thresholds[level]  # This is now in minutes
        
        # If user meets either threshold for this rank
        if message_points >= msg_threshold or voice_minutes >= voice_threshold:
            highest_rank = level
            break
    
    return highest_rank

async def update_combined_rank(member):
    uid = str(member.id)
    message_points = message_data.get(uid, 0)
    voice_seconds = voice_data.get(uid, 0)
    voice_minutes = voice_seconds // 60
    voice_hours = voice_minutes // 60
    remaining_minutes = voice_minutes % 60

    # Debug info
    print(f"\n==== RANK UPDATE for {member} ====")
    print(f"Messages: {message_points}")
    print(f"Voice Time: {voice_hours}h {remaining_minutes}m ({voice_minutes}m total)")
    
    # Calculate highest rank user qualifies for
    highest_rank = await calculate_rank(message_points, voice_minutes)
    current_rank_name = rank_roles.get(highest_rank, "Unranked")
    print(f"Calculated rank: {current_rank_name} (Level {highest_rank})")

    # Show which thresholds were met
    if highest_rank > 0:
        msg_threshold = message_thresholds[highest_rank]
        voice_threshold_minutes = voice_thresholds[highest_rank]
        voice_threshold_hours = voice_thresholds_hours[highest_rank]
        
        if message_points >= msg_threshold:
            print(f"✅ Message threshold met: {message_points}/{msg_threshold}")
        else:
            print(f"❌ Message threshold not met: {message_points}/{msg_threshold}")
            
        if voice_minutes >= voice_threshold_minutes:
            print(f"✅ Voice threshold met: {voice_hours}h {remaining_minutes}m/{voice_threshold_hours}h")
        else:
            print(f"❌ Voice threshold not met: {voice_hours}h {remaining_minutes}m/{voice_threshold_hours}h")

    try:
        # Get all rank roles the user currently has
        guild_roles = {r.name: r for r in member.guild.roles}
        current_rank_roles = [r for r in member.roles if r.name in rank_roles.values()]
        
        # Check if user already has the correct rank
        already_has_correct_rank = False
        if highest_rank > 0:
            correct_role_name = rank_roles[highest_rank]
            correct_role = guild_roles.get(correct_role_name)
            if correct_role and correct_role in current_rank_roles:
                already_has_correct_rank = True
                print(f"User already has correct rank: {correct_role_name}")
        
        # If user has no rank roles and doesn't qualify for any, do nothing
        if not current_rank_roles and highest_rank == 0:
            print("User doesn't have any rank roles and doesn't qualify for any. No changes needed.")
            return
        
        # If user already has correct rank and no other rank roles, do nothing
        if already_has_correct_rank and len(current_rank_roles) == 1:
            print("User already has the correct rank and no other rank roles. No changes needed.")
            return
        
        # Remove all current rank roles
        roles_to_remove = []
        for role in current_rank_roles:
            if highest_rank == 0 or role.name != rank_roles[highest_rank]:
                roles_to_remove.append(role)
                print(f"Will remove role: {role.name}")
        
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)
            print(f"Removed {len(roles_to_remove)} roles from {member}")
        
        # Add the correct rank role if needed
        updated = False
        new_role = None
        
        if highest_rank > 0 and not already_has_correct_rank:
            role_name = rank_roles[highest_rank]
            if role_name in guild_roles:
                new_role = guild_roles[role_name]
                await member.add_roles(new_role)
                updated = True
                print(f"Added role {role_name} to {member}")
        
        # Send promotion message if user got a new rank
        if updated and new_role:
            # Determine promotion reason
            reason = []
            if message_points >= message_thresholds.get(highest_rank, 0):
                reason.append("TEXT DUTY")
            if voice_minutes >= voice_thresholds.get(highest_rank, 0):
                reason.append("VOICE COMMAND")

            reason_text = " and ".join(reason)

            # Send promotion message
            channel = member.guild.get_channel(PROMOTION_CHANNEL_ID)
            if channel and channel.permissions_for(member.guild.me).send_messages:
                await channel.send(
                    f"**PROMOTION ORDER**\n"
                    f"Soldier {member.mention} has been promoted to **{new_role.name}**\n"
                    f"🎖️ Reason: Exceptional performance in **{reason_text}**\n"
                    f"Carry your stripes with honour. Dismissed!"
                )
                print(f"Sent promotion message in {channel.name}")
            else:
                print(f"⚠️ Could not find or send message to channel ID: {PROMOTION_CHANNEL_ID}")
    except Exception as e:
        print(f"Error updating rank for {member}: {e}")

@bot.command(name="myrank")
async def my_rank(ctx):
    uid = str(ctx.author.id)
    msg_count = message_data.get(uid, 0)
    voice_seconds = voice_data.get(uid, 0)
    voice_minutes = voice_seconds // 60
    voice_hours = voice_minutes // 60
    remaining_minutes = voice_minutes % 60

    highest_rank = await calculate_rank(msg_count, voice_minutes)
    current_rank = rank_roles.get(highest_rank, "Unranked")

    # Debug info
    print(f"{ctx.author} requested rank info")
    print(f"Messages: {msg_count}, Voice: {voice_hours}h {remaining_minutes}m, Rank: {current_rank}")

    # Show next rank requirements
    next_rank_info = ""
    if highest_rank < 7:  # If not at max rank
        next_level = highest_rank + 1
        next_rank = rank_roles.get(next_level)
        next_msg = message_thresholds.get(next_level)
        next_voice_hours = voice_thresholds_hours.get(next_level)
        
        msg_needed = max(0, next_msg - msg_count)
        voice_minutes_needed = max(0, voice_thresholds.get(next_level) - voice_minutes)
        voice_hours_needed = voice_minutes_needed // 60
        voice_min_remaining = voice_minutes_needed % 60
        
        next_rank_info = f"\n⬆️ **Next Rank:** {next_rank}\n"
        next_rank_info += f"📝 Need {msg_needed} more messages OR\n"
        next_rank_info += f"🎙️ Need {voice_hours_needed}h {voice_min_remaining}m more voice time"

    await ctx.send(
        f"📊 **Stats for {ctx.author.mention}**\n"
        f"📝 Messages Sent: `{msg_count}`\n"
        f"🎙️ Voice Time: `{voice_hours}h {remaining_minutes}m`\n"
        f"🎖️ Rank: **{current_rank}**"
        f"{next_rank_info}"
    )

@bot.command(name="checkranks")
@commands.has_permissions(administrator=True)
async def check_ranks(ctx):
    """Admin command to check all users' ranks and fix any discrepancies"""
    await ctx.send("Starting rank check for all members. This might take a while...")
    
    count = 0
    updated = 0
    
    for member in ctx.guild.members:
        if member.bot:
            continue
            
        count += 1
        uid = str(member.id)
        msg_count = message_data.get(uid, 0)
        voice_seconds = voice_data.get(uid, 0)
        voice_minutes = voice_seconds // 60
        
        before_roles = [r.name for r in member.roles if r.name in rank_roles.values()]
        await update_combined_rank(member)
        after_roles = [r.name for r in member.roles if r.name in rank_roles.values()]
        
        if before_roles != after_roles:
            updated += 1
    
    await ctx.send(f"Rank check complete! Checked {count} members, updated {updated} ranks.")

@bot.command(name="resetdata")
@commands.has_permissions(administrator=True)
async def reset_data(ctx, user: discord.Member = None):
    """Admin command to reset data for a user or all users"""
    if user:
        uid = str(user.id)
        if uid in message_data:
            del message_data[uid]
        if uid in voice_data:
            del voice_data[uid]
        
        save_data(message_data_file, message_data)
        save_data(voice_data_file, voice_data)
        
        # Remove all rank roles
        guild_roles = {r.name: r for r in ctx.guild.roles}
        roles_to_remove = []
        for role_name in rank_roles.values():
            if role_name in guild_roles and guild_roles[role_name] in user.roles:
                roles_to_remove.append(guild_roles[role_name])
        
        if roles_to_remove:
            await user.remove_roles(*roles_to_remove)
        
        await ctx.send(f"Reset data and removed rank roles for {user.mention}")
    else:
        await ctx.send("Please specify a user to reset data for.")

@bot.command(name="addvoice")
@commands.has_permissions(administrator=True)
async def add_voice(ctx, user: discord.Member, hours: int):
    """Admin command to add voice hours to a user"""
    uid = str(user.id)
    minutes = hours * 60
    seconds = minutes * 60
    
    # Add voice time
    voice_data[uid] = voice_data.get(uid, 0) + seconds
    save_data(voice_data_file, voice_data)
    
    # Update rank
    await update_combined_rank(user)
    
    await ctx.send(f"Added {hours} hours of voice time to {user.mention}")

@bot.command(name="stats")
async def stats(ctx, user: discord.Member = None):
    """Command to check stats for a user (default: self)"""
    target = user or ctx.author
    uid = str(target.id)
    msg_count = message_data.get(uid, 0)
    voice_seconds = voice_data.get(uid, 0)
    voice_minutes = voice_seconds // 60
    voice_hours = voice_minutes // 60
    remaining_minutes = voice_minutes % 60

    highest_rank = await calculate_rank(msg_count, voice_minutes)
    current_rank = rank_roles.get(highest_rank, "Unranked")

    # Debug info
    print(f"{ctx.author} requested stats for {target}")
    print(f"Messages: {msg_count}, Voice: {voice_hours}h {remaining_minutes}m, Rank: {current_rank}")

    # Show next rank requirements
    next_rank_info = ""
    if highest_rank < 7:  # If not at max rank
        next_level = highest_rank + 1
        next_rank = rank_roles.get(next_level)
        next_msg = message_thresholds.get(next_level)
        next_voice_hours = voice_thresholds_hours.get(next_level)
        
        msg_needed = max(0, next_msg - msg_count)
        voice_minutes_needed = max(0, voice_thresholds.get(next_level) - voice_minutes)
        voice_hours_needed = voice_minutes_needed // 60
        voice_min_remaining = voice_minutes_needed % 60
        
        next_rank_info = f"\n⬆️ **Next Rank:** {next_rank}\n"
        next_rank_info += f"📝 Need {msg_needed} more messages OR\n"
        next_rank_info += f"🎙️ Need {voice_hours_needed}h {voice_min_remaining}m more voice time"

    await ctx.send(
        f"📊 **Stats for {target.mention}**\n"
        f"📝 Messages Sent: `{msg_count}`\n"
        f"🎙️ Voice Time: `{voice_hours}h {remaining_minutes}m`\n"
        f"🎖️ Rank: **{current_rank}**"
        f"{next_rank_info}"
    )

@bot.command(name="liststats")
@commands.has_permissions(administrator=True)
async def list_stats(ctx):
    """Admin command to list stats for all members"""
    stats_list = []
    for member in ctx.guild.members:
        if member.bot:
            continue
        uid = str(member.id)
        msg_count = message_data.get(uid, 0)
        voice_seconds = voice_data.get(uid, 0)
        voice_minutes = voice_seconds // 60
        voice_hours = voice_minutes // 60
        remaining_minutes = voice_minutes % 60

        highest_rank = await calculate_rank(msg_count, voice_minutes)
        current_rank = rank_roles.get(highest_rank, "Unranked")

        stats_list.append(
            f"{member.display_name}: 📝 `{msg_count}` messages, 🎙️ `{voice_hours}h {remaining_minutes}m` voice, 🎖️ Rank: **{current_rank}**"
        )

    if stats_list:
        # Split the stats list into chunks of messages under 2000 characters
        chunk_size = 2000
        message = "📋 **Member Stats:**\n"
        for stat in stats_list:
            if len(message) + len(stat) + 1 > chunk_size:
                await ctx.send(message)
                message = ""
            message += stat + "\n"
        if message:
            await ctx.send(message)
    else:
        await ctx.send("No stats available for members.")

@bot.command(name="commands")
async def command_list(ctx):
    """Replacement for the help command"""
    embed = discord.Embed(
        title="🪖 Military Rank Bot Commands",
        description="Available commands for tracking your service and progress in the ranks",
        color=discord.Color.green()
    )
    
    # User commands
    embed.add_field(
        name="📊 User Commands",
        value=(
            "**>myrank** - View your current rank and progress\n"
            "**>stats [user]** - Check stats for yourself or someone else\n"
        ),
        inline=False
    )
    
    # Admin commands - only show if user has admin permissions
    if ctx.author.guild_permissions.administrator:
        embed.add_field(
            name="⚙️ Admin Commands",
            value=(
                "**>checkranks** - Update ranks for all members\n"
                "**>resetdata [user]** - Reset data for a specific user\n"
                "**>addvoice [user] [hours]** - Add voice time to a user\n"
                "**>liststats** - List stats for all members\n"
            ),
            inline=False
        )
    
    # Add rank information
    rank_info = ""
    for level in sorted(rank_roles.keys()):
        rank_name = rank_roles[level]
        msg_req = message_thresholds[level]
        voice_req = voice_thresholds_hours[level]
        rank_info += f"**{rank_name}**: {msg_req} messages OR {voice_req} hours voice\n"
    
    embed.add_field(
        name="🎖️ Rank Requirements",
        value=rank_info,
        inline=False
    )
    
    await ctx.send(embed=embed)

bot.run(TOKEN)