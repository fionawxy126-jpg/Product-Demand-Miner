"""
Crawler connectors for public market-signal sources.
"""

import requests
import time
import os
from html.parser import HTMLParser
from html import unescape
from urllib.parse import parse_qs, unquote, urlparse
from datetime import datetime
from requests.auth import HTTPBasicAuth

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

SORT_METHODS = ["relevance", "top", "new"]
MAX_PER_QUERY = 100
_REDDIT_TOKEN = {"value": None, "expires_at": 0}
_LAST_WARNINGS = []


def _timestamp(date_str):
    return int(datetime.strptime(date_str, "%Y-%m-%d").timestamp())


def _warn(message):
    if message not in _LAST_WARNINGS:
        _LAST_WARNINGS.append(message)


def get_last_crawl_warnings():
    return list(_LAST_WARNINGS)


def _get_reddit_token():
    client_id = os.environ.get("REDDIT_CLIENT_ID", "").strip()
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return None

    now = time.time()
    if _REDDIT_TOKEN["value"] and _REDDIT_TOKEN["expires_at"] > now + 60:
        return _REDDIT_TOKEN["value"]

    user_agent = os.environ.get(
        "REDDIT_USER_AGENT",
        "ProductDemandMiner/0.1 by open-source-user",
    )
    try:
        resp = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=HTTPBasicAuth(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": user_agent},
            timeout=15,
        )
        if resp.status_code != 200:
            _warn(f"Reddit OAuth 获取失败（HTTP {resp.status_code}），已尝试公开搜索入口。")
            return None
        data = resp.json()
        _REDDIT_TOKEN["value"] = data.get("access_token")
        _REDDIT_TOKEN["expires_at"] = now + int(data.get("expires_in", 3600))
        return _REDDIT_TOKEN["value"]
    except Exception as exc:
        _warn(f"Reddit OAuth 获取失败：{exc}")
        return None


# ---------- 板块推荐 ----------

def suggest_subreddits(keywords, limit=20):
    """根据关键词搜索相关 Reddit 板块"""
    results = {}
    for kw in keywords:
        url = "https://www.reddit.com/subreddits/search.json"
        params = {"q": kw, "limit": 15}
        try:
            token = _get_reddit_token()
            if token:
                url = "https://oauth.reddit.com/subreddits/search"
                headers = {**HEADERS, "Authorization": f"Bearer {token}"}
            else:
                headers = HEADERS
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            if resp.status_code != 200:
                _warn(f"Reddit 社区推荐失败（HTTP {resp.status_code}）。")
                continue
            for child in resp.json().get("data", {}).get("children", []):
                d = child["data"]
                name = d.get("display_name", "")
                if name and name not in results:
                    results[name] = {
                        "name": name,
                        "title": d.get("title", ""),
                        "subscribers": d.get("subscribers", 0),
                        "description": (d.get("public_description", "") or "")[:120],
                    }
        except Exception:
            continue
        time.sleep(1)

    return sorted(results.values(), key=lambda x: x["subscribers"] or 0, reverse=True)[:limit]


# ---------- Reddit 爬虫 ----------

def _search_once(subreddit, keyword, sort, time_filter, ts_start):
    token = _get_reddit_token()
    if token:
        if subreddit:
            url = f"https://oauth.reddit.com/r/{subreddit}/search"
        else:
            url = "https://oauth.reddit.com/search"
        headers = {**HEADERS, "Authorization": f"Bearer {token}"}
    else:
        if subreddit:
            url = f"https://www.reddit.com/r/{subreddit}/search.json"
        else:
            url = "https://www.reddit.com/search.json"
        headers = HEADERS

    params = {
        "q": keyword,
        "sort": sort,
        "t": time_filter,
        "limit": MAX_PER_QUERY,
        "type": "link",
    }
    if subreddit:
        params["restrict_sr"] = "on"

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=20)
        if resp.status_code != 200:
            scope = f"r/{subreddit}" if subreddit else "Reddit 全站"
            if resp.status_code in (401, 403, 429):
                _warn(
                    f"{scope} 搜索被 Reddit 拒绝或限流（HTTP {resp.status_code}）。"
                    "稳定使用建议配置 REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET。"
                )
            else:
                _warn(f"{scope} 搜索失败（HTTP {resp.status_code}）。")
            return []
        posts = []
        for child in resp.json().get("data", {}).get("children", []):
            d = child["data"]
            created = d.get("created_utc", 0)
            if created < ts_start:
                continue
            posts.append({
                "id": "rd_" + d.get("name", ""),
                "title": d.get("title", ""),
                "body": (d.get("selftext", "") or "")[:800],
                "subreddit": d.get("subreddit", ""),
                "score": d.get("score", 0),
                "num_comments": d.get("num_comments", 0),
                "url": "https://reddit.com" + d.get("permalink", ""),
                "created_utc": datetime.fromtimestamp(created).strftime("%Y-%m-%d"),
                "keyword": keyword,
                "source": "reddit",
            })
        return posts
    except Exception:
        return []


def crawl_reddit(keywords, subreddits, time_start, time_end=None,
                 max_posts=None, time_filter="year", on_progress=None):
    _LAST_WARNINGS.clear()
    ts_start = _timestamp(time_start)
    all_posts = {}
    search_scopes = subreddits or [""]
    total = len(search_scopes) * len(keywords)
    current = 0

    for sub in search_scopes:
        for kw in keywords:
            current += 1
            for sort in SORT_METHODS:
                for p in _search_once(sub, kw, sort, time_filter, ts_start):
                    if p["id"] not in all_posts:
                        all_posts[p["id"]] = p
                if sort == SORT_METHODS[0]:
                    time.sleep(1.5)

            if on_progress:
                on_progress(current, total, len(all_posts))

            if max_posts and len(all_posts) >= max_posts:
                return list(all_posts.values())

    return list(all_posts.values())


# ---------- Hacker News 爬虫 ----------

HN_API = "https://hacker-news.firebaseio.com/v0"


def _hn_item(item_id):
    try:
        resp = requests.get(f"{HN_API}/item/{item_id}.json", timeout=10)
        return resp.json() if resp.status_code == 200 else None
    except Exception:
        return None


def crawl_hackernews(keywords, time_start, time_end=None, max_posts=200, on_progress=None):
    """通过 HN Algolia API 搜索帖子"""
    ts_start = _timestamp(time_start)
    all_posts = {}

    for kw in keywords:
        try:
            url = "https://hn.algolia.com/api/v1/search"
            params = {
                "query": kw,
                "tags": "story",
                "numericFilters": f"created_at_i>{ts_start}",
                "hitsPerPage": 100,
            }
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code != 200:
                continue
            for hit in resp.json().get("hits", []):
                oid = hit.get("objectID", "")
                pid = f"hn_{oid}"
                if pid in all_posts:
                    continue
                created = hit.get("created_at_i", 0)
                all_posts[pid] = {
                    "id": pid,
                    "title": hit.get("title", ""),
                    "body": (hit.get("story_text") or "")[:800],
                    "subreddit": "HackerNews",
                    "score": hit.get("points", 0) or 0,
                    "num_comments": hit.get("num_comments", 0) or 0,
                    "url": f"https://news.ycombinator.com/item?id={oid}",
                    "created_utc": datetime.fromtimestamp(created).strftime("%Y-%m-%d") if created else "",
                    "keyword": kw,
                    "source": "hackernews",
                }
        except Exception:
            continue
        time.sleep(1)

        if on_progress:
            on_progress(0, 0, len(all_posts))

        if len(all_posts) >= max_posts:
            break

    return list(all_posts.values())


# ---------- Web Search / X public search ----------

class _DuckDuckGoParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self._current = None
        self._capture_title = False
        self._capture_snippet = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set((attrs.get("class") or "").split())

        if tag == "a" and "result__a" in classes:
            self._current = {
                "title": "",
                "url": _unwrap_ddg_url(attrs.get("href", "")),
                "body": "",
            }
            self._capture_title = True
            return

        if self._current and tag in ("a", "div") and (
            "result__snippet" in classes or "result__extras__url" in classes
        ):
            self._capture_snippet = True

    def handle_data(self, data):
        if not self._current:
            return
        text = unescape(data).strip()
        if not text:
            return
        if self._capture_title:
            self._current["title"] += (" " if self._current["title"] else "") + text
        elif self._capture_snippet:
            self._current["body"] += (" " if self._current["body"] else "") + text

    def handle_endtag(self, tag):
        if tag == "a" and self._capture_title:
            if self._current and self._current.get("title") and self._current.get("url"):
                self.results.append(self._current)
            self._current = None
            self._capture_title = False
            self._capture_snippet = False
        elif self._capture_snippet and tag in ("a", "div"):
            self._capture_snippet = False


def _unwrap_ddg_url(url):
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    parsed = urlparse(url)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        uddg = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(uddg) if uddg else url
    return url


def _search_duckduckgo(query, max_results=10):
    url = "https://html.duckduckgo.com/html/"
    try:
        resp = requests.get(url, params={"q": query}, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            _warn(f"Web Search 查询失败（HTTP {resp.status_code}）：{query}")
            return []
        parser = _DuckDuckGoParser()
        parser.feed(resp.text)
        return parser.results[:max_results]
    except Exception as exc:
        _warn(f"Web Search 查询失败：{exc}")
        return []


def _market_queries(keywords):
    modifiers = [
        "",
        "problem issue pain point",
        "frustrating bug expensive alternative",
    ]
    for kw in keywords:
        for modifier in modifiers:
            yield f"{kw} {modifier}".strip()


def crawl_web_search(keywords, time_start=None, time_end=None, max_posts=80, on_progress=None):
    """Search public web results without requiring a paid search API key."""
    _LAST_WARNINGS.clear()
    all_posts = {}
    queries = list(_market_queries(keywords))

    for i, query in enumerate(queries, 1):
        for item in _search_duckduckgo(query, max_results=8):
            url = item.get("url", "")
            if not url or url in all_posts:
                continue
            all_posts[url] = {
                "id": "web_" + str(abs(hash(url))),
                "title": item.get("title", ""),
                "body": item.get("body", ""),
                "subreddit": "Web",
                "score": 0,
                "num_comments": 0,
                "url": url,
                "created_utc": datetime.now().strftime("%Y-%m-%d"),
                "keyword": query,
                "source": "web",
            }
        if on_progress:
            on_progress(i, len(queries), len(all_posts))
        if len(all_posts) >= max_posts:
            break
        time.sleep(1)

    return list(all_posts.values())[:max_posts]


def crawl_x_search(keywords, time_start=None, time_end=None, max_posts=60, on_progress=None):
    """
    Search public X/Twitter pages through web search.

    This avoids paid X API usage and does not log in or bypass platform controls.
    """
    _LAST_WARNINGS.clear()
    all_posts = {}
    queries = [f"site:x.com OR site:twitter.com {query}" for query in _market_queries(keywords)]

    for i, query in enumerate(queries, 1):
        for item in _search_duckduckgo(query, max_results=8):
            url = item.get("url", "")
            if not url or url in all_posts:
                continue
            host = urlparse(url).netloc.lower()
            if not ("x.com" in host or "twitter.com" in host):
                continue
            all_posts[url] = {
                "id": "x_" + str(abs(hash(url))),
                "title": item.get("title", ""),
                "body": item.get("body", ""),
                "subreddit": "X",
                "score": 0,
                "num_comments": 0,
                "url": url,
                "created_utc": datetime.now().strftime("%Y-%m-%d"),
                "keyword": query,
                "source": "x",
            }
        if on_progress:
            on_progress(i, len(queries), len(all_posts))
        if len(all_posts) >= max_posts:
            break
        time.sleep(1)

    return list(all_posts.values())[:max_posts]
