# Minecraft RCON & LinuxGSM Discord Bot

A powerful Discord bot that bridges your Discord server with your Minecraft server. It allows for sending RCON commands directly from Discord and managing the server lifecycle (Start/Stop/Restart) via [LinuxGSM](https://linuxgsm.com/).

## Features

- **remote Console (RCON)**: Send commands to your Minecraft server console directly from Discord (e.g., `/send op player`, `/send whitelist add player`).
- **Server Lifecycle Management**: Securely `/start`, `/stop`, and `/restart` the server using LinuxGSM integration.
- **Secure Configuration**: Uses a template-based configuration system with environment variables to keep your secrets safe.
- **Role-Based Access Control**: Restrict sensitive commands to specific Discord roles and users.
- **Docker Ready**: Includes a `Dockerfile` and `docker-compose.yml` for easy deployment.

## Prerequisites

- **Python 3.9+** (if running locally) or **Docker**.
- A Minecraft Server with **RCON enabled** in `server.properties`.
- **LinuxGSM** installed on the host (for lifecycle commands).
- **Discord Bot Token**: Obtained from the [Discord Developer Portal](https://discord.com/developers/applications).

## Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/minecraft-rcon-discord-bot.git
cd minecraft-rcon-discord-bot
```

### 2. Configuration

The bot uses a **template configuration** pattern. `config.json` defines the structure, and `.env` holds the secrets.

**Step A: Create `.env` file**
Create a file named `.env` in the `src/` directory (or root, depending on your deployment):

```env
# Your Discord Bot Token
DISCORD_TOKEN=your_bot_token_here

# Comma-separated list of Discord User IDs allowed to use RCON commands
DISCORD_ALLOWED_USERS=123456789012345678,987654321098765432

# The Role ID that allows a user to Start/Stop/Restart the server
DISCORD_ADMIN_ROLE_ID=123456789012345678

# Minecraft Server Connection Details
MINECRAFT_IP=127.0.0.1
MINECRAFT_PASS=your_rcon_password
RCON_PORT=25575
RCON_TIMEOUT=10
```

**Step B: Verify `config.json`**
Ensure `config.json` maps these keys to your environment variables (default provided in repo).

### 3. LinuxGSM Integration (Host Setup)

For the bot to execute `/start`, `/stop`, `/restart` commands, the user running the bot must have permission to execute the LinuxGSM script as the game server user.

**Add to `sudoers` on the Host:**
Run `visudo` and add the following line. Replace `app_user` with the user running the bot (or container user) and `mcserver` with your LinuxGSM user.

```bash
# Allow bot user to run the mcserver script as the mcserver user
app_user ALL=(mcserver) NOPASSWD: /home/mcserver/mcserver
```

## Deployment

### Option A: Docker (Recommended)

This requires `docker` and `docker-compose`.

1.  Edit `src/.env` with your credentials.
2.  Deploy using Docker Compose:
    ```bash
    docker-compose up -d --build
    ```
    _Note: The default `docker-compose.yml` uses `network_mode: host` to simplify connecting to a local Minecraft server._

### Option B: Portainer

1.  Create a new **Stack**.
2.  Copy the contents of `docker-compose.yml` into the web editor.
3.  Upload your `.env` file or manually define the Environment Variables in the "Environment" section.
4.  Deploy the stack.

### Option C: Manual (Python)

1.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
2.  Run the bot:
    ```bash
    python src/bot.py
    ```

## Usage

### User Commands

- **/send `<command>`**: Sends a command to the Minecraft server via RCON.
  - _Example_: `/send say Hello World`
  - _Permission_: Restricted to users in `DISCORD_ALLOWED_USERS`.

### Admin Commands

- **/start**: Starts the Minecraft server.
- **/stop**: Stops the Minecraft server.
- **/restart**: Restarts the Minecraft server.
  - _Permission_: Restricted to users with the role defined in `DISCORD_ADMIN_ROLE_ID`.

## Troubleshooting

- **Bot not responding?** Check the Docker logs (`docker logs mconbot`).
- **"Connection Refused" on RCON?** Ensure `enable-rcon=true` in `server.properties` and that the `rcon.password` matches your `.env`.
- **"Permission Denied" on /start?** Verify your `sudoers` configuration on the host machine.
