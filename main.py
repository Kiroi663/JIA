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

# Initialisation de l'application Flask
app = Flask(__name__)

class JobBot:
    def __init__(self):
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

        # Configuration du groupe requis
        self.REQUIRED_GROUP = "JobFinderHub001"
        self.GROUP_LINK = f"https://t.me/{self.REQUIRED_GROUP}"

        # Templates de messages
        self.templates = [
            "📌 *{title}* chez *{company}* à {location}.\n{resume}\n",
            "🚀 Opportunité : *{title}* !\nEntreprise : *{company}*\n📍 Localisation : {location}\n👉 {resume}\n",
            "🎯 Poste : *{title}*\n🏢 Employeur : *{company}*\n📍 Lieu : {location}\n📜 {resume}\n"
        ]

        # Catégories disponibles
        self.categories = {
            "Informatique / IT": ["développeur", "it", "digital"],
            "Finance / Comptabilité": ["finance", "comptable", "audit"],
            "Communication / Marketing": ["communication", "marketing"],
            "Conseil / Stratégie": ["consultant", "analyse"],
            "Transport / Logistique": ["transport", "logistique"],
            "Ingénierie / BTP": ["ingénieur", "technicien"],
            "Santé / Médical": ["santé", "hôpital"],
            "Éducation / Formation": ["éducation", "professeur"],
            "Ressources humaines": ["recrutement", "rh"],
            "Droit / Juridique": ["juridique", "avocat"],
            "Environnement": ["environnement", "écologie"],
            "Alternance / Stage": ["Alternance", "Stage"],
            "Remote": ["Remote", "A distance"],
            "Autre": []
        }

        # États utilisateur
        self.user_states = {}

        # Configuration des handlers
        self.setup_handlers()

    def setup_handlers(self):
        @self.bot.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            await self.handle_start(event)

        @self.bot.on(events.CallbackQuery(data=b'verify_membership'))
        async def verify_handler(event):
            await self.verify_membership(event)

        @self.bot.on(events.CallbackQuery(data=b'show_categories'))
        async def show_categories_handler(event):
            await self.show_categories(event)

        @self.bot.on(events.CallbackQuery(data=b'show_main_menu'))
        async def show_main_menu_handler(event):
            await self.show_main_menu(event)

        @self.bot.on(events.CallbackQuery(pattern=b'category_'))
        async def category_handler(event):
            await self.handle_category_selection(event)

        @self.bot.on(events.CallbackQuery(pattern=b'page_'))
        async def page_handler(event):
            await self.handle_pagination(event)

        @self.bot.on(events.CallbackQuery(data=b'quit_category'))
        async def quit_handler(event):
            await self.quit_category(event)

        @self.bot.on(events.CallbackQuery(data=b'show_favorites'))
        async def show_favorites_handler(event):
            await self.show_favorites(event)

        @self.bot.on(events.CallbackQuery(pattern=b'fav_category_'))
        async def fav_category_handler(event):
            await self.toggle_favorite_category(event)

        @self.bot.on(events.CallbackQuery(data=b'show_advanced_search'))
        async def show_advanced_search_handler(event):
            await self.show_advanced_search(event)

    async def is_group_member(self, user_id):
        try:
            await self.bot(GetParticipantRequest(
                channel=self.REQUIRED_GROUP,
                participant=user_id
            ))
            return True
        except UserNotParticipantError:
            return False
        except Exception as e:
            print(f"Erreur de vérification: {e}")
            return False

    async def handle_start(self, event):
        user = await event.get_sender()
        if await self.is_group_member(event.sender_id):
            await self.show_welcome(event, user)
        else:
            await self.request_join_group(event, user)

    async def show_welcome(self, event, user):
        welcome_msg = (
            f"Bienvenue {user.first_name} dans JobFinder!\n\n"
            "Votre réseau professionnel pour les meilleures opportunités.\n"
            "✅ Accès autorisé"
        )
        buttons = [
            [Button.inline("🔍 Explorer les offres", "show_categories")],
            [Button.inline("⭐ Mes favoris", "show_favorites")]
        ]
        if isinstance(event, events.CallbackQuery.Event):
            await event.edit(welcome_msg, buttons=buttons, parse_mode='md')
        else:
            await event.respond(welcome_msg, buttons=buttons, parse_mode='md')

    async def request_join_group(self, event, user):
        message = (
            f"Bonjour {user.first_name},\n\n"
            "Pour accéder à notre base d'offres d'emploi, "
            f"veuillez rejoindre notre communauté :\n"
            f"👉 {self.GROUP_LINK}\n\n"
            "Après avoir rejoint, cliquez sur le bouton ci-dessous :"
        )
        buttons = [
            [Button.inline("✅ J'ai rejoint", "verify_membership")],
            [Button.url("🔗 Rejoindre maintenant", self.GROUP_LINK)]
        ]
        if isinstance(event, events.CallbackQuery.Event):
            await event.edit(message, buttons=buttons, parse_mode='md')
        else:
            await event.respond(message, buttons=buttons, parse_mode='md')

    async def show_categories(self, event):
        if not await self.is_group_member(event.sender_id):
            await event.answer("❌ Accès réservé aux membres", alert=True)
            return

        icons = {
            "Informatique / IT": "💻", "Finance / Comptabilité": "💰",
            "Communication / Marketing": "📢", "Conseil / Stratégie": "📊",
            "Transport / Logistique": "🚚", "Ingénierie / BTP": "🏗️",
            "Santé / Médical": "🏥", "Éducation / Formation": "🎓",
            "Ressources humaines": "👥", "Droit / Juridique": "⚖️",
            "Environnement": "🌱", "Alternance / Stage": "🧑‍🎓",
            "Remote": "🌍", "Autre": "📦"
        }

        buttons = []
        for category in sorted(self.categories.keys()):
            buttons.append([Button.inline(
                f"{icons.get(category, '🔹')} {category}",
                f"category_{category}"
            )])

        buttons.append([Button.inline("🌐 Toutes les offres", "category_all")])
        buttons.append([Button.inline("🔙 Retour", "show_main_menu")])

        await event.edit(
            "📋 Sélectionnez votre domaine :",
            buttons=buttons,
            parse_mode='md'
        )

    async def handle_category_selection(self, event):
        if not await self.is_group_member(event.sender_id):
            await event.answer("❌ Accès non autorisé", alert=True)
            return

        category = event.data.decode().split('_', 1)[1]
        chat_id = event.chat_id
        query = {} if category == "all" else {"category": category}

        jobs = await self.jobs_collection.find(query).to_list(length=None)
        if not jobs:
            await event.answer(f"ℹ️ Aucune offre dans '{category}'", alert=True)
            return

        self.user_states[chat_id] = {
            "category": category,
            "current_page": 0,
            "jobs": jobs,
            "message_ids": []
        }
        await self.send_job_page(event, chat_id)

    async def send_job_page(self, event, chat_id):
        state = self.user_states.get(chat_id)
        if not state:
            return

        current_page = state["current_page"]
        jobs = state["jobs"]
        per_page = 5
        start = current_page * per_page
        page_jobs = jobs[start:start + per_page]

        # Supprimer les anciens messages
        if state.get("message_ids"):
            await self.bot.delete_messages(chat_id, state["message_ids"])
            state["message_ids"] = []

        # En-tête de page
        header = await event.respond(
            f"📄 Page {current_page + 1}/{(len(jobs) // per_page) + 1}\n"
            f"🏷️ Catégorie: {state['category']}\n"
            f"🔢 Total: {len(jobs)} offres\n"
            "────────────────────",
            parse_mode='md'
        )
        state["message_ids"].append(header.id)

        # Affichage des offres
        for job in page_jobs:
            template = random.choice(self.templates).format(
                title=job.get("title", "Titre inconnu"),
                company=job.get("company", "Entreprise inconnue"),
                location=job.get("location", "Lieu inconnu"),
                resume=job.get("description", "Plus de détails dans le lien")
            )
            msg = await event.respond(
                template,
                buttons=[[Button.url("📝 Postuler", job.get("url", "#"))],
                parse_mode='md'
            )
            state["message_ids"].append(msg.id)

        # Boutons de navigation
        nav_buttons = []
        if current_page > 0:
            nav_buttons.append(Button.inline("⬅️ Précédent", f"page_{current_page - 1}"))
        if (current_page + 1) * per_page < len(jobs):
            nav_buttons.append(Button.inline("Suivant ➡️", f"page_{current_page + 1}"))

        footer = await event.respond(
            "────────────────────\n"
            "🔎 Navigation :",
            buttons=[nav_buttons, [Button.inline("🔙 Retour", "show_categories")]],
            parse_mode='md'
        )
        state["message_ids"].append(footer.id)

    async def run_bot(self):
        print("🤖 JobFinder Bot - Prêt à fonctionner")
        print(f"🔗 Groupe requis: {self.GROUP_LINK}")
        
        # Boucle de notification
        async def notification_loop():
            while True:
                try:
                    await self.check_new_jobs()
                except Exception as e:
                    print(f"Erreur dans la boucle de notification: {e}")
                await asyncio.sleep(60)  # Vérifie toutes les minutes

        asyncio.create_task(notification_loop())
        await self.bot.run_until_disconnected()

    async def check_new_jobs(self):
        """Vérifie et notifie les nouveaux jobs"""
        new_jobs = await self.jobs_collection.find(
            {"is_notified": False}
        ).to_list(length=None)

        for job in new_jobs:
            await self.notify_subscribers(job["category"], job)
            await self.jobs_collection.update_one(
                {"_id": job["_id"]},
                {"$set": {"is_notified": True}}
            )

    async def notify_subscribers(self, category, job_data):
        """Notifie les abonnés d'une nouvelle offre"""
        subscribers = self.user_favorites.find({"categories": category})
        async for user in subscribers:
            try:
                await self.bot.send_message(
                    user["user_id"],
                    "🚨 NOUVELLE OFFRE !\n\n" + random.choice(self.templates).format(
                        title=job_data.get("title", "Titre inconnu"),
                        company=job_data.get("company", "Entreprise inconnue"),
                        location=job_data.get("location", "Lieu inconnu"),
                        resume=job_data.get("description", "Description non disponible")
                    ),
                    buttons=[[Button.url("📝 Postuler", job_data.get("url", "#"))]],
                    parse_mode='md'
                )
            except Exception as e:
                print(f"Erreur de notification à {user['user_id']}: {e}")

# Initialisation du bot
bot = JobBot()

# Routes Flask
@app.route('/')
def health_check():
    return "JobFinder Bot est en ligne!", 200

@app.route('/api/jobs', methods=['POST'])
def add_job():
    if not request.is_json:
        return jsonify({"error": "Requête JSON requise"}), 400

    job_data = request.get_json()
    required_fields = ["title", "company", "location", "description", "url", "category"]
    
    if not all(field in job_data for field in required_fields):
        return jsonify({"error": "Champs manquants"}), 400

    # Ajout asynchrone du job
    async def async_add_job():
        job_data["is_notified"] = False
        await bot.jobs_collection.insert_one(job_data)
        return True

    success = asyncio.run(async_add_job())
    
    if success:
        return jsonify({"message": "Offre ajoutée avec succès"}), 201
    else:
        return jsonify({"error": "Échec de l'ajout"}), 500

# Fonction pour exécuter le bot dans un thread séparé
def run_telegram_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(bot.run_bot())

if __name__ == "__main__":
    # Démarrer le bot Telegram dans un thread séparé
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()

    # Démarrer le serveur Flask
    app.run(host='0.0.0.0', port=10000, debug=False)
