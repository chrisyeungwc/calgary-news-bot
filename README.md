# 📰 Calgary News Intelligence Pipeline (Hybrid-LLM Edition)

An automated serverless data pipeline that extracts local news from CBC Calgary, processes it via Hybrid LLM architectures, and delivers AI-summarized bilingual reports to Telegram.

## 🚀 Key Features
* **Hybrid-LLM Orchestration**: Supports both Cloud-based (**DeepSeek-V3**) for high-fidelity bilingual reporting and Edge-computing (**Qwen3-0.6B**) for resource-efficient experimentation.
* **Bilingual Intelligence**: Delivers reports in **English** and **Traditional Chinese (HK Style)**, specifically optimized for newcomers in Calgary.
* **Automated ETL Pipeline**: Fully serverless architecture using GitHub Actions to handle daily RSS scraping, processing, and delivery.
* **Edge AI Integration**: Implemented local LLM inference using **Ollama** within GitHub Actions' ephemeral runners.

## 📊 System Architecture & Model Selection
1. **Extraction**: Python scraper pulls daily updates from CBC Calgary/National RSS feeds.
2. **Model A (Production - DeepSeek-V3)**: Handles 30+ news items with complex sentiment analysis and perfect bilingual output.
3. **Model B (Experimental - Qwen3-0.6B)**: A stress-test implementation to explore the limits of Small Language Models (SLM) in a 2-core CPU environment.
4. **Delivery**: Intelligent message splitting to bypass Telegram’s 4096 character limit.

## 💡 Technical Challenges & Lessons Learned (New!)
* **SLM Performance Bottleneck**: During testing, we identified that sub-billion parameter models (like Qwen3-0.6B) struggle with multi-tasking (Summarization + Translation) in resource-constrained environments (GitHub Runners). 
* **Latency vs. Accuracy**: Benchmarked local inference latency, leading to the implementation of a 300s timeout and a 10-item input limit for SLM to prevent pipeline failure.
* **Instruction Drift**: Documented how 0.6B models may ignore complex formatting constraints, reinforcing the importance of "Prompt Simplification" for edge AI.

## 📸 Project Showcase

![Telegram Report Screenshot](https://private-user-images.githubusercontent.com/52281668/539288863-b5b9a5ef-bf9c-491e-9fad-3ba8d0772acf.png?jwt=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3NjkxMDI2NTgsIm5iZiI6MTc2OTEwMjM1OCwicGF0aCI6Ii81MjI4MTY2OC81MzkyODg4NjMtYjViOWE1ZWYtYmY5Yy00OTFlLTlmYWQtM2JhOGQwNzcyYWNmLnBuZz9YLUFtei1BbGdvcml0aG09QVdTNC1ITUFDLVNIQTI1NiZYLUFtei1DcmVkZW50aWFsPUFLSUFWQ09EWUxTQTUzUFFLNFpBJTJGMjAyNjAxMjIlMkZ1cy1lYXN0LTElMkZzMyUyRmF3czRfcmVxdWVzdCZYLUFtei1EYXRlPTIwMjYwMTIyVDE3MTkxOFomWC1BbXotRXhwaXJlcz0zMDAmWC1BbXotU2lnbmF0dXJlPWQ4ZmViODIyYThmNTkyNzAyMzBjMGZiOThjY2E1NzFmZThjMTVjNDgxNTM3MTkxZTk4NzQxZWM1YTViNTViNjAmWC1BbXotU2lnbmVkSGVhZGVycz1ob3N0In0.Irjg4mIncgLDzx2sZKLjVVI1XCh8NFwNNBFw-wmuDxw)

## 🛠️ Tech Stack
* **Language**: Python 3.11
* **Libraries**: Pandas, BeautifulSoup4, Lxml, Requests, Pytz
* **DevOps**: GitHub Actions (Automation & CI/CD)
* **AI Model**: DeepSeek-V3
* **Communication**: Telegram Bot API

## 📈 Future Scope
* **Phase 2**: Implement an interactive query system using **n8n** to allow real-time historical data lookup via Telegram.
* **Phase 3**: Build a Streamlit dashboard to visualize news sentiment trends in Alberta over time.
