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
    return "Bot is running perfectly!"

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
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        with httpx.Client(follow_redirects=True, headers=headers, timeout=12.0) as client:
            resp = client.get(url)
            soup = BeautifulSoup(resp.text, 'html.parser')
            title = soup.title.string if soup.title else ""
            desc = ""
            desc_tag = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
            if desc_tag and desc_tag.get('content'):
                desc = desc_tag['content']
            return f"Матч: {title} | {desc}"
    except Exception:
        return url

def analyze_with_search(user_input: str) -> str:
    headers = {"Content-Type": "application/json"}
    
    prompt = f"""
ВХОДНЫЕ ДАННЫЕ:
{user_input}

ЖЕСТКИЕ ПРАВИЛА И ЯЗЫК:
- ОТВЕТ ДОЛЖЕН БЫТЬ ПОЛНОСТЬЮ НА РУССКОМ ЯЗЫКЕ.
- КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО выводить внутренние мысли, рассуждения (Chain of Thought), черновики, промпты или технические команды.
- Выдавай СРАЗУ готовый структурированный отчет без лишних вступительных приветствий.

ИНСТРУКЦИЯ ПО ВЕБ-ПОИСКУ:
1. Выполни поиск через Google Search по базам Tennis Abstract, Flashscore и официальной статистике тура:
   - Последние 5 сыгранных матчей каждого игрока (дата, счет, турнир).
   - Личные встречи (H2H) за последние 6-12 месяцев.
   - Метрики Tennis Abstract (за 52 недели на текущем покрытии):
     * Hard/Clay/Grass Elo Rating
     * Hold % (удержание подачи) и Break % (брейки)
     * Dominance Ratio (DR)
     * Win % на 2-й подаче (своей и чужой)

2. РОЛЬ И АЛГОРИТМ ПРОВЕРКИ:
   Ты — сухой аналитик спортивной линии.
   - Оцени уровень оппозиции (отсекай низкосортные турниры).
   - Проверь физическую усталость (>2.5 ч на корте, снятия).
   - Обоснуй маркеты: анализируй не только исходы, но и форы по геймам/сетам и тоталы для нивелирования рисков.

3. СТРОГИЙ ФОРМАТ ВЫДАЧИ (ТОЛЬКО ЭТОТ БЛОК НА РУССКОМ):

**1. Метрики Tennis Abstract**
[Показатели Elo на покрытии, Hold/Break %, DR, 2nd Serve Win %]

**2. Последние 5 матчей и H2H**
[Сухие факты по результатам]

**3. Анализ рисков и маркетов**
[Математическое обоснование выбора фор/тоталов]

**4. Итоговая таблица**
| Турнир/Время | Матч | Рекомендуемый выбор (все маркеты) | Главный фактор / Уровень риска |
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}]
    }

    try:
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}"
        list_res = httpx.get(list_url, timeout=15.0).json()
        
        if "error" in list_res:
            return f"Ошибка API ключа: {list_res['error'].get('message')}"
            
        available_models = [
            m["name"] for m in list_res.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        ]
        available_models.sort(key=lambda x: ("flash" in x, "3." in x, "pro" in x), reverse=True)

        last_error = ""
        for full_model_name in available_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/{full_model_name}:generateContent?key={GEMINI_KEY}"
            try:
                res = httpx.post(url, headers=headers, json=payload, timeout=60.0)
                res_json = res.json()
                if "candidates" in res_json:
                    text_out = res_json["candidates"][0]["content"]["parts"][0]["text"]
                    # Очистка от возможных служебных тегов
                    text_out = re.sub(r'<thought>.*?</thought>', '', text_out, flags=re.DOTALL)
                    text_out = re.sub(r'```json.*?```', '', text_out, flags=re.DOTALL)
                    return text_out.strip()
                else:
                    last_error = f"{full_model_name}: {res_json.get('error', {}).get('message', 'нет ответа')}"
            except Exception as e:
                last_error = f"{full_model_name}: {str(e)}"
                continue

        return f"Ошибка при запросе к модели: {last_error}"

    except Exception as e:
        return f"Ошибка соединения: {str(e)}"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "🎾 Аналитический бот готов к работе. Отправьте ссылку на матч Flashscore или имена игроков.")

@bot.message_handler(content_types=['text', 'photo'])
def handle_msg(message):
    raw_text = message.text or message.caption or ""
    if not raw_text.strip():
        bot.reply_to(message, "Пожалуйста, отправьте ссылку на матч или имена игроков.")
        return
        
    msg = bot.reply_to(message, "⏳ Собираю статистику Tennis Abstract, форму и рассчитываю риски...")
    
    urls = re.findall(r'https?://[^\s]+', raw_text)
    match_context = raw_text
    if urls:
        extracted = [fetch_page_context(u) for u in urls]
        match_context = "\n".join(extracted) + "\n\nИсходный текст: " + raw_text
        
    report = analyze_with_search(match_context)
    send_long_message(message.chat.id, report, reply_to_msg_id=msg.message_id)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling()
