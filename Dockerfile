FROM python:3.9-slim

# Install sudo to allow the bot to run the sudo command
# The user needs to verify if this is sufficient or if they need to mount the host's sudo.
# In a standard container, 'sudo' is just the binary. The permissions come from /etc/sudoers.
RUN apt-get update && apt-get install -y sudo && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy config and source
COPY config.json .
COPY src/ ./src/

# Create a non-privileged user 'app_user'
RUN useradd -m app_user
USER app_user

# Run the bot
CMD ["python", "src/bot.py"]
