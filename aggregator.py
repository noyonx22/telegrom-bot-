import asyncio
import os
from urllib.parse import urlparse

from dotenv import load_dotenv
from telethon import TelegramClient, events

load_dotenv()

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")

SESSION_NAME = "aggregator_session"
CHANNELS_FILE = "channels.txt"

client = TelegramClient(SESSION_NAME, api_id, api_hash)


def load_channels():
    """Read public Telegram channel links/usernames from channels.txt."""
    if not os.path.exists(CHANNELS_FILE):
        print(f"ERROR: {CHANNELS_FILE} not found.")
        return []

    channels = []

    with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            # Ignore blank lines and comments
            if not line or line.startswith("#"):
                continue

            if line.startswith(("https://t.me/", "http://t.me/")):
                username = urlparse(line).path.strip("/")
            elif line.startswith("t.me/"):
                username = line[5:].strip("/")
            elif line.startswith("@"):
                username = line[1:]
            else:
                username = line

            username = username.split("?")[0].strip("/")

            if username:
                channels.append(username)

    return channels


async def main():
    channels = load_channels()

    if not channels:
        print("No channels found in channels.txt")
        return

    print("Loading channels...\n")

    entities = []

    for username in channels:
        try:
            entity = await client.get_entity(username)
            entities.append(entity)

            print(
                f"OK  | {getattr(entity, 'title', 'Unknown')} "
                f"| @{getattr(entity, 'username', username)}"
            )

        except Exception as e:
            print(f"ERROR | {username} | {e}")

    if not entities:
        print("\nNo valid channels could be loaded.")
        return

    @client.on(events.NewMessage(chats=entities))
    async def new_post(event):
        chat = await event.get_chat()
        title = getattr(chat, "title", "Unknown channel")
        username = getattr(chat, "username", None)

        print("\n" + "=" * 60)
        print("NEW POST DETECTED")
        print("Channel:", title)
        print("Username:", f"@{username}" if username else "N/A")
        print("Message ID:", event.message.id)
        print("Text:")
        print(event.message.message or "[No text / media post]")
        print("=" * 60)

    print("\nListener is running...")
    print("Waiting for new posts. Press Ctrl+C to stop.\n")

    await client.run_until_disconnected()


with client:
    client.loop.run_until_complete(main())
