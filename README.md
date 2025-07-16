# 📜 בוט "היסטורי" - בוט טלגרם לתוכן היסטורי יומי

בוט טלגרם אישי ואלגנטי עם סבב יומי של תוכן היסטורי איכותי ומכובד בעברית.

## 🎯 תכונות

- **תוכן יומי איכותי**: שליפה אוטומטית מ-History.com ו-National Geographic
- **תרגום מלא לעברית**: באמצעות Groq AI
- **4 שלבים בכל סבב**:
  1. 📅 מה קרה היום בהיסטוריה
  2. 🌍 תוכן מעניין מהעולם  
  3. 💎 עובדה היסטורית על יהלומים
  4. 🎬 סרטון יוטיוב לסיום
- **ממשק ידידותי**: כפתורי המשך, ללא צורך בהקלדה
- **מקורות אמינים**: כל תוכן כולל קישור למקור

## 🛠️ התקנה

### 1. הורדת הקוד

```bash
git clone <repository-url>
cd history-telegram-bot
```

### 2. התקנת תלויות

```bash
pip install -r requirements.txt
```

### 3. הגדרת משתני סביבה

צור קובץ `.env` בתיקיית הפרויקט:

```bash
cp .env.example .env
```

ערוך את הקובץ עם המפתחות שלך:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
GEMINI_API_KEY=your_gemini_api_key_here  
YOUTUBE_API_KEY=your_youtube_api_key_here
```

## 🔑 קבלת מפתחות API

### Telegram Bot Token
1. פתח טלגרם וחפש את @BotFather
2. שלח `/newbot` ועקב אחר ההנחיות
3. העתק את הטוקן שתקבל

### Google Gemini API Key
1. היכנס ל-https://aistudio.google.com/app/apikey
2. התחבר עם חשבון Google
3. לחץ "Create API Key"
4. העתק את המפתח

### YouTube API Key
1. היכנס ל-Google Cloud Console
2. צור פרויקט חדש או בחר קיים
3. הפעל את YouTube Data API v3
4. צור credentials מסוג API Key
5. העתק את המפתח

## 🚀 הפעלה

### הפעלה מקומית

```bash
python main.py
```

### דיפלוי ב-Render

1. העלה את הקוד ל-GitHub
2. צור חשבון ב-Render.com
3. צור Web Service חדש מ-GitHub
4. הגדר משתני סביבה בלוח הבקרה של Render
5. הבוט יעלה אוטומטית

## 📖 שימוש

1. שלח `/start` לבוט בטלגרם
2. קבל תוכן היסטורי על "מה קרה היום"
3. לחץ על הכפתור להמשך - "תראה לי משהו מעניין מהעולם"
4. לחץ שוב - "תן לי עובדה נדירה על יהלומים" 
5. לחץ לסיום - "סיים לי עם סרטון קצר"
6. נהנה מהסבב היומי!

## 🏗️ ארכיטקטורה

```
├── main.py              # קובץ ראשי של הבוט
├── requirements.txt     # תלויות Python
├── .env.example        # דוגמה למשתני סביבה
└── README.md           # מדריך זה
```

### רכיבים עיקריים

- **HistoryBot Class**: המחלקה הראשית המנהלת את כל הפונקציות
- **RSS Parsing**: שליפת תוכן מ-History.com ו-National Geographic
- **Gemini Translation**: תרגום אוטומטי לעברית
- **YouTube Search**: חיפוש סרטונים רלוונטיים
- **Conversation Handler**: ניהול זרימת השיחה עם המשתמש
- **Flask Keep-Alive**: שרת HTTP לשמירה על הבוט פעיל

## 🔧 התאמה אישית

### הוספת מקורות RSS

ערוך את רשימת המקורות ב-`HistoryBot.__init__()`:

```python
self.custom_rss = "https://your-rss-source.com/feed"
```

### שינוי נושאי יהלומים

ערוך את `self.diamond_sources` כדי להוסיף מקורות חדשים:

```python
{
    "name": "מקור חדש",
    "url": "https://example.com",
    "topics": ["נושא 1", "נושא 2"]
}
```

## 🐛 פתרון בעיות

### הבוט לא מגיב
- ודא שהטוקן של הבוט נכון
- בדוק שהבוט פועל (log messages)

### שגיאות תרגום
- ודא שמפתח Groq תקין ופעיל
- בדוק גבולות השימוש ב-API

### תוכן לא נטען
- בדוק חיבור לאינטרנט
- ודא שמקורות RSS זמינים

## 📝 רישיון

הפרויקט זמין למטרות אישיות. אנא כבד את זכויות היוצרים של המקורות המצוטטים.

## 🤝 תרומה

מוזמן לשלוח Pull Requests או לפתוח Issues לשיפורים!

---

**ברוך הבא לחוויה יומית של תוכן היסטורי מעשיר! 📜✨**
