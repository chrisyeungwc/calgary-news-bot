import os
import requests
import pandas as pd
import pytz
from bs4 import BeautifulSoup
from dateutil import parser
from datetime import datetime, timedelta

# --- 1. Configuration and Constants ---
CALGARY_TZ = pytz.timezone('America/Edmonton')
FEEDS_LIST = ['topstories', 'world', 'canada', 'business', 'health', 'technology', 'canada-calgary']
FEED_DICT = {
    'topstories': 'Top Stories', 'world': 'World', 'canada': 'Canada', 
    'business': 'Business', 'health': 'Health', 'technology': 'Technology', 
    'canada-calgary': 'Calgary'
}
BASE_URL = 'https://www.cbc.ca/webfeed/rss/rss-'
CSV_FILE = 'cbc_news.csv'

# Fetch secrets from environment variables
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
TG_TOKEN = os.getenv('TELEGRAM_TOKEN')
TG_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def grab_news(feed_type):
    """Scrape news from CBC RSS feeds and return a DataFrame"""
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
            
            # Parse publication date and convert to Calgary time
            pub_date = item.find('pubDate').text
            dt_calgary = parser.parse(pub_date).astimezone(CALGARY_TZ)

            # Robust handling for missing descriptions or images
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
        print(f"Error scraping {feed_type}: {e}")
        return pd.DataFrame()

def get_ai_summary(news_text):
    """Call DeepSeek API for bilingual summary and sentiment analysis"""
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}", 
        "Content-Type": "application/json"
    }
    
    prompt = f"""
    You are a professional Data Analyst assistant. 
    Below are the latest Calgary news:
    {news_text}
    
    Tasks:
    1. Select 5 most important news.
    2. For each news, provide a summary with the English version FIRST, followed by the Traditional Chinese (Hong Kong style) version.
    3. Format the output professionally for a Telegram message using Markdown. Use bold English titles for clarity.

    At the end, provide a 'Daily Insight' section (English First):
    1. A brief Sentiment Analysis (Positive/Neutral/Negative) with reasons in both languages.
    2. 3 Key Topics (Keywords) in both languages.
    3. A 'Summary Conclusion' (1-2 sentences) in English followed by Traditional Chinese.
    """
    
    data = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    try:
        resp = requests.post(url, json=data, headers=headers)
        return resp.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"AI Service Error: {e}"

def send_telegram(text):
    """Send formatted text to Telegram Bot"""
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def get_daily_batch(df):
    """Filter news from the last 24 hours based on Calgary timezone"""
    calgary_now = datetime.now(CALGARY_TZ)
    yesterday_calgary = calgary_now - timedelta(days=1)
    
    df['DateTime'] = pd.to_datetime(df['DateTime'])
    # Force convert to Calgary timezone for accurate comparison
    mask = (df['DateTime'].dt.tz_localize(None).dt.tz_localize(CALGARY_TZ) > yesterday_calgary)
    return df[mask]

# --- Main Pipeline Execution ---
if __name__ == "__main__":
    # 1. Scrape new data
    all_new_news = []
    for f in FEEDS_LIST:
        all_new_news.append(grab_news(f))
    df_new = pd.concat(all_new_news).drop_duplicates(subset=['Guid'])

    # 2. Incremental Update for CSV Database
    if os.path.exists(CSV_FILE):
        df_old = pd.read_csv(CSV_FILE)
        df_final = pd.concat([df_old, df_new]).drop_duplicates(subset=['Guid'], keep='last')
    else:
        df_final = df_new

    # Save to local CSV file
    df_final.sort_values('DateTime', ascending=False).to_csv(CSV_FILE, index=False)

    # 3. Filter daily news for AI processing
    daily_batch = get_daily_batch(df_final)
    # Target Calgary and Top Stories for AI analysis
    target_news = daily_batch[(daily_batch['FeedType'] == 'Calgary') | (daily_batch['FeedType'] == 'Top Stories')].head(15)
    
    if not target_news.empty:
        news_summary_input = ""
        for _, row in target_news.iterrows():
            desc = row['DescriptionTitle'] if row['DescriptionTitle'] else row['DescriptionAlt']
            news_summary_input += f"Title: {row['Title']}\nDesc: {desc}\nLink: {row['Link']}\n\n"
        
        # 4. Generate AI Report and Dispatch
        final_report = get_ai_summary(news_summary_input)
        send_telegram(final_report)
        print("Data Pipeline Executed Successfully.")
    else:
        print("No new updates found in the last 24 hours.")
