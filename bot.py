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
            return f"Матч: {title} | {desc}"
    except Exception:
        return url
def analyze_with_search(user_input: str) -> str:
    headers = {"Content-Type": "application/json"}
    
    prompt = f"""
ВХОДНЫЕ ДАННЫЕ (СПИСОК МАТЧЕЙ):
{user_input}
Ты — сухой спортивный аналитик линии и калькулятор рисков.
Текущий год: 2026. Язык: строго русский.
ЗАДАЧА:
Для КАЖДОГО матча из списка найди через Google Search (Tennis Abstract, Flashscore):
- Surface Elo, Hold %, Break %, Dominance Ratio (DR), Win % на 2-й подаче.
- Текущую форму и H2H.
- Проанализируй все рынки (исходы, форы по сетам/геймам, тоталы для нивелирования рисков).
ФОРМАТ ВЫДАЧИ:
Никаких вводных слов, мыслей и воды. Только компактный отчет:
📊 **Метрики Tennis Abstract**
[Для каждого матча короткая строка: Игрок 1 vs Игрок 2 -> Elo / Hold / Break / DR]
📋 **Сводная таблица по линии**

| # | Матч | Выбор (все маркеты) | Главный фактор и риск |
| :--- | :--- | :--- | :--- |
| 1 | Игрок 1 vs Игрок 2 | ... | ... |
| 2 | Игрок 3 vs Игрок 4 | ... | ... |

"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0.1}
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
                res = httpx.post(url, headers=headers, json=payload, timeout=90.0)
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
    bot.reply_to(message, "🎾 Отправьте список ссылок Flashscore (по одной в строке) или список матчей текстом.")
@bot.message_handler(content_types=['text', 'photo'])
def handle_msg(message):
    raw_text = message.text or message.caption or ""
    if not raw_text.strip():
        bot.reply_to(message, "Отправьте список матчей.")
        return
        
    urls = re.findall(r'https?://[^\s]+', raw_text)
    
    count_label = f"({len(urls)} шт.)" if urls else ""
    msg = bot.reply_to(message, f"⏳ Анализирую блок матчей {count_label}... Сверяю Tennis Abstract и линию...")
    
    match_context = raw_text
    if urls:
        extracted = [fetch_page_context(u) for u in urls]
        match_context = "\n".join(extracted) + "\n\nИсходный ввод:\n" + raw_text
        
    report = analyze_with_search(match_context)
    send_long_message(message.chat.id, report, reply_to_msg_id=msg.message_id)
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception:
        pass
    bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)
