import asyncio
import os
import re
import httpx
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
import google.generativeai as genai

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
genai.configure(api_key=os.getenv("GEMINI_KEY"))

async def fetch_data(url: str) -> str:
    try:
        async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:
            resp = await client.get(url, timeout=10.0)
            soup = BeautifulSoup(resp.text, 'html.parser')
            text = soup.get_text(separator=' ', strip=True)
            return f"\n--- МАТЧ ({url}) ---\n" + text[:2000] # берем первые 2000 символов
    except Exception as e:
        return f"\nОшибка {url}: {e}"

def analyze(data: str) -> str:
    model = genai.GenerativeModel('gemini-1.5-flash')
    return model.generate_content(f"Аналитик, данные: {data}. Выдай анализ рынков и таблицу: | Турнир | Матч | Выбор | Риск |").text

@dp.message()
async def handle(message: types.Message):
    urls = re.findall(r'https?://[^\s]+', message.text)
    if not urls: return
    await message.answer("⏳ Анализирую...")
    results = await asyncio.gather(*[fetch_data(u) for u in urls])
    await message.answer(analyze("\n".join(results)))

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
