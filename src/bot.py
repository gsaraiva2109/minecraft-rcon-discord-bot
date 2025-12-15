import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from os import getenv
import json
import subprocess
import asyncio
from rcon import rcon
import os

# Load environment variables
load_dotenv()

# Load Config
def get_config_val(key, default=None):
    val = CONFIG.get(key, default)
    if isinstance(val, str) and val.startswith("ENV_"):
        env_var = val.replace("ENV_", "", 1)
        return getenv(env_var, default)
    return val

try:
    # Resolve config path relative to this script: ../config.json
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, '..', 'config.json')
    
    with open(config_path, 'r') as f:
        CONFIG = json.load(f)
        
    TOKEN = get_config_val('discord_token')
    # ALLOWED_USERS handling (string to list of ints)
    allowed_users_str = get_config_val('discord_allowed_users', '')
    ALLOWED_USERS = [int(u.strip()) for u in allowed_users_str.split(',')] if allowed_users_str else []

    # ALLOWED_CHANNELS handling
    allowed_channels_str = get_config_val('discord_allowed_channels', '')
    ALLOWED_CHANNELS = [int(ch.strip()) for ch in allowed_channels_str.split(',')] if allowed_channels_str else []
    
    IP = get_config_val('minecraft_ip')
    PASS = get_config_val('minecraft_password')
    PORT = int(get_config_val('minecraft_port', 25575))
    TIMEOUT = int(get_config_val('rcon_timeout', 10))
    ADMIN_ROLE_ID = int(get_config_val('discord_admin_role_id', 0))

except FileNotFoundError:
    print("CRITICAL: config.json not found.")
    exit(1)
except Exception as e:
    print(f"CRITICAL: Failed to load configuration: {e}")
    exit(1)

# Setup bot intents
intents = discord.Intents.default()
intents.message_content = True # Required for hybrid commands and on_message mention check

# Architect's Notes:
# We subclass commands.Bot to implement setup_hook. 
# This is the robust v2.0 way to ensure sync and status updates happen correctly on startup.

class MinecraftBot(commands.Bot):
    async def setup_hook(self):
        # Sync Commands
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

# Initialize Bot
activity = discord.Game(name="Developed by Pluppys")
bot = MinecraftBot(command_prefix="!", intents=intents, activity=activity)


# --- Checks ---
def is_allowed_channel():
    async def predicate(ctx):
        if not ALLOWED_CHANNELS:
            return True 
        
        if ctx.channel.id in ALLOWED_CHANNELS:
            return True

        embed = discord.Embed(
            title="Wrong Channel", 
            description=f"⛔ You cannot use commands here. Please go to <#{ALLOWED_CHANNELS[0]}>.", 
            color=discord.Color.red()
        )
        if ctx.interaction:
            await ctx.interaction.response.send_message(embed=embed, ephemeral=True)
        else:
             await ctx.reply(embed=embed, delete_after=5)
        return False
    return commands.check(predicate)

@bot.event
async def on_ready():
    # on_ready can be called multiple times (reconnects)
    # Status is handled in setup_hook (for initial) but we can re-assert it here just in case of weird reconnections
    # But usually setup_hook is sufficient for permanent status.
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Check for mention (Ping)
    if ALLOWED_CHANNELS and message.channel.id not in ALLOWED_CHANNELS and not isinstance(message.channel, discord.DMChannel):
         return

    if bot.user.mentioned_in(message) and message.mention_everyone is False:
        embed = discord.Embed(
            title="Minecraft Manager Bot Guide",
            description="Here is how to use the bot commands:",
            color=discord.Color.blue()
        )
        embed.add_field(name="/start", value="Start the Minecraft server (Admin only)", inline=False)
        embed.add_field(name="/stop", value="Stop the Minecraft server (Admin only)", inline=False)
        embed.add_field(name="/restart", value="Restart the Minecraft server (Admin only)", inline=False)
        embed.add_field(name="/send <cmd>", value="Send RCON command to console (Authorized users only)", inline=False)
        embed.set_footer(text="Developed by Pluppys")
        
        await message.channel.send(embed=embed)
        
    await bot.process_commands(message)

# --- Helper Function for System Commands ---
async def run_system_command(ctx, action: str):
    """
    Executes a LinuxGSM command securely via sudo.
    User must have the configured Admin Role.
    """
    # Role Check
    user_roles = [role.id for role in ctx.author.roles]
    if ADMIN_ROLE_ID not in user_roles:
        embed = discord.Embed(title="Permission Denied", description="⛔ You do not have permission to run this command.", color=discord.Color.red())
        # CTX handles both interaction and text automatically
        await ctx.reply(embed=embed, ephemeral=True) 
        return

    await ctx.defer() 

    action_verb = f"{action.capitalize()}ing"
    embed_loading = discord.Embed(
        title=f"{action.capitalize()} Server",
        description=f"⏳ **{action_verb} the Minecraft server...** Please wait.",
        color=discord.Color.orange()
    )
    msg = await ctx.send(embed=embed_loading)

    # Construct command: sudo -u mcserver /home/mcserver/mcserver <start|stop|restart>
    cmd = ["sudo", "-u", "mcserver", "/home/mcserver/mcserver", action]

    try:
        def _exec():
            return subprocess.run(cmd, capture_output=True, text=True)

        result = await asyncio.to_thread(_exec)

        if result.returncode == 0:
            # Success
            output = result.stdout[:1900] 
            embed_success = discord.Embed(
                title=f"Server {action.capitalize()} Successful",
                description=f"✅ **Action completed successfully.**",
                color=discord.Color.green()
            )
            if output:
                embed_success.add_field(name="Output", value=f"```{output}```", inline=False)
                
            await msg.edit(embed=embed_success)
        else:
            # Failure
            error_msg = result.stderr[:1900] if result.stderr else result.stdout[:1900]
            embed_fail = discord.Embed(
                title=f"Server {action.capitalize()} Failed",
                description=f"❌ **Failed to execute command.**",
                color=discord.Color.red()
            )
            embed_fail.add_field(name="Error Code", value=str(result.returncode), inline=True)
            if error_msg:
                embed_fail.add_field(name="Error Output", value=f"```{error_msg}```", inline=False)
            
            await msg.edit(embed=embed_fail)

    except Exception as e:
        embed_error = discord.Embed(title="Internal Error", description=f"❌ **An exception occurred:** {str(e)}", color=discord.Color.dark_red())
        await msg.edit(embed=embed_error)


# --- Commands (Hybrid) ---

@bot.hybrid_command(name="start", description="Start the Minecraft server")
@is_allowed_channel()
async def start_server(ctx):
    await run_system_command(ctx, "start")

@bot.hybrid_command(name="stop", description="Stop the Minecraft server")
@is_allowed_channel()
async def stop_server(ctx):
    await run_system_command(ctx, "stop")

@bot.hybrid_command(name="restart", description="Restart the Minecraft server")
@is_allowed_channel()
async def restart_server(ctx):
    await run_system_command(ctx, "restart")


@bot.hybrid_command(name="send", description="Send a command to the Minecraft server via RCON")
@app_commands.describe(command="The command to execute")
@is_allowed_channel()
async def send(ctx, command: str):
    if ctx.author.id not in ALLOWED_USERS:
        embed = discord.Embed(title="Permission Denied", description="⛔ You are not authorized to use this command.", color=discord.Color.red())
        await ctx.reply(embed=embed, ephemeral=True)
        return

    await ctx.defer(ephemeral=True)

    try:
        # Using the imported rcon context manager
        # Note: rcon.py was not modified, assuming it works as before
        with rcon(IP, PASS, PORT, timeout=TIMEOUT) as mcr:
            response = mcr.command(command)
    except Exception as e:
        embed_error = discord.Embed(title="RCON Error", description=f"Failed to send command: {e}", color=discord.Color.red())
        await ctx.send(embed=embed_error, ephemeral=True)
        return

    if not response:
        response = "No response received."

    embed_response = discord.Embed(title="RCON Command Executed", color=discord.Color.purple())
    embed_response.add_field(name="Command", value=f"```{command}```", inline=False)
    # Truncate response if too long
    if len(response) > 1024:
         response = response[:1020] + "..."
    embed_response.add_field(name="Response", value=f"```{response}```", inline=False)
    
    await ctx.send(embed=embed_response, ephemeral=True)

if __name__ == "__main__":
    bot.run(TOKEN)
