"""
爬虫模块 — Reddit (.json) + Hacker News (Firebase API)
"""

import requests
import time
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

SORT_METHODS = ["relevance", "top", "new"]
MAX_PER_QUERY = 100


def _timestamp(date_str):
    return int(datetime.strptime(date_str, "%Y-%m-%d").timestamp())


# ---------- 板块推荐 ----------

def suggest_subreddits(keywords, limit=20):
    """根据关键词搜索相关 Reddit 板块"""
    results = {}
    for kw in keywords:
        url = "https://www.reddit.com/subreddits/search.json"
        params = {"q": kw, "limit": 15}
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
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
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {
        "q": keyword,
        "sort": sort,
        "t": time_filter,
        "limit": MAX_PER_QUERY,
        "restrict_sr": "on",
    }
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
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
    ts_start = _timestamp(time_start)
    all_posts = {}
    total = len(subreddits) * len(keywords)
    current = 0

    for sub in subreddits:
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
