# 🤖 בוט היסטורי - Telegram History Bot

בוט טלגרם חכם שמספק תוכן יומי מעניין: היסטוריה → עולם → יהלומים → סרטון

## ✨ תכונות

- 📅 **הודעות יומיות אוטומטיות** ב-9:00 בבוקר (שעון ישראל)
- 🌍 **תוכן מגוון**: היסטוריה, טבע, מדע, יהלומים מפורסמים
- 🔄 **מניעת כפילויות** - לא שולח אותה כתבה פעמיים
- 🌐 **תרגום אוטומטי** לעברית באמצעות Google Gemini
- 📺 **סרטונים רלוונטיים** מ-YouTube
- 📊 **סטטיסטיקות** ופקודות ניהול
- 🚀 **עובד ב-Render.com** עם keep-alive

## 🚀 התקנה מהירה

### 1. הגדרת משתני סביבה ב-Render

```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
GEMINI_API_KEY=your_gemini_api_key_here
YOUTUBE_API_KEY=your_youtube_api_key_here
ADMIN_CHAT_ID=your_chat_id_here  # אופציונלי - להודעות יומיות
```

### 2. Deploy ל-Render

1. Fork את הפרויקט
2. הוסף את משתני הסביבה ב-Render
3. Deploy אוטומטי!

## 📋 פקודות זמינות

- `/start` - התחל סבב יומי חדש
- `/stats` - הצג סטטיסטיקות הבוט
- `/debug` - בדוק את כל הרכיבים
- `/getchatid` - קבל את ה-Chat ID שלך
- `/cancel` - בטל את הסבב הנוכחי

## 🔧 תיקונים אחרונים

### ✅ בעיה 1: פקודות חדשות לא עובדות
**תוקן:** שינוי סדר ה-handlers - פקודות רגילות לפני ConversationHandler

### ✅ בעיה 2: סיכומים קצרים מדי
**תוקן:** הגדלת הסיכומים ל-900 תווים (היסטוריה) ו-750 תווים (עולם)

### ✅ בעיה 3: כתבות חוזרות על עצמן
**תוקן:** SQLite database עם נתיב `/tmp` ל-Render compatibility

### ✅ בעיה 4: בעיות RTL בתרגום
**תוקן:** הוספת RTL markers ושיפור ה-prompt

### ✅ בעיה 5: JobQueue scheduling
**תוקן:** הוספת תזמון הודעות יומיות אוטומטי

## 🗄️ מבנה Database

```sql
CREATE TABLE sent_articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_hash TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    date_sent TEXT NOT NULL,
    source TEXT NOT NULL
);
```

## 🌐 מקורות RSS

### היסטוריה
- History.com (ראשי)
- Smithsonian Magazine (גיבוי)
- History Today (גיבוי)

### עולם וטבע
- National Geographic (ראשי)
- BBC Science (גיבוי)
- Scientific American (גיבוי)

## 🔍 בדיקת תקינות

שלח `/debug` לבוט כדי לבדוק:
- ✅ RSS feeds
- ✅ Gemini API
- ✅ YouTube API
- ✅ Database connection

## 📊 סטטיסטיקות

שלח `/stats` כדי לראות:
- מספר כתבות שנשלחו
- מקורות שונים
- כתבה אחרונה
- מצב הודעות יומיות

## 🚨 פתרון בעיות

### הבוט לא מגיב לפקודות
1. בדוק שהפקודות נרשמו לפני ConversationHandler
2. שלח `/debug` לבדיקת מערכת

### כתבות חוזרות על עצמן
1. וודא שה-SQLite database נוצר ב-`/tmp`
2. בדוק שהפונקציות `is_article_sent` ו-`mark_article_sent` עובדות

### תרגום לא עובד
1. בדוק שה-GEMINI_API_KEY מוגדר נכון
2. שלח `/debug` לבדיקת Gemini API

## 📝 היסטוריית שינויים

### v2.1 - תיקונים מרכזיים
- 🔧 תיקון סדר handlers
- 📏 הגדלת סיכומים
- 🗄️ SQLite עם נתיב זמני
- 🌐 שיפור RTL
- ⏰ JobQueue scheduling

### v2.0 - שדרוגים
- 🤖 מעבר ל-Google Gemini
- 📅 הודעות יומיות אוטומטיות
- 🔄 מניעת כפילויות
- 📊 סטטיסטיקות מתקדמות

## 🤝 תרומה

1. Fork את הפרויקט
2. צור branch חדש
3. Commit את השינויים
4. Push ל-branch
5. פתח Pull Request

## 📄 רישיון

MIT License - חופשי לשימוש ולשינוי

---

**🎯 מטרה:** לספק תוכן מעניין ואיכותי בעברית, מדי יום, בצורה אוטומטית ומתקדמת.
