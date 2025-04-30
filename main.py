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

# Configuration de l'application Flask
app = Flask(__name__)

class JobBot:
    def __init__(self):
        self._initialized = False
        self.bot = None
        self.mongo_client = None
        self.db = None
        self.jobs_collection = None
        self.user_favorites = None
        
        # Configuration des paramètres
        self.REQUIRED_GROUP = "JobFinderHub001"
        self.GROUP_LINK = f"https://t.me/{self.REQUIRED_GROUP}"
        
        self.templates = [
            "📌 *{title}* chez *{company}* à {location}.\n{resume}\n",
            "🚀 Opportunité : *{title}* !\nEntreprise : *{company}*\n📍 Localisation : {location}\n👉 {resume}\n",
            "🎯 Poste : *{title}*\n🏢 Employeur : *{company}*\n📍 Lieu : {location}\n📜 {resume}\n"
        ]
        
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
        
        self.user_states = {}

    async def initialize(self):
        """Initialisation asynchrone des composants"""
        if self._initialized:
            return

        # Configuration du client Telegram
        self.bot = TelegramClient(
            "jobfinder_session",
            offreBot.API_ID,
            offreBot.API_HASH
        )
        await self.bot.start(bot_token=offreBot.TELEGRAM_BOT_TOKEN)

        # Connexion à MongoDB
        self.mongo_client = AsyncIOMotorClient(offreBot.MONGO_URI)
        self.db = self.mongo_client["job_database"]
        self.jobs_collection = self.db["christ"]
        self.user_favorites = self.db["user_favorites"]

        # Configuration des handlers
        self.setup_handlers()
        
        self._initialized = True
        print("✅ Initialisation terminée")

    def setup_handlers(self):
        """Configuration des handlers Telethon"""

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
        """Vérifie si l'utilisateur est membre du groupe requis"""
        try:
            await self.bot(GetParticipantRequest(
                channel=self.REQUIRED_GROUP,
                participant=user_id
            ))
            return True
        except UserNotParticipantError:
            return False
        except Exception as e:
            print(f"Erreur vérification membre: {e}")
            return False

    async def handle_start(self, event):
        """Gère la commande /start"""
        user = await event.get_sender()
        if await self.is_group_member(event.sender_id):
            await self.show_welcome(event, user)
        else:
            await self.show_welcome(event, user)

    async def show_welcome(self, event, user):
        """Affiche le message de bienvenue"""
        welcome_msg = (
            f"👋 Bienvenue {user.first_name} dans JobFinder !\n\n"
            "Votre plateforme d'opportunités professionnelles\n"
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
        """Demande à l'utilisateur de rejoindre le groupe"""
        message = (
            f"Bonjour {user.first_name},\n\n"
            "Pour accéder à notre base d'offres, "
            f"veuillez rejoindre notre communauté :\n"
            f"👉 {self.GROUP_LINK}\n\n"
            "Après avoir rejoint, cliquez ci-dessous :"
        )
        buttons = [
            [Button.inline("✅ J'ai rejoint", "verify_membership")],
            [Button.url("🔗 Rejoindre maintenant", self.GROUP_LINK)]
        ]
        
        if isinstance(event, events.CallbackQuery.Event):
            await event.edit(message, buttons=buttons, parse_mode='md')
        else:
            await event.respond(message, buttons=buttons, parse_mode='md')

    async def verify_membership(self, event):
        """Vérifie si l'utilisateur a rejoint le groupe"""
        if await self.is_group_member(event.sender_id):
            user = await event.get_sender()
            await self.show_welcome(event, user)
        else:
            await event.answer("❌ Vous n'avez pas rejoint le groupe", alert=True)

    async def show_categories(self, event):
        """Affiche les catégories disponibles"""
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
        """Gère la sélection d'une catégorie"""
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
        """Affiche une page d'offres"""
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
                buttons=[Button.url("📝 Postuler", job.get("url", "#"))],
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

    async def handle_pagination(self, event):
        """Gère la pagination"""
        chat_id = event.chat_id
        if chat_id not in self.user_states:
            return

        page_num = int(event.data.decode().split('_')[1])
        self.user_states[chat_id]["current_page"] = page_num
        await self.send_job_page(event, chat_id)

    async def show_main_menu(self, event):
        """Affiche le menu principal"""
        await self.show_welcome(event, await event.get_sender())

    async def quit_category(self, event):
        """Quitte la vue des catégories"""
        chat_id = event.chat_id
        if chat_id in self.user_states:
            if self.user_states[chat_id].get("message_ids"):
                await self.bot.delete_messages(chat_id, self.user_states[chat_id]["message_ids"])
            del self.user_states[chat_id]
        await self.show_main_menu(event)

    async def show_favorites(self, event):
        """Affiche les favoris de l'utilisateur"""
        user_id = event.sender_id
        favorites = await self.user_favorites.find_one({"user_id": user_id})
        
        if not favorites or not favorites.get("categories"):
            await event.answer("⭐ Vous n'avez pas encore de favoris", alert=True)
            return

        buttons = []
        for category in favorites["categories"]:
            buttons.append([Button.inline(
                f"🔹 {category}",
                f"category_{category}"
            )])
        
        buttons.append([Button.inline("🔙 Retour", "show_main_menu")])
        
        await event.edit(
            "⭐ Vos catégories favorites :",
            buttons=buttons,
            parse_mode='md'
        )

    async def toggle_favorite_category(self, event):
        """Ajoute/retire une catégorie des favoris"""
        category = event.data.decode().split('_', 2)[2]
        user_id = event.sender_id
        
        favorites = await self.user_favorites.find_one({"user_id": user_id})
        
        if not favorites:
            await self.user_favorites.insert_one({
                "user_id": user_id,
                "categories": [category]
            })
            await event.answer(f"⭐ {category} ajouté aux favoris", alert=True)
        else:
            if category in favorites["categories"]:
                await self.user_favorites.update_one(
                    {"user_id": user_id},
                    {"$pull": {"categories": category}}
                )
                await event.answer(f"❌ {category} retiré des favoris", alert=True)
            else:
                await self.user_favorites.update_one(
                    {"user_id": user_id},
                    {"$push": {"categories": category}}
                )
                await event.answer(f"⭐ {category} ajouté aux favoris", alert=True)

    async def show_advanced_search(self, event):
        """Affiche la recherche avancée"""
        await event.answer("🔍 Fonctionnalité en développement", alert=True)

    async def run_bot(self):
        """Point d'entrée principal du bot"""
        await self.initialize()
        print("🤖 JobFinder Bot - Opérationnel")
        print(f"🔗 Groupe requis: {self.GROUP_LINK}")
        
        # Boucle de notification
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
                print(f"Erreur notification à {user['user_id']}: {e}")

# Initialisation globale
bot = JobBot()

# Routes Flask
@app.route('/')
def health_check():
    return "🚀 Service actif - JobFinder Bot", 200

@app.route('/api/jobs', methods=['POST'])
def add_job():
    if not request.is_json:
        return jsonify({"error": "Requête JSON requise"}), 400

    job_data = request.get_json()
    required_fields = ["title", "company", "location", "description", "url", "category"]
    
    if not all(field in job_data for field in required_fields):
        return jsonify({"error": "Champs manquants"}), 400

    async def async_add_job():
        await bot.initialize()
        job_data["is_notified"] = False
        await bot.jobs_collection.insert_one(job_data)
        return True

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(async_add_job())
        loop.close()
        return jsonify({"message": "Offre ajoutée avec succès"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def run_telegram_bot():
    """Lance le bot Telegram dans sa propre boucle d'événements"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(bot.run_bot())
    except Exception as e:
        print(f"⚠️ Erreur critique: {e}")
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
    app.run(host='0.0.0.0', port=10000, use_reloader=False, threaded=True)
