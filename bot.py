import os
import re
import threading
import httpx
import telebot
from bs4 import BeautifulSoup
import google.generativeai as genai
from flask import Flask

# Запуск простого веб-сервера для Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# Инициализация бота и нейросети
bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))
genai.configure(api_key=os.getenv("GEMINI_KEY"))

def fetch_data(url: str) -> str:
    try:
        resp = httpx.get(url, timeout=10.0, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, 'html.parser')
        return f"\n--- {url} ---\n" + soup.get_text(separator=' ', strip=True)[:2000]
    except Exception as e:
        return f"\nОшибка {url}: {e}"

def analyze(data: str) -> str:
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""
Ты — сухой аналитик спортивной линии. На основе фактов ниже сделай глубокий анализ рынков (исходы, форы, тоталы):
{data}

Выдай краткий разбор и финальную таблицу:
| Турнир | Матч | Выбор маркета | Риск |
"""
    return model.generate_content(prompt).text

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "🎾 Бот готов! Отправьте мне ссылку на матч Flashscore.")

@bot.message_handler(content_types=['text', 'photo'])
def handle_msg(message):
    raw_text = message.text or message.caption or ""
    urls = re.findall(r'https?://[^\s]+', raw_text)
    if not urls:
        bot.reply_to(message, "Пожалуйста, отправьте ссылку на матч.")
        return
        
    msg = bot.reply_to(message, "⏳ Собираю статистику и запускаю анализ...")
    results = [fetch_data(u) for u in urls]
    bot.edit_message_text("📊 Gemini анализирует рынки...", chat_id=message.chat.id, message_id=msg.message_id)
    report = analyze("\n".join(results))
    bot.edit_message_text(report, chat_id=message.chat.id, message_id=msg.message_id)

if __name__ == "__main__":
    # Фоновый поток для веб-порта
    threading.Thread(target=run_flask, daemon=True).start()
    # Запуск бота
    bot.infinity_polling()
    
