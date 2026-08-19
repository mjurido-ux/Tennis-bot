import os
import re
import httpx
import telebot
from bs4 import BeautifulSoup
import google.generativeai as genai

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
    return model.generate_content(f"Аналитик, данные: {data}. Выдай анализ рынков и таблицу: | Турнир | Матч | Выбор | Риск |").text

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Бот готов. Пришлите ссылку на матч.")

@bot.message_handler(func=lambda message: True)
def handle_msg(message):
    urls = re.findall(r'https?://[^\s]+', message.text)
    if not urls: return
    msg = bot.reply_to(message, "⏳ Сбор данных...")
    results = [fetch_data(u) for u in urls]
    bot.edit_message_text("📊 Анализ...", chat_id=message.chat.id, message_id=msg.message_id)
    report = analyze("\n".join(results))
    bot.edit_message_text(report, chat_id=message.chat.id, message_id=msg.message_id)

bot.infinity_polling()
