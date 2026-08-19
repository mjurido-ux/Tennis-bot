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
    """Разбивает длинный отчет на части до 4000 символов и отправляет последовательно."""
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

    # Если текст длинный — удаляем статусное сообщение и шлем частями
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

ИНСТРУКЦИЯ ПО ВЕБ-ПОИСКУ:
1. Выполни поиск через Google Search по базам Tennis Abstract, Flashscore и статистике тура:
   - Найди последние 5 сыгранных матчей каждого игрока (дата, счет по сетам/геймам, турнир, статус).
   - Найди историю H2H за последние 6-12 месяцев.
   - ОБЯЗАТЕЛЬНО найди метрики Tennis Abstract (за 52 недели на текущем покрытии):
     * Surface Elo Rating обоих игроков
     * Hold % (удержание подачи) и Break % (брейки на приеме)
     * Dominance Ratio (DR)
     * Win % на 2-й подаче (своей и чужой)

2. РОЛЬ И АЛГОРИТМ ПРОВЕРКИ:
   Ты — сухой аналитик спортивной линии и калькулятор рисков.
   - Оцени уровень оппозиции в последних 5 играх, отсекай победы на ITF/Челленджерах.
   - Проверь маркеры физической усталости (>2.5 ч на корте, снятия, тайм-ауты).
   - Обоснуй маркеты: если рассматривается фора (-3.5 и крупнее), подтверди ее через разницу Hold/Break % и Dominance Ratio. Ищи страхующие форы и тоталы для нивелирования рисков.

3. СТРУКТУРА ВЫДАЧИ:
   - Метрики Tennis Abstract (Hard Elo, Hold %, Break %, DR).
   - Последние 5 матчей и H2H.
   - Разбор рисков и логика маркетов.
   - Финальная таблица:
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
                    return res_json["candidates"][0]["content"]["parts"][0]["text"]
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
    bot.reply_to(message, "🎾 Аналитический бот готов к работе. Отправьте ссылку на матч или имена игроков.")

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
