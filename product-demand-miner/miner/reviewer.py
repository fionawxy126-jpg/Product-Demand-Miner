"""
Create and apply a lightweight human-review layer between analysis and reports.
"""

from copy import deepcopy
from datetime import datetime

from .insights import infer_core_issue


def _serialize_post(post, body_limit=260):
    body = post.get("body", "") or ""
    return {
        "id": post.get("id", ""),
        "title": post.get("title", ""),
        "body_preview": body[:body_limit],
        "subreddit": post.get("subreddit", ""),
        "score": post.get("score", 0),
        "num_comments": post.get("num_comments", 0),
        "url": post.get("url", ""),
        "created_utc": post.get("created_utc", ""),
        "keyword": post.get("keyword", ""),
        "source": post.get("source", ""),
    }


def _review_notes(count, top_score, evidence):
    notes = []
    if count <= 1:
        notes.append("证据较少，建议人工确认是否保留")
    if top_score < 5:
        notes.append("代表帖互动偏低，结论权重建议下调")
    if not evidence:
        notes.append("缺少代表帖证据")
    if not notes:
        notes.append("证据链可用，可快速复核")
    return notes


def create_review_draft(analysis, context=None, normalization=None):
    """Convert analyzer output into editable review data for the UI."""
    pain_points = []
    for item in analysis.get("pain_points", []):
        top = item["posts"][0]
        evidence = [_serialize_post(post) for post in item.get("posts", [])[:5]]
        pain_points.append({
            "key": item.get("key", ""),
            "keep": True,
            "label": item.get("label", ""),
            "core_issue": infer_core_issue(top),
            "manual_note": "",
            "count": item.get("count", 0),
            "top_score": item.get("top_score", 0),
            "avg_score": item.get("avg_score", 0),
            "total_comments": item.get("total_comments", 0),
            "review_notes": _review_notes(
                item.get("count", 0),
                item.get("top_score", 0),
                evidence,
            ),
            "evidence": evidence,
        })

    features = []
    for item in analysis.get("features", []):
        evidence = [_serialize_post(post) for post in item.get("posts", [])[:5]]
        top_score = evidence[0]["score"] if evidence else 0
        features.append({
            "key": item.get("key", ""),
            "keep": True,
            "label": item.get("label", ""),
            "manual_note": "",
            "count": item.get("count", 0),
            "review_notes": _review_notes(item.get("count", 0), top_score, evidence),
            "evidence": evidence,
        })

    return {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "context": context or {},
        "normalization": normalization or {},
        "meta": analysis.get("meta", {}),
        "pain_points": pain_points,
        "features": features,
        "top_posts": [_serialize_post(post) for post in analysis.get("top10", [])],
    }


def _review_map(review_payload, section):
    return {
        item.get("key"): item
        for item in review_payload.get(section, [])
        if item.get("key")
    }


def apply_review_to_analysis(analysis, review_payload):
    """
    Merge human edits back into analyzer output.

    The reviewer may keep/remove items and override labels, core issues, or notes.
    """
    reviewed = deepcopy(analysis)

    pain_reviews = _review_map(review_payload or {}, "pain_points")
    pain_points = []
    for item in reviewed.get("pain_points", []):
        review = pain_reviews.get(item.get("key"))
        if review and not review.get("keep", True):
            continue
        if review:
            label = (review.get("label") or "").strip()
            core_issue = (review.get("core_issue") or "").strip()
            manual_note = (review.get("manual_note") or "").strip()

            if label:
                item["label"] = label
            if core_issue:
                item["core_issue"] = core_issue
            if manual_note:
                item["manual_note"] = manual_note
            else:
                item.pop("manual_note", None)
        pain_points.append(item)
    reviewed["pain_points"] = pain_points

    feature_reviews = _review_map(review_payload or {}, "features")
    features = []
    for item in reviewed.get("features", []):
        review = feature_reviews.get(item.get("key"))
        if review and not review.get("keep", True):
            continue
        if review:
            label = (review.get("label") or "").strip()
            manual_note = (review.get("manual_note") or "").strip()

            if label:
                item["label"] = label
            if manual_note:
                item["manual_note"] = manual_note
            else:
                item.pop("manual_note", None)
        features.append(item)
    reviewed["features"] = features

    return reviewed
