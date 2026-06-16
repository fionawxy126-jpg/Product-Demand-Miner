"""
Normalize crawler output into a stable post list for analysis and reporting.
"""

from datetime import date, datetime
import hashlib
import re


REQUIRED_FIELDS = {
    "id": "",
    "title": "",
    "body": "",
    "subreddit": "",
    "score": 0,
    "num_comments": 0,
    "url": "",
    "created_utc": "",
    "keyword": "",
    "source": "unknown",
}


def _clean_text(value):
    text = "" if value is None else str(value)
    return re.sub(r"\s+", " ", text).strip()


def _to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value).date()

    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _format_date(value):
    parsed = _parse_date(value)
    return parsed.isoformat() if parsed else ""


def _post_key(post):
    if post.get("id"):
        return post["id"]
    if post.get("url"):
        return f"url:{post['url']}"

    raw = f"{post.get('source', '')}|{post.get('title', '')}|{post.get('created_utc', '')}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"generated:{digest}"


def _merge_keywords(left, right):
    items = []
    for value in (left, right):
        if not value:
            continue
        items.extend([part.strip() for part in str(value).split(",") if part.strip()])
    return ", ".join(sorted(set(items), key=str.lower))


def normalize_post(raw_post):
    """Return a single post with the fields analyzer/reporter expect."""
    raw = {**REQUIRED_FIELDS, **(raw_post or {})}
    post = {
        "id": _clean_text(raw.get("id")),
        "title": _clean_text(raw.get("title")),
        "body": _clean_text(raw.get("body")),
        "subreddit": _clean_text(raw.get("subreddit")),
        "score": _to_int(raw.get("score")),
        "num_comments": _to_int(raw.get("num_comments")),
        "url": _clean_text(raw.get("url")),
        "created_utc": _format_date(raw.get("created_utc")),
        "keyword": _clean_text(raw.get("keyword")),
        "source": _clean_text(raw.get("source")) or "unknown",
    }
    post["id"] = post["id"] or _post_key(post)
    return post


def _merge_posts(existing, incoming):
    existing["score"] = max(existing["score"], incoming["score"])
    existing["num_comments"] = max(existing["num_comments"], incoming["num_comments"])
    existing["keyword"] = _merge_keywords(existing.get("keyword"), incoming.get("keyword"))

    if len(incoming.get("body", "")) > len(existing.get("body", "")):
        existing["body"] = incoming["body"]
    if not existing.get("url") and incoming.get("url"):
        existing["url"] = incoming["url"]
    if not existing.get("created_utc") and incoming.get("created_utc"):
        existing["created_utc"] = incoming["created_utc"]
    return existing


def normalize_posts(raw_posts, time_start=None, time_end=None):
    """
    Clean, date-filter, and dedupe posts from all crawlers.

    Returns:
        {
            "posts": [...],
            "stats": {...},
        }
    """
    start = _parse_date(time_start)
    end = _parse_date(time_end)
    deduped = {}
    stats = {
        "raw_count": len(raw_posts or []),
        "kept_count": 0,
        "duplicate_count": 0,
        "date_filtered_count": 0,
        "missing_date_count": 0,
        "source_counts": {},
        "subreddits": [],
    }

    for raw_post in raw_posts or []:
        post = normalize_post(raw_post)
        created = _parse_date(post.get("created_utc"))

        if not created:
            stats["missing_date_count"] += 1
        if start and created and created < start:
            stats["date_filtered_count"] += 1
            continue
        if end and created and created > end:
            stats["date_filtered_count"] += 1
            continue

        key = _post_key(post)
        if key in deduped:
            stats["duplicate_count"] += 1
            deduped[key] = _merge_posts(deduped[key], post)
        else:
            deduped[key] = post

    posts = list(deduped.values())
    posts.sort(
        key=lambda p: (
            p.get("score", 0),
            p.get("num_comments", 0),
            _parse_date(p.get("created_utc")) or date.min,
        ),
        reverse=True,
    )

    source_counts = {}
    subreddits = set()
    for post in posts:
        source = post.get("source") or "unknown"
        source_counts[source] = source_counts.get(source, 0) + 1
        if post.get("subreddit"):
            subreddits.add(post["subreddit"])

    stats["kept_count"] = len(posts)
    stats["source_counts"] = source_counts
    stats["subreddits"] = sorted(subreddits)

    return {"posts": posts, "stats": stats}
