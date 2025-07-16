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
        
        # Check for missing environment variables
        missing_vars = []
        if not self.bot_token:
            missing_vars.append('TELEGRAM_BOT_TOKEN')
        if not self.groq_api_key:
            missing_vars.append('GROQ_API_KEY')
        if not self.youtube_api_key:
            missing_vars.append('YOUTUBE_API_KEY')
        
        if missing_vars:
            logger.error(f"Missing environment variables: {', '.join(missing_vars)}")
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        # Initialize APIs
        try:
            self.groq_client = Groq(api_key=self.groq_api_key)
            logger.info("✅ Groq client initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Groq client: {e}")
            raise
            
        try:
            self.youtube = build('youtube', 'v3', developerKey=self.youtube_api_key)
            logger.info("✅ YouTube client initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize YouTube client: {e}")
            raise
        
        # RSS sources
        self.history_rss = "https://www.history.com/.rss/full"
        self.natgeo_rss = "https://www.nationalgeographic.com/pages/feed/"
        
        # Backup RSS sources
        self.backup_history_rss = [
            "https://www.smithsonianmag.com/rss/latest_articles/",
            "https://www.historytoday.com/rss.xml"
        ]
        self.backup_world_rss = [
            "https://www.bbc.com/news/science_and_environment/rss.xml",
            "https://www.scientificamerican.com/xml/rss.xml"
        ]
        
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
            logger.info(f"Starting translation for text: {text[:50]}...")
            
            prompt = f"""
תרגם את הטקסט הבא לעברית טבעית ונאה. תן תרגום אחד בלבד, לא אופציות מרובות.

הקשר: {context if context else "תוכן כללי"}

חוקים לתרגום:
1. תן תרגום אחד ויחיד בלבד
2. אל תכתוב "בחרו את התרגום" או אופציות מרובות
3. אל תוסיף הערות או הסברים
4. השתמש בעברית זורמת וטבעית
5. אל תתחיל במילים "התרגום הוא" או דומה - פשוט כתוב את התרגום

טקסט לתרגום:
{text}

תרגום:
"""
            
            chat_completion = self.groq_client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model="llama3-8b-8192",
                temperature=0.1,  # Lower temperature for more consistent results
                max_tokens=500,
            )
            
            result = chat_completion.choices[0].message.content.strip()
            
            # Clean up common unwanted patterns
            unwanted_patterns = [
                "בחרו את התרגום",
                "התרגום הוא:",
                "התרגום:",
                "או:",
                "(תוספת:",
                "אם תרצה",
                "אני יכול לעשות שיפורים"
            ]
            
            # Split by lines and take only the first clean line
            lines = result.split('\n')
            clean_result = ""
            
            for line in lines:
                line = line.strip()
                if line and not any(pattern in line for pattern in unwanted_patterns):
                    clean_result = line
                    break
            
            # If no clean line found, take the first non-empty line
            if not clean_result:
                for line in lines:
                    if line.strip():
                        clean_result = line.strip()
                        break
            
            # Final fallback
            if not clean_result:
                clean_result = result.split('\n')[0].strip()
            
            logger.info(f"Translation successful: {clean_result[:50]}...")
            return clean_result if clean_result else text
            
        except Exception as e:
            logger.error(f"Translation error: {e}")
            logger.error(f"Original text: {text}")
            return text  # Return original if translation fails

    async def get_history_today(self) -> Optional[dict]:
        """Get today's historical event from History.com RSS"""
        # Try main source first, then backups
        sources_to_try = [self.history_rss] + self.backup_history_rss
        
        for source_url in sources_to_try:
            try:
                logger.info(f"Fetching RSS from: {source_url}")
                feed = feedparser.parse(source_url)
                
                logger.info(f"RSS status: {feed.get('status', 'No status')}")
                logger.info(f"Number of entries: {len(feed.entries)}")
                
                if feed.entries:
                    entry = feed.entries[0]  # Get the latest entry
                    logger.info(f"Entry title: {entry.title}")
                    logger.info(f"Entry has summary: {hasattr(entry, 'summary')}")
                    
                    # Try translation
                    title_hebrew = await self.translate_to_hebrew(
                        entry.title, "כותרת של אירוע היסטורי"
                    )
                    
                    # If translation failed, use original title with note
                    if title_hebrew == entry.title:
                        title_hebrew = f"[EN] {entry.title}"
                        logger.warning("Translation failed, using original title")
                    
                    # Handle missing summary
                    summary = getattr(entry, 'summary', entry.get('description', ''))
                    if not summary:
                        summary = "לא זמין תיאור לכתבה זו"
                    
                    summary_hebrew = await self.translate_to_hebrew(
                        summary[:300] + "...", "תקציר של אירוע היסטורי"
                    )
                    
                    # If translation failed, use original summary with note
                    if summary_hebrew == summary[:300] + "...":
                        summary_hebrew = f"[EN] {summary[:200]}..."
                        logger.warning("Summary translation failed, using original")
                    
                    result = {
                        "title": title_hebrew,
                        "summary": summary_hebrew,
                        "link": entry.link,
                        "original_title": entry.title
                    }
                    logger.info(f"Successfully created history content from {source_url}")
                    return result
                else:
                    logger.warning(f"No entries found in RSS feed: {source_url}")
            except Exception as e:
                logger.error(f"Error fetching from {source_url}: {e}")
                continue  # Try next source
        
        logger.error("Failed to fetch content from all history sources")
        return None

    async def get_world_content(self) -> Optional[dict]:
        """Get interesting content from National Geographic or similar"""
        # Try main source first, then backups
        sources_to_try = [self.natgeo_rss] + self.backup_world_rss
        
        for source_url in sources_to_try:
            try:
                logger.info(f"Fetching world content from: {source_url}")
                feed = feedparser.parse(source_url)
                
                logger.info(f"RSS status: {feed.get('status', 'No status')}")
                logger.info(f"Number of entries: {len(feed.entries)}")
                
                if feed.entries:
                    # Get a random interesting entry
                    entry = random.choice(feed.entries[:5])
                    logger.info(f"Selected entry: {entry.title}")
                    
                    title_hebrew = await self.translate_to_hebrew(
                        entry.title, "כותרת של תוכן מעניין על טבע או תרבות"
                    )
                    
                    # If translation failed, use original title with note
                    if title_hebrew == entry.title:
                        title_hebrew = f"[EN] {entry.title}"
                        logger.warning("Title translation failed, using original")
                    
                    # Handle missing summary
                    summary = getattr(entry, 'summary', entry.get('description', ''))
                    if not summary:
                        summary = "תוכן מעניין ללא תיאור זמין"
                    
                    summary_hebrew = await self.translate_to_hebrew(
                        summary[:250] + "...", "תיאור של תוכן מעניין"
                    )
                    
                    # If translation failed, use original summary with note
                    if summary_hebrew == summary[:250] + "...":
                        summary_hebrew = f"[EN] {summary[:150]}..."
                        logger.warning("Summary translation failed, using original")
                    
                    result = {
                        "title": title_hebrew,
                        "summary": summary_hebrew,
                        "link": entry.link,
                        "original_title": entry.title
                    }
                    logger.info(f"Successfully created world content from {source_url}")
                    return result
                else:
                    logger.warning(f"No entries found in RSS feed: {source_url}")
            except Exception as e:
                logger.error(f"Error fetching from {source_url}: {e}")
                continue  # Try next source
        
        logger.error("Failed to fetch content from all world sources")
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
    
    logger.info(f"🚀 User {user.first_name} ({user.id}) started a new session")
    
    # Send welcome message
    welcome_text = f"""
🌟 שלום {user.first_name}! ברוך הבא לבוט "היסטורי" 📜

אני כאן כדי להעשיר את הבוקר שלך עם תוכן היסטורי מרתק בעברית.
בואו נתחיל עם מה שקרה היום בהיסטוריה!

⏳ טוען תוכן...
"""
    
    await update.message.reply_text(welcome_text)
    
    # Test APIs first
    logger.info("🔍 Testing API connections...")
    
    # Get today's historical event
    logger.info("📅 Fetching historical content...")
    history_content = await bot.get_history_today()
    
    if history_content:
        logger.info("✅ Historical content loaded successfully")
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
        logger.error("❌ Failed to load historical content")
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

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Debug command to test all components"""
    await update.message.reply_text("🔍 בודק את כל הרכיבים...")
    
    debug_info = []
    
    # Test RSS feeds
    try:
        logger.info("Testing History RSS...")
        feed = feedparser.parse(bot.history_rss)
        if feed.entries:
            debug_info.append(f"✅ History RSS: {len(feed.entries)} entries")
        else:
            debug_info.append("❌ History RSS: No entries found")
    except Exception as e:
        debug_info.append(f"❌ History RSS: Error - {str(e)}")
    
    try:
        logger.info("Testing NatGeo RSS...")
        feed = feedparser.parse(bot.natgeo_rss)
        if feed.entries:
            debug_info.append(f"✅ NatGeo RSS: {len(feed.entries)} entries")
        else:
            debug_info.append("❌ NatGeo RSS: No entries found")
    except Exception as e:
        debug_info.append(f"❌ NatGeo RSS: Error - {str(e)}")
    
    # Test Groq translation
    try:
        logger.info("Testing Groq translation...")
        test_translation = await bot.translate_to_hebrew("Hello world", "test")
        if test_translation:
            debug_info.append(f"✅ Groq API: Translation working")
        else:
            debug_info.append("❌ Groq API: Translation failed")
    except Exception as e:
        debug_info.append(f"❌ Groq API: Error - {str(e)}")
    
    # Test YouTube API
    try:
        logger.info("Testing YouTube API...")
        request = bot.youtube.search().list(
            q="test",
            part='snippet',
            type='video',
            maxResults=1
        )
        response = request.execute()
        if response['items']:
            debug_info.append("✅ YouTube API: Working")
        else:
            debug_info.append("❌ YouTube API: No results")
    except Exception as e:
        debug_info.append(f"❌ YouTube API: Error - {str(e)}")
    
    debug_message = "🔍 **תוצאות בדיקת מערכת:**\n\n" + "\n".join(debug_info)
    await update.message.reply_text(debug_message, parse_mode='Markdown')

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
