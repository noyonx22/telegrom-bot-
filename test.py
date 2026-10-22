import os
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")

client = TelegramClient("aggregator_session", api_id, api_hash)

async def main():
    me = await client.get_me()
    print("Connected successfully!")
    print("Account:", me.first_name)
    print("Username:", me.username)

with client:
    client.loop.run_until_complete(main())