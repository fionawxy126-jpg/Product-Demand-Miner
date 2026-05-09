"""
Reddit 调研工具 v2 — 大规模版
目标：抓取 1000+ 帖子，时间范围 2025年10月-2026年5月
"""

import requests
import csv
import time
import json
from datetime import datetime

# 扩大搜索关键词
KEYWORDS = [
    "Claude Code",
    "Cursor AI",
    "AI coding assistant",
    "AI CLI",
    "AI code editor",
    "AI agent coding",
    "Copilot vs Cursor",
    "Claude Code pricing",
    "AI coding token cost",
    "vibe coding",
    "AI code review",
    "agentic coding",
]

# 扩大搜索板块
SUBREDDITS = [
    "ClaudeAI",
    "ClaudeCode",
    "Cursor",
    "programming",
    "coding",
    "MachineLearning",
    "webdev",
    "LocalLLaMA",
    "SoftwareEngineering",
    "ChatGPTCoding",
    "vibecoding",
    "artificial",
]

# 每个搜索最多返回多少条（Reddit .json 接口上限 100）
MAX_POSTS = 100

# 用多种排序方式增加覆盖
SORT_METHODS = ["relevance", "top", "new"]

# 时间范围：year 覆盖过去一年
TIME_FILTER = "year"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

def search_subreddit(subreddit, keyword, sort="relevance"):
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {
        "q": keyword,
        "sort": sort,
        "t": TIME_FILTER,
        "limit": MAX_POSTS,
        "restrict_sr": "on",
    }
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            return []
        data = resp.json()
        posts = []
        for child in data.get("data", {}).get("children", []):
            d = child["data"]
            created = d.get("created_utc", 0)
            # 只保留 2025-10-01 之后的帖子
            if created < 1759305600:  # 2025-10-01 timestamp
                continue
            posts.append({
                "id": d.get("name", ""),
                "title": d.get("title", ""),
                "body": (d.get("selftext", "") or "")[:800],
                "subreddit": d.get("subreddit", ""),
                "score": d.get("score", 0),
                "num_comments": d.get("num_comments", 0),
                "url": "https://reddit.com" + d.get("permalink", ""),
                "created_utc": datetime.fromtimestamp(created).strftime("%Y-%m-%d"),
                "keyword": keyword,
                "sort": sort,
            })
        return posts
    except Exception as e:
        print(f"    ⚠ {e}")
        return []


def search_all():
    all_posts = {}
    total_queries = len(SUBREDDITS) * len(KEYWORDS)
    current = 0

    for sub in SUBREDDITS:
        for keyword in KEYWORDS:
            current += 1
            print(f"  [{current}/{total_queries}] r/{sub} — '{keyword}'", end="")
            for sort in SORT_METHODS:
                posts = search_subreddit(sub, keyword, sort)
                new_count = 0
                for p in posts:
                    if p["id"] not in all_posts:
                        all_posts[p["id"]] = p
                        new_count += 1
                if sort == "relevance":  # 只在第一种排序时 sleep
                    time.sleep(1.5)
            print(f" → 总计 {len(all_posts)} 条")

    return list(all_posts.values())


def export_csv(posts, filename="reddit_posts_v2.csv"):
    if not posts:
        print("  没有抓到帖子")
        return
    keys = ["id", "title", "body", "subreddit", "score", "num_comments", "url", "created_utc", "keyword", "sort"]
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(posts)
    print(f"\n  已导出 {len(posts)} 条 → {filename}")


def main():
    print("=" * 60)
    print("Reddit AI Coding 调研工具 v2（大规模版）")
    print(f"板块: {len(SUBREDDITS)} | 关键词: {len(KEYWORDS)} | 排序: {len(SORT_METHODS)}")
    print(f"时间范围: 2025-10 至今")
    print("=" * 60)

    print("\n[1/2] 搜索帖子中...\n")
    posts = search_all()
    print(f"\n  共找到 {len(posts)} 条去重帖子")

    print("\n[2/2] 导出 CSV...")
    export_csv(posts)

    print("\n完成！下一步请运行 python3 generate_summary.py 生成摘要")


if __name__ == "__main__":
    main()
