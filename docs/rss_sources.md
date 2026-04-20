# RSS Sources

## AI

- OpenAI News: `https://openai.com/news/rss.xml`
- InfoQ Anthropic: `https://feed.infoq.com/anthropic/`
- Google DeepMind Blog: `https://deepmind.google/blog/rss.xml`
- Hugging Face Blog: `https://huggingface.co/blog/feed.xml`
- TechCrunch AI: `https://techcrunch.com/category/artificial-intelligence/feed/`
- VentureBeat AI: `https://venturebeat.com/category/ai/feed/`
- The Verge: `https://www.theverge.com/rss/index.xml`

## AI Research & Safety

- arXiv Computer Science AI: `https://export.arxiv.org/api/query?search_query=cat:cs.AI&sortBy=submittedDate&sortOrder=descending&max_results=25`
- arXiv Machine Learning: `https://export.arxiv.org/api/query?search_query=cat:cs.LG&sortBy=submittedDate&sortOrder=descending&max_results=25`
- arXiv AI Safety & Alignment: `https://export.arxiv.org/api/query?search_query=all:%22AI%20safety%22+OR+all:alignment+OR+all:%22model%20evaluation%22+OR+all:%22red%20teaming%22&sortBy=submittedDate&sortOrder=descending&max_results=25`
- Journal of Machine Learning Research: `https://www.jmlr.org/jmlr.xml`
- Journal of Artificial Intelligence Research: `https://www.jair.org/index.php/jair/gateway/plugin/WebFeedGatewayPlugin/rss2`
- Alignment Forum: `https://www.alignmentforum.org/feed.xml`

## Finance

- Financial Times Markets: `https://www.ft.com/markets?format=rss`
- Financial Times Global Economy: `https://www.ft.com/global-economy?format=rss`
- Wall Street Journal Markets: `https://feeds.content.dowjones.io/public/rss/RSSMarketsMain`
- Wall Street Journal Business: `https://feeds.content.dowjones.io/public/rss/WSJcomUSBusiness`
- MarketWatch Top Stories: `https://feeds.content.dowjones.io/public/rss/mw_topstories`
- CNBC Finance: `https://www.cnbc.com/id/10000664/device/rss/rss.html`
- CNBC Top News: `https://www.cnbc.com/id/100003114/device/rss/rss.html`
- BIS Press Releases: `https://www.bis.org/doclist/all_pressrels.rss`
- Federal Reserve Press Releases: `https://www.federalreserve.gov/feeds/press_all.xml`

## Tuning Guidance

Keep the first version intentionally small. If a feed repeatedly fails, duplicates other sources, or produces low-signal stories, move it out before adding more sources.

FT and WSJ feeds are useful high-signal market sources, but their article bodies may be paywalled. The digest should treat their public RSS titles and summaries as signals, then rely on accessible market and official sources for additional detail where needed.
