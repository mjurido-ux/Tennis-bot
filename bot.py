import os
import re
import threading
import httpx
import telebot
from bs4 import BeautifulSoup
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "OK"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))
GEMINI_KEY = os.getenv("GEMINI_KEY")

def fetch_data(url: str) -> str:
    try:
        resp = httpx.get(url, timeout=15.0, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        soup = BeautifulSoup(resp.text, 'html.parser')
        return f"\n--- {url} ---\n" + soup.get_text(separator=' ', strip=True)[:3000]
    except Exception as e:
        return f"\nОшибка загрузки {url}: {e}"

def analyze(data: str) -> str:
    # Пробуем актуальные эндпоинты по очереди
    candidate_urls = [
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}",
        f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}",
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_KEY}",
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_KEY}"
    ]
    
    headers = {"Content-Type": "application/json"}
    prompt = f"""
Ты — профессиональный аналитик спортивной линии. Проанализируй данные матча:
{data}

Оцени форму, H2H, покрытие, физическую готовность и маркеты (форы/тоталы/исход).
Выдай строгий разбор и сводную таблицу:
| Турнир | Матч | Выбор | Риск |
"""
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    last_error = ""
    for api_url in candidate_urls:
        try:
            res = httpx.post(api_url, headers=headers, json=payload, timeout=35.0)
            res_json = res.json()
            if "candidates" in res_json:
                return res_json["candidates"][0]["content"]["parts"][0]["text"]
            else:
                last_error = res_json.get("error", {}).get("message", str(res_json))
        except Exception as e:
            last_error = str(e)
            
    return f"Ошибка API: {last_error}"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "🎾 Бот готов! Отправьте ссылку на матч Flashscore.")

@bot.message_handler(content_types=['text', 'photo'])
def handle_msg(message):
    raw_text = message.text or message.caption or ""
    urls = re.findall(r'https?://[^\s]+', raw_text)
    if not urls:
        bot.reply_to(message, "Пожалуйста, отправьте ссылку на матч.")
        return
        
    msg = bot.reply_to(message, "⏳ Собираю статистику...")
    results = [fetch_data(u) for u in urls]
    bot.edit_message_text("📊 Gemini проводит расчет...", chat_id=message.chat.id, message_id=msg.message_id)
    report = analyze("\n".join(results))
    bot.edit_message_text(report, chat_id=message.chat.id, message_id=msg.message_id)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling()
