import asyncio
import os
from urllib.parse import urlparse

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import (
    FloodWaitError,
    UserAlreadyParticipantError,
    ChannelPrivateError,
    InviteHashExpiredError,
    InviteHashInvalidError,
)
from telethon.tl.functions.channels import JoinChannelRequest

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

SESSION_NAME = "aggregator_session"
CHANNELS_FILE = "channels.txt"
DESTINATION_LINK = "https://t.me/EarningBDAuto"

MAX_CONCURRENT = 1
TIMEOUT = 20

client = TelegramClient(
    SESSION_NAME,
    API_ID,
    API_HASH,
    sequential_updates=False,
)


def extract_username(link):
    link = link.strip()

    if link.startswith(("https://t.me/", "http://t.me/")):
        value = urlparse(link).path.strip("/")
    elif link.startswith("t.me/"):
        value = link[5:].strip("/")
    elif link.startswith("@"):
        value = link[1:]
    else:
        value = link

    return value.split("?")[0].split("/")[0].strip("/")


def load_channels():
    if not os.path.exists(CHANNELS_FILE):
        return []

    result = []
    seen = set()

    with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            username = extract_username(line)

            if username and username.lower() not in seen:
                seen.add(username.lower())
                result.append(username)

    return result


async def join_and_resolve(username, semaphore, index, total):
    async with semaphore:
        try:
            entity = await asyncio.wait_for(
                client.get_entity(username),
                timeout=TIMEOUT,
            )

            # Try to join public channels automatically.
            try:
                await client(JoinChannelRequest(entity))
                print(f"[{index}/{total}] JOINED  @{username}")
            except UserAlreadyParticipantError:
                print(f"[{index}/{total}] MEMBER  @{username}")
            except FloodWaitError as e:
                print(
                    f"[{index}/{total}] RATE LIMIT @{username} "
                    f"({e.seconds}s)"
                )
                return None
            except Exception as e:
                # Some channels can be read without joining.
                print(
                    f"[{index}/{total}] ACCESS  @{username} "
                    f"(join skipped: {type(e).__name__})"
                )

            # Deliberately wait between channels to reduce Telegram rate-limit risk.
            await asyncio.sleep(5)
            return entity

        except asyncio.TimeoutError:
            print(f"[{index}/{total}] SKIP    @{username} (timeout)")
        except ChannelPrivateError:
            print(f"[{index}/{total}] SKIP    @{username} (private)")
        except Exception as e:
            print(
                f"[{index}/{total}] SKIP    @{username} "
                f"({type(e).__name__})"
            )
            await asyncio.sleep(5)

        return None


async def load_sources(usernames):
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    tasks = [
        join_and_resolve(username, semaphore, i, len(usernames))
        for i, username in enumerate(usernames, 1)
    ]

    results = await asyncio.gather(*tasks)
    return [entity for entity in results if entity is not None]


async def main():
    usernames = load_channels()

    if not usernames:
        print("No channels found in channels.txt")
        return

    print(f"Found {len(usernames)} unique source channels.")
    print("Joining/resolving sources...\n")

    # Destination must be accessible to the logged-in account.
    try:
        destination = await asyncio.wait_for(
            client.get_entity(extract_username(DESTINATION_LINK)),
            timeout=TIMEOUT,
        )
        print(
            f"Destination OK: "
            f"{getattr(destination, 'title', 'Unknown')} "
            f"(@{getattr(destination, 'username', 'N/A')})\n"
        )
    except Exception as e:
        print("Destination channel could not be accessed.")
        print("Make sure your account can post there.")
        print("Error:", e)
        return

    sources = await load_sources(usernames)

    print("\n" + "=" * 60)
    print(f"READY: {len(sources)}/{len(usernames)} sources active")
    print("=" * 60)

    if not sources:
        print("No source channels are active.")
        return

    # Listen for new messages from all successfully resolved sources.
    @client.on(events.NewMessage(chats=sources))
    async def new_post(event):
        chat = await event.get_chat()
        title = getattr(chat, "title", "Unknown")
        username = getattr(chat, "username", None)

        print(
            f"\nNEW POST | {title} | "
            f"@{username if username else 'unknown'} | "
            f"ID {event.message.id}"
        )

        try:
            await client.forward_messages(destination, event.message)
            print("FORWARDED ->", DESTINATION_LINK)
        except FloodWaitError as e:
            print(f"Forward rate limit: waiting {e.seconds}s")
            await asyncio.sleep(e.seconds)
            try:
                await client.forward_messages(destination, event.message)
                print("FORWARDED after wait")
            except Exception as retry_error:
                print("Forward retry failed:", retry_error)
        except Exception as e:
            print("Forward error:", e)

    print("\nListener is running.")
    print("New posts from active sources will be forwarded automatically.")
    print("Press Ctrl+C to stop.\n")

    await client.run_until_disconnected()


with client:
    client.loop.run_until_complete(main())
