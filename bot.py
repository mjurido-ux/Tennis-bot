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
    headers = {"Content-Type": "application/json"}
    prompt = f"""
Ты — профессиональный спортивный аналитик линии. Проанализируй данные матча:
{data}

Оцени форму, H2H, покрытие, физическую готовность и маркеты (форы/тоталы/исход).
Выдай строгий разбор и сводную таблицу:
| Турнир | Матч | Выбор | Риск |
"""
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        # 1. Автоматически получаем список доступных моделей для вашего ключа
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}"
        list_res = httpx.get(list_url, timeout=15.0).json()
        
        if "error" in list_res:
            return f"Ошибка API ключа: {list_res['error'].get('message')}"
            
        models = [
            m["name"] for m in list_res.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        ]
        
        if not models:
            return f"Нет доступных моделей для генерации. Ответ сервера: {list_res}"

        # Предпочитаем flash, если есть, иначе берем первую доступную
        target_model = next((m for m in models if "flash" in m), models[0])

        # 2. Отправляем запрос к гарантированно активной модели
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/{target_model}:generateContent?key={GEMINI_KEY}"
        res = httpx.post(gen_url, headers=headers, json=payload, timeout=40.0)
        res_json = res.json()

        if "candidates" in res_json:
            return res_json["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return f"Ответ Google ({target_model}): {res_json.get('error', {}).get('message', str(res_json))}"

    except Exception as e:
        return f"Ошибка соединения: {str(e)}"

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
