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

API_TOKEN = os.getenv("API_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
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
            # گرفتن محتوای لینک خبر برای استخراج خلاصه و عکس
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
                if img:
                    img_data = download_image(img)
                    if img_data:
                        temp_file = "temp_image.jpg"
                        with open(temp_file, "wb") as f:
                            f.write(img_data)
                        photo = FSInputFile(temp_file)
                        await bot.send_photo(CHANNEL_ID, photo=photo, caption=text)
                        os.remove(temp_file)
                    else:
                        # اگر دانلود عکس نشد، فقط پیام ارسال کن
                        await bot.send_message(CHANNEL_ID, text)
                else:
                    await bot.send_message(CHANNEL_ID, text)
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
