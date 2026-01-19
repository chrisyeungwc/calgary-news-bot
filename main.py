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
FEED_DICT = {'topstories': 'Top Stories', 'world': 'World', 'canada': 'Canada', 'business': 'Business', 'health': 'Health', 'technology': 'Technology', 'canada-calgary': 'Calgary'}
BASE_URL = 'https://www.cbc.ca/webfeed/rss/rss-'
CSV_FILE = 'cbc_news.csv'

# Secrets from environment variables
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
TG_TOKEN = os.getenv('TELEGRAM_TOKEN')
TG_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
# Automatically reads the language choice from GitHub UI
LANG_CHOICE = os.getenv('LANG_CHOICE', 'Bilingual')

def grab_news(feed_type):
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
        print(f"Error: {e}")
        return pd.DataFrame()

def get_ai_summary(news_text):
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    
    # Enhanced Prompt with Dynamic Language Choice
    prompt = f"""
    You are a professional Data Analyst assistant. 
    Below are the latest Calgary news:
    {news_text}
    
    Tasks:
    1. Select 5 most important news.
    2. Format the output professionally for a Telegram message using Markdown. 
    3. **CRITICAL: Every title, section header, and summary must be Bilingual (English First, then Traditional Chinese).**

    Output Structure (for Bilingual):
    # 📰 Daily Brief | 每日摘要
    ## [Index]. [English Title] | [Chinese Title]
    **Summary:** [English]
    **摘要：** [Chinese]
    🔗 [Link](URL_HERE)  <-- CRITICAL: Use this format for links

    CRITICAL: You MUST wrap the URL in the [🔗 Link](URL) format. 
    Do not display the raw URL.
    
    ---
    ## 📊 Daily Insight | 每日洞察
    1. Sentiment Analysis | 情感分析: 
    - [English Sentiment & Reason]
    - [Chinese Sentiment & Reason]
    2. Key Topics | 關鍵主題: 
    - [English Topics]
    - [Chinese Topics]
    3. Summary Conclusion | 總結結論: 
    - [English Conclusion]
    - [Chinese Conclusion]
    """
    
    data = {"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0.5}
    resp = requests.post(url, json=data, headers=headers)
    return resp.json()['choices'][0]['message']['content']

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True}
    requests.post(url, json=payload)

def get_daily_batch(df):
    calgary_now = datetime.now(CALGARY_TZ)
    yesterday_calgary = calgary_now - timedelta(days=1)
    df['DateTime'] = pd.to_datetime(df['DateTime'])
    mask = (df['DateTime'].dt.tz_localize(None).dt.tz_localize(CALGARY_TZ) > yesterday_calgary)
    return df[mask]

if __name__ == "__main__":
    all_new_news = []
    for f in FEEDS_LIST:
        all_new_news.append(grab_news(f))
    df_new = pd.concat(all_new_news).drop_duplicates(subset=['Guid'])

    if os.path.exists(CSV_FILE):
        df_old = pd.read_csv(CSV_FILE)
        df_final = pd.concat([df_old, df_new]).drop_duplicates(subset=['Guid'], keep='last')
    else:
        df_final = df_new

    df_final.sort_values('DateTime', ascending=False).to_csv(CSV_FILE, index=False)
    
    daily_batch = get_daily_batch(df_final)
    target_news = daily_batch[(daily_batch['FeedType'] == 'Calgary') | (daily_batch['FeedType'] == 'Top Stories')].head(15)

    if not target_news.empty:
        news_summary_input = ""
        for _, row in target_news.iterrows():
            desc = row['DescriptionTitle'] if row['DescriptionTitle'] else row['DescriptionAlt']
            # Use Markdown [Link Text](Link) format
            link_markdown = f"[🔗 News Link]({row['Link']})"
            news_summary_input += f"標題: {row['Title']}\n簡介: {desc}\n{link_markdown}\n\n"
        
        # 4. AI Summarize and Send
        final_report = get_ai_summary(news_summary_input)
        send_telegram(final_report)
        print("Success: Report sent!")
    else:
        print("No new news found.")
