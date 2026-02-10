import os
from pyrogram import Client
from dotenv import load_dotenv

# Yapılandırmayı Yükle
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

with Client("asistant", api_id=API_ID, api_hash=API_HASH) as app:
    print("\nSenin String Session Kodun:\n")
    print(app.export_session_string())
    print("\nBu kodu kopyalayıp .env dosyanıza ekleyin.")
