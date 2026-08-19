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
    # Используем endpoint с поддержкой Google Search Grounding
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
    headers = {"Content-Type": "application/json"}
    
    prompt = f"""
ВХОДНЫЕ ДАННЫЕ:
{user_input}

ИНСТРУКЦИЯ:
1. Сделай веб-поиск (через Google Search) и найди точные статистические факты для игроков/команд:
   - Последние 5 сыгранных матчей по календарю (дата, счет, турнир, затяжные 3-сетовики/снятия).
   - Личные встречи (H2H) за последние 6-12 месяцев.
   
2. РОЛЬ И РЕЖИМ РАБОТЫ:
   Ты — сухой, бескомпромиссный аналитик линии спортивных событий и калькулятор рисков. Приступай к глубокому анализу без лишних вступлений и воды.

3. АЛГОРИТМ ПРОВЕРКИ:
   - Уровень оппозиции: Оцени последние 5 матчей. Победы над игроками с Челленджеров/ITF или из третьей сотни не являются показателем формы.
   - H2H и покрытие: Кто побеждал в свежих встречах? Винрейт и профильность на текущем покрытии.
   - Физический риск: Маркеры усталости (матчи >2.5 часов, медицинские тайм-ауты, свежие снятия).
   - Календарь: Защита очков, возможный спад перед более крупным турниром.
   - АНАЛИЗ ВСЕХ МАРКЕТОВ: Анализируй все рынки, а не только базовые П1/П2. Ищи варианты, где форы (плюсовые/минусовые по геймам/сетам) или тоталы идеально нивелируют опасные ситуации и сглаживают риски.

4. ФОРМАТ ВЫДАЧИ:
   - Никаких оценочных суждений про «настрой». Только цифры и жесткая логика.
   - Если в линии подходит 0 вариантов — пиши прямо.
   - Итоговая таблица:
| Турнир/Время | Матч | Выбор (с учетом всех маркетов) | Главный риск или фактор |
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}]  # Включение веб-поиска Google внутри Gemini
    }

    try:
        res = httpx.post(url, headers=headers, json=payload, timeout=60.0)
        res_json = res.json()
        
        # Если модель 2.0 недоступна, запасной запрос без явного инструмента поиска
        if "candidates" in res_json:
            return res_json["candidates"][0]["content"]["parts"][0]["text"]
        else:
            fallback_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_KEY}"
            fallback_payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "tools": [{"google_search": {}}]
            }
            res_fb = httpx.post(fallback_url, headers=headers, json=fallback_payload, timeout=60.0)
            fb_json = res_fb.json()
            if "candidates" in fb_json:
                return fb_json["candidates"][0]["content"]["parts"][0]["text"]
            return f"Ответ Google API: {res_json.get('error', {}).get('message', str(res_json))}"
    except Exception as e:
        return f"Ошибка выполнения анализа: {str(e)}"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "🎾 Аналитический бот готов. Отправьте ссылку на матч, скриншот с текстом или просто имена игроков/команд.")

@bot.message_handler(content_types=['text', 'photo'])
def handle_msg(message):
    raw_text = message.text or message.caption or ""
    if not raw_text.strip():
        bot.reply_to(message, "Пожалуйста, отправьте ссылку на матч или имена соперников.")
        return
        
    msg = bot.reply_to(message, "⏳ Выполняю веб-поиск данных, H2H и расчет рисков...")
    
    # Если в сообщении есть ссылка, извлекаем заголовок страницы для точного поиска
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
    
