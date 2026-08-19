import os
import asyncio
import threading
import httpx
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Ключи
TELEGRAM_BOT_TOKEN = "8941843904:" + "AAGJ4jY3xPZZx1rOmPSOznZDJIpEoE7Y3vQ"
GEMINI_API_KEY = "AQ.Ab8RN6Iov2hfVt-o" + "Hpiv5vSkcDMDD8W2c43EuIaNFd4ZTvKNAw"

# --- 1. Фоновый веб-сервер для Render ---
server = Flask(__name__)

@server.route('/')
def home():
    return "Tennis Bot is Live!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    server.run(host="0.0.0.0", port=port)

# --- 2. Системный промпт с L8 и моделью gemini-3.7-flash ---
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.7-flash:generateContent?key={GEMINI_API_KEY}"

SYSTEM_PROMPT = """
ТЫ — ПРОФЕССИОНАЛЬНЫЙ АНАЛИТИК ТЕННИСНЫХ ЛИНИЙ И МАРКЕТОВ.
Твоя задача — строгий предматчевый аудит. Запрещено делать выводы только по устаревшим или средним годовым цифрам.

ОБЯЗАТЕЛЬНЫЙ АЛГОРИТМ ПРОВЕРКИ (ДЛЯ КАЖДОГО МАТЧА):

1. ТЕКУЩАЯ ФОРМА L8 (ОБЯЗАТЕЛЬНЫЙ БАЗОВЫЙ ФИЛЬТР):
   - Найди через поиск точные результаты последних 8 официальных матчей (W/L) для каждого игрока.
   - Детализация: точные счета, покрытие, уровень обыгранных соперников (топ-10/20/50/челленджеры), наличие отказов (retirements), признаков травм или физического спада.

2. МЕТРИКИ TENNIS ABSTRACT:
   - Surface Elo, Hold %, Break %, Dominance Ratio (DR).

3. АНАЛИЗ ВСЕХ РЫНКОВ (НЕ ТОЛЬКО ИСХОДЫ):
   - Оценивать чистые исходы, форы по геймам/сетам и тоталы.
   - Обязательно использовать плюсовые/минусовые форы (point spreads) для нейтрализации опасных сценариев и защиты ставки.

ФОРМАТ ВЫВОДА:

📊 Форма игроков (L8) и метрики
• [Игрок 1]: L8: [W/L 8 матчей] (Детализация: соперники, кого обыграл/кому уступил, отказы) | Elo: [X] | Hold: [X]% | Break: [X]% | DR: [X]
• [Игрок 2]: L8: [W/L 8 матчей] (Детализация: соперники, кого обыграл/кому уступил, отказы) | Elo: [X] | Hold: [X]% | Break: [X]% | DR: [X]

📋 Итоговый вердикт по линии
Матч: [Игрок 1] vs [Игрок 2]
Маркет: [П1 / П2 / Фора / Тотал]
Анализ: [Уровень риска: Низкий/Средний/Высокий]. Обоснование с обязательной привязкой к серии L8, оппозиции и покрытию.
"""

async def query_gemini(user_message: str) -> str:
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": SYSTEM_PROMPT},
                    {"text": f"Проанализируй следующие матчи:\n{user_message}"}
                ]
            }
        ],
        "tools": [
            {"google_search": {}}
        ]
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(GEMINI_API_URL, headers=headers, json=payload)
        
        if response.status_code == 429:
            return "⚠️ Ошибка 429: Исчерпан лимит запросов к Google API."
        
        if response.status_code != 200:
            return f"⚠️ Ошибка API ({response.status_code}): {response.text}"
            
        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            return "⚠️ Не удалось разобрать ответ от Gemini API."

async def send_safe_message(update: Update, status_msg, text: str):
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    first_chunk = chunks[0]
    try:
        await status_msg.edit_text(first_chunk, parse_mode="Markdown")
    except Exception:
        await status_msg.edit_text(first_chunk)
        
    for chunk in chunks[1:]:
        try:
            await update.message.reply_text(chunk, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(chunk)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎾 Бот спортивной аналитики готов к работе.\n\n"
        "Отправьте список матчей, и я сделаю аудит по форме L8 (последние 8 игр), метрикам Tennis Abstract и подберу оптимальные маркеты."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    status_msg = await update.message.reply_text("🔍 Анализирую последние 8 матчей игроков и рассчитываю маркеты...")
    
    analysis = await query_gemini(user_text)
    await send_safe_message(update, status_msg, analysis)

def main():
    threading.Thread(target=run_flask, daemon=True).start()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Бот успешно запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
