"""
Reddit 调研工具（免登录版）
直接请求 Reddit 的 .json 接口，不需要任何 API 凭证
"""

import requests       # HTTP 请求
import csv            # 写 CSV
import time           # 控制请求频率，避免被ban
import json
from datetime import datetime

# 搜索关键词
KEYWORDS = [
    "Claude Code",
    "Cursor AI",
    "AI coding assistant",
    "AI CLI",
]

# 搜索的 subreddit（板块）
SUBREDDITS = ["ClaudeAI", "Cursor", "programming", "coding", "MachineLearning"]

# 每个关键词在每个板块抓多少条
MAX_POSTS = 25

# 模拟浏览器请求头（必须，否则 Reddit 会拒绝）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}


def search_subreddit(subreddit, keyword):
    """搜索某个板块的某个关键词，返回帖子列表"""
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {
        "q": keyword,
        "sort": "relevance",
        "t": "month",        # 最近一个月
        "limit": MAX_POSTS,
        "restrict_sr": "on",  # 限制在当前板块内搜索
    }

    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"    ⚠ HTTP {resp.status_code}，跳过")
            return []

        data = resp.json()
        posts = []
        for child in data.get("data", {}).get("children", []):
            d = child["data"]
            posts.append({
                "id": d.get("name", ""),
                "title": d.get("title", ""),
                "body": (d.get("selftext", "") or "")[:500],
                "subreddit": d.get("subreddit", ""),
                "score": d.get("score", 0),
                "num_comments": d.get("num_comments", 0),
                "url": "https://reddit.com" + d.get("permalink", ""),
                "created_utc": datetime.fromtimestamp(d.get("created_utc", 0)).strftime("%Y-%m-%d"),
                "keyword": keyword,
            })
        return posts

    except Exception as e:
        print(f"    ⚠ 出错: {e}")
        return []


def search_all():
    """搜索所有板块 × 所有关键词"""
    all_posts = {}  # 用 id 去重

    for sub in SUBREDDITS:
        for keyword in KEYWORDS:
            print(f"  搜索: r/{sub} - '{keyword}'")
            posts = search_subreddit(sub, keyword)
            for p in posts:
                if p["id"] not in all_posts:
                    all_posts[p["id"]] = p
            time.sleep(2)  # 每次请求间隔2秒，礼貌爬取

    return list(all_posts.values())


def export_csv(posts, filename="reddit_posts.csv"):
    """导出 CSV"""
    if not posts:
        print("  没有抓到帖子")
        return

    keys = ["id", "title", "body", "subreddit", "score", "num_comments", "url", "created_utc", "keyword"]
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(posts)

    print(f"  已导出 {len(posts)} 条 → {filename}")


def generate_summary(posts, filename="summary.md"):
    """生成调研摘要"""
    if not posts:
        print("  没有帖子，跳过摘要")
        return

    top = sorted(posts, key=lambda x: x["score"], reverse=True)[:20]

    # 关键词分类
    pain_kw = ["bug", "issue", "problem", "broken", "error", "crash", "slow", "fail", "frustrat", "annoying", "doesn't work", "not working"]
    expect_kw = ["wish", "want", "hope", "feature request", "would love", "missing", "need"]
    complaint_kw = ["suck", "terrible", "worst", "hate", "disappoint", "overrated", "waste"]

    pain = [p for p in top if any(k in (p["title"] + p["body"]).lower() for k in pain_kw)]
    expect = [p for p in top if any(k in (p["title"] + p["body"]).lower() for k in expect_kw)]
    complain = [p for p in top if any(k in (p["title"] + p["body"]).lower() for k in complaint_kw)]

    with open(filename, "w", encoding="utf-8") as f:
        f.write("# Reddit AI Coding 工具调研摘要\n\n")
        f.write(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"> 共抓取 **{len(posts)}** 条帖子\n\n")

        f.write("## 数据概览\n\n")
        f.write(f"- 搜索板块: {', '.join(SUBREDDITS)}\n")
        f.write(f"- 搜索关键词: {', '.join(KEYWORDS)}\n")
        f.write(f"- 总帖子数: {len(posts)}\n")
        f.write(f"- 总评论数: {sum(p['num_comments'] for p in posts)}\n")
        f.write(f"- 平均点赞: {sum(p['score'] for p in posts) // max(len(posts), 1)}\n\n")

        def write_section(title, items):
            f.write(f"---\n\n## {title}\n\n")
            if items:
                for p in items[:10]:
                    f.write(f"- **{p['title']}**\n")
                    f.write(f"  r/{p['subreddit']} | {p['score']}赞 | {p['num_comments']}评论 | {p['created_utc']}\n")
                    f.write(f"  {p['url']}\n")
            else:
                f.write("暂未发现相关帖子\n")
            f.write("\n")

        write_section("用户痛点", pain)
        write_section("期待功能", expect)
        write_section("对现有 CLI/工具 的吐槽", complain)

        f.write("---\n\n## 热门帖子 Top 10\n\n")
        for i, p in enumerate(top[:10], 1):
            f.write(f"{i}. **{p['title']}**\n")
            f.write(f"   r/{p['subreddit']} | {p['score']}赞 | {p['num_comments']}评论 | {p['created_utc']}\n")
            f.write(f"   {p['url']}\n\n")

    print(f"  摘要已生成 → {filename}")


def main():
    print("=" * 50)
    print("Reddit AI Coding 调研工具（免登录版）")
    print("=" * 50)

    print("\n[1/3] 搜索帖子中（每个请求间隔2秒，请耐心等待）...\n")
    posts = search_all()
    print(f"\n  共找到 {len(posts)} 条去重帖子")

    print("\n[2/3] 导出 CSV...")
    export_csv(posts)

    print("\n[3/3] 生成摘要...")
    generate_summary(posts)

    print("\n" + "=" * 50)
    print("完成！输出文件：reddit_posts.csv / summary.md")
    print("=" * 50)


if __name__ == "__main__":
    main()
