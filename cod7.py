import asyncio
import logging
import sqlite3
import html
import requests
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.types import InputMediaPhoto
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from bs4 import BeautifulSoup
import feedparser

API_TOKEN = '8052447897:AAEEHwLSy7OIvZnPDnsGXTjGwiPtoRzrdHo'
CHANNEL_ID = -1002648195972
DB_NAME = "news2.db"
HEADERS = {"User-Agent": "Mozilla/5.0"}

logging.basicConfig(level=logging.INFO)

session = AiohttpSession()
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


def create_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE,
            site TEXT,
            image TEXT
        )
    """)
    conn.commit()
    conn.close()


def is_new(title):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM news WHERE title=?", (title,))
    result = c.fetchone()
    conn.close()
    return result is None


def save_news(title, site, image):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO news (title, site, image) VALUES (?, ?, ?)", (title, site, image))
    conn.commit()
    c.execute("DELETE FROM news WHERE id NOT IN (SELECT id FROM news ORDER BY id DESC LIMIT 50)")
    conn.commit()
    conn.close()


def fetch_news():
    url = 'https://techcrunch.com/feed/'
    feed = feedparser.parse(url)
    news_items = []

    for entry in feed.entries:
        title = html.unescape(entry.title)
        link = entry.link

        if not is_new(title):
            continue

        try:
            response = requests.get(link, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')

            paragraphs = soup.find_all('p')
            summary = paragraphs[0].text.strip() if paragraphs else '...'

            img_tag = soup.find('img')
            img_url = img_tag['src'] if img_tag and 'src' in img_tag.attrs else None

            full_text = f"{title}\n\n{summary}\n\nمنبع: TechCrunch"
            news_items.append((full_text, img_url))
            save_news(title, "TechCrunch", img_url)

            if len(news_items) >= 5:
                break
        except Exception as e:
            logging.warning(f"خطا در پردازش خبر: {e}")
            continue

    return news_items


async def main():
    create_db()
    while True:
        try:
            news_items = fetch_news()
            if not news_items:
                logging.info("خبری برای ارسال وجود ندارد.")
            for text, img in news_items:
                if img:
                    await bot.send_photo(CHANNEL_ID, img, caption=text)
                else:
                    await bot.send_message(CHANNEL_ID, text)
            await asyncio.sleep(900)
        except Exception as e:
            logging.error(f"خطا در دریافت خبر: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())