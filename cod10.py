import asyncio
import logging
import sqlite3
import html
import os
import requests
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile
from bs4 import BeautifulSoup
import feedparser

# تنظیمات محیطی: اگر ترجیح می‌دهی از متغیرهای محیطی استفاده کنی، اینا رو از سیستم بخون
API_TOKEN = '8052447897:AAE2cTsJucX2CIKrjW8UxsxQiyFFvaeGS2M'
CHANNEL_ID = -1002648195972
DB_NAME = "news2.db"
HEADERS = {"User-Agent": "Mozilla/5.0"}

logging.basicConfig(level=logging.INFO)

# تعریف ربات و دیسپچر (با aiogram 3.0.0)
bot = Bot(token=API_TOKEN, parse_mode=ParseMode.HTML)
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

def download_image(img_url):
    try:
        response = requests.get(img_url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            return response.content
    except Exception as e:
        logging.warning(f"Error downloading image: {e}")
    return None

async def send_news_item(text, img_url):
    if img_url:
        img_data = download_image(img_url)
        if img_data:
            temp_filename = "temp_image.jpg"
            with open(temp_filename, "wb") as f:
                f.write(img_data)
            try:
                await bot.send_photo(CHANNEL_ID, FSInputFile(temp_filename), caption=text)
            except Exception as e:
                logging.error(f"Error sending photo: {e}")
            finally:
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
        else:
            await bot.send_message(CHANNEL_ID, text)
    else:
        await bot.send_message(CHANNEL_ID, text)

def fetch_news():
    url = 'https://techcrunch.com/feed/'
    feed_data = feedparser.parse(url)
    news_items = []

    for entry in feed_data.entries:
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

async def news_loop():
    create_db()
    while True:
        try:
            logging.info("بررسی اخبار جدید...")
            news_items = fetch_news()
            if not news_items:
                logging.info("خبری برای ارسال وجود ندارد.")
            for text, img in news_items:
                await send_news_item(text, img)
            await asyncio.sleep(900)  # هر 15 دقیقه
        except Exception as e:
            logging.error(f"خطا در دریافت خبر: {e}")
            await asyncio.sleep(60)

async def main():
    logging.info("ربات شروع به کار کرد.")
    asyncio.create_task(news_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
