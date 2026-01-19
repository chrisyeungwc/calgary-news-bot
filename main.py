import os
import requests
import pandas as pd
import pytz
from bs4 import BeautifulSoup
from dateutil import parser
from datetime import datetime, timedelta

# --- 1. 配置與常量 ---
CALGARY_TZ = pytz.timezone('America/Edmonton')
FEEDS_LIST = ['topstories', 'world', 'canada', 'business', 'health', 'technology', 'canada-calgary']
FEED_DICT = {'topstories': 'Top Stories', 'world': 'World', 'canada': 'Canada', 'business': 'Business', 'health': 'Health', 'technology': 'Technology', 'canada-calgary': 'Calgary'}
BASE_URL = 'https://www.cbc.ca/webfeed/rss/rss-'
CSV_FILE = 'cbc_news.csv'

# 從 GitHub Secrets 獲取密鑰
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
TG_TOKEN = os.getenv('TELEGRAM_TOKEN')
TG_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

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
            
            # 處理時間
            pub_date = item.find('pubDate').text
            dt_calgary = parser.parse(pub_date).astimezone(CALGARY_TZ)

            # 處理 Description (增加容錯)
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
        print(f"Error grabbing {feed_type}: {e}")
        return pd.DataFrame()

def get_ai_summary(news_text):
    """調用 DeepSeek API 生成中英雙語摘要"""
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}", 
        "Content-Type": "application/json"
    }
    
    # 修改 Prompt，要求雙語輸出
    prompt = f"""
    You are a helpful AI assistant. 
    Below are the latest Calgary news:
    {news_text}
    
    Tasks:
    1. Select 5 most important news.
    2. For each news, provide a summary in both Traditional Chinese (Hong Kong/Canton style) and English.
    3. Format the output professionally for a Telegram message.

    """
    
    data = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7 # 增加一點點創造力
    }
    resp = requests.post(url, json=data, headers=headers)
    return resp.json()['choices'][0]['message']['content']

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

# --- 執行主流程 ---
if __name__ == "__main__":
    # 1. 抓取新數據
    all_new_news = []
    for f in FEEDS_LIST:
        all_new_news.append(grab_news(f))
    df_new = pd.concat(all_new_news).drop_duplicates(subset=['Guid'])

    # 2. 合併舊數據 (實現增量更新)
    if os.path.exists(CSV_FILE):
        df_old = pd.read_csv(CSV_FILE)
        df_final = pd.concat([df_old, df_new]).drop_duplicates(subset=['Guid'], keep='last')
    else:
        df_final = df_new

    # 存回 CSV
    df_final.sort_values('DateTime', ascending=False).to_csv(CSV_FILE, index=False)

    # 3. 篩選過去 24 小時的新聞給 AI (只限 Calgary 類別或 Top Stories)
    df_final['DateTime'] = pd.to_datetime(df_final['DateTime'])
    yesterday = datetime.now() - timedelta(days=1)
    # 優先選 Calgary 的新聞
    mask = (df_final['DateTime'] > yesterday) & (df_final['FeedType'] == 'Calgary')
    daily_batch = df_final[mask].head(15) # 取 15 條給 AI 選 5 條

    if not daily_batch.empty:
        news_summary_input = ""
        for _, row in daily_batch.iterrows():
            desc = row['DescriptionTitle'] if row['DescriptionTitle'] else row['DescriptionAlt']
            news_summary_input += f"標題: {row['Title']}\n簡介: {desc}\nLink: {row['Link']}\n\n"
        
        # 4. AI 總結並發送
        final_report = get_ai_summary(news_summary_input)
        send_telegram(final_report)
        print("Report sent to Telegram!")
    else:
        print("No new news in the last 24h.")