"""
Product Demand Miner — Flask Web 入口
"""

import os
import threading
from flask import Flask, render_template, request, jsonify, send_file

from miner.crawler import crawl_reddit, crawl_hackernews, suggest_subreddits
from miner.analyzer import analyze_posts
from miner.reporter import generate_report, generate_docx

app = Flask(__name__)

_tasks = {}
_lock = threading.Lock()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/suggest_subreddits", methods=["POST"])
def suggest_subs():
    """根据关键词推荐相关板块"""
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
    subreddits = data.get("subreddits", [])
    time_start = data.get("time_start", "2025-10-01")
    time_end = data.get("time_end", "")
    time_filter = data.get("time_filter", "year")
    platforms = data.get("platforms", ["reddit"])
    other_platforms = data.get("other_platforms", "")

    if not keywords:
        return jsonify({"error": "请至少输入一个关键词"}), 400
    if not subreddits:
        return jsonify({"error": "请至少选择一个板块或点击推荐板块"}), 400

    task_id = f"task_{os.getpid()}_{id(data)}"
    with _lock:
        _tasks[task_id] = {"status": "running", "progress": "", "result": None}

    def _worker():
        try:
            all_posts = []

            # Reddit
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

            # Hacker News
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

            _tasks[task_id]["progress"] = f"搜索完成，共 {len(all_posts)} 条帖子。正在分析..."

            analysis = analyze_posts(all_posts)

            # 去重（跨平台）
            seen = set()
            unique = []
            for p in all_posts:
                if p["id"] not in seen:
                    seen.add(p["id"])
                    unique.append(p)
            analysis_dedup = analyze_posts(unique)

            time_range = f"{time_start} 至今" if not time_end else f"{time_start} 至 {time_end}"
            platform_labels = []
            if "reddit" in platforms:
                platform_labels.append("Reddit")
            if "hackernews" in platforms:
                platform_labels.append("Hacker News")
            if other_platforms:
                platform_labels.append(other_platforms)

            output_dir = os.path.join(os.path.dirname(__file__), "output")
            report_kwargs = dict(
                product_name=product_name,
                product_desc=product_desc,
                product_scope=product_scope,
                keywords=keywords,
                subreddits=subreddits,
                time_range=time_range,
                analysis=analysis_dedup,
                platforms=platform_labels,
                output_dir=output_dir,
            )

            md_path, csv_path = generate_report(**report_kwargs)

            _tasks[task_id]["progress"] = "正在生成 Word 文档..."

            docx_path = generate_docx(**report_kwargs)

            with _lock:
                _tasks[task_id]["status"] = "done"
                _tasks[task_id]["result"] = {
                    "md_path": md_path,
                    "csv_path": csv_path,
                    "docx_path": docx_path,
                    "total_posts": analysis_dedup["meta"]["total_posts"],
                    "pain_count": len(analysis_dedup["pain_points"]),
                    "feature_count": len(analysis_dedup["features"]),
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
    task = _tasks.get(task_id, {"status": "not_found"})
    return jsonify(task)


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
