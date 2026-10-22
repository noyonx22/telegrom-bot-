import asyncio
import os
from urllib.parse import urlparse
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, UserAlreadyParticipantError, ChannelPrivateError
from telethon.tl.functions.channels import JoinChannelRequest

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

SESSION_NAME = "aggregator_session"
CHANNELS_FILE = "channels.txt"

# Main destination: receives every post
DESTINATION_LINK = "https://t.me/EarningBDAuto"

# Second destination: receives only posts containing "Instant"
INSTANT_DESTINATION_LINK = "https://t.me/instandfeedbd"
INSTANT_KEYWORD = "instant"

MAX_CONCURRENT = 1
TIMEOUT = 20
JOIN_DELAY = 5

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

            try:
                await client(JoinChannelRequest(entity))
                print(f"[{index}/{total}] JOINED  @{username}")

            except UserAlreadyParticipantError:
                print(f"[{index}/{total}] MEMBER  @{username}")

            except FloodWaitError as e:
                print(f"[{index}/{total}] RATE LIMIT @{username} ({e.seconds}s)")
                return None

            except Exception as e:
                print(
                    f"[{index}/{total}] ACCESS  @{username} "
                    f"(join skipped: {type(e).__name__})"
                )

            await asyncio.sleep(JOIN_DELAY)
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

        await asyncio.sleep(JOIN_DELAY)
        return None


async def load_sources(usernames):
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    tasks = [
        join_and_resolve(username, semaphore, i, len(usernames))
        for i, username in enumerate(usernames, 1)
    ]

    results = await asyncio.gather(*tasks)
    return [entity for entity in results if entity is not None]


async def safe_forward(destination, message, label):
    try:
        await client.forward_messages(destination, message)
        print(f"FORWARDED -> {label}")
        return True

    except FloodWaitError as e:
        print(f"{label} rate limit: waiting {e.seconds}s")
        await asyncio.sleep(e.seconds)

        try:
            await client.forward_messages(destination, message)
            print(f"FORWARDED after wait -> {label}")
            return True
        except Exception as retry_error:
            print(f"Forward retry failed -> {label}: {retry_error}")
            return False

    except Exception as e:
        print(f"Forward error -> {label}: {e}")
        return False


async def main():
    usernames = load_channels()

    if not usernames:
        print("No channels found in channels.txt")
        return

    print(f"Found {len(usernames)} unique source channels.")
    print("Joining/resolving sources...\n")

    # Main destination
    try:
        destination = await asyncio.wait_for(
            client.get_entity(extract_username(DESTINATION_LINK)),
            timeout=TIMEOUT,
        )

        print(
            f"Main destination OK: "
            f"{getattr(destination, 'title', 'Unknown')} "
            f"(@{getattr(destination, 'username', 'N/A')})"
        )

    except Exception as e:
        print("Main destination could not be accessed.")
        print("Error:", e)
        return

    # Instant destination
    try:
        instant_destination = await asyncio.wait_for(
            client.get_entity(extract_username(INSTANT_DESTINATION_LINK)),
            timeout=TIMEOUT,
        )

        print(
            f"Instant destination OK: "
            f"{getattr(instant_destination, 'title', 'Unknown')} "
            f"(@{getattr(instant_destination, 'username', 'N/A')})"
        )

    except Exception as e:
        print("Instant destination could not be accessed.")
        print("Instant forwarding will be disabled.")
        print("Error:", e)
        instant_destination = None

    sources = await load_sources(usernames)

    print("\n" + "=" * 60)
    print(f"READY: {len(sources)}/{len(usernames)} sources active")
    print("=" * 60)

    if not sources:
        print("No source channels are active.")
        return

    @client.on(events.NewMessage(chats=sources))
    async def new_post(event):
        chat = await event.get_chat()

        title = getattr(chat, "title", "Unknown")
        username = getattr(chat, "username", None)

        # Works for text-only posts and media posts with captions.
        text = (event.message.message or "").strip()

        is_instant = INSTANT_KEYWORD.casefold() in text.casefold()

        print(
            f"\nNEW POST | {title} | "
            f"@{username if username else 'unknown'} | "
            f"ID {event.message.id}"
        )

        # Every post -> main destination
        await safe_forward(
            destination,
            event.message,
            DESTINATION_LINK,
        )

        # Instant post -> second destination as well
        if is_instant:
            print("INSTANT DETECTED")

            if instant_destination is not None:
                await safe_forward(
                    instant_destination,
                    event.message,
                    INSTANT_DESTINATION_LINK,
                )
            else:
                print("Instant destination unavailable.")

        else:
            print("No 'Instant' keyword -> second destination skipped.")

    print("\n" + "=" * 60)
    print(f"Instant keyword: {INSTANT_KEYWORD}")
    print(f"Instant destination: {INSTANT_DESTINATION_LINK}")
    print("Listener is running.")
    print("Every post -> main destination")
    print("Instant posts -> main + instant destination")
    print("=" * 60)
    print("\nWaiting for new posts... Press Ctrl+C to stop.\n")

    await client.run_until_disconnected()


with client:
    client.loop.run_until_complete(main())
