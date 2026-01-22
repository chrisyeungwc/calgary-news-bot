# 📰 Calgary News Intelligence Pipeline (Bilingual)

An automated serverless data pipeline that extracts local news from CBC Calgary, processes it via LLM (DeepSeek-V3), and delivers AI-summarized bilingual reports through Telegram.

## 🚀 Key Features
* **Automated ETL Pipeline**: Extracts data from multi-channel RSS feeds daily using GitHub Actions.
* **LLM Integration**: Leverages DeepSeek-V3 API for intelligent summarization and sentiment analysis.
* **Bilingual Intelligence**: Delivers reports in both **English** and **Traditional Chinese (HK Style)**, tailored for newcomers in Canada.
* **Zero-Cost Architecture**: Operates entirely on serverless infrastructure (GitHub Actions) with no maintenance costs.
* **Data Persistence**: Maintains an incremental historical database in CSV format for future trend analysis.

## 📊 System Architecture
1. **Extraction**: Python scraper pulls the latest items from CBC Calgary/National RSS feeds.
2. **Transformation**:
    * Filters news from the last 24 hours (Calgary MST Timezone).
    * **Regional Priority Sorting**: Prioritizes local Calgary news > Canada > World updates.
    * Analyzes sentiment and extracts keywords via DeepSeek LLM.
3. **Storage**: Updates `cbc_news.csv` incrementally within the GitHub repository.
4. **Delivery**: Formats and dispatches a clean, Markdown-ready report to a Telegram Bot.

## 💡 Technical Challenges & Solutions
* **Telegram 4096 Character Limit**: To deliver 10 comprehensive bilingual news items without data loss, I implemented an **Intelligent Message Splitting** logic. The pipeline automatically detects the message length and splits the report into two distinct parts: "Daily Intelligence" and "Daily Insight".
* **Data Prioritization**: Developed a custom mapping logic using Pandas to ensure local Calgary news remains the focal point, even when high volumes of national news are present.

## 📸 Project Showcase

![Telegram Report Screenshot](https://private-user-images.githubusercontent.com/52281668/539288863-b5b9a5ef-bf9c-491e-9fad-3ba8d0772acf.png?jwt=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3NjkxMDIzNjcsIm5iZiI6MTc2OTEwMjA2NywicGF0aCI6Ii81MjI4MTY2OC81Mzc0NjM1NTUtMzJjYzM1MGItYmRhMi00YTc5LWFmNGQtN2EzMmJiODZjNjY4LnBuZz9YLUFtei1BbGdvcml0aG09QVdTNC1ITUFDLVNIQTI1NiZYLUFtei1DcmVkZW50aWFsPUFLSUFWQ09EWUxTQTUzUFFLNFpBJTJGMjAyNjAxMjIlMkZ1cy1lYXN0LTElMkZzMyUyRmF3czRfcmVxdWVzdCZYLUFtei1EYXRlPTIwMjYwMTIyVDE3MTQyN1omWC1BbXotRXhwaXJlcz0zMDAmWC1BbXotU2lnbmF0dXJlPTQ3ZjkwMTNiOTdhMmRkNjFiMDcyZjU5MjJjMGJiZWUwZGUzOGRlYTMzOWNhMjJiOGNjYjdlYWJkODdhMmVlNjcmWC1BbXotU2lnbmVkSGVhZGVycz1ob3N0In0.8XIVSYejDbHan2QO5kMxPIAqdkpXnz8j56ZAoay_MaU)

## 🛠️ Tech Stack
* **Language**: Python 3.11
* **Libraries**: Pandas, BeautifulSoup4, Lxml, Requests, Pytz
* **DevOps**: GitHub Actions (Automation & CI/CD)
* **AI Model**: DeepSeek-V3
* **Communication**: Telegram Bot API

## 📈 Future Scope
* **Phase 2**: Implement an interactive query system using **n8n** to allow real-time historical data lookup via Telegram.
* **Phase 3**: Build a Streamlit dashboard to visualize news sentiment trends in Alberta over time.
