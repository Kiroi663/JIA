import asyncio
import random
import threading
from datetime import datetime
from flask import Flask, request, jsonify
from motor.motor_asyncio import AsyncIOMotorClient
from telethon import TelegramClient, events, Button
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.errors import UserNotParticipantError
import offreBot

app = Flask(__name__)

class JobBot:
    def __init__(self):
        self.client = None
        self.bot = None
        self.mongo_client = None
        self.initialized = False

    async def initialize(self):
        """Initialisation asynchrone des composants"""
        if self.initialized:
            return

        # Configuration du client Telegram
        self.bot = TelegramClient(
            "jobfinder_bot_session",
            offreBot.API_ID,
            offreBot.API_HASH
        ).start(bot_token=offreBot.TELEGRAM_BOT_TOKEN)

        # Connexion à MongoDB
        self.mongo_client = AsyncIOMotorClient(offreBot.MONGO_URI)
        self.db = self.mongo_client["job_database"]
        self.jobs_collection = self.db["christ"]
        self.user_favorites = self.db["user_favorites"]

        # Configuration des handlers
        self.setup_handlers()
        
        self.REQUIRED_GROUP = "JobFinderHub001"
        self.GROUP_LINK = f"https://t.me/{self.REQUIRED_GROUP}"
        self.templates = [...]  # Garder les templates précédents
        self.categories = {...}  # Garder les catégories précédentes
        self.user_states = {}
        
        self.initialized = True
        print("✅ Composants initialisés avec succès")

    def setup_handlers(self):
        """Configuration des handlers Telethon"""
        @self.bot.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            await self.handle_start(event)
        
        # Ajouter les autres handlers comme avant...

    async def run_bot(self):
        """Point d'entrée principal du bot"""
        await self.initialize()
        print("🤖 JobFinder Bot - Opérationnel")
        print(f"🔗 Groupe requis: {self.GROUP_LINK}")
        
        async def notification_loop():
            while True:
                try:
                    await self.check_new_jobs()
                    await asyncio.sleep(60)
                except Exception as e:
                    print(f"⚠️ Erreur boucle notification: {e}")
                    await asyncio.sleep(10)

        asyncio.create_task(notification_loop())
        await self.bot.run_until_disconnected()

# Initialisation globale
bot = JobBot()

# Routes Flask
@app.route('/')
def health_check():
    return "🚀 Service actif - JobFinder Bot", 200

@app.route('/api/jobs', methods=['POST'])
def add_job():
    # Validation des données comme avant...
    
    async def async_add_job():
        await bot.initialize()
        # Ajout du job...
    
    asyncio.run(async_add_job())
    return jsonify({"message": "Offre ajoutée"}), 201

def run_telegram_bot():
    """Lance le bot Telegram dans sa propre boucle d'événements"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(bot.run_bot())
    finally:
        loop.close()

if __name__ == "__main__":
    # Démarrer le bot dans un thread séparé
    bot_thread = threading.Thread(
        target=run_telegram_bot,
        daemon=True,
        name="TelegramBotThread"
    )
    bot_thread.start()

    # Démarrer Flask dans le thread principal
    app.run(host='0.0.0.0', port=10000, use_reloader=False)
