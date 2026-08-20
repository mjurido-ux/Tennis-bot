import os
import re
import time
import threading
import httpx
import telebot
from bs4 import BeautifulSoup
from flask import Flask
from duckduckgo_search import DDGS
app = Flask(__name__)
ALLOWED_USER_ID = 365657270
@app.route('/')
def home():
    return "OK"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
threading.Thread(target=run_flask, daemon=True).start()
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
def get_live_tennis_data(query_text: str) -> str:
    collected = []
    try:
        with DDGS() as ddgs:
            search_query = f"tennis flashscore {query_text} recent results 2026"
            results = list(ddgs.text(search_query, max_results=6))
            for r in results:
                collected.append(f"[{r.get('title', '')}]: {r.get('body', '')}")
    except Exception:
        pass
    return "\n".join(collected)
def analyze_with_search(user_input: str) -> str:
    headers = {"Content-Type": "application/json"}
    live_facts = get_live_tennis_data(user_input)
    
    prompt = f"""
Контекст запроса:
{user_input}
Реальные факты и результаты из сети (используй строго их, не выдумывай матчи):
{live_facts}
Ты — профессиональный спортивный аналитик линии и калькулятор рисков.
Язык: строго русский.
ЗАДАЧА:
1. Выведи метрики Tennis Abstract и форму L5 строго по реальным последним матчам (счет, соперник). Если матчей в фактах нет, напиши реальный статус формы без выдумок.
2. Сформируй итоговую таблицу: ровно 1 маркет на матч для нивелирования рисков + ключевой риск (травмы, отказы, усталость).
СТРОГИЙ ФОРМАТ ВЫДАЧИ:
📊 **Метрики Tennis Abstract и форма L5**
• **[Игрок 1]**: Elo: [X] | Hold: [X]% | Break: [X]% | DR: [X] | L5: [W-L] (соперники, отказы/травмы)
• **[Игрок 2]**: Elo: [X] | Hold: [X]% | Break: [X]% | DR: [X] | L5: [W-L] (соперники, отказы/травмы)
📋 **Итоговый вердикт**

| Матч | Выбор маркета | Риск / Фактор |
| :--- | :--- | :--- |
| **[Игрок 1] vs [Игрок 2]** | [Выбор исхода/форы/тотала] | **[Низкий / Средний / Высокий].** [Суть перевеса и главный фактор] |

"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1}
    }
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={GEMINI_KEY}"
    
    for attempt in range(3):
        try:
            with httpx.Client(timeout=60.0) as client:
                res = client.post(url, headers=headers, json=payload)
                res_json = res.json()
                
                if res.status_code == 200 and "candidates" in res_json:
                    parts = res_json["candidates"][0].get("content", {}).get("parts", [])
                    text_parts = [p.get("text", "") for p in parts if "text" in p and not p.get("thought", False)]
                    full_text = "".join(text_parts).strip()
                    clean_text = re.sub(r'(?i)^.*?(?=📊|\*\*Метрики)', '', full_text, flags=re.DOTALL)
                    return clean_text.strip() if clean_text.strip() else full_text
                elif res.status_code == 503 and attempt < 2:
                    time.sleep(2)
                    continue
                elif "error" in res_json:
                    return f"⚠️ Ошибка API: {res_json['error'].get('message', 'Неизвестная ошибка')}"
                else:
                    return f"⚠️ Ошибка сервера ({res.status_code}): {res.text}"
        except Exception as e:
            if attempt == 2:
                return f"⚠️ Ошибка сети: {e}"
            time.sleep(2)
            
    return "⚠️ Сервер временно не отвечает. Попробуйте еще раз."
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
        
    msg = bot.reply_to(message, "⏳ Ищу свежие результаты L5 и считаю линию...")
    report = analyze_with_search(raw_text)
    send_long_message(message.chat.id, report, reply_to_msg_id=msg.message_id)
if __name__ == "__main__":
    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception:
        pass
    bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)
