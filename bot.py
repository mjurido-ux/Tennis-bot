import os
import re
import time
import threading
import httpx
import telebot
from bs4 import BeautifulSoup
from flask import Flask
app = Flask(__name__)
# Приватный доступ
ALLOWED_USER_ID = 365657270
@app.route('/')
def home():
    return "OK"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
threading.Thread(target=run_flask, daemon=True).start()
# Ключи напрямую
TELEGRAM_BOT_TOKEN = "8941843904:" + "AAGJ4jY3xPZZx1rOmPSOznZDJIpEoE7Y3vQ"
GEMINI_KEY = "AQ.Ab8RN6Iov2hfVt-o" + "Hpiv5vSkcDMDD8W2c43EuIaNFd4ZTvKNAw"
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, threaded=True)
def send_long_message(chat_id, text, reply_to_msg_id=None):
    max_len = 4000
    if len(text) <= max_len:
        if reply_to_msg_id:
            try:
                bot.edit_message_text(text, chat_id=chat_id, message_id=reply_to_msg_id)
                return
            except Exception:
                pass
        bot.send_message(chat_id, text)
        return
    if reply_to_msg_id:
        try:
            bot.delete_message(chat_id=chat_id, message_id=reply_to_msg_id)
        except Exception:
            pass
    parts = []
    while len(text) > max_len:
        split_idx = text.rfind('\n', 0, max_len)
        if split_idx == -1:
            split_idx = max_len
        parts.append(text[:split_idx])
        text = text[split_idx:].lstrip()
    if text:
        parts.append(text)
    for part in parts:
        bot.send_message(chat_id, part)
def fetch_page_context(url: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        with httpx.Client(follow_redirects=True, headers=headers, timeout=8.0) as client:
            resp = client.get(url)
            soup = BeautifulSoup(resp.text, 'html.parser')
            title = soup.title.string if soup.title else ""
            desc = ""
            tag = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
            if tag and tag.get('content'):
                desc = tag['content']
            return f"{title} | {desc}"
    except Exception:
        return url
def analyze_with_search(user_input: str) -> str:
    headers = {"Content-Type": "application/json"}
    
    prompt = f"""
Контекст запроса:
{user_input}
Ты — спортивный аналитик линии и калькулятор рисков.
Язык: строго русский.
ЗАДАЧА:
Для каждого матча найди через Google Search по базам Flashscore и Tennis Abstract:
1. ТЕКУЩАЯ ФОРМА L8 (ОБЯЗАТЕЛЬНЫЙ БАЗОВЫЙ ФИЛЬТР):
   - Детальный разбор последних 8 официальных матчей (W/L) каждого игрока: счета, покрытие, уровень оппозиции, отказы, спад формы.
2. МЕТРИКИ TENNIS ABSTRACT:
   - Surface Elo, Hold %, Break %, Dominance Ratio (DR), 2nd Serve Win %.
3. АНАЛИЗ ВСЕХ РЫНКОВ:
   - Оцени чистые исходы, форы по геймам/сетам и тоталы для нивелирования рисков.
ФОРМАТ ВЫДАЧИ:
📊 **Форма L8 и метрики Tennis Abstract**
• [Игрок 1]: L8: [W/L за 8 матчей] (Детали: соперники, кого обыграл/кому уступил, отказы) | Elo: [X] | Hold: [X]% | Break: [X]% | DR: [X]
• [Игрок 2]: L8: [W/L за 8 матчей] (Детали: соперники, кого обыграл/кому уступил, отказы) | Elo: [X] | Hold: [X]% | Break: [X]% | DR: [X]
📋 **Сводная таблица по линии**

| # | Матч | Выбор (все маркеты) | Главный фактор и риск |
| :--- | :--- | :--- | :--- |
| 1 | ... | ... | ... |

"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0.1}
    }
    
    models = ["gemini-3.7-flash", "gemini-2.5-flash", "gemini-2.0-flash"]
    last_error = ""
    
    for model_name in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_KEY}"
        try:
            with httpx.Client(timeout=90.0) as client:
                res = client.post(url, headers=headers, json=payload)
                res_json = res.json()
                
                if "candidates" in res_json:
                    parts = res_json["candidates"][0].get("content", {}).get("parts", [])
                    text_parts = [p.get("text", "") for p in parts if "text" in p and not p.get("thought", False)]
                    full_text = "".join(text_parts).strip()
                    clean_text = re.sub(r'(?i)^.*?(?=📊|\*\*Форма|\*\*Метрики)', '', full_text, flags=re.DOTALL)
                    return clean_text.strip() if clean_text.strip() else full_text
                elif "error" in res_json:
                    last_error = res_json["error"].get("message", "Лимит исчерпан")
        except Exception as e:
            last_error = str(e)
            continue
            
    return f"⚠️ Ошибка обработки: {last_error}"
@bot.message_handler(commands=['start'])
def send_welcome(message):
    if message.from_user.id != ALLOWED_USER_ID:
        bot.reply_to(message, "⛔ Доступ запрещен. Это приватный бот.")
        return
    bot.reply_to(message, "🎾 Аналитический бот активен. Отправьте список матчей.")
@bot.message_handler(content_types=['text', 'photo'])
def handle_msg(message):
    if message.from_user.id != ALLOWED_USER_ID:
        bot.reply_to(message, "⛔ Доступ запрещен.")
        return
    raw_text = message.text or message.caption or ""
    if not raw_text.strip():
        bot.reply_to(message, "Отправьте список матчей.")
        return
        
    msg = bot.reply_to(message, "⏳ Рассчитываю форму L8, метрики и маркеты...")
    
    urls = re.findall(r'https?://[^\s]+', raw_text)
    match_context = raw_text
    if urls:
        extracted = [fetch_page_context(u) for u in urls]
        match_context = "\n".join(extracted) + "\n\n" + raw_text
        
    report = analyze_with_search(match_context)
    send_long_message(message.chat.id, report, reply_to_msg_id=msg.message_id)
if __name__ == "__main__":
    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception:
        pass
    bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)
