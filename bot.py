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

ИНСТРУКЦИЯ:
1. Сделай веб-поиск (через Google Search) и найди точные статистические факты для участников матча:
   - Последние 5 сыгранных матчей по календарю (дата, точный счет по сетам/геймам, турнир, уровень оппозиции, затяжные матчи/снятия).
   - Личные встречи (H2H) за последние 6-12 месяцев.
   
2. РОЛЬ И РЕЖИМ РАБОТЫ:
   Ты — сухой, бескомпромиссный аналитик линии спортивных событий и калькулятор рисков. Приступай к глубокому анализу без лишних вступлений и воды.

3. АЛГОРИТМ ПРОВЕРКИ:
   - Уровень оппозиции: Оцени последние 5 матчей. Победы над игроками из третьей сотни/Челленджеров не являются показателем формы.
   - H2H и покрытие: Кто побеждал в свежих встречах? Винрейт и профильность на текущем покрытии.
   - Физический риск: Маркеры усталости (затяжные матчи вчера/позавчера, медицинские тайм-ауты, снятия).
   - Календарь: Защита очков, возможная потеря концентрации перед более крупным стартом.
   - АНАЛИЗ ВСЕХ МАРКЕТОВ (КРИТИЧЕСКИ ВАЖНО): Анализируй все рынки для игры, а не только базовые исходы П1/П2. Ищи варианты, где форы (плюсовые или минусовые по геймам/сетам) или тоталы идеально нивелируют опасные ситуации и сглаживают риски.

4. ФОРМАТ ВЫДАЧИ:
   - Никаких оценочных суждений про «настрой». Только цифры и жесткая логика.
   - Если в линии подходит 0 вариантов — пиши прямо.
   - Итоговая таблица:
| Турнир/Время | Матч | Выбор (с учетом всех маркетов) | Главный риск или фактор |
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}]
    }

    try:
        # 1. Получаем список реально доступных моделей в вашем ключе
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}"
        list_res = httpx.get(list_url, timeout=15.0).json()
        
        if "error" in list_res:
            return f"Ошибка API ключа: {list_res['error'].get('message')}"
            
        available_models = [
            m["name"] for m in list_res.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        ]
        
        if not available_models:
            return f"Доступные модели не найдены. Ответ Google: {list_res}"

        # 2. Перебираем исключительно те модели, которые отдал сам Google
        last_error = ""
        for full_model_name in available_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/{full_model_name}:generateContent?key={GEMINI_KEY}"
            try:
                res = httpx.post(url, headers=headers, json=payload, timeout=60.0)
                res_json = res.json()
                if "candidates" in res_json:
                    return res_json["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    last_error = f"{full_model_name}: {res_json.get('error', {}).get('message', 'нет ответа')}"
            except Exception as e:
                last_error = f"{full_model_name}: {str(e)}"
                continue

        return f"Ошибки при запросе к моделям:\n{last_error}\n\nСписок доступных моделей: {', '.join(available_models)}"

    except Exception as e:
        return f"Ошибка соединения: {str(e)}"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "🎾 Бот готов! Отправьте ссылку на матч Flashscore или имена соперников.")

@bot.message_handler(content_types=['text', 'photo'])
def handle_msg(message):
    raw_text = message.text or message.caption or ""
    if not raw_text.strip():
        bot.reply_to(message, "Пожалуйста, отправьте ссылку на матч или имена соперников.")
        return
        
    msg = bot.reply_to(message, "⏳ Выполняю веб-поиск и расчет рисков...")
    
    urls = re.findall(r'https?://[^\s]+', raw_text)
    match_context = raw_text
    if urls:
        extracted = [fetch_page_context(u) for u in urls]
        match_context = "\n".join(extracted) + "\n\nИсходный текст: " + raw_text
        
    report = analyze_with_search(match_context)
    bot.edit_message_text(report, chat_id=message.chat.id, message_id=msg.message_id)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling()
