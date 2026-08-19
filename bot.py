import os
import re
import time
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
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
# Запуск Flask в фоновом потоке ДО бота
threading.Thread(target=run_flask, daemon=True).start()
bot_token = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(bot_token, threaded=True)
GEMINI_KEY = os.getenv("GEMINI_KEY")
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
Язык: русский.
ЗАДАЧА:
Найди через Google Search по базам Tennis Abstract и Flashscore:
1. Hard/Surface Elo, Hold %, Break %, Dominance Ratio (DR), Win % на 2-й подаче.
2. Итоги последних матчей и H2H.
ВЫДАЙ ТОЛЬКО КОРОТКУЮ ВЫЖИМКУ:
📊 **Метрики Tennis Abstract**
• [Игрок 1]: Elo: X | Hold: X% | Break: X% | DR: X
• [Игрок 2]: Elo: X | Hold: X% | Break: X% | DR: X
📋 **Итоговый вердикт**

| Матч | Выбор маркета | Риск / Фактор |
| :--- | :--- | :--- |
| Игрок 1 vs Игрок 2 | ... | ... |

"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0.1}
    }
    try:
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}"
        list_res = httpx.get(list_url, timeout=10.0).json()
        
        if "error" in list_res:
            return f"Ошибка API ключа: {list_res['error'].get('message')}"
            
        models = [
            m["name"] for m in list_res.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        ]
        models.sort(key=lambda x: ("flash" in x, "3." in x), reverse=True)
        for model_name in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={GEMINI_KEY}"
            try:
                res = httpx.post(url, headers=headers, json=payload, timeout=60.0)
                res_json = res.json()
                if "candidates" in res_json:
                    parts = res_json["candidates"][0].get("content", {}).get("parts", [])
                    text_parts = [p.get("text", "") for p in parts if "text" in p and not p.get("thought", False)]
                    full_text = "".join(text_parts).strip()
                    clean_text = re.sub(r'(?i)^.*?(?=📊|\*\*Метрики)', '', full_text, flags=re.DOTALL)
                    return clean_text.strip() if clean_text.strip() else full_text
            except Exception:
                continue
        return "Не удалось получить расчет от модели. Попробуйте еще раз."
    except Exception as e:
        return f"Ошибка соединения: {str(e)}"
@bot.message_handler(commands=['start'])
def send_welcome(message):
    print(f"--> Получена команда /start от {message.chat.id}", flush=True)
    bot.reply_to(message, "🎾 Аналитический бот активен. Отправьте матч или список матчей.")
@bot.message_handler(content_types=['text', 'photo'])
def handle_msg(message):
    raw_text = message.text or message.caption or ""
    print(f"--> Получено сообщение: {raw_text[:30]}...", flush=True)
    if not raw_text.strip():
        bot.reply_to(message, "Отправьте список матчей.")
        return
        
    msg = bot.reply_to(message, "⏳ Рассчитываю метрики и риски...")
    
    urls = re.findall(r'https?://[^\s]+', raw_text)
    match_context = raw_text
    if urls:
        extracted = [fetch_page_context(u) for u in urls]
        match_context = "\n".join(extracted) + "\n\n" + raw_text
        
    report = analyze_with_search(match_context)
    try:
        bot.edit_message_text(report, chat_id=message.chat.id, message_id=msg.message_id)
    except Exception:
        bot.send_message(message.chat.id, report)
if __name__ == "__main__":
    print("--> Бот запускается...", flush=True)
    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception:
        pass
        
    print("--> Polling запущен", flush=True)
    bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)
