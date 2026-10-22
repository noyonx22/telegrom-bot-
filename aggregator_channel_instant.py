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
DESTINATION_LINK = "https://t.me/EarningBDAuto"
INSTANT_DESTINATION_LINK = "https://t.me/instandfeedbd"
INSTANT_KEYWORD = "instant"

client = TelegramClient(SESSION_NAME, api_id, api_hash)


def extract_username(link):
    link = link.strip()
    if link.startswith(("https://t.me/", "http://t.me/")):
        username = urlparse(link).path.strip("/")
    elif link.startswith("t.me/"):
        username = link[5:].strip("/")
    elif link.startswith("@"):
        username = link[1:]
    else:
        username = link
    return username.split("?")[0].strip("/")


def load_channels():
    if not os.path.exists(CHANNELS_FILE):
        print(f"ERROR: {CHANNELS_FILE} not found.")
        return []

    channels = []
    with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            username = extract_username(line)
            if username:
                channels.append(username)
    return channels


async def main():
    channels = load_channels()

    if not channels:
        print("No channels found in channels.txt")
        return

    try:
        destination = await client.get_entity(extract_username(DESTINATION_LINK))
        print(
            f"Destination OK | {getattr(destination, 'title', 'Unknown')} "
            f"| @{getattr(destination, 'username', 'N/A')}"
        )
    except Exception as e:
        print("\nCould not access destination group.")
        print("Make sure your Telegram account is a member of the group.")
        print("Error:", e)
        return

    try:
        instant_destination = await client.get_entity(
            extract_username(INSTANT_DESTINATION_LINK)
        )
        print(
            f"Instant destination OK | "
            f"{getattr(instant_destination, 'title', 'Unknown')} "
            f"| @{getattr(instant_destination, 'username', 'N/A')}"
        )
    except Exception as e:
        print("\nCould not access Instant destination channel.")
        print("Instant-only forwarding will be disabled.")
        print("Error:", e)
        instant_destination = None

    print("\nLoading source channels...\n")
    entities = []

    for username in channels:
        try:
            entity = await client.get_entity(username)
            entities.append(entity)
            print(
                f"OK | {getattr(entity, 'title', 'Unknown')} "
                f"| @{getattr(entity, 'username', username)}"
            )
        except Exception as e:
            print(f"ERROR | {username} | {e}")

    if not entities:
        print("\nNo valid source channels could be loaded.")
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

        # Every post continues to the original destination.
        try:
            await client.forward_messages(destination, event.message)
            print("FORWARDED ->", DESTINATION_LINK)
        except Exception as e:
            print("FORWARD ERROR:", e)

        # If "Instant" appears in the post text/caption, also forward it
        # to the dedicated Instant channel.
        text = event.message.message or ""
        if INSTANT_KEYWORD.casefold() in text.casefold():
            print("INSTANT DETECTED")

            if instant_destination is not None:
                try:
                    await client.forward_messages(
                        instant_destination,
                        event.message
                    )
                    print(
                        "INSTANT FORWARDED ->",
                        INSTANT_DESTINATION_LINK
                    )
                except Exception as e:
                    print("INSTANT FORWARD ERROR:", e)
            else:
                print("Instant destination unavailable.")
        else:
            print("No 'Instant' keyword -> second destination skipped.")

        print("=" * 60)

    print("\nListener is running...")
    print("New source posts will be forwarded to:")
    print(DESTINATION_LINK)
    print("Instant posts also go to:")
    print(INSTANT_DESTINATION_LINK)
    print("\nPress Ctrl+C to stop.\n")

    await client.run_until_disconnected()


with client:
    client.loop.run_until_complete(main())
