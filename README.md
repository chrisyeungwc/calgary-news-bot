📰 Calgary News Intelligence Pipeline (Bilingual)
An automated serverless data pipeline that extracts local news from CBC Calgary, processes it via LLM (DeepSeek-V3), and delivers AI-summarized bilingual reports through Telegram.

🚀 Key Features
Automated ETL Pipeline: Extracts data from multi-channel RSS feeds daily using GitHub Actions.

LLM Integration: Leverages DeepSeek-V3 API for intelligent summarization and sentiment analysis.

Bilingual Intelligence: Delivers reports in both English and Traditional Chinese (HK Style), tailored for newcomers in Canada.

Zero-Cost Architecture: Operates entirely on serverless infrastructure (GitHub Actions) with no maintenance costs.

Data Persistence: Maintains an incremental historical database in CSV format for future trend analysis.

📊 System Architecture
Extraction: Python scraper pulls the latest items from CBC Calgary/National RSS feeds.

Transformation:

Filters news from the last 24 hours (Calgary MST Timezone).

Analyzes sentiment and extracts keywords via DeepSeek LLM.

Storage: Updates cbc_news.csv incrementally within the GitHub repository.

Delivery: Formats and dispatches a clean, Markdown-ready report to a Telegram Bot.

📸 Project Showcase
Tip for Hanshan: Here you should place your Telegram screenshot!

🛠️ Tech Stack
Language: Python 3.11

Libraries: Pandas (Data manipulation), BeautifulSoup4 (Web scraping), Pytz (Timezone handling)

DevOps: GitHub Actions (Automation & CI/CD)

AI Model: DeepSeek-V3

Communication: Telegram Bot API

📈 Future Scope
Phase 2: Implement an interactive query system using n8n to allow real-time historical data lookup via Telegram.

Phase 3: Build a Streamlit dashboard to visualize news sentiment trends in Alberta over time.
