# 🚀 הפעלה מהירה של בוט "היסטורי"

## 📋 דרישות מוקדמות

1. **Python 3.8+** מותקן במחשב
2. **חשבון טלגרם** עם אפשרות ליצירת בוט
3. **חשבונות API** (הוראות למטה)

## ⚡ הפעלה מהירה (5 דקות)

### שלב 1: הורדה והתקנה
```bash
git clone <repository-url>
cd history-telegram-bot
pip install -r requirements.txt
```

### שלב 2: יצירת קובץ משתני סביבה
צור קובץ `.env` עם התוכן הבא:
```env
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN_HERE
GROQ_API_KEY=YOUR_GROQ_KEY_HERE
YOUTUBE_API_KEY=YOUR_YOUTUBE_KEY_HERE
```

### שלב 3: קבלת מפתחות API

#### 🤖 Telegram Bot Token (2 דקות)
1. פתח טלגרם → חפש `@BotFather`
2. שלח `/newbot`
3. תן שם לבוט: `בוט היסטורי`
4. תן username: `your_history_bot`
5. העתק את הטוקן לקובץ `.env`

#### 🧠 Groq API Key (בחינם!)
1. לך ל-https://console.groq.com/
2. הירשם עם Google/GitHub
3. לך ל-"API Keys" ולחץ "Create API Key"
4. העתק את המפתח לקובץ `.env`

#### 📺 YouTube API Key
1. לך ל-https://console.cloud.google.com/
2. צור פרויקט חדש
3. הפעל "YouTube Data API v3"
4. צור Credentials → API Key
5. העתק את המפתח לקובץ `.env`

### שלב 4: הפעלה!
```bash
python main.py
```

## 🌐 דיפלוי ב-Render (בחינם!)

### אופציה A: GitHub → Render
1. העלה את הקוד ל-GitHub
2. לך ל-https://render.com/ והירשם
3. "New" → "Web Service" → חבר GitHub
4. בחר את הרפוזיטורי
5. הגדר משתני סביבה בלוח הבקרה
6. לחץ "Deploy"

### אופציה B: ידני
1. ב-Render: "New" → "Web Service"
2. Git Repository → הכנס את ה-URL
3. Environment: Python 3
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `python main.py`
6. הוסף משתני סביבה
7. Deploy!

## ✅ בדיקה

לאחר ההפעלה:
1. חפש את הבוט שלך בטלגרם
2. שלח `/start`
3. עקוב אחר הזרימה: היסטוריה → עולם → יהלומים → סרטון

## 🔧 פתרון בעיות נפוצות

**הבוט לא עונה:**
- ודא שהטוקן נכון
- בדוק logs: `tail -f bot.log`

**שגיאות תרגום:**
- ודא שמפתח Groq תקין
- בדוק מכסת השימוש ב-Groq Console

**אין סרטונים:**
- ודא שמפתח YouTube פעיל
- בדוק שה-API מופעל ב-Google Console

## 📊 פקודות נוספות

- `/start` - התחלת סבב חדש
- `/stats` - סטטיסטיקות הבוט
- `/cancel` - ביטול סבב נוכחי

## 🆘 תמיכה

אם נתקעת:
1. בדוק את קובץ `bot.log`
2. ודא שכל המפתחות נכונים
3. נסה להפעיל מחדש

---

**הצלחה! הבוט שלך מוכן לפעולה! 🎉**
