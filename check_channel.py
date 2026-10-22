1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26
27
28
29
30
31
32
33
34
35
36
37
38
39
40
41
42
43
44
45
46
47
48
49
50
51
52
53
54
55
import asyncio
import os
from urllib.parse import urlparse

from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")

client = TelegramClient("aggregator_session", api_id, api_hash)

# Your public Telegram channel
CHANNEL_LINK = "https://t.me/BDLITE2"


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


async def main():
    username = extract_username(CHANNEL_LINK)

    print("Checking:", CHANNEL_LINK)
    print("Username:", username)

    try:
        entity = await client.get_entity(username)

        print("\nChannel found successfully!")
        print("Title:", getattr(entity, "title", "N/A"))
        print("Username:", getattr(entity, "username", "N/A"))
        print("ID:", entity.id)

    except Exception as e:
        print("\nCould not access this channel.")
        print("Error:", e)


with client:
    client.loop.run_until_complete(main())
