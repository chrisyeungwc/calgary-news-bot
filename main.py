import os
import warnings
import requests
import pandas as pd
import pytz
from bs4 import BeautifulSoup, FeatureNotFound, XMLParsedAsHTMLWarning
from dateutil import parser
from datetime import datetime, timedelta

# --- 1. Configuration ---
CALGARY_TZ = pytz.timezone('America/Edmonton')
TZINFOS = {
    'EST': -5 * 3600,
    'EDT': -4 * 3600,
    'MST': -7 * 3600,
    'MDT': -6 * 3600,
}
FEEDS_LIST = ['topstories', 'world', 'canada', 'business', 'health', 'technology', 'canada-calgary']
FEED_DICT = {
    'topstories': 'Top Stories', 
    'world': 'World', 
    'canada': 'Canada', 
    'business': 'Business', 
    'health': 'Health', 
    'technology': 'Technology', 
    'canada-calgary': 'Calgary'
}
BASE_URL = 'https://www.cbc.ca/webfeed/rss/rss-'
CSV_FILE = 'cbc_news.csv'
NEWS_COUNT = int(os.getenv('NEWS_COUNT', '20'))
CANDIDATE_NEWS_COUNT = int(os.getenv('CANDIDATE_NEWS_COUNT', str(NEWS_COUNT * 2)))
TELEGRAM_CHAR_LIMIT = 3900

# Secrets from environment variables
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
TG_TOKEN = os.getenv('TELEGRAM_TOKEN')
TG_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

def get_item_text(item, tag_name, default=""):
    """Read RSS tag text in both XML and HTML-parser fallback modes."""
    tag = item.find(tag_name) or item.find(tag_name.lower())
    if not tag:
        return default

    text = tag.get_text(strip=True)
    if text:
        return text

    # html.parser treats RSS <link>URL</link> as <link/>URL.
    if tag_name.lower() == 'link' and tag.next_sibling:
        return str(tag.next_sibling).strip()

    return default

def make_soup(markup, preferred_parser='xml'):
    """Use lxml when available, then fall back to Python's built-in parser."""
    try:
        return BeautifulSoup(markup, features=preferred_parser)
    except FeatureNotFound:
        return BeautifulSoup(markup, 'html.parser')

def grab_news(feed_type):
    """Scrape news items from a specific CBC RSS feed."""
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        resp = requests.get(BASE_URL + feed_type, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = make_soup(resp.text, 'xml')
        items = soup.find_all('item')
        news = []
        for item in items:
            title = get_item_text(item, 'title')
            link = get_item_text(item, 'link')
            guid = get_item_text(item, 'guid', link)
            category = get_item_text(item, 'category')
            pub_date = get_item_text(item, 'pubDate')
            if not pub_date:
                continue
            dt_calgary = parser.parse(pub_date, tzinfos=TZINFOS).astimezone(CALGARY_TZ)

            des_alt, des_title = "", ""
            desc_raw = item.find('description') or item.find('description'.lower())
            if desc_raw:
                desc_soup = make_soup(desc_raw.text, 'html.parser')
                img = desc_soup.find('img')
                if img:
                    des_alt = img.get('alt', '')
                    des_title = img.get('title', '')

            news.append({
                'Guid': guid, 'Title': title, 'Link': link, 
                'FeedType': FEED_DICT[feed_type], 
                'DateTime': dt_calgary.strftime('%Y-%m-%d %H:%M:%S'), 
                'DescriptionAlt': des_alt, 'DescriptionTitle': des_title, 
                'Category': category
            })
        return pd.DataFrame(news)
    except Exception as e:
        print(f"Scraping Error: {e}")
        return pd.DataFrame()

def get_ai_summary(news_text):
    """Process news data using LLM for bilingual summarization."""
    MODEL_CHOICE = os.getenv('MODEL_CHOICE', 'qwen3:0.6b')

    prompt_deepseek = f"""
    You are a professional Data Analyst. 
    Task: Summarize the latest news from the input provided:
    {news_text}
    
    Requirements:
    1. Return EXACTLY {NEWS_COUNT} important, non-duplicate news items.
    2. Priority: Calgary > Canada > World.
    3. Language: Bilingual (English & Traditional Chinese HK Style).
    4. **STRICT LIMIT: Each summary must be under 40 words (English) and 80 characters (Chinese).**
    5. Do not stop early. Continue until all {NEWS_COUNT} items are complete.

    Structure:
    # 📰 Daily Intelligence | 每日精要
    ## [Index]. [English Title] | [Chinese Title]
    **Summary:** [English]
    **摘要：** [Chinese]
    [🔗 Link](URL)
    ---------
    """

    prompt_qwen3 = f"""
    Task: Translate and summarize EXACTLY {NEWS_COUNT} news items from the input provided.
    Language: Bilingual (English & Traditional Chinese HK Style).
    Input: {news_text}
    Format:
    # Daily Intelligence | 每日精要
    ## [Index]. [English Title] | [Chinese Title]
    **Summary:** [English]
    **摘要：** [Chinese]
    [Link](URL)
    ---------
    """

    if MODEL_CHOICE == 'deepseek':
        url = "https://api.deepseek.com/chat/completions"
        headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
        model_playload = "deepseek-chat"
        active_prompt = prompt_deepseek
        data = {"model": model_playload, "messages": [{"role": "user", "content": active_prompt}], "temperature": 0.5}
    else:
        # Ollama 在 GitHub Action 的預設地址
        url = "http://localhost:11434/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        model_playload = "qwen3:0.6b"
        active_prompt = prompt_qwen3
        data = {"model": model_playload, "messages": [{"role": "user", "content": active_prompt}], "temperature": 0.1}
    
    try:
        resp = requests.post(url, json=data, headers=headers, timeout=300)
        resp.raise_for_status()
        return resp.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"AI Summary Error: {e}"

def send_telegram(text):
    """Send text via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()

def split_telegram_message(text, limit=TELEGRAM_CHAR_LIMIT):
    """Split long Telegram messages without dropping any news items."""
    if len(text) <= limit:
        return [text]

    chunks = []
    current = ""
    sections = text.split("---------")

    for index, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue

        block = section
        if index < len(sections) - 1:
            block += "\n---------"

        if len(block) > limit:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(block[i:i + limit] for i in range(0, len(block), limit))
            continue

        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) > limit:
            chunks.append(current.strip())
            current = block
        else:
            current = candidate

    if current:
        chunks.append(current.strip())

    return chunks

def send_report(final_report):
    """Send the full report, split into Telegram-safe chunks."""
    for chunk in split_telegram_message(final_report):
        send_telegram(chunk)

def get_daily_batch(df):
    """Filter news items within the last 24 hours."""
    if df.empty or 'DateTime' not in df.columns:
        return pd.DataFrame()

    calgary_now = datetime.now(CALGARY_TZ)
    yesterday_calgary = calgary_now - timedelta(days=1)
    df['DateTime'] = pd.to_datetime(df['DateTime'])
    mask = (df['DateTime'].dt.tz_localize(None).dt.tz_localize(CALGARY_TZ) > yesterday_calgary)
    return df[mask]

if __name__ == "__main__":
    # 1. Extraction
    all_new_news = []
    for f in FEEDS_LIST:
        all_new_news.append(grab_news(f))
    all_new_news = [df for df in all_new_news if not df.empty]
    df_new = pd.concat(all_new_news).drop_duplicates(subset=['Guid']) if all_new_news else pd.DataFrame()

    # 2. Storage
    if os.path.exists(CSV_FILE):
        df_old = pd.read_csv(CSV_FILE)
        df_final = pd.concat([df_old, df_new]).drop_duplicates(subset=['Guid'], keep='last')
    else:
        df_final = df_new
    df_final.sort_values('DateTime', ascending=False).to_csv(CSV_FILE, index=False)
    
    # 3. Processing
    daily_batch = get_daily_batch(df_final)
    if not daily_batch.empty:
        priority_map = {'Calgary': 0, 'Canada': 1, 'Health': 2, 'Technology': 3, 'Business': 4}
        daily_batch['Priority'] = daily_batch['FeedType'].map(priority_map).fillna(5)
        sorted_news = daily_batch.sort_values(by=['Priority', 'DateTime'], ascending=[True, False])
        target_news = sorted_news.head(CANDIDATE_NEWS_COUNT)
        news_summary_input = ""
        for _, row in target_news.iterrows():
            desc = row['DescriptionTitle'] if row['DescriptionTitle'] else row['DescriptionAlt']
            news_summary_input += f"Source: {row['FeedType']}\nTitle: {row['Title']}\nDesc: {desc}\nLink: {row['Link']}\n\n"
        
        # 4. AI Generation
        final_report = get_ai_summary(news_summary_input)
        
        # 5. Delivery: Split report to handle Telegram's 4096 character limit
        send_report(final_report)
            
        print("Pipeline executed successfully: Reports sent.")
    else:
        print("No news found.")
