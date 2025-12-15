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
intents.message_content = True # Required for hybrid commands if using prefix (though we primarily use slash)

# Initialize Bot
bot = commands.Bot(command_prefix="!", intents=intents)

# Architect's Notes:
# We are using discord.ext.commands.Bot to leverage the powerful 'hybrid_command' system.
# This allows us to easily implement slash commands with role-based access control.
# Subprocess calls are constructed as lists to prevent shell injection, adhering to Prime Directive 2.

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

# --- Helper Function for System Commands ---
async def run_system_command(interaction: discord.Interaction, action: str):
    """
    Executes a LinuxGSM command securely via sudo.
    User must have the configured Admin Role.
    """
    # Role Check
    user_roles = [role.id for role in interaction.user.roles]
    if ADMIN_ROLE_ID not in user_roles:
        await interaction.response.send_message("⛔ You do not have permission to run this command.", ephemeral=True)
        return

    # Defer response as these commands can take time
    await interaction.response.defer(ephemeral=False) # Public visibility for server lifecycle events is usually good, but let's keep it visible.

    action_verb = f"{action.capitalize()}ing"
    await interaction.followup.send(f"⏳ **{action_verb} the Minecraft server...** Please wait.")

    # Construct command: sudo -u mcserver /home/mcserver/mcserver <start|stop|restart>
    cmd = ["sudo", "-u", "mcserver", "/home/mcserver/mcserver", action]

    try:
        # Run command in a separate thread to not block the bot's event loop
        # Subprocess.run is blocking, so we run it in an executor if we strictly follow async principles,
        # but for simplicity and low load, direct call might be okay. 
        # However, to be robust, let's wrap it.
        
        def _exec():
            return subprocess.run(cmd, capture_output=True, text=True)

        result = await asyncio.to_thread(_exec)

        if result.returncode == 0:
            # Success
            # LinuxGSM output can be long, maybe just send simplest confirmation.
            # But user requested feedback based on command's output.
            # We'll truncate if too long (Discord limit 2000 chars)
            output = result.stdout[:1900] 
            await interaction.followup.send(f"✅ **Server {action} successful!**\n```{output}```")
        else:
            # Failure
            error_msg = result.stderr[:1900] if result.stderr else result.stdout[:1900]
            await interaction.followup.send(f"❌ **Failed to {action} server.**\nCode: {result.returncode}\nError:\n```{error_msg}```")

    except Exception as e:
        await interaction.followup.send(f"❌ **Internal Error:** {str(e)}")


# --- Commands ---

@bot.tree.command(name="start", description="Start the Minecraft server")
async def start_server(interaction: discord.Interaction):
    await run_system_command(interaction, "start")

@bot.tree.command(name="stop", description="Stop the Minecraft server")
async def stop_server(interaction: discord.Interaction):
    await run_system_command(interaction, "stop")

@bot.tree.command(name="restart", description="Restart the Minecraft server")
async def restart_server(interaction: discord.Interaction):
    await run_system_command(interaction, "restart")


@bot.tree.command(name="send", description="Send a command to the Minecraft server via RCON")
@app_commands.describe(command="The command to execute")
async def send(interaction: discord.Interaction, command: str):
    if interaction.user.id not in ALLOWED_USERS:
        await interaction.response.send_message("⛔ You are not authorized to use this command.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        # Using the imported rcon context manager
        # Note: rcon.py was not modified, assuming it works as before
        with rcon(IP, PASS, PORT, timeout=TIMEOUT) as mcr:
            response = mcr.command(command)
    except Exception as e:
        await interaction.followup.send(f"Failed to send command: {e}", ephemeral=True)
        return

    if not response:
        response = "No response received."

    await interaction.followup.send(f"Command executed:\n```{command}```\nResponse:\n```{response}```", ephemeral=True)

if __name__ == "__main__":
    bot.run(TOKEN)
