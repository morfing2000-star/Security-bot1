import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
import time
from collections import defaultdict
import json
import os
import datetime

# Bot token - Βάλε εδώ το token του bot σου
BOT_TOKEN = "MTQxMTc5NzQ3ODkzNTc2MDk4Nw.GSp4eV.jRu3cXwI4m1Usiik70768mqG1oahb8Dz1P1ba0"

# Bot setup
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Data storage
DATA_FILE = "security_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            
            # Fix missing keys in existing data
            default_settings = {
                "anti_spam": True, "anti_nuke": True, "beast_mode": False,
                "beast_mode_auto_ban": True, "beast_mode_sensitivity": 1.0,
                "max_messages": 5, "time_window": 5, "max_joins": 3, 
                "join_window": 10, "log_channel": None
            }
            
            # Ensure all guilds have proper settings
            for guild_id in data.get('settings', {}):
                for key, value in default_settings.items():
                    if key not in data['settings'][guild_id]:
                        data['settings'][guild_id][key] = value
            
            # Ensure all other keys exist
            for key in ['whitelist', 'limits', 'punishments', 'anti_nuke_settings', 'action_tracking']:
                if key not in data:
                    data[key] = {}
            
            return data
            
    return {
        "whitelist": {},
        "settings": {},
        "limits": {},
        "punishments": {},
        "anti_nuke_settings": {},
        "action_tracking": {}
    }

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# Initialize data
data = load_data()

# Anti-spam tracking
message_times = defaultdict(list)
join_times = defaultdict(list)

# Security settings
DEFAULT_SETTINGS = {
    "anti_spam": True,
    "anti_nuke": True,
    "beast_mode": False,
    "beast_mode_auto_ban": True,
    "beast_mode_sensitivity": 1.0,
    "max_messages": 5,
    "time_window": 5,
    "max_joins": 3,
    "join_window": 10,
    "log_channel": None
}

DEFAULT_LIMITS = {
    "ban_members": 2,
    "kick_members": 3,
    "create_roles": 2,
    "delete_roles": 2,
    "create_channels": 3,
    "delete_channels": 2,
    "add_bots": 1
}

BEAST_MODE_LIMITS = {
    "ban_members": 1,
    "kick_members": 1,
    "create_roles": 1,
    "delete_roles": 1,
    "create_channels": 1,
    "delete_channels": 1,
    "add_bots": 0
}

DEFAULT_PUNISHMENTS = {
    "ban_members": "ban",
    "kick_members": "kick",
    "create_roles": "ban",
    "delete_roles": "ban",
    "create_channels": "kick",
    "delete_channels": "ban",
    "add_bots": "ban"
}

BEAST_MODE_PUNISHMENTS = {
    "ban_members": "ban",
    "kick_members": "ban",
    "create_roles": "ban",
    "delete_roles": "ban",
    "create_channels": "ban",
    "delete_channels": "ban",
    "add_bots": "ban"
}

# Default anti-nuke settings for individual actions
DEFAULT_ANTI_NUKE_SETTINGS = {
    "ban_members": True,
    "kick_members": True,
    "create_roles": True,
    "delete_roles": True,
    "create_channels": True,
    "delete_channels": True,
    "add_bots": True
}

# Events
@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    
    # Initialize guild settings
    for guild in bot.guilds:
        guild_id = str(guild.id)
        
        # Βεβαιώνουμε ότι όλα τα απαραίτητα κλειδιά υπάρχουν για κάθε server
        if guild_id not in data['settings']:
            data['settings'][guild_id] = DEFAULT_SETTINGS.copy()
        else:
            # Add any missing keys to existing settings
            for key, value in DEFAULT_SETTINGS.items():
                if key not in data['settings'][guild_id]:
                    data['settings'][guild_id][key] = value
        
        if guild_id not in data['limits']:
            data['limits'][guild_id] = DEFAULT_LIMITS.copy()
        
        if guild_id not in data['punishments']:
            data['punishments'][guild_id] = DEFAULT_PUNISHMENTS.copy()
        
        if guild_id not in data['anti_nuke_settings']:
            data['anti_nuke_settings'][guild_id] = DEFAULT_ANTI_NUKE_SETTINGS.copy()
        
        if guild_id not in data['whitelist']:
            data['whitelist'][guild_id] = []
        
        if guild_id not in data['action_tracking']:
            data['action_tracking'][guild_id] = {}
    
    save_data(data)
    
    try:
        # Sync commands
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} commands")
        
        # Debug: Print all available commands
        print("📋 Available commands:")
        for command in bot.tree.get_commands():
            print(f"  - /{command.name}")
            
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

@bot.event
async def on_guild_join(guild):
    try:
        # Create security logs channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
        }

        # Create security logs channel
        log_channel = await guild.create_text_channel(
            "security-bot-logs", 
            overwrites=overwrites,
            reason="Automatic security logs channel creation"
        )

        # Update settings
        guild_id = str(guild.id)
        data['settings'][guild_id] = DEFAULT_SETTINGS.copy()
        data['settings'][guild_id]['log_channel'] = log_channel.id
        data['limits'][guild_id] = DEFAULT_LIMITS.copy()
        data['punishments'][guild_id] = DEFAULT_PUNISHMENTS.copy()
        data['anti_nuke_settings'][guild_id] = DEFAULT_ANTI_NUKE_SETTINGS.copy()
        data['whitelist'][guild_id] = []
        data['action_tracking'][guild_id] = {}

        save_data(data)

        # Send welcome message
        embed = discord.Embed(
            title="🛡️ Security Bot Enabled",
            description="This server is now protected by Security Bot. Use `/help` to see available commands.",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Logging Channel",
            value=f"All security and moderation logs will be sent to {log_channel.mention}",
            inline=False
        )
        await log_channel.send(embed=embed)
        
    except Exception as e:
        print(f"Error in on_guild_join: {e}")

@bot.event
async def on_message(message):
    # Ignore bot messages and DMs
    if message.author.bot or not message.guild:
        return await bot.process_commands(message)

    guild_id = str(message.guild.id)
    
    # Make sure guild is in data
    if guild_id not in data['settings']:
        data['settings'][guild_id] = DEFAULT_SETTINGS.copy()
        save_data(data)

    # Anti-spam system
    if data['settings'][guild_id].get('anti_spam', True):
        user_id = message.author.id
        current_time = time.time()

        # Track message times
        message_times[user_id].append(current_time)

        # Clean old messages
        message_times[user_id] = [t for t in message_times[user_id] 
                                 if current_time - t < data['settings'][guild_id].get('time_window', 5)]

        # Check if user is spamming
        max_msgs = data['settings'][guild_id].get('max_messages', 5)
        if data['settings'][guild_id].get('beast_mode', False):
            max_msgs = max(2, max_msgs - 2)  # Stricter in beast mode

        if len(message_times[user_id]) > max_msgs:
            try:
                await message.delete()
                warning_msg = await message.channel.send(f"{message.author.mention}, please stop spamming!", delete_after=5)

                # Log spam attempt
                await log_action(
                    guild_id, 
                    "security",
                    f"🚫 {message.author} was detected for spamming in {message.channel.mention}",
                    discord.Color.orange()
                )

                # Add a timeout if continues
                if len(message_times[user_id]) > max_msgs + 2:
                    try:
                        await message.author.timeout(discord.utils.utcnow() + discord.utils.timedelta(minutes=10), reason="Spamming")
                        await log_action(
                            guild_id, 
                            "mod",
                            f"⏰ {message.author} was muted for 10 minutes due to spamming",
                            discord.Color.red()
                        )
                    except:
                        pass
            except:
                pass

    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    if not member.guild:
        return
        
    guild_id = str(member.guild.id)
    
    # Make sure guild is in data
    if guild_id not in data['settings']:
        data['settings'][guild_id] = DEFAULT_SETTINGS.copy()
        save_data(data)

    # Anti-raid system
    if data['settings'][guild_id].get('anti_nuke', True):
        current_time = time.time()

        # Track join times
        join_times[guild_id].append(current_time)

        # Clean old joins
        join_times[guild_id] = [t for t in join_times[guild_id] 
                               if current_time - t < data['settings'][guild_id].get('join_window', 10)]

        # Check if this is a raid
        max_joins = data['settings'][guild_id].get('max_joins', 3)
        if data['settings'][guild_id].get('beast_mode', False):
            max_joins = max(1, max_joins - 2)  # Stricter in beast mode

        if len(join_times[guild_id]) > max_joins:
            try:
                await member.ban(reason="Anti-raid protection")
                await log_action(
                    guild_id, 
                    "security", 
                    f"🛡️ {member} was banned by anti-raid system",
                    discord.Color.red()
                )
            except:
                pass

@bot.event
async def on_member_ban(guild, user):
    guild_id = str(guild.id)
    await log_action(
        guild_id, 
        "mod", 
        f"🔨 {user} was banned from the server",
        discord.Color.red()
    )

@bot.event
async def on_member_remove(member):
    if not member.guild:
        return
        
    guild_id = str(member.guild.id)
    
    # Check if the member was kicked (not banned or left)
    try:
        async for entry in member.guild.audit_logs(limit=5, action=discord.AuditLogAction.kick):
            if entry.target.id == member.id:
                await log_action(
                    guild_id, 
                    "mod", 
                    f"👢 {member} was kicked by {entry.user}",
                    discord.Color.orange()
                )
                break
    except:
        pass

@bot.event
async def on_guild_channel_create(channel):
    if not channel.guild:
        return
        
    guild_id = str(channel.guild.id)
    
    # Make sure guild is in data
    if guild_id not in data['anti_nuke_settings']:
        return
        
    if not data['anti_nuke_settings'][guild_id].get('create_channels', True):
        return

    # Check who created the channel
    try:
        async for entry in channel.guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_create):
            if entry.target.id == channel.id:
                await check_nuke_action(
                    entry.user, 
                    guild_id, 
                    "create_channels", 
                    f"created channel {channel.name}"
                )
                break
    except:
        pass

@bot.event
async def on_guild_channel_delete(channel):
    if not channel.guild:
        return
        
    guild_id = str(channel.guild.id)
    
    # Make sure guild is in data
    if guild_id not in data['anti_nuke_settings']:
        return
        
    if not data['anti_nuke_settings'][guild_id].get('delete_channels', True):
        return

    # Check who deleted the channel
    try:
        async for entry in channel.guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_delete):
            if entry.target.id == channel.id:
                await check_nuke_action(
                    entry.user, 
                    guild_id, 
                    "delete_channels", 
                    f"deleted channel {channel.name}"
                )
                break
    except:
        pass

@bot.event
async def on_guild_role_create(role):
    if not role.guild:
        return
        
    guild_id = str(role.guild.id)
    
    # Make sure guild is in data
    if guild_id not in data['anti_nuke_settings']:
        return
        
    if not data['anti_nuke_settings'][guild_id].get('create_roles', True):
        return

    # Check who created the role
    try:
        async for entry in role.guild.audit_logs(limit=5, action=discord.AuditLogAction.role_create):
            if entry.target.id == role.id:
                await check_nuke_action(
                    entry.user, 
                    guild_id, 
                    "create_roles", 
                    f"created role {role.name}"
                )
                break
    except:
        pass

@bot.event
async def on_guild_role_delete(role):
    if not role.guild:
        return
        
    guild_id = str(role.guild.id)
    
    # Make sure guild is in data
    if guild_id not in data['anti_nuke_settings']:
        return
        
    if not data['anti_nuke_settings'][guild_id].get('delete_roles', True):
        return

    # Check who deleted the role
    try:
        async for entry in role.guild.audit_logs(limit=5, action=discord.AuditLogAction.role_delete):
            if entry.target.id == role.id:
                await check_nuke_action(
                    entry.user, 
                    guild_id, 
                    "delete_roles", 
                    f"deleted role {role.name}"
                )
                break
    except:
        pass

@bot.event
async def on_member_update(before, after):
    if not after.guild:
        return
        
    # Check for role additions
    if len(before.roles) < len(after.roles):
        new_roles = set(after.roles) - set(before.roles)
        guild_id = str(after.guild.id)

        # Check who added the role
        try:
            async for entry in after.guild.audit_logs(limit=5, action=discord.AuditLogAction.member_role_update):
                if entry.target.id == after.id:
                    for role in new_roles:
                        await log_action(
                            guild_id, 
                            "mod", 
                            f"🎭 {entry.user} added role {role.name} to {after}",
                            discord.Color.blue()
                        )
                    break
        except:
            pass

# Helper functions
async def log_action(guild_id, log_type, message, color=discord.Color.blue()):
    try:
        if guild_id not in data['settings'] or not data['settings'][guild_id].get('log_channel'):
            return
            
        channel_id = data['settings'][guild_id]['log_channel']
        channel = bot.get_channel(channel_id)

        if channel:
            # Create embed for better looking logs
            embed = discord.Embed(
                description=message,
                color=color,
                timestamp=datetime.datetime.now()
            )
            
            # Set title based on log type
            if log_type == "security":
                embed.set_author(name="🛡️ Security Log")
            elif log_type == "mod":
                embed.set_author(name="🔨 Moderation Log")
            elif log_type == "system":
                embed.set_author(name="⚙️ System Log")
            
            await channel.send(embed=embed)
    except Exception as e:
        print(f"Error logging action: {e}")

async def check_nuke_action(user, guild_id, action_type, description):
    try:
        # Ignore if user is bot or whitelisted
        if user.bot or str(user.id) in data['whitelist'].get(guild_id, []):
            return

        # Check if this specific action is enabled in anti-nuke
        if not data['anti_nuke_settings'][guild_id].get(action_type, True):
            return

        # Beast mode immediate action
        if data['settings'][guild_id].get('beast_mode', False) and data['settings'][guild_id].get('beast_mode_auto_ban', True):
            try:
                await user.ban(reason=f"Beast Mode: {description}")
                await log_action(
                    guild_id, 
                    "security", 
                    f"🦁 {user} was instantly banned by Beast Mode for {description}",
                    discord.Color.purple()
                )
                return  # Skip normal tracking in beast mode
            except Exception as e:
                print(f"Error in beast mode ban: {e}")

        # Initialize action tracking
        user_id = str(user.id)
        if user_id not in data['action_tracking'][guild_id]:
            data['action_tracking'][guild_id][user_id] = {}
            
        if action_type not in data['action_tracking'][guild_id][user_id]:
            data['action_tracking'][guild_id][user_id][action_type] = {
                "count": 0,
                "last_action": time.time()
            }

        # Update action count
        current_time = time.time()
        action_data = data['action_tracking'][guild_id][user_id][action_type]

        # Reset count if enough time has passed (60 seconds window)
        if current_time - action_data["last_action"] > 60:
            action_data["count"] = 0

        action_data["count"] += 1
        action_data["last_action"] = current_time

        # Check if user exceeded the limit
        limit = data['limits'][guild_id].get(action_type, 2)
        if action_data["count"] >= limit:
            punishment = data['punishments'][guild_id].get(action_type, "ban")

            # Apply punishment
            try:
                if punishment == "ban":
                    await user.ban(reason=f"Anti-nuke: {description}")
                    action_msg = f"banned for {description}"
                    log_color = discord.Color.red()
                elif punishment == "kick":
                    await user.kick(reason=f"Anti-nuke: {description}")
                    action_msg = f"kicked for {description}"
                    log_color = discord.Color.orange()
                elif punishment == "clear_roles":
                    for role in user.roles[1:]:  # Keep only @everyone
                        await user.remove_roles(role)
                    action_msg = f"roles cleared for {description}"
                    log_color = discord.Color.gold()

                # Log the action
                await log_action(
                    guild_id, 
                    "security", 
                    f"🛡️ {user} was {action_msg} (anti-nuke protection)",
                    log_color
                )

                # Reset count after punishment
                action_data["count"] = 0
            except Exception as e:
                print(f"Error applying punishment: {e}")

        save_data(data)
    except Exception as e:
        print(f"Error in check_nuke_action: {e}")

# Beast Mode Commands
@bot.tree.command(name="beast_mode", description="Enable or disable extreme protection mode")
@app_commands.describe(status="Enable or disable beast mode")
@app_commands.choices(status=[
    app_commands.Choice(name="enable", value="enable"),
    app_commands.Choice(name="disable", value="disable")
])
async def beast_mode_command(interaction: discord.Interaction, status: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need administrator permissions to use this command.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    enabled = status == "enable"
    
    # Βεβαιώνουμε ότι ο server υπάρχει στα δεδομένα
    if guild_id not in data['settings']:
        data['settings'][guild_id] = DEFAULT_SETTINGS.copy()
    
    data['settings'][guild_id]['beast_mode'] = enabled
    
    # Αυτόματη ρύθμιση όταν ενεργοποιείται το beast mode
    if enabled:
        # Enable all protections
        for key in data['anti_nuke_settings'][guild_id]:
            data['anti_nuke_settings'][guild_id][key] = True
        
        # Set beast mode limits and punishments
        data['limits'][guild_id] = BEAST_MODE_LIMITS.copy()
        data['punishments'][guild_id] = BEAST_MODE_PUNISHMENTS.copy()
        
        # Stricter spam protection
        data['settings'][guild_id]['max_messages'] = 3
        data['settings'][guild_id]['time_window'] = 3
        data['settings'][guild_id]['max_joins'] = 1
        
        message = "🦁 **BEAST MODE ENABLED** - Maximum security protection activated!"
        log_msg = f"🦁 **BEAST MODE ACTIVATED** by {interaction.user.mention}"
        color = discord.Color.purple()
    else:
        # Restore default settings
        data['limits'][guild_id] = DEFAULT_LIMITS.copy()
        data['punishments'][guild_id] = DEFAULT_PUNISHMENTS.copy()
        data['settings'][guild_id]['max_messages'] = 5
        data['settings'][guild_id]['time_window'] = 5
        data['settings'][guild_id]['max_joins'] = 3
        
        message = "😴 **Beast Mode Disabled** - Returning to normal security mode."
        log_msg = f"😴 **BEAST MODE DEACTIVATED** by {interaction.user.mention}"
        color = discord.Color.blue()

    save_data(data)

    await interaction.response.send_message(message, ephemeral=True)
    await log_action(guild_id, "system", log_msg, color)

@bot.tree.command(name="beast_mode_status", description="View current beast mode settings")
async def beast_mode_status_command(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need administrator permissions to use this command.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    
    # Βεβαιώνουμε ότι ο server υπάρχει στα δεδομένα
    if guild_id not in data['settings']:
        data['settings'][guild_id] = DEFAULT_SETTINGS.copy()
        save_data(data)
        
    settings = data['settings'][guild_id]

    embed = discord.Embed(
        title="🦁 Beast Mode Status",
        description="Current beast mode configuration",
        color=discord.Color.purple() if settings['beast_mode'] else discord.Color.blue()
    )

    status = "✅ **ACTIVE**" if settings['beast_mode'] else "❌ **INACTIVE**"
    embed.add_field(
        name="Status",
        value=status,
        inline=False
    )
    
    if settings['beast_mode']:
        embed.add_field(
            name="Auto Ban",
            value="✅ Enabled" if settings['beast_mode_auto_ban'] else "❌ Disabled",
            inline=True
        )
        
        embed.add_field(
            name="Sensitivity",
            value=f"{settings['beast_mode_sensitivity']}x",
            inline=True
        )
        
        embed.add_field(
            name="Protection Level",
            value="**MAXIMUM** - Zero tolerance policy",
            inline=False
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)

# Anti-Nuke Commands
@bot.tree.command(name="anti_nuke", description="Enable or disable anti-nuke protection for specific actions")
@app_commands.describe(action="The action to configure", status="Enable or disable protection")
@app_commands.choices(action=[
    app_commands.Choice(name="ban_members", value="ban_members"),
    app_commands.Choice(name="kick_members", value="kick_members"),
    app_commands.Choice(name="create_roles", value="create_roles"),
    app_commands.Choice(name="delete_roles", value="delete_roles"),
    app_commands.Choice(name="create_channels", value="create_channels"),
    app_commands.Choice(name="delete_channels", value="delete_channels"),
    app_commands.Choice(name="add_bots", value="add_bots"),
    app_commands.Choice(name="all", value="all")
])
@app_commands.choices(status=[
    app_commands.Choice(name="enable", value="enable"),
    app_commands.Choice(name="disable", value="disable")
])
async def anti_nuke_command(interaction: discord.Interaction, action: str, status: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need administrator permissions to use this command.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    enabled = status == "enable"

    # Βεβαιώνουμε ότι ο server υπάρχει στα δεδομένα
    if guild_id not in data['anti_nuke_settings']:
        data['anti_nuke_settings'][guild_id] = DEFAULT_ANTI_NUKE_SETTINGS.copy()

    if action == "all":
        # Enable/disable all actions
        for key in data['anti_nuke_settings'][guild_id]:
            data['anti_nuke_settings'][guild_id][key] = enabled

        action_text = "all anti-nuke actions"
    else:
        # Enable/disable specific action
        data['anti_nuke_settings'][guild_id][action] = enabled
        action_text = action.replace('_', ' ')

    save_data(data)

    status_text = "enabled" if enabled else "disabled"
    await interaction.response.send_message(
        f"Anti-nuke protection for {action_text} has been {status_text}.", 
        ephemeral=True
    )

    # Log the action
    await log_action(
        guild_id, 
        "security", 
        f"⚙️ {interaction.user.mention} {status_text} anti-nuke protection for {action_text}",
        discord.Color.blue()
    )

@bot.tree.command(name="anti_nuke_status", description="View current anti-nuke protection status")
async def anti_nuke_status_command(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need administrator permissions to use this command.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    
    # Βεβαιώνουμε ότι ο server υπάρχει στα δεδομένα
    if guild_id not in data['anti_nuke_settings']:
        data['anti_nuke_settings'][guild_id] = DEFAULT_ANTI_NUKE_SETTINGS.copy()
        save_data(data)
        
    anti_nuke_settings = data['anti_nuke_settings'][guild_id]

    embed = discord.Embed(
        title="Anti-Nuke Protection Status",
        description="Current status of anti-nuke protection for various actions",
        color=discord.Color.blue()
    )

    enabled_count = 0
    disabled_count = 0

    for action, enabled in anti_nuke_settings.items():
        status = "✅ Enabled" if enabled else "❌ Disabled"
        embed.add_field(
            name=action.replace('_', ' ').title(),
            value=status,
            inline=True
        )

        if enabled:
            enabled_count += 1
        else:
            disabled_count += 1

    embed.set_footer(text=f"Enabled: {enabled_count} | Disabled: {disabled_count}")

    await interaction.response.send_message(embed=embed, ephemeral=True)

# Anti-Spam Commands
@bot.tree.command(name="anti_spam", description="Enable or disable anti-spam protection")
@app_commands.describe(status="Enable or disable anti-spam")
@app_commands.choices(status=[
    app_commands.Choice(name="enable", value="enable"),
    app_commands.Choice(name="disable", value="disable")
])
async def anti_spam_command(interaction: discord.Interaction, status: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need administrator permissions to use this command.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    enabled = status == "enable"
    
    # Βεβαιώνουμε ότι ο server υπάρχει στα δεδομένα
    if guild_id not in data['settings']:
        data['settings'][guild_id] = DEFAULT_SETTINGS.copy()
        
    data['settings'][guild_id]['anti_spam'] = enabled
    save_data(data)

    status_text = "enabled" if enabled else "disabled"
    await interaction.response.send_message(
        f"Anti-spam protection has been {status_text}.", 
        ephemeral=True
    )

    # Log the action
    await log_action(
        guild_id, 
        "security", 
        f"⚙️ {interaction.user.mention} {status_text} anti-spam protection",
        discord.Color.blue()
    )

@bot.tree.command(name="set_spam_limit", description="Set anti-spam limits")
@app_commands.describe(max_messages="Max messages allowed in time window", time_window="Time window in seconds")
async def set_spam_limit_command(interaction: discord.Interaction, max_messages: int, time_window: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need administrator permissions to use this command.", ephemeral=True)
        return

    if max_messages < 1 or max_messages > 20:
        await interaction.response.send_message("Max messages must be between 1 and 20.", ephemeral=True)
        return
        
    if time_window < 1 or time_window > 60:
        await interaction.response.send_message("Time window must be between 1 and 60 seconds.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    
    # Βεβαιώνουμε ότι ο server υπάρχει στα δεδομένα
    if guild_id not in data['settings']:
        data['settings'][guild_id] = DEFAULT_SETTINGS.copy()
    
    old_max = data['settings'][guild_id]['max_messages']
    old_window = data['settings'][guild_id]['time_window']
    
    data['settings'][guild_id]['max_messages'] = max_messages
    data['settings'][guild_id]['time_window'] = time_window
    save_data(data)

    await interaction.response.send_message(
        f"Updated anti-spam limits from {old_max} messages/{old_window}s to {max_messages} messages/{time_window}s.", 
        ephemeral=True
    )

    # Log the action
    await log_action(
        guild_id, 
        "security", 
        f"⚙️ {interaction.user.mention} updated anti-spam limits to {max_messages} messages/{time_window}s",
        discord.Color.blue()
    )

@bot.tree.command(name="spam_status", description="View current anti-spam settings")
async def spam_status_command(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need administrator permissions to use this command.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    
    # Βεβαιώνουμε ότι ο server υπάρχει στα δεδομένα
    if guild_id not in data['settings']:
        data['settings'][guild_id] = DEFAULT_SETTINGS.copy()
        save_data(data)
        
    settings = data['settings'][guild_id]

    embed = discord.Embed(
        title="Anti-Spam Settings",
        description="Current anti-spam configuration",
        color=discord.Color.blue()
    )

    status = "✅ Enabled" if settings['anti_spam'] else "❌ Disabled"
    embed.add_field(
        name="Status",
        value=status,
        inline=False
    )
    
    embed.add_field(
        name="Max Messages",
        value=f"{settings['max_messages']} messages per {settings['time_window']} seconds",
        inline=True
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)

# Whitelist Commands
@bot.tree.command(name="whitelist", description="Manage whitelisted users")
@app_commands.describe(action="Add, remove or list whitelisted users", user="The user to whitelist")
@app_commands.choices(action=[
    app_commands.Choice(name="add", value="add"),
    app_commands.Choice(name="remove", value="remove"),
    app_commands.Choice(name="list", value="list")
])
async def whitelist_command(interaction: discord.Interaction, action: str, user: discord.User = None):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need administrator permissions to use this command.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)

    if guild_id not in data['whitelist']:
        data['whitelist'][guild_id] = []

    if action == "add" and user:
        if str(user.id) not in data['whitelist'][guild_id]:
            data['whitelist'][guild_id].append(str(user.id))
            save_data(data)
            await interaction.response.send_message(f"Added {user.mention} to the whitelist.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{user.mention} is already whitelisted.", ephemeral=True)

    elif action == "remove" and user:
        if str(user.id) in data['whitelist'][guild_id]:
            data['whitelist'][guild_id].remove(str(user.id))
            save_data(data)
            await interaction.response.send_message(f"Removed {user.mention} from the whitelist.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{user.mention} is not in the whitelist.", ephemeral=True)

    elif action == "list":
        if not data['whitelist'][guild_id]:
            await interaction.response.send_message("The whitelist is empty.", ephemeral=True)
        else:
            whitelist_users = [f"<@{user_id}>" for user_id in data['whitelist'][guild_id]]
            await interaction.response.send_message(
                f"Whitelisted users:\n" + "\n".join(whitelist_users), 
                ephemeral=True
            )

    else:
        await interaction.response.send_message("Invalid action or user not specified.", ephemeral=True)

# Setup Log Channel Command
@bot.tree.command(name="setup_logs", description="Setup the security logs channel")
async def setup_logs_command(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need administrator permissions to use this command.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    
    try:
        # Create or get existing channel
        existing_channel = None
        for channel in interaction.guild.channels:
            if channel.name == "security-bot-logs" and isinstance(channel, discord.TextChannel):
                existing_channel = channel
                break

        if existing_channel:
            # Use existing channel
            data['settings'][guild_id]['log_channel'] = existing_channel.id
            message = f"📝 Using existing log channel: {existing_channel.mention}"
        else:
            # Create new channel
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
            }

            log_channel = await interaction.guild.create_text_channel(
                "security-bot-logs", 
                overwrites=overwrites,
                reason="Security logs channel creation"
            )
            data['settings'][guild_id]['log_channel'] = log_channel.id
            message = f"📝 Created new log channel: {log_channel.mention}"

        save_data(data)

        # Send confirmation
        await interaction.response.send_message(message, ephemeral=True)
        
        # Send welcome message to log channel
        channel_id = data['settings'][guild_id]['log_channel']
        channel = bot.get_channel(channel_id)
        
        if channel:
            embed = discord.Embed(
                title="📝 Security Bot Logging",
                description="This channel will receive all security and moderation logs.",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now()
            )
            embed.add_field(
                name="Log Types",
                value="• 🛡️ Security Events\n• 🔨 Moderation Actions\n• ⚙️ System Changes\n• 🦁 Beast Mode Activities",
                inline=False
            )
            embed.set_footer(text=f"Setup by {interaction.user}")
            await channel.send(embed=embed)
            
    except Exception as e:
        await interaction.response.send_message(f"Error setting up log channel: {e}", ephemeral=True)

# Action Stats Command
@bot.tree.command(name="action_stats", description="View action statistics for a user")
async def action_stats_command(interaction: discord.Interaction, user: discord.User):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need administrator permissions to use this command.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    user_id = str(user.id)
    
    # Βεβαιώνουμε ότι ο server υπάρχει στα δεδομένα
    if guild_id not in data['action_tracking']:
        data['action_tracking'][guild_id] = {}
        save_data(data)
    
    if user_id not in data['action_tracking'][guild_id]:
        await interaction.response.send_message(f"No action data found for {user.mention}.", ephemeral=True)
        return
        
    user_actions = data['action_tracking'][guild_id][user_id]
    
    embed = discord.Embed(
        title=f"Action Statistics for {user}",
        description="Tracked actions and their counts",
        color=discord.Color.blue()
    )
    
    for action, action_data in user_actions.items():
        time_since_last = time.time() - action_data["last_action"]
        embed.add_field(
            name=action.replace('_', ' ').title(),
            value=f"Count: {action_data['count']}\nLast: {int(time_since_last)}s ago",
            inline=True
        )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Sync Commands Command
@bot.tree.command(name="sync_commands", description="Sync bot commands (admin only)")
async def sync_commands(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need administrator permissions to use this command.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        synced = await bot.tree.sync()
        await interaction.followup.send(f"✅ Successfully synced {len(synced)} commands!", ephemeral=True)
        
        # Print commands for debugging
        commands_list = "\n".join([f"• /{cmd.name}" for cmd in bot.tree.get_commands()])
        await interaction.followup.send(f"📋 Available commands:\n{commands_list}", ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to sync commands: {e}", ephemeral=True)

# Help Command
@bot.tree.command(name="help", description="Show all available commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🛡️ Security Bot Help",
        description="All commands for managing server security",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="🔧 Configuration",
        value="• `/setup_logs` - Setup logging channel\n• `/whitelist` - Manage whitelisted users\n• `/anti_nuke` - Configure anti-nuke\n• `/anti_spam` - Configure anti-spam",
        inline=False
    )

    embed.add_field(
        name="🦁 Beast Mode",
        value="• `/beast_mode` - Enable/disable extreme protection\n• `/beast_mode_status` - View beast mode settings",
        inline=False
    )

    embed.add_field(
        name="📊 Status",
        value="• `/anti_nuke_status` - Anti-nuke status\n• `/spam_status` - Anti-spam status\n• `/action_stats` - User action statistics",
        inline=False
    )

    embed.add_field(
        name="🛠️ Utilities",
        value="• `/sync_commands` - Sync bot commands",
        inline=False
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)

# Run the bot
if __name__ == "__main__":
    print("🚀 Starting security bot...")
    bot.run(BOT_TOKEN)