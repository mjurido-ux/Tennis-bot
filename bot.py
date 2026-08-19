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
        import asyncio
import os
import re
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from playwright.async_api import async_playwright
from google import genai

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
ai_client = genai.Client(api_key=GEMINI_KEY)

async def scrape_match_data(browser, url: str) -> str:
    """Открывает страницу и забирает точные данные матчей."""
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
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
        return f"\n--- Ошибка загрузки ({url}): {str(e)} ---"
    finally:
        await page.close()
        await context.close()

def analyze_all(raw_data: str) -> str:
    """Глубокий бескомпромиссный анализ линии и рынков."""
    prompt = f"""
РОЛЬ И РЕЖИМ РАБОТЫ:
Ты — сухой, бескомпромиссный аналитик линии спортивных событий и калькулятор рисков. Немедленно приступай к нормальному, глубокому анализу на основе предоставленных ниже фактов без лишних вступлений и воды.

ВХОДНЫЕ ДАННЫЕ (ФАКТЫ ИЗ СЕТКИ / H2H):
{raw_data}

АЛГОРИТМ ПРОВЕРКИ (ОБЯЗАТЕЛЕН К ИСПОЛНЕНИЮ):
1. **Уровень оппозиции:** Оцени последние 5 матчей. Победы над игроками с Челленджеров/ITF или из третьей сотни не являются показателем формы для матча основного тура.
2. **H2H и покрытие:** Кто побеждал в свежих личных встречах? У кого выше профильность и винрейт на текущем покрытии?
3. **Физический риск:** Учти маркеры усталости (матчи дольше 2.5 часов, 3 сета, медицинские тайм-ауты/снятия).
4. **Календарь:** Проверь логику турнира (защита очков, фактор перегруза перед крупными стартами).
5. **АНАЛИЗ ВСЕХ МАРКЕТОВ (КРИТИЧЕСКИ ВАЖНО):** Анализируй ВСЕ рынки для игры, а не только базовые исходы П1/П2. Ищи варианты, где форы (плюсовые или минусовые по геймам/сетам) или тоталы могут идеально нивелировать опасные ситуации и сгладить риски.

ФОРМАТ ВЫДАЧИ:
- Никаких оценочных суждений про «настрой». Только цифры, факты и жесткая логика.
- Если в линии подходит 0 вариантов — пиши прямо: «НЕТ НАДЕЖНЫХ ВАРИАНТОВ». Не натягивай сову на глобус. Проходной балл — 100% соответствие критериям надежности.
- Для каждого разобранного матча сделай краткую выжимку по 5 пунктам алгоритма, а в конце выдай финальную сводную таблицу:
  | Турнир / Время | Матч | Выбор (с учетом всех маркетов: форы/тоталы/исход) | Главный риск или фактор |
"""
    response = ai_client.models.generate_content(
        model="gemini-2.5-pro",
        contents=prompt
    )
    return response.text

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer("Пришлите одну или несколько ссылок на матчи Flashscore (каждую с новой строки) для автоматического сбора статистики и глубокого анализа рынков.")

@dp.message()
async def handle_links(message: types.Message):
    urls = re.findall(r'https?://[^\s]+', message.text)
    if not urls:
        await message.answer("Пришлите ссылки на матчи, начинающиеся с http/https.")
        return

    status = await message.answer(f"⏳ Сбор данных для {len(urls)} матчей...")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            tasks = [scrape_match_data(browser, u) for u in urls]
            results = await asyncio.gather(*tasks)
            await browser.close()

        combined = "\n".join(results)
        await status.edit_text("📊 Статистика собрана. Gemini проводит анализ рынков...")
        
        report = analyze_all(combined)
        
        if len(report) > 4000:
            for x in range(0, len(report), 4000):
                await message.answer(report[x:x+4000])
        else:
            await message.answer(report)
            
        await status.delete()
    except Exception as e:
        await status.edit_text(f"Ошибка при выполнении: {str(e)}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
  
