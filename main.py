import os
import logging
import asyncio
import feedparser
import requests
from datetime import datetime, time
from typing import Optional, Dict, List
import random
import sqlite3
import hashlib

# Telegram with job queue
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, JobQueue

# Gemini for translation
import google.generativeai as genai

# YouTube API
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Flask for keep alive
from flask import Flask, jsonify
from threading import Thread

# Timezone support
import pytz

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
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.youtube_api_key = os.getenv('YOUTUBE_API_KEY')
        
        # Check for missing environment variables
        missing_vars = []
        if not self.bot_token:
            missing_vars.append('TELEGRAM_BOT_TOKEN')
        if not self.gemini_api_key:
            missing_vars.append('GEMINI_API_KEY')
        if not self.youtube_api_key:
            missing_vars.append('YOUTUBE_API_KEY')
        
        if missing_vars:
            logger.error(f"Missing environment variables: {', '.join(missing_vars)}")
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        # Initialize APIs
        try:
            genai.configure(api_key=self.gemini_api_key)
            self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
            logger.info("✅ Gemini client initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini client: {e}")
            raise
            
        try:
            self.youtube = build('youtube', 'v3', developerKey=self.youtube_api_key)
            logger.info("✅ YouTube client initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize YouTube client: {e}")
            raise
        
        # Initialize SQLite database for persistent storage
        self.init_database()
        
        # RSS sources
        self.history_rss = "https://www.history.com/.rss/full"
        self.natgeo_rss = "https://www.nationalgeographic.com/pages/feed/"
        
        # Backup RSS sources
        self.backup_history_rss = [
            "https://www.smithsonianmag.com/rss/latest_articles/",
            "https://www.historytoday.com/rss.xml"
        ]
        
        # Admin chat ID for daily messages
        self.admin_chat_id = os.getenv('ADMIN_CHAT_ID')
        
        # Sent articles tracking (legacy - now using SQLite)
        self.sent_articles = set()
        
        # World content RSS sources
        self.world_rss = "https://www.nationalgeographic.com/pages/feed/"
        
        # Backup world RSS sources
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

    def init_database(self):
        """Initialize SQLite database for persistent storage"""
        try:
            # Use tmp directory for Render compatibility
            db_path = '/tmp/bot_data.db'
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            
            # Create sent_articles table if it doesn't exist
            cursor = self.conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sent_articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_hash TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    date_sent TEXT NOT NULL,
                    source TEXT NOT NULL
                )
            ''')
            self.conn.commit()
            logger.info("✅ SQLite database initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize database: {e}")
            raise

    def is_article_sent(self, title: str, source: str) -> bool:
        """Check if article was already sent using SQLite"""
        try:
            article_hash = hashlib.md5(f"{title}_{source}".encode()).hexdigest()
            cursor = self.conn.cursor()
            cursor.execute('SELECT 1 FROM sent_articles WHERE article_hash = ?', (article_hash,))
            return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking article: {e}")
            return False

    def mark_article_sent(self, title: str, source: str):
        """Mark article as sent in SQLite"""
        try:
            article_hash = hashlib.md5(f"{title}_{source}".encode()).hexdigest()
            cursor = self.conn.cursor()
            cursor.execute(
                'INSERT OR IGNORE INTO sent_articles (article_hash, title, date_sent, source) VALUES (?, ?, ?, ?)',
                (article_hash, title, datetime.now().isoformat(), source)
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error marking article as sent: {e}")

    async def send_daily_history(self, context: ContextTypes.DEFAULT_TYPE):
        """Send daily history message automatically at 9 AM"""
        try:
            if not self.admin_chat_id:
                logger.warning("No ADMIN_CHAT_ID set, cannot send daily messages")
                return
            
            logger.info("🕘 Sending daily history message...")
            
            # Get today's historical event
            history_content = await self.get_history_today()
            
            if history_content:
                message_text = f"""
🌅 **בוקר טוב! מה קרה היום בהיסטוריה?**

🔸 **{history_content['title']}**

{history_content['summary']}

🔗 [קרא עוד במקור]({history_content['link']})

---

💡 **רוצה עוד תוכן מעניין?** לחץ על הכפתור למטה להמשך הסבב היומי!
"""
                
                keyboard = [
                    [InlineKeyboardButton("📸 תראה לי משהו מעניין מהעולם", callback_data='world_content')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await context.bot.send_message(
                    chat_id=self.admin_chat_id,
                    text=message_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
                
                logger.info("✅ Daily history message sent successfully")
            else:
                # Send fallback message
                await context.bot.send_message(
                    chat_id=self.admin_chat_id,
                    text="🌅 בוקר טוב! מצטער, לא הצלחתי לטעון תוכן היסטורי כרגע. נסה לשלוח /start למשך ידני."
                )
                logger.error("❌ Failed to send daily history - no content available")
                
        except Exception as e:
            logger.error(f"Error sending daily history: {e}")

    def schedule_daily_messages(self, job_queue: JobQueue):
        """Schedule daily messages at 9 AM Israel time"""
        try:
            israel_tz = pytz.timezone('Asia/Jerusalem')
            
            # Schedule for 9:00 AM Israel time every day
            job_queue.run_daily(
                self.send_daily_history,
                time=time(hour=9, minute=0),  # 9:00 AM
                days=(0, 1, 2, 3, 4, 5, 6),  # Every day of the week
                timezone=israel_tz,
                name='daily_history'
            )
            
            logger.info("✅ Daily message scheduler initialized for 9:00 AM Israel time")
        except Exception as e:
            logger.error(f"❌ Failed to schedule daily messages: {e}")

    def should_filter_content(self, title: str, summary: str) -> bool:
        """Check if content should be filtered out (mystical, supernatural, etc.)"""
        filter_keywords = [
            'mystical', 'supernatural', 'paranormal', 'ghost', 'spirit', 'haunted',
            'ufo', 'alien', 'conspiracy', 'prophecy', 'fortune telling', 'astrology',
            'zodiac', 'horoscope', 'crystal', 'energy', 'aura', 'chakra'
        ]
        
        text_to_check = f"{title} {summary}".lower()
        return any(keyword in text_to_check for keyword in filter_keywords)

    async def translate_to_hebrew(self, text: str, context: str = "") -> str:
        """Translate text to Hebrew using Gemini with RTL formatting"""
        try:
            logger.info(f"Starting translation for text: {text[:50]}...")
            
            prompt = f"""
תרגם את הטקסט הבא לעברית טבעית וזורמת. תן תרגום אחד בלבד.

הקשר: {context if context else "תוכן כללי"}

חוקים חשובים לתרגום:
1. תרגם לעברית נכונה וטבעית
2. תן תרגום אחד בלבד - לא אופציות מרובות  
3. אל תוסיף הערות או הסברים
4. השתמש במילים נכונות בעברית
5. אל תכתוב "התרגום הוא" - פשוט כתוב את התרגום
6. חשוב: תרגם את כל המילים לעברית - לא תשאיר מילים באנגלית
7. שמות פרטיים ומקומות: תכתב אותם בעברית ואחר כך תוסיף את השם המקורי בסוגריים
8. תאריכים ומספרים: תשאיר אותם כמו שהם

טקסט באנגלית:
{text}

תרגום לעברית (ללא מילים באנגלית):
"""
            
            response = self.gemini_model.generate_content(prompt)
            result = response.text.strip()
            
            # Clean up unwanted patterns
            unwanted_patterns = [
                "התרגום הוא:",
                "התרגום:",
                "בעברית:",
                "תרגום:",
                "או:",
                "אופציה"
            ]
            
            # Take first clean line
            lines = result.split('\n')
            clean_result = ""
            
            for line in lines:
                line = line.strip()
                if line and not any(pattern in line for pattern in unwanted_patterns):
                    clean_result = line
                    break
            
            if not clean_result:
                clean_result = result.split('\n')[0].strip()
            
            # Fix RTL/LTR issues by adding RTL markers
            clean_result = f"‏{clean_result}‏"
            
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
                    # Try multiple entries until we find one that hasn't been sent
                    for entry in feed.entries[:10]:  # Check first 10 entries
                        if self.is_article_sent(entry.title, source_url):
                            logger.info(f"Skipping already sent article: {entry.title}")
                            continue
                        
                        # Check for filtered content
                        summary = getattr(entry, 'summary', entry.get('description', ''))
                        if self.should_filter_content(entry.title, summary):
                            logger.info(f"Filtering out mystical content: {entry.title}")
                            continue
                        
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
                        
                        # Handle missing summary and make it longer (3x)
                        if not summary:
                            summary = "לא זמין תיאור לכתבה זו"
                        
                        # Make summary longer - take up to 900 characters instead of 300
                        longer_summary = summary[:900] + "..." if len(summary) > 900 else summary
                        
                        summary_hebrew = await self.translate_to_hebrew(
                            longer_summary, "תקציר מפורט של אירוע היסטורי"
                        )
                        
                        # If translation failed, use original summary with note
                        if summary_hebrew == longer_summary:
                            summary_hebrew = f"[EN] {summary[:600]}..."
                            logger.warning("Summary translation failed, using original")
                        
                        result = {
                            "title": title_hebrew,
                            "summary": summary_hebrew,
                            "link": entry.link,
                            "original_title": entry.title
                        }
                        
                        # Mark as sent
                        self.mark_article_sent(entry.title, source_url)
                        
                        # Store context for video search
                        self.current_content_context = f"history {entry.title}"
                        
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
                    # Try multiple entries until we find one that hasn't been sent
                    for entry in random.sample(feed.entries[:15], min(10, len(feed.entries))):
                        if self.is_article_sent(entry.title, source_url):
                            logger.info(f"Skipping already sent article: {entry.title}")
                            continue
                        
                        # Check for filtered content
                        summary = getattr(entry, 'summary', entry.get('description', ''))
                        if self.should_filter_content(entry.title, summary):
                            logger.info(f"Filtering out mystical content: {entry.title}")
                            continue
                        
                        logger.info(f"Selected entry: {entry.title}")
                        
                        title_hebrew = await self.translate_to_hebrew(
                            entry.title, "כותרת של תוכן מעניין על טבע או תרבות"
                        )
                        
                        # If translation failed, use original title with note
                        if title_hebrew == entry.title:
                            title_hebrew = f"[EN] {entry.title}"
                            logger.warning("Title translation failed, using original")
                        
                        # Handle missing summary and make it longer
                        if not summary:
                            summary = "תוכן מעניין ללא תיאור זמין"
                        
                        # Make summary longer - take up to 750 characters instead of 250
                        longer_summary = summary[:750] + "..." if len(summary) > 750 else summary
                        
                        summary_hebrew = await self.translate_to_hebrew(
                            longer_summary, "תיאור מפורט של תוכן מעניין"
                        )
                        
                        # If translation failed, use original summary with note
                        if summary_hebrew == longer_summary:
                            summary_hebrew = f"[EN] {summary[:450]}..."
                            logger.warning("Summary translation failed, using original")
                        
                        result = {
                            "title": title_hebrew,
                            "summary": summary_hebrew,
                            "link": entry.link,
                            "original_title": entry.title
                        }
                        
                        # Mark as sent
                        self.mark_article_sent(entry.title, source_url)
                        
                        # Store context for video search
                        self.current_content_context = f"nature science {entry.title}"
                        
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

    async def search_youtube_video(self, custom_query: str = None) -> Optional[dict]:
        """Search for a relevant YouTube video based on current content"""
        try:
            # Use current content context for better relevance
            if custom_query:
                search_queries = [custom_query]
            elif self.current_content_context:
                # Extract keywords from current content context
                base_query = self.current_content_context.split()[:3]  # Take first 3 words
                search_queries = [
                    f"{' '.join(base_query)} דוקומנטרי בעברית",
                    f"{' '.join(base_query)} documentary",
                    f"{' '.join(base_query)} educational",
                    f"תוכן חינוכי {' '.join(base_query)}"
                ]
            else:
                # Fallback queries
                search_queries = [
                    "דוקומנטרי היסטוריה בעברית",
                    "תוכן חינוכי מדע",
                    "דוקומנטרי טבע",
                    "educational documentary",
                    "science documentary"
                ]
            
            for search_query in search_queries:
                try:
                    logger.info(f"Searching YouTube for: {search_query}")
                    request = self.youtube.search().list(
                        q=search_query,
                        part='snippet',
                        type='video',
                        maxResults=10,
                        order='relevance',
                        videoDuration='medium',
                        videoDefinition='any',
                        relevanceLanguage='he'  # Prefer Hebrew content
                    )
                    
                    response = request.execute()
                    
                    if response['items']:
                        # Filter for quality videos
                        for video in response['items']:
                            title = video['snippet']['title']
                            
                            # Skip if title contains unwanted content
                            skip_keywords = ['trailer', 'reaction', 'live', 'stream', 'review']
                            if any(keyword.lower() in title.lower() for keyword in skip_keywords):
                                continue
                            
                            title_hebrew = await self.translate_to_hebrew(
                                title, "כותרת של סרטון חינוכי"
                            )
                            
                            description = video['snippet']['description'][:200]
                            description_hebrew = await self.translate_to_hebrew(
                                description, "תיאור סרטון חינוכי"
                            )
                            
                            return {
                                "title": title_hebrew,
                                "description": description_hebrew,
                                "url": f"https://www.youtube.com/watch?v={video['id']['videoId']}",
                                "original_title": title,
                                "search_query": search_query
                            }
                except Exception as e:
                    logger.warning(f"YouTube search failed for '{search_query}': {e}")
                    continue
                            
        except Exception as e:
            logger.error(f"Unexpected error in YouTube search: {e}")
        
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
    """Handle video content request - now based on previous content instead of diamonds"""
    try:
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text("⏳ מחפש סרטון רלוונטי לתוכן שראינו...")
        
        # Search for a video related to the current content context
        video_content = await bot.search_youtube_video()
        
        if video_content:
            message_text = f"""
🎥 **סרטון לסיום**

🔸 **{video_content['title']}**

{video_content['description']}

🎬 [צפה בסרטון]({video_content['url']})

*חיפשתי סרטון על: {video_content.get('search_query', 'תוכן רלוונטי')}*

---

🌀 **זהו הסבב היומי שלך. ניפגש מחר ב-9:00!** 💎

💡 **טיפ:** תוכל לשלוח /start בכל עת כדי להתחיל סבב חדש
📊 שלח /stats לסטטיסטיקות הבוט
"""
            
            await query.edit_message_text(
                message_text,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
        else:
            await query.edit_message_text("""
🌀 **זהו הסבב היומי שלך. ניפגש מחר ב-9:00!** 💎

💡 **טיפ:** תוכל לשלוח /start בכל עת כדי להתחיל סבב חדש
📊 שלח /stats לסטטיסטיקות הבוט

*לא הצלחתי למצוא סרטון מתאים הפעם, אבל התוכן שקיבלת היה איכותי!*
""")
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in video_content_handler: {e}")
        await query.edit_message_text("❌ אירעה שגיאה בחיפוש הסרטון.")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation"""
    await update.message.reply_text("🌀 הסבב בוטל. שלח /start כדי להתחיל מחדש.")
    return ConversationHandler.END

async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get user's chat ID for daily messages setup"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    message = f"""
🆔 **פרטי החשבון שלך:**

👤 **שם:** {user.first_name}
🆔 **Chat ID:** `{chat_id}`

📋 **איך להגדיר הודעות יומיות:**
1. העתק את ה-Chat ID למעלה
2. הוסף למשתני הסביבה ב-Render:
   `ADMIN_CHAT_ID={chat_id}`
3. Deploy מחדש את הבוט
4. מחר ב-9:00 תקבל הודעה אוטומטית!

💡 **טיפ:** אם אתה האדמין של הבוט, שמור את המספר הזה.
"""
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics"""
    try:
        # Get database stats
        cursor = bot.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM sent_articles')
        total_articles = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT source) FROM sent_articles')
        unique_sources = cursor.fetchone()[0]
        
        # Get latest article
        cursor.execute('SELECT title, date_sent FROM sent_articles ORDER BY date_sent DESC LIMIT 1')
        latest = cursor.fetchone()
        
        stats_text = f"""
📊 **סטטיסטיקות הבוט**

📄 **כתבות שנשלחו:** {total_articles}
🔗 **מקורות שונים:** {unique_sources}
🕐 **כתבה אחרונה:** {latest[0][:50] + '...' if latest else 'אין נתונים'}
📅 **תאריך אחרון:** {latest[1][:10] if latest else 'אין נתונים'}

⏰ **שליחה יומית:** {"מופעלת" if bot.admin_chat_id else "לא מוגדרת"}
🤖 **מצב הבוט:** פעיל ותקין

💡 שלח /getchatid כדי לקבל את ה-Chat ID שלך
"""
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in stats command: {e}")
        await update.message.reply_text("❌ לא ניתן לטעון סטטיסטיקות כרגע.")

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
    
    # Test Gemini translation
    try:
        logger.info("Testing Gemini translation...")
        test_translation = await bot.translate_to_hebrew("Hello world", "test")
        if test_translation:
            debug_info.append(f"✅ Gemini API: Translation working")
        else:
            debug_info.append("❌ Gemini API: Translation failed")
    except Exception as e:
        debug_info.append(f"❌ Gemini API: Error - {str(e)}")
    
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
    
    # Create bot instance
    global bot
    bot = HistoryBot()
    
    # Start Flask in background
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Create application with job queue
    application = Application.builder().token(bot.bot_token).build()
    
    # Schedule daily messages
    bot.schedule_daily_messages(application.job_queue)
    
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
    
    # Add handlers - תיקון סדר!
    application.add_handler(CommandHandler('debug', debug_command))
    application.add_handler(CommandHandler('stats', stats_command))
    application.add_handler(CommandHandler('getchatid', get_chat_id))
    application.add_handler(conv_handler)  # ConversationHandler אחרון!
    
    # Add error handler
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error(f"Exception while handling an update: {context.error}")
    
    application.add_error_handler(error_handler)
    
    # Start the bot
    logger.info("🚀 בוט היסטורי מתחיל לפעול...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
