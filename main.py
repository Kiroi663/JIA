from telethon import TelegramClient, events, Button
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.errors import UserNotParticipantError
from motor.motor_asyncio import AsyncIOMotorClient
import random
import asyncio
import offreBot
from datetime import datetime
from flask import Flask, request, jsonify
import threading

app = Flask(__name__)

class JobBot:
    def __init__(self):
        # Initialisation du bot Telegram
        self.bot = TelegramClient(
            "bot",
            offreBot.API_ID,
            offreBot.API_HASH
        ).start(bot_token=offreBot.TELEGRAM_BOT_TOKEN)

        # Connexion ASYNCHRONE à MongoDB avec Motor
        self.client = AsyncIOMotorClient(offreBot.MONGO_URI)
        self.db = self.client["job_database"]
        self.jobs_collection = self.db["christ"]
        self.user_favorites = self.db["user_favorites"]

        # Groupe requis pour l'accès
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
            "Alternance / Stage" : ["Alternance", "Stage"],
            "Remote" : ["Remote", "A distance"],
            "Autre": []
        }

        # Etats utilisateur pour pagination
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

    async def verify_membership(self, event):
        user = await event.get_sender()
        if await self.is_group_member(event.sender_id):
            await self.show_welcome(event, user)
        else:
            await event.answer("❌ Veuillez d'abord rejoindre notre communauté professionnelle", alert=True)
            await self.request_join_group(event, user)

    async def show_welcome(self, event, user):
        welcome_msg = (
            f"Bienvenue {user.first_name}\n\n"
            "JobFinder, votre réseau de référence pour découvrir les meilleures opportunités professionnelles\n\n"
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
            "Pour accéder à notre base exclusive d'offres d'emploi, "
            f"nous vous invitons à rejoindre notre communauté professionnelle :\n"
            f"👉 {self.GROUP_LINK}\n\n"
            "Après avoir rejoint, veuillez confirmer votre adhésion :"
        )
        buttons = [
            [Button.inline("✅ Confirmer mon adhésion", "verify_membership")],
            [Button.url("🔗 Accéder à la communauté", self.GROUP_LINK)]
        ]
        if isinstance(event, events.CallbackQuery.Event):
            await event.edit(message, buttons=buttons, parse_mode='md')
        else:
            await event.respond(message, buttons=buttons, parse_mode='md')

    async def show_main_menu(self, event, user=None):
        if user is None:
            user = await event.get_sender()
        welcome_msg = (
            f"👋 Bienvenue {user.first_name} dans JobFinder\n\n"
            "📍 Menu principal - Sélectionnez une option :"
        )
        buttons = [
            [Button.inline("📋 Liste des catégories", "show_categories")],
            [Button.inline("🔍 Voir toutes les offres", "category_all")],
            [Button.inline("⭐ Mes favoris", "show_favorites")],
            [Button.inline("🔎 Recherche avancée", "show_advanced_search")]
        ]
        if isinstance(event, events.CallbackQuery.Event):
            await event.edit(welcome_msg, buttons=buttons, parse_mode='md')
        else:
            await event.respond(welcome_msg, buttons=buttons, parse_mode='md')

    async def show_categories(self, event):
        if not await self.is_group_member(event.sender_id):
            await event.answer("❌ Accès réservé aux membres de notre communauté", alert=True)
            return
        icons = {
            "Informatique / IT": "💻", "Finance / Comptabilité": "💰",
            "Communication / Marketing": "📢", "Conseil / Stratégie": "📊",
            "Transport / Logistique": "🚚", "Ingénierie / BTP": "🏗️",
            "Santé / Médical": "🏥", "Éducation / Formation": "🎓",
            "Ressources humaines": "👥", "Droit / Juridique": "⚖️",
            "Environnement": "🌱", "Alternance / Stage": "🧑‍🎓",
            "Remote": "🌍","Autre": "📦"
        }
        buttons = []
        categories = sorted(self.categories.keys())
        for i in range(0, len(categories), 2):
            row = []
            for cat in categories[i:i+2]:
                row.append(Button.inline(f"{icons.get(cat, '🔹')} {cat}", f"category_{cat}"))
            buttons.append(row)
        buttons.append([Button.inline("🌐 Toutes les offres", "category_all")])
        buttons.append([Button.inline("🔙 Retour", "show_main_menu")])
        await event.edit(
            "📋 Nos secteurs d'activité :\nSélectionnez votre domaine :",
            buttons=buttons,
            parse_mode='md'
        )

    async def handle_category_selection(self, event):
        if not await self.is_group_member(event.sender_id):
            await event.answer("❌ Accès réservé aux membres de notre communauté", alert=True)
            return
        category = event.data.decode().split('_', 1)[1]
        chat_id = event.chat_id
        query = {} if category == "all" else {"category": category}
        jobs = await self.jobs_collection.find(query).to_list(length=None)
        if not jobs:
            await event.answer(f"ℹ️ Aucune offre dans '{category}' actuellement.", alert=True)
            return
        self.user_states[chat_id] = {"category": category, "current_page": 0, "jobs": jobs, "message_ids": []}
        await self.send_job_page(event, chat_id)

    async def send_job_page(self, event, chat_id):
        state = self.user_states.get(chat_id)
        if not state:
            return
        current_page = state["current_page"]
        jobs = state["jobs"]
        per_page = 5
        start = current_page * per_page
        page_jobs = jobs[start:start+per_page]
        if state.get("message_ids"):
            await self.bot.delete_messages(chat_id, state["message_ids"])
            state["message_ids"] = []
        header = await event.respond(
            f"📄 *Page {current_page+1}/{(len(jobs)//per_page)+1}*\n"
            f"🏷️ Catégorie: {state['category']}\n"
            f"🔢 Total offres: {len(jobs)}\n"
            "──────────────────────────────────",
            parse_mode='md'
        )
        state["message_ids"].append(header.id)
        for job in page_jobs:
            msg = await event.respond(
                random.choice(self.templates).format(
                    title=job.get("title", "Titre inconnu"),
                    company=job.get("company", "Entreprise inconnue"),
                    location=job.get("location", "Lieu inconnu"),
                    resume=job.get("description", "Plus de details dans le lien ci-dessous")
                ),
                buttons=[[Button.url("📝 Postuler", job.get("url", "#"))]],
                parse_mode='md'
            )
            state["message_ids"].append(msg.id)
        nav = []
        if current_page > 0:
            nav.append(Button.inline("⬅️ PRÉCÉDENT", f"page_{current_page-1}"))
        if (current_page+1)*per_page < len(jobs):
            nav.append(Button.inline("SUIVANT ➡️", f"page_{current_page+1}"))
        footer = await event.respond(
            "──────────────────────────────────\n"
            "🔎 *NAVIGATION* :",
            buttons=[nav, [Button.inline("🔙 RETOUR AU MENU", "show_categories")]],
            parse_mode='md'
        )
        state["message_ids"].append(footer.id)

    async def handle_pagination(self, event):
        chat_id = event.chat_id
        new_page = int(event.data.decode().split("_", 1)[1])
        if chat_id in self.user_states:
            self.user_states[chat_id]["current_page"] = new_page
            await self.send_job_page(event, chat_id)

    async def quit_category(self, event):
        chat_id = event.chat_id
        if chat_id in self.user_states:
            if self.user_states[chat_id].get("message_ids"):
                await self.bot.delete_messages(chat_id, self.user_states[chat_id]["message_ids"])
            del self.user_states[chat_id]
        await self.show_categories(event)

    async def show_favorites(self, event):
        if not await self.is_group_member(event.sender_id):
            await event.answer("❌ Accès réservé aux membres de notre communauté", alert=True)
            return
        user_id = event.sender_id
        user_fav = await self.user_favorites.find_one({"user_id": user_id}) or {"categories": []}
        current = user_fav.get("categories", [])
        message = (
            "⭐ Gestion des notifications\n\n"
            "🔔 Vous recevez des alertes pour :\n"
        ) + ("Aucune catégorie sélectionnée\n" if not current else "".join(f"• {c}\n" for c in current)) + (
            "\nSélectionnez une catégorie pour activer/désactiver les notifications :"
        )
        buttons = [[Button.inline(f"{'✅' if cat in current else '◻️'} {cat}", f"fav_category_{cat}")] for cat in sorted(self.categories)]
        buttons.append([Button.inline("🔙 Retour", "show_main_menu")])
        await event.edit(message, buttons=buttons, parse_mode='md')

    async def toggle_favorite_category(self, event):
        user_id = event.sender_id
        category = event.data.decode().split('_', 2)[2]
        user_fav = await self.user_favorites.find_one({"user_id": user_id}) or {"categories": []}
        current = user_fav.get("categories", [])
        if category in current:
            new = [c for c in current if c != category]
            action = "désactivées"
        else:
            new = current + [category]
            action = "activées"
        await self.user_favorites.update_one(
            {"user_id": user_id},
            {"$set": {"categories": new, "last_updated": datetime.utcnow()}},
            upsert=True
        )
        await event.answer(f"Notifications {action} pour {category}", alert=False)
        await self.show_favorites(event)

    async def notify_subscribers(self, category, job_data):
        template = random.choice(self.templates).format(
            title=job_data.get("title", "Titre inconnu"),
            company=job_data.get("company", "Entreprise inconnue"),
            location=job_data.get("location", "Lieu inconnu"),
            resume=job_data.get("description", "Plus de données via le lien ci-dessous")
        )
        buttons = [[Button.url("📝 Postuler", job_data.get("url", "#"))]]
        async for user in self.user_favorites.find({"categories": category}):
            try:
                await self.bot.send_message(
                    user["user_id"],
                    f"🚨 NOUVELLE OFFRE DANS VOS FAVORIS 🚨\n\n{template}",
                    buttons=buttons,
                    parse_mode='md'
                )
            except Exception as e:
                print(f"Erreur notification pour {user['user_id']}: {e}")

    async def add_job(self, job_data):
        job_data.setdefault("is_notified", False)
        await self.jobs_collection.insert_one(job_data)
        return True

    async def hatch_op(self):
        pending = await self.jobs_collection.find({"is_notified": False}).to_list(length=None)
        for job in pending:
            await self.notify_subscribers(job["category"], job)
            await self.jobs_collection.update_one(
                {"_id": job["_id"]},
                {"$set": {"is_notified": True, "notifiedAt": datetime.utcnow()}}
            )

    async def run_bot(self):
        print("🤖 JobFinder Professionnel - Prêt à servir")
        print(f"🔗 Communauté requise: {self.GROUP_LINK}")
        print("⭐ Système de notifications activé")
        
        # Démarrer la boucle HatchOp en arrière-plan
        async def hatch_op_loop():
            while True:
                try:
                    await self.hatch_op()
                except Exception as e:
                    print(f"Erreur in HatchOp: {e}")
                await asyncio.sleep(60)
        
        asyncio.create_task(hatch_op_loop())
        
        await self.bot.run_until_disconnected()

    async def show_advanced_search(self, event):
        await event.answer("🔎 Fonctionnalité Recherche avancée disponible prochainement", alert=True)

# Création et démarrage du bot
bot = JobBot()

# Route Flask pour vérifier que le service est en ligne
@app.route('/')
def home():
    return "JobFinder Telegram Bot is running!"

# Route pour ajouter un job via API
@app.route('/api/jobs', methods=['POST'])
def add_job_api():
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
    
    job_data = request.get_json()
    
    # Validation minimale des données
    required_fields = ["title", "company", "location", "description", "url", "category"]
    for field in required_fields:
        if field not in job_data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    # Ajout asynchrone du job
    async def add_job_async():
        return await bot.add_job(job_data)
    
    success = asyncio.run(add_job_async())
    
    if success:
        return jsonify({"message": "Job added successfully"}), 201
    else:
        return jsonify({"error": "Failed to add job"}), 500

def run_flask():
    app.run(host='0.0.0.0', port=10000)

def run_bot():
    asyncio.run(bot.run_bot())

if __name__ == "__main__":
    # Démarrer Flask dans un thread séparé
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    # Démarrer le bot Telegram dans le thread principal
    run_bot()