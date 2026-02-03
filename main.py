import os
import requests
import pandas as pd
import pytz
from bs4 import BeautifulSoup
from dateutil import parser
from datetime import datetime, timedelta

# --- 1. Configuration ---
CALGARY_TZ = pytz.timezone('America/Edmonton')
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

# Secrets from environment variables
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
TG_TOKEN = os.getenv('TELEGRAM_TOKEN')
TG_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def grab_news(feed_type):
    """Scrape news items from a specific CBC RSS feed."""
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        resp = requests.get(BASE_URL + feed_type, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, features='xml')
        items = soup.find_all('item')
        news = []
        for item in items:
            title = item.find('title').text if item.find('title') else ""
            link = item.find('link').text if item.find('link') else ""
            guid = item.find('guid').text if item.find('guid') else link
            category = item.find('category').text if item.find('category') else ""
            pub_date = item.find('pubDate').text
            dt_calgary = parser.parse(pub_date).astimezone(CALGARY_TZ)

            des_alt, des_title = "", ""
            desc_raw = item.find('description')
            if desc_raw:
                desc_soup = BeautifulSoup(desc_raw.text, 'lxml')
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
    1. Select EXACTLY 10 important, non-duplicate news items.
    2. Priority: Calgary > Canada > World.
    3. Language: Bilingual (English & Traditional Chinese HK Style).
    4. **STRICT LIMIT: Each summary must be under 30 words (English) and 60 characters (Chinese).**

    Structure:
    # 📰 Daily Intelligence | 每日精要
    ## [Index]. [English Title] | [Chinese Title]
    **Summary:** [English]
    **摘要：** [Chinese]
    [🔗 Link](URL)

    ---------
    ## 📊 Daily Insight | 每日洞察
    1. Sentiment: [Bilingual]
    2. Key Topics: [Bilingual]
    3. Conclusion: [Bilingual]
    """

    prompt_qwen3 = f"""
    Summarize these news items. 
    Output Language: Bilingual (English and Traditional Chinese).
    For each item, provide:
    1. Title
    2. One sentence summary in English
    3. 一句中文摘要
    4. Link

    News Content:
    {news_text}
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
        data = {"model": model_playload, "messages": [{"role": "user", "content": active_prompt}], "temperature": 0.2}
    
    try:
        resp = requests.post(url, json=data, headers=headers, timeout=300)
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
    requests.post(url, json=payload)

def get_daily_batch(df):
    """Filter news items within the last 24 hours."""
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
    df_new = pd.concat(all_new_news).drop_duplicates(subset=['Guid'])

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
        priority_map = {'Calgary': 0, 'Canada': 1, 'World': 2}
        daily_batch['Priority'] = daily_batch['FeedType'].map(priority_map).fillna(3)
        sorted_news = daily_batch.sort_values(by=['Priority', 'DateTime'], ascending=[True, False])
        MODEL_CHOICE = os.getenv('MODEL_CHOICE', 'qwen3:0.6b')
        
        if MODEL_CHOICE == 'deepseek':
            num_news = 30 
        else: 
            num_news = 10 # Qwen 10 news only 
        target_news = sorted_news.head(num_news)
        news_summary_input = ""
        for _, row in target_news.iterrows():
            desc = row['DescriptionTitle'] if row['DescriptionTitle'] else row['DescriptionAlt']
            news_summary_input += f"Source: {row['FeedType']}\nTitle: {row['Title']}\nDesc: {desc}\nLink: {row['Link']}\n\n"
        
        # 4. AI Generation
        final_report = get_ai_summary(news_summary_input)
        
        # 5. Delivery: Split report to handle Telegram's 4096 character limit
        # split logic: report included "---------" and the model is deepseek 
        if "---------" in final_report:
            parts = final_report.split("---------")
            news_part = parts[0].strip()
            # The rest after the first "---------" becomes the insight part
            insight_part = "---------".join(parts[1:]).strip()
            
            # Send the News Part first
            if news_part:
                send_telegram(news_part)
            
            # Send the Insight Part as a follow-up
            if insight_part:
                # Adding a header to the second message for clarity, only for deepseek model
                send_telegram(f"📊 **Daily Insight Continued...**\n\n{insight_part}")
        else:
            send_telegram(final_report)
            
        print("Pipeline executed successfully: Reports sent.")
    else:
        print("No news found.")
