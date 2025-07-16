import os
import logging
import asyncio
import feedparser
import requests
from datetime import datetime
from typing import Optional
import random

# Telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler

# Groq for translation
from groq import Groq

# YouTube API
from googleapiclient.discovery import build

# Flask for keep alive
from flask import Flask
from threading import Thread

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for conversation handler
WAITING_FOR_WORLD, WAITING_FOR_DIAMOND, WAITING_FOR_VIDEO = range(3)

class HistoryBot:
    def __init__(self):
        # Environment variables
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.groq_api_key = os.getenv('GROQ_API_KEY')
        self.youtube_api_key = os.getenv('YOUTUBE_API_KEY')
        
        # Initialize APIs
        self.groq_client = Groq(api_key=self.groq_api_key)
        self.youtube = build('youtube', 'v3', developerKey=self.youtube_api_key)
        
        # RSS sources
        self.history_rss = "https://www.history.com/.rss/full"
        self.natgeo_rss = "https://www.nationalgeographic.com/pages/feed/"
        
        # Diamond sources (rotate daily)
        self.diamond_sources = [
            {
                "name": "Natural Diamond Council",
                "url": "https://www.naturaldiamonds.com/journal/",
                "topics": ["cullinan diamond history", "hope diamond facts", "famous diamonds timeline"]
            },
            {
                "name": "Smithsonian",
                "url": "https://www.si.edu/",
                "topics": ["hope diamond smithsonian", "famous gems history", "diamond collection"]
            },
            {
                "name": "Royal Collection Trust",
                "url": "https://www.rct.uk/",
                "topics": ["crown jewels diamonds", "cullinan diamond story", "royal diamonds history"]
            }
        ]

    async def translate_to_hebrew(self, text: str, context: str = "") -> str:
        """Translate text to Hebrew using Groq"""
        try:
            prompt = f"""
            תרגם את הטקסט הבא לעברית טבעית ונאה. 
            {f"הקשר: {context}" if context else ""}
            
            טקסט לתרגום:
            {text}
            
            תרגום לעברית:
            """
            
            chat_completion = self.groq_client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model="llama3-8b-8192",
                temperature=0.3,
            )
            
            return chat_completion.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return text  # Return original if translation fails

    async def get_history_today(self) -> Optional[dict]:
        """Get today's historical event from History.com RSS"""
        try:
            feed = feedparser.parse(self.history_rss)
            if feed.entries:
                entry = feed.entries[0]  # Get the latest entry
                
                title_hebrew = await self.translate_to_hebrew(
                    entry.title, "כותרת של אירוע היסטורי"
                )
                
                summary_hebrew = await self.translate_to_hebrew(
                    entry.summary[:300] + "...", "תקציר של אירוע היסטורי"
                )
                
                return {
                    "title": title_hebrew,
                    "summary": summary_hebrew,
                    "link": entry.link,
                    "original_title": entry.title
                }
        except Exception as e:
            logger.error(f"Error fetching history: {e}")
        return None

    async def get_world_content(self) -> Optional[dict]:
        """Get interesting content from National Geographic or similar"""
        try:
            feed = feedparser.parse(self.natgeo_rss)
            if feed.entries:
                # Get a random interesting entry
                entry = random.choice(feed.entries[:5])
                
                title_hebrew = await self.translate_to_hebrew(
                    entry.title, "כותרת של תוכן מעניין על טבע או תרבות"
                )
                
                summary_hebrew = await self.translate_to_hebrew(
                    entry.summary[:250] + "...", "תיאור של תוכן מעניין"
                )
                
                return {
                    "title": title_hebrew,
                    "summary": summary_hebrew,
                    "link": entry.link,
                    "original_title": entry.title
                }
        except Exception as e:
            logger.error(f"Error fetching world content: {e}")
        return None

    async def get_diamond_fact(self) -> Optional[dict]:
        """Get a historical diamond fact from reliable sources"""
        try:
            # Rotate source daily
            today = datetime.now().day
            source = self.diamond_sources[today % len(self.diamond_sources)]
            topic = random.choice(source["topics"])
            
            # Create educational content about diamonds
            diamond_facts = [
                {
                    "title": "היהלום הכחול המפורסם - Hope Diamond",
                    "content": "יהלום התקווה הכחול שוקל 45.52 קראט ונחשב לאחד היהלומים המפורסמים בעולם. הוא מוצג כיום במוזיאון הסמיתסוניאן בוושינגטון ונקרא על שם הנרי פיליפ הופ שרכש אותו בשנת 1839.",
                    "source": "Smithsonian Institution",
                    "link": "https://www.si.edu/spotlight/hope-diamond"
                },
                {
                    "title": "יהלום קוליןנן - הגדול שנמצא אי פעם",
                    "content": "יהלום קוליןנן שוקל 3,106 קראט והוא היהלום הגדול ביותר שנמצא אי פעם. הוא התגלה בדרום אפריקה בשנת 1905 וחולק לתשעה יהלומים עיקריים, כאשר הגדול שבהם מוטמע בכתר המלכותי הבריטי.",
                    "source": "Royal Collection Trust",
                    "link": "https://www.rct.uk/collection/themes/exhibitions/diamonds-a-jubilee-celebration"
                },
                {
                    "title": "היהלום הורוד הגדול - The Pink Star",
                    "content": "The Pink Star הוא יהלום ורוד נדיר שוקל 59.60 קראט. הוא נמכר במכירה פומבית בשנת 2017 תמורת 71.2 מיליון דולר, שיא עולמי עבור יהלום שנמכר במכירה פומבית.",
                    "source": "Natural Diamond Council",
                    "link": "https://www.naturaldiamonds.com/"
                }
            ]
            
            fact = random.choice(diamond_facts)
            return fact
            
        except Exception as e:
            logger.error(f"Error fetching diamond fact: {e}")
        return None

    async def search_youtube_video(self, query: str) -> Optional[dict]:
        """Search for a relevant YouTube video"""
        try:
            # Search in Hebrew first, then English
            search_queries = [
                f"{query} בעברית",
                f"{query} היסטוריה",
                query
            ]
            
            for search_query in search_queries:
                request = self.youtube.search().list(
                    q=search_query,
                    part='snippet',
                    type='video',
                    maxResults=5,
                    order='relevance',
                    videoDuration='short'  # Prefer shorter videos
                )
                
                response = request.execute()
                
                if response['items']:
                    video = response['items'][0]
                    
                    title_hebrew = await self.translate_to_hebrew(
                        video['snippet']['title'], "כותרת של סרטון"
                    )
                    
                    description_hebrew = await self.translate_to_hebrew(
                        video['snippet']['description'][:150] + "...", "תיאור סרטון"
                    )
                    
                    return {
                        "title": title_hebrew,
                        "description": description_hebrew,
                        "url": f"https://www.youtube.com/watch?v={video['id']['videoId']}",
                        "original_title": video['snippet']['title']
                    }
                    
        except Exception as e:
            logger.error(f"Error searching YouTube: {e}")
        return None

# Bot handlers
bot = HistoryBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the daily history cycle"""
    user = update.effective_user
    
    # Send welcome message
    welcome_text = f"""
🌟 שלום {user.first_name}! ברוך הבא לבוט "היסטורי" 📜

אני כאן כדי להעשיר את הבוקר שלך עם תוכן היסטורי מרתק בעברית.
בואו נתחיל עם מה שקרה היום בהיסטוריה!

⏳ טוען תוכן...
"""
    
    await update.message.reply_text(welcome_text)
    
    # Get today's historical event
    history_content = await bot.get_history_today()
    
    if history_content:
        message_text = f"""
📅 **מה קרה היום בהיסטוריה?**

🔸 **{history_content['title']}**

{history_content['summary']}

🔗 [קרא עוד במקור]({history_content['link']})
"""
        
        keyboard = [
            [InlineKeyboardButton("📸 תראה לי משהו מעניין מהעולם", callback_data='world_content')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message_text, 
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
        return WAITING_FOR_WORLD
    else:
        await update.message.reply_text("❌ מצטער, לא הצלחתי לטעון תוכן כרגע. נסה שוב מאוחר יותר.")
        return ConversationHandler.END

async def world_content_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle world content request"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("⏳ מחפש תוכן מעניין מהעולם...")
    
    world_content = await bot.get_world_content()
    
    if world_content:
        message_text = f"""
🌍 **רגע מהעולם - טבע ותרבות**

🔸 **{world_content['title']}**

{world_content['summary']}

🔗 [קרא עוד במקור]({world_content['link']})
"""
        
        keyboard = [
            [InlineKeyboardButton("💎 תן לי עובדה נדירה על יהלומים", callback_data='diamond_fact')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
        return WAITING_FOR_DIAMOND
    else:
        await query.edit_message_text("❌ לא הצלחתי לטעון תוכן כרגע.")
        return ConversationHandler.END

async def diamond_fact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle diamond fact request"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("⏳ מחפש עובדה מרתקת על יהלומים...")
    
    diamond_content = await bot.get_diamond_fact()
    
    if diamond_content:
        message_text = f"""
💎 **עובדה היסטורית על יהלומים**

🔸 **{diamond_content['title']}**

{diamond_content['content']}

📚 **מקור:** {diamond_content['source']}
🔗 [קרא עוד במקור]({diamond_content['link']})
"""
        
        keyboard = [
            [InlineKeyboardButton("🎬 סיים לי עם סרטון קצר", callback_data='video_content')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
        return WAITING_FOR_VIDEO
    else:
        await query.edit_message_text("❌ לא הצלחתי לטעון תוכן כרגע.")
        return ConversationHandler.END

async def video_content_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle video content request"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("⏳ מחפש סרטון מעניין...")
    
    # Search for a relevant video based on previous content
    video_queries = [
        "היסטוריה מעניינת",
        "יהלומים מפורסמים",
        "עובדות היסטוריות",
        "גילויים ארכיאולוגיים"
    ]
    
    video_content = await bot.search_youtube_video(random.choice(video_queries))
    
    if video_content:
        message_text = f"""
🎥 **סרטון לסיום**

🔸 **{video_content['title']}**

{video_content['description']}

🎬 [צפה בסרטון]({video_content['url']})

---

🌀 **זהו הסבב היומי שלך. ניפגש מחר!** 💎

תוכל לשלוח /start בכל עת כדי להתחיל סבב חדש.
"""
        
        await query.edit_message_text(
            message_text,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
    else:
        await query.edit_message_text("""
🌀 **זהו הסבב היומי שלך. ניפגש מחר!** 💎

תוכל לשלוח /start בכל עת כדי להתחיל סבב חדש.
""")
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation"""
    await update.message.reply_text("🌀 הסבב בוטל. שלח /start כדי להתחיל מחדש.")
    return ConversationHandler.END

# Flask app for keep alive
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🤖 בוט היסטורי פועל! Bot is running!"

@flask_app.route('/health')
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

def run_flask():
    """Run Flask app in a separate thread"""
    flask_app.run(host='0.0.0.0', port=8000)

def main():
    """Main function to run the bot"""
    
    # Start Flask in background
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Create application
    application = Application.builder().token(bot.bot_token).build()
    
    # Create conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            WAITING_FOR_WORLD: [CallbackQueryHandler(world_content_handler, pattern='^world_content$')],
            WAITING_FOR_DIAMOND: [CallbackQueryHandler(diamond_fact_handler, pattern='^diamond_fact$')],
            WAITING_FOR_VIDEO: [CallbackQueryHandler(video_content_handler, pattern='^video_content$')],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Add handlers
    application.add_handler(conv_handler)
    
    # Add error handler
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error(f"Exception while handling an update: {context.error}")
    
    application.add_error_handler(error_handler)
    
    # Start the bot
    logger.info("🚀 בוט היסטורי מתחיל לפעול...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
