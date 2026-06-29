# Product Demand Miner

Product Demand Miner is a small Flask tool for collecting public market signals from multiple sources, cleaning the raw posts, clustering pain points, adding a human review step, and exporting a research report.

## Workflow

```text
crawler -> normalizer -> analyzer -> reviewer -> reporter
```

The web UI is designed for keyword-based market research. Data sources are connectors; the main output is product pain points and demand signals. Reddit communities are optional filters, not the main input.

## Run Locally

```bash
cd product-demand-miner
pip3 install -r requirements.txt
python3 app.py
```

Open:

```text
http://127.0.0.1:5001
```

## Reddit Setup

Reddit public JSON search may return HTTP 403. For stable Reddit search, create a Reddit app and configure OAuth credentials on the server.

1. Open https://www.reddit.com/prefs/apps
2. Click `create app`
3. Choose `script` for local/server-side usage
4. Set redirect uri to `http://localhost:8080`
5. Copy the app credentials
6. Create `product-demand-miner/.env` from `product-demand-miner/.env.example`

```bash
cp product-demand-miner/.env.example product-demand-miner/.env
```

Fill in:

```bash
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=ProductDemandMiner/0.1 by your_reddit_username
```

Do not commit `.env`.

## Data Sources

- Reddit: uses OAuth when credentials are configured, with public JSON fallback.
- Hacker News: uses public Algolia API.
- Web Search: uses public web search fallback without a paid search API key.
- X / Twitter: searches public X/Twitter pages through web search. It does not use paid X API, log in, or bypass platform controls.
- Other platforms: currently recorded in reports only. Douyin, TikTok, Xiaohongshu, and similar platforms usually require official platform access, review, or a commercial data provider.

## Outputs

After AI/local review and human edits, the app exports:

- Markdown report
- Word document
- CSV evidence file
