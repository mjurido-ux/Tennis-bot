import asyncio
import os
import re
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from playwright.async_api import async_playwright
import google.generativeai as genai

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
genai.configure(api_key=GEMINI_KEY)

async def scrape_match_data(browser, url: str) -> str:
    context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await asyncio.sleep(2)
        elements = await page.locator(".h2h__section, .event__match").all()
        lines = []
        for el in elements[:12]:
            txt = await el.inner_text()
            clean = " ".join(txt.split())
            if clean:
                lines.append(clean)
        return f"\n--- МАТЧ ({url}) ---\n" + ("\n".join(lines) if lines else "Данные не найдены")
    except Exception as e:
        return f"\n--- Ошибка ({url}): {str(e)} ---"
    finally:
        await page.close()
        await context.close()

def analyze_all(raw_data: str) -> str:
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""
РОЛЬ: Сухой аналитик, калькулятор рисков. Данные:
{raw_data}

АЛГОРИТМ:
1. Уровень оппозиции (форма по 5 матчам).
2. H2H и покрытие.
3. Физический риск (усталость).
4. Календарь (логика турнира).
5. АНАЛИЗ МАРКЕТОВ: Форы, тоталы, риски.

ФОРМАТ: Только цифры и факты. Если нет надежных вариантов — пиши «НЕТ НАДЕЖНЫХ ВАРИАНТОВ». Итоговая таблица:
| Турнир | Матч | Выбор | Риск |
"""
    response = model.generate_content(prompt)
    return response.text

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer("Бот готов. Пришлите ссылки.")

@dp.message()
async def handle_links(message: types.Message):
    urls = re.findall(r'https?://[^\s]+', message.text)
    if not urls: return
    status = await message.answer("⏳ Сбор данных...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        tasks = [scrape_match_data(browser, u) for u in urls]
        results = await asyncio.gather(*tasks)
        await browser.close()
    combined = "\n".join(results)
    await status.edit_text("📊 Анализ...")
    report = analyze_all(combined)
    await message.answer(report)
    await status.delete()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
