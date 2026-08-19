import os
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
# Ключи берутся из настроек Render (Environment Variables)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# --- Веб-сервер для Render ---
server = Flask(__name__)
@server.route('/')
def home():
    return "Bot is active"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    server.run(host="0.0.0.0", port=port)
# --- Промпт L8 ---
SYSTEM_PROMPT = """
ТЫ — ПРОФЕССИОНАЛЬНЫЙ АНАЛИТИК ТЕННИСНЫХ ЛИНИЙ И МАРКЕТОВ.
ОБЯЗАТЕЛЬНЫЙ АЛГОРИТМ ПРОВЕРКИ (ДЛЯ КАЖДОГО МАТЧА):
1. ТЕКУЩАЯ ФОРМА L8: Найди точные результаты последних 8 матчей. Детализация: соперники, отказы, покрытие.
2. МЕТРИКИ TENNIS ABSTRACT: Surface Elo, Hold %, Break %, Dominance Ratio (DR).
3. АНАЛИЗ МАРКЕТОВ: Оцени исходы, форы и тоталы. Используй форы для защиты ставки.
ФОРМАТ ВЫВОДА:
📊 **Форма игроков (L8) и метрики**
• **[Игрок 1]**: L8: [...] | Elo: [X] | Hold: [X]% | Break: [X]% | DR: [X]
• **[Игрок 2]**: L8: [...] | Elo: [X] | Hold: [X]% | Break: [X]% | DR: [X]
📋 **Итоговый вердикт по линии**

| Матч | Выбор | Обоснование (риск + L8) |
| :--- | :--- | :--- |
| **[Игрок 1] vs [Игрок 2]** | [Маркет] | [Риск: Низкий/Средний/Высокий]. Анализ L8 и покрытия. |

"""
async def query_gemini(user_message: str):
    import httpx
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": SYSTEM_PROMPT}, {"text": user_message}]}], "tools": [{"google_search": {}}]}
    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(url, json=payload)
        return response.json()["candidates"][0]["content"]["parts"][0]["text"] if response.status_code == 200 else "Ошибка API"
async def handle_message(update: Update, context):
    msg = await update.message.reply_text("🔍 Анализирую L8...")
    response = await query_gemini(update.message.text)
    await msg.edit_text(response, parse_mode="Markdown")
def main():
    threading.Thread(target=run_flask, daemon=True).start()
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    app.run_polling()
if __name__ == "__main__":
    main()
