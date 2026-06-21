# -*- coding: utf-8 -*-
"""具公信力的新聞 RSS 來源清單。

每個來源標註 category 與 region，update_news.py 會逐一抓取。
若某個 feed 失效，直接在此替換 url 即可（不需改其他檔案）。

category: finance | ai | investment
region:   taiwan  | international
"""

FEEDS = [
    # ───────────── 台灣 · 金融 / 投資 ─────────────
    {
        "name": "鉅亨網 台股",
        "url": "https://news.cnyes.com/rss/v1/news/category/tw_stock",
        "category": "investment",
        "region": "taiwan",
    },
    {
        "name": "鉅亨網 頭條",
        "url": "https://news.cnyes.com/rss/v1/news/category/headline",
        "category": "finance",
        "region": "taiwan",
    },
    {
        "name": "中央社 財經",
        "url": "https://feeds.feedburner.com/rsscna/finance",
        "category": "finance",
        "region": "taiwan",
    },
    {
        "name": "鉅亨網 國際股市",
        "url": "https://news.cnyes.com/rss/v1/news/category/wd_stock",
        "category": "investment",
        "region": "taiwan",
    },

    # ───────────── 台灣 · AI 科技 ─────────────
    {
        "name": "iThome",
        "url": "https://www.ithome.com.tw/rss",
        "category": "ai",
        "region": "taiwan",
    },
    {
        "name": "科技新報 TechNews",
        "url": "https://technews.tw/feed/",
        "category": "ai",
        "region": "taiwan",
    },
    {
        "name": "中央社 科技",
        "url": "https://feeds.feedburner.com/rsscna/technology",
        "category": "ai",
        "region": "taiwan",
    },

    # ───────────── 國際 · 金融 / 投資 ─────────────
    {
        "name": "CNBC Finance",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
        "category": "finance",
        "region": "international",
    },
    {
        "name": "CNBC Markets",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
        "category": "investment",
        "region": "international",
    },
    {
        "name": "MarketWatch Top Stories",
        "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        "category": "investment",
        "region": "international",
    },
    {
        "name": "Yahoo Finance",
        "url": "https://finance.yahoo.com/news/rssindex",
        "category": "finance",
        "region": "international",
    },

    # ───────────── 國際 · AI 科技 ─────────────
    {
        "name": "TechCrunch AI",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "category": "ai",
        "region": "international",
    },
    {
        "name": "The Verge",
        "url": "https://www.theverge.com/rss/index.xml",
        "category": "ai",
        "region": "international",
    },
    {
        "name": "Ars Technica",
        "url": "https://feeds.arstechnica.com/arstechnica/index",
        "category": "ai",
        "region": "international",
    },
    {
        "name": "MIT Technology Review",
        "url": "https://www.technologyreview.com/feed/",
        "category": "ai",
        "region": "international",
    },
]

# 每個「分類 × 地區」桶最多保留幾則最新新聞（控制 Gemini API 用量）
MAX_PER_BUCKET = 5
