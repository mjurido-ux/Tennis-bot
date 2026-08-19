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
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))
GEMINI_KEY = os.getenv("GEMINI_KEY")
def fetch_page_context(url: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        with httpx.Client(follow_redirects=True, headers=headers, timeout=10.0) as client:
            resp = client.get(url)
            soup = BeautifulSoup(resp.text, 'html.parser')
            title = soup.title.string if soup.title else ""
            desc = ""
            tag = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
            if tag and tag.get('content'):
                desc = tag['content']
            return f"Данные страницы: {title} | {desc}"
    except Exception:
        return url
def analyze_with_search(user_input: str) -> str:
    headers = {"Content-Type": "application/json"}
    
    prompt = f"""
Контекст:
{user_input}
Ты — сухой спортивный аналитик линии и калькулятор рисков.
Текущий год: 2026. Язык: строго русский.
ИНСТРУКЦИЯ:
Найди через Google Search по базам Tennis Abstract и Flashscore:
1. Hard/Surface Elo, Hold %, Break %, Dominance Ratio (DR), Win % на 2-й подаче.
2. Итоги 5 последних игр и H2H.
ФОРМАТ ВЫДАЧИ:
Никакой воды, мыслей и вступительных фраз. Выдай ТОЛЬКО короткий блок:
📊 **Метрики Tennis Abstract**
• [Игрок 1]: Elo: X | Hold: X% | Break: X% | DR: X | 2nd Srv Win: X%
• [Игрок 2]: Elo: X | Hold: X% | Break: X% | DR: X | 2nd Srv Win: X%
📋 **Итоговый вердикт по линии**

| Матч | Рекомендуемый выбор (форы/тоталы/исход) | Главный фактор и риск |
| :--- | :--- | :--- |
| Игрок 1 vs Игрок 2 | ... | ... |

"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {
            "temperature": 0.1
        }
    }
    try:
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}"
        list_res = httpx.get(list_url, timeout=12.0).json()
        
        if "error" in list_res:
            return f"Ошибка ключа: {list_res['error'].get('message')}"
            
        models = [
            m["name"] for m in list_res.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        ]
        models.sort(key=lambda x: ("flash" in x, "3." in x), reverse=True)
        last_error = ""
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
                else:
                    last_error = f"{model_name}: {res_json.get('error', {}).get('message', 'нет ответа')}"
            except Exception as e:
                last_error = f"{model_name}: {str(e)}"
                continue
        return f"Ошибка модели: {last_error}"
    except Exception as e:
        return f"Ошибка сети: {str(e)}"
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "🎾 Отправьте ссылку на матч Flashscore.")
@bot.message_handler(content_types=['text', 'photo'])
def handle_msg(message):
    raw_text = message.text or message.caption or ""
    if not raw_text.strip():
        bot.reply_to(message, "Отправьте ссылку на матч Flashscore.")
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
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Сброс зависших сессий и хуков
    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception:
        pass
    bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)
