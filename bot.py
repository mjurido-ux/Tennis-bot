import os
import re
import threading
import httpx
import telebot
from bs4 import BeautifulSoup
import google.generativeai as genai
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "OK"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))
genai.configure(api_key=os.getenv("GEMINI_KEY"))

def fetch_data(url: str) -> str:
    try:
        resp = httpx.get(url, timeout=15.0, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        soup = BeautifulSoup(resp.text, 'html.parser')
        return f"\n--- {url} ---\n" + soup.get_text(separator=' ', strip=True)[:3000]
    except Exception as e:
        return f"\nОшибка загрузки {url}: {e}"

def analyze(data: str) -> str:
    try:
        # Используем универсальное имя модели
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        prompt = f"""
Ты — профессиональный спортивный аналитик линии. Данные по матчам:
{data}

Проанализируй форму, покрытие, очные встречи и риски. Выдай краткий вердикт и таблицу:
| Турнир | Матч | Выбор маркета | Риск |
"""
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        # Запасной вариант на случай сбоя модели
        try:
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(f"Анализ матча: {data}")
            return response.text
        except Exception as err:
            return f"Ошибка API Gemini: {str(err)}"

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
        
    msg = bot.reply_to(message, "⏳ Собираю данные матча...")
    results = [fetch_data(u) for u in urls]
    bot.edit_message_text("📊 Gemini рассчитывает риски...", chat_id=message.chat.id, message_id=msg.message_id)
    report = analyze("\n".join(results))
    bot.edit_message_text(report, chat_id=message.chat.id, message_id=msg.message_id)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling()
    
