"""
Product Demand Miner — Flask Web 入口
"""

import os
import re
import threading
from flask import Flask, render_template, request, jsonify, send_file

from miner.crawler import (
    crawl_reddit,
    crawl_hackernews,
    crawl_web_search,
    crawl_x_search,
    suggest_subreddits,
    get_last_crawl_warnings,
)
from miner.analyzer import analyze_posts
from miner.normalizer import normalize_posts
from miner.reviewer import create_review_draft, apply_review_to_analysis
from miner.reporter import generate_report, generate_docx


def _load_env_file():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

_tasks = {}
_lock = threading.Lock()
_SUBREDDIT_RE = re.compile(r"^[A-Za-z0-9_]{3,21}$")


def _clean_subreddits(values):
    cleaned = []
    invalid = []
    seen = set()
    for raw in values or []:
        name = str(raw).strip().removeprefix("r/").removeprefix("R/")
        if not name:
            continue
        if not _SUBREDDIT_RE.match(name):
            invalid.append(name)
            continue
        key = name.lower()
        if key not in seen:
            cleaned.append(name)
            seen.add(key)
    return cleaned, invalid


def _platform_labels(platforms, other_platforms=""):
    labels = []
    if "reddit" in platforms:
        labels.append("Reddit")
    if "hackernews" in platforms:
        labels.append("Hacker News")
    if "web" in platforms:
        labels.append("Web Search")
    if "x" in platforms:
        labels.append("X / Twitter")
    if other_platforms:
        labels.append(other_platforms)
    return labels


def _public_task(task):
    if not task:
        return {"status": "not_found"}
    return {
        "status": task.get("status"),
        "progress": task.get("progress", ""),
        "result": task.get("result"),
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/suggest_subreddits", methods=["POST"])
def suggest_subs():
    """根据关键词推荐相关 Reddit 社区"""
    data = request.get_json()
    keywords = [k.strip() for k in data.get("keywords", "").split(",") if k.strip()]
    if not keywords:
        return jsonify({"subreddits": []})
    try:
        subs = suggest_subreddits(keywords, limit=20)
        return jsonify({"subreddits": subs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/run", methods=["POST"])
def run():
    data = request.get_json()
    product_name = data.get("product_name", "未命名产品")
    product_desc = data.get("product_desc", "")
    product_scope = data.get("product_scope", "")
    keywords = [k.strip() for k in data.get("keywords", "").split(",") if k.strip()]
    subreddits, invalid_subreddits = _clean_subreddits(data.get("subreddits", []))
    time_start = data.get("time_start", "2025-10-01")
    time_end = data.get("time_end", "")
    time_filter = data.get("time_filter", "year")
    platforms = data.get("platforms", ["reddit"])
    other_platforms = data.get("other_platforms", "")

    if not keywords:
        return jsonify({"error": "请至少输入一个关键词"}), 400
    if not platforms:
        return jsonify({"error": "请至少选择一个数据来源平台"}), 400
    if invalid_subreddits:
        return jsonify({
            "error": (
                f"{', '.join(invalid_subreddits)} 看起来不是 Reddit 社区名。"
                "关键词请放在“爬取关键词”，限定社区可以留空。"
            )
        }), 400
    task_id = f"task_{os.getpid()}_{id(data)}"
    with _lock:
        _tasks[task_id] = {"status": "running", "progress": "", "result": None}

    def _worker():
        try:
            all_posts = []
            crawl_warnings = []

            if "reddit" in platforms:
                def on_reddit_progress(current, total, count):
                    _tasks[task_id]["progress"] = f"[Reddit] 搜索 {current}/{total}（已找到 {count} 条）"

                reddit_posts = crawl_reddit(
                    keywords=keywords,
                    subreddits=subreddits,
                    time_start=time_start,
                    time_end=time_end or None,
                    time_filter=time_filter,
                    on_progress=on_reddit_progress,
                )
                all_posts.extend(reddit_posts)
                crawl_warnings.extend(get_last_crawl_warnings())

            if "hackernews" in platforms:
                _tasks[task_id]["progress"] = f"正在搜索 Hacker News..."

                hn_posts = crawl_hackernews(
                    keywords=keywords,
                    time_start=time_start,
                    time_end=time_end or None,
                    on_progress=lambda c, t, n: _tasks[task_id].update(
                        {"progress": f"[Hacker News] 已找到 {n} 条帖子"}
                    ),
                )
                all_posts.extend(hn_posts)

            if "web" in platforms:
                _tasks[task_id]["progress"] = "正在搜索公开网页..."

                web_posts = crawl_web_search(
                    keywords=keywords,
                    time_start=time_start,
                    time_end=time_end or None,
                    on_progress=lambda c, t, n: _tasks[task_id].update(
                        {"progress": f"[Web Search] 搜索 {c}/{t}（已找到 {n} 条）"}
                    ),
                )
                all_posts.extend(web_posts)
                crawl_warnings.extend(get_last_crawl_warnings())

            if "x" in platforms:
                _tasks[task_id]["progress"] = "正在搜索 X / Twitter 公开结果..."

                x_posts = crawl_x_search(
                    keywords=keywords,
                    time_start=time_start,
                    time_end=time_end or None,
                    on_progress=lambda c, t, n: _tasks[task_id].update(
                        {"progress": f"[X / Twitter] 搜索 {c}/{t}（已找到 {n} 条）"}
                    ),
                )
                all_posts.extend(x_posts)
                crawl_warnings.extend(get_last_crawl_warnings())

            _tasks[task_id]["progress"] = f"搜索完成，共 {len(all_posts)} 条帖子。正在清洗去重..."

            normalized = normalize_posts(
                all_posts,
                time_start=time_start,
                time_end=time_end or None,
            )
            posts = normalized["posts"]
            stats = normalized["stats"]

            if not posts:
                with _lock:
                    _tasks[task_id]["status"] = "empty"
                    _tasks[task_id]["progress"] = (
                        "没有找到可分析的帖子。请放宽时间范围，减少限定社区，或换一组更贴近用户表达的关键词。"
                    )
                    _tasks[task_id]["result"] = {
                        "normalization": stats,
                        "warnings": crawl_warnings,
                        "total_posts": 0,
                        "pain_count": 0,
                        "feature_count": 0,
                    }
                return

            _tasks[task_id]["progress"] = (
                f"清洗完成，保留 {len(posts)} 条帖子。正在分析和 AI 复核..."
            )

            analysis = analyze_posts(posts)

            time_range = f"{time_start} 至今" if not time_end else f"{time_start} 至 {time_end}"
            platform_labels = _platform_labels(platforms, other_platforms)

            output_dir = os.path.join(os.path.dirname(__file__), "output")
            report_context = dict(
                product_name=product_name,
                product_desc=product_desc,
                product_scope=product_scope,
                keywords=keywords,
                subreddits=subreddits,
                time_range=time_range,
                platforms=platform_labels,
                output_dir=output_dir,
            )

            review = create_review_draft(
                analysis,
                context={
                    "product_name": product_name,
                    "keywords": keywords,
                    "time_range": time_range,
                    "platforms": platform_labels,
                },
                normalization=stats,
            )

            with _lock:
                _tasks[task_id]["status"] = "review_ready"
                _tasks[task_id]["progress"] = "AI 复核完成，请检查后导出报告。"
                _tasks[task_id]["analysis"] = analysis
                _tasks[task_id]["report_context"] = report_context
                _tasks[task_id]["result"] = {
                    "review": review,
                    "normalization": stats,
                    "warnings": crawl_warnings,
                    "total_posts": analysis["meta"]["total_posts"],
                    "pain_count": len(analysis["pain_points"]),
                    "feature_count": len(analysis["features"]),
                }
        except Exception as e:
            with _lock:
                _tasks[task_id]["status"] = "error"
                _tasks[task_id]["progress"] = str(e)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    return jsonify({"task_id": task_id})


@app.route("/status/<task_id>")
def status(task_id):
    return jsonify(_public_task(_tasks.get(task_id)))


@app.route("/export/<task_id>", methods=["POST"])
def export_report(task_id):
    data = request.get_json() or {}
    review_payload = data.get("review", {})

    with _lock:
        task = _tasks.get(task_id)
        if not task:
            return jsonify({"error": "任务不存在或已过期"}), 404
        if task.get("status") not in ("review_ready", "done"):
            return jsonify({"error": "任务还未完成 AI 复核，暂不能导出"}), 400
        task["status"] = "exporting"
        task["progress"] = "正在根据复核结果生成报告..."
        analysis = task.get("analysis")
        report_context = task.get("report_context")

    try:
        reviewed_analysis = apply_review_to_analysis(analysis, review_payload)
        report_kwargs = {**report_context, "analysis": reviewed_analysis}

        md_path, csv_path = generate_report(**report_kwargs)
        docx_path = generate_docx(**report_kwargs)

        result = {
            "md_path": md_path,
            "csv_path": csv_path,
            "docx_path": docx_path,
            "total_posts": reviewed_analysis["meta"]["total_posts"],
            "pain_count": len(reviewed_analysis["pain_points"]),
            "feature_count": len(reviewed_analysis["features"]),
        }
        with _lock:
            task["status"] = "done"
            task["progress"] = "报告已生成。"
            task["result"] = result
        return jsonify({"result": result})
    except Exception as e:
        with _lock:
            task["status"] = "review_ready"
            task["progress"] = f"导出失败: {e}"
        return jsonify({"error": str(e)}), 500


@app.route("/download/<path:filename>")
def download(filename):
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    path = os.path.join(output_dir, os.path.basename(filename))
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return "File not found", 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)
