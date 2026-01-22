import os
import requests
import pandas as pd
import pytz
from bs4 import BeautifulSoup
from dateutil import parser
from datetime import datetime, timedelta

# --- 1. Configuration ---
# Set local timezone for Calgary
CALGARY_TZ = pytz.timezone('America/Edmonton')

# Define RSS feed categories from CBC
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

# Environment variables for API keys and sensitive IDs
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
TG_TOKEN = os.getenv('TELEGRAM_TOKEN')
TG_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
LANG_CHOICE = os.getenv('LANG_CHOICE', 'Bilingual')

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
            
            # Convert UTC publication date to Calgary local time
            dt_calgary = parser.parse(pub_date).astimezone(CALGARY_TZ)

            # Extract image metadata from description if available
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
    """Process news data using DeepSeek LLM for bilingual summarization."""
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""
    You are a professional Data Analyst assistant. 
    Below are the latest news items sorted by regional priority (Calgary > Canada > World):
    {news_text}
    
    Tasks:
    1. Select the 10 most important and RELEVANT news items.
    2. **CRITICAL: DO NOT repeat the same story.** If multiple sources report the same event, select the best one.
    3. **PRIORITY RULE:** Prioritize local Calgary news, then National Canada news, then International news.
    4. **BILINGUAL REQUIREMENT:** Every title and summary must be Bilingual (English First, then Traditional Chinese HK Style).

    Output Structure:
    # 📰 Daily Intelligence | 每日新聞精要 (Top 10)
    
    ## [Index]. [English Title] | [Chinese Title]
    **Summary:** [English - concise]
    **摘要：** [Traditional Chinese - natural]
    [🔗 Link](URL_HERE)

    ---
    ## 📊 Daily Insight | 每日洞察
    1. **Sentiment Analysis | 情感分析** (Bilingual)
    2. **Key Topics | 關鍵主題** (Bilingual)
    3. **Regional Focus | 地域分布** (Mention the ratio of Calgary/Canada/World news)
    4. **Summary Conclusion | 總結結論** (Bilingual)
       
    CRITICAL: Wrap all URLs in [🔗 Link](URL) format.
    Each summary must be under 150 characters.
    """
    
    data = {"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0.5}
    resp = requests.post(url, json=data, headers=headers)
    return resp.json()['choices'][0]['message']['content']

def send_telegram(text):
    """Send the final report via Telegram Bot API with link previews disabled."""
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
    # Ensure timezone-aware comparison
    mask = (df['DateTime'].dt.tz_localize(None).dt.tz_localize(CALGARY_TZ) > yesterday_calgary)
    return df[mask]

if __name__ == "__main__":
    # 1. Extraction: Collect data from all RSS feeds
    all_new_news = []
    for f in FEEDS_LIST:
        all_new_news.append(grab_news(f))
    df_new = pd.concat(all_new_news).drop_duplicates(subset=['Guid'])

    # 2. Storage: Incremental update of the CSV database
    if os.path.exists(CSV_FILE):
        df_old = pd.read_csv(CSV_FILE)
        df_final = pd.concat([df_old, df_new]).drop_duplicates(subset=['Guid'], keep='last')
    else:
        df_final = df_new

    # Save to local CSV file
    df_final.sort_values('DateTime', ascending=False).to_csv(CSV_FILE, index=False)
    
    # 3. Processing: Regional Priority Sorting
    daily_batch = get_daily_batch(df_final)
    if not daily_batch.empty:
        # Define priority: Calgary (0) > Canada (1) > World (2) > Others (3)
        priority_map = {'Calgary': 0, 'Canada': 1, 'World': 2}
        daily_batch['Priority'] = daily_batch['FeedType'].map(priority_map).fillna(3)
        
        # Sort by regional priority then by time
        sorted_news = daily_batch.sort_values(by=['Priority', 'DateTime'], ascending=[True, False])
        target_news = sorted_news.head(35) # Pass top 35 candidates to LLM for final selection

        news_summary_input = ""
        for _, row in target_news.iterrows():
            desc = row['DescriptionTitle'] if row['DescriptionTitle'] else row['DescriptionAlt']
            # Format raw data for LLM input
            news_summary_input += f"Source: {row['FeedType']}\nTitle: {row['Title']}\nDesc: {desc}\nLink: {row['Link']}\n\n"
        
        # 4. Intelligence: AI Analysis and Delivery
        final_report = get_ai_summary(news_summary_input)
        send_telegram(final_report)
        print("Pipeline executed successfully: Report sent.")
    else:
        print("Pipeline executed successfully: No new updates found.")
