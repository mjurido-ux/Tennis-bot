import os
import re
import threading
import httpx
import telebot
from bs4 import BeautifulSoup
from flask import Flask

# Запуск простого веб-сервера для платформы Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running perfectly!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# Инициализация Telegram-бота и API Gemini
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
Ты — профессиональный аналитик спортивной линии. Проанализируй данные матча:
{data}

Оцени текущую форму игроков/команд, очные встречи, покрытие/условия и возможные риски. 
Рассмотри все ключевые маркеты: чистые исходы, плюсовые/минусовые форы (по сетам/геймам) и тоталы.
Выдай краткий аргументированный разбор и финальную таблицу:
| Турнир | Матч | Рекомендуемый маркет | Риск |
"""
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        # Получаем список поддерживаемых моделей прямо из аккаунта
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}"
        list_res = httpx.get(list_url, timeout=15.0).json()
        
        if "error" in list_res:
            return f"Ошибка API ключа: {list_res['error'].get('message')}"
            
        models = [
            m["name"] for m in list_res.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        ]
        
        # Сортируем: вперед идут самые быстрые и современные flash/pro модели
        models.sort(key=lambda x: ("flash" in x, "2.0" in x, "pro" in x), reverse=True)

        last_error = ""
        for model_name in models:
            gen_url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={GEMINI_KEY}"
            try:
                res = httpx.post(gen_url, headers=headers, json=payload, timeout=45.0)
                res_json = res.json()
                if "candidates" in res_json:
                    return res_json["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    last_error = res_json.get("error", {}).get("message", "Нет подходящего ответа")
            except Exception as e:
                last_error = str(e)
                continue

        return f"Не удалось получить ответ ни от одной модели. Ошибка: {last_error}"

    except Exception as e:
        return f"Ошибка соединения: {str(e)}"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "🎾 Бот готов к работе! Отправьте ссылку на матч Flashscore.")

@bot.message_handler(content_types=['text', 'photo'])
def handle_msg(message):
    raw_text = message.text or message.caption or ""
    urls = re.findall(r'https?://[^\s]+', raw_text)
    if not urls:
        bot.reply_to(message, "Пожалуйста, отправьте корректную ссылку на матч.")
        return
        
    msg = bot.reply_to(message, "⏳ Собираю статистику по матчу...")
    results = [fetch_data(u) for u in urls]
    bot.edit_message_text("📊 Gemini проводит глубокий анализ линии...", chat_id=message.chat.id, message_id=msg.message_id)
    report = analyze("\n".join(results))
    bot.edit_message_text(report, chat_id=message.chat.id, message_id=msg.message_id)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling()
