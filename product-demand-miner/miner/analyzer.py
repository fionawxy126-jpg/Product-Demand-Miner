"""
数据清洗 + 痛点聚类模块
动态聚类，按数据量排序，最多 10 个痛点 + 10 个期待功能
"""

import re

# 痛点模式库（会自动过滤无匹配的类别）
PAIN_PATTERNS = {
    "prompt_error": {
        "label": "指令错误 / Prompt 不准",
        "patterns": [r"wrong prompt", r"prompt error", r"bad prompt", r"notice an error on my prompt",
                     r"wrong instruction", r"misunderstood", r"misinterpret"],
    },
    "billing_hidden": {
        "label": "隐性收费 / 计费不透明",
        "patterns": [r"billing", r"charge", r"charged", r"cost me", r"extra usage",
                     r"hidden fee", r"refund", r"hermes", r"silently.*bill"],
    },
    "token_transparency": {
        "label": "Token 消耗不透明",
        "patterns": [r"token.*go", r"where.*token", r"ccusage", r"token.*spend",
                     r"token.*cost", r"token.*transparent", r"visibility.*token"],
    },
    "pro_plan_removed": {
        "label": "订阅计划变更 / 付费墙",
        "patterns": [r"pro plan", r"no longer.*include", r"paywall", r"locked.*behind",
                     r"removed.*feature", r"quietly.*chang", r"price.*increase"],
    },
    "token_limit": {
        "label": "额度不够 / 限额过低",
        "patterns": [r"rate limit", r"hitting.*limit", r"quota", r"allowance",
                     r"hitting pro", r"ran out", r"usage cap", r"throttl"],
    },
    "agent_loop": {
        "label": "Agent 死循环 / 失控",
        "patterns": [r"loop", r"stuck", r"infinite", r"runaway", r"burning.*token",
                     r"overnight", r"spiraled", r"went crazy", r"won.?t stop"],
    },
    "context_memory": {
        "label": "上下文记忆 / 遗忘问题",
        "patterns": [r"memory", r"context window", r"forget", r"forgets",
                     r"claude\.md", r"doesn.?t remember", r"lost context", r"amnesia"],
    },
    "hallucination": {
        "label": "幻觉 / 编造内容",
        "patterns": [r"hallucinat", r"made up", r"fabricat", r"wrong api",
                     r"nonexistent", r"fake.*library", r"invented"],
    },
    "data_loss": {
        "label": "数据丢失 / 代码损坏",
        "patterns": [r"data loss", r"lost.*code", r"deleted", r"destroyed",
                     r"corrupted", r"wiped", r"overwrote", r"nuked"],
    },
    "performance": {
        "label": "性能问题 / 响应慢",
        "patterns": [r"slow", r"performance", r"latency", r"takes forever",
                     r"hang", r"timeout", r"response time", r"laggy"],
    },
    "output_quality": {
        "label": "输出质量不稳定",
        "patterns": [r"inconsistent", r"quality.*varies", r"unreliable.*output",
                     r"sometimes good sometimes", r"regression", r"got worse"],
    },
    "onboarding": {
        "label": "上手门槛高 / 文档不足",
        "patterns": [r"steep learning", r"hard to learn", r"confusing",
                     r"overwhelming", r"documentation.*bad", r"unclear.*setup"],
    },
    "integration": {
        "label": "集成困难 / 兼容性差",
        "patterns": [r"integration.*issue", r"doesn.?t work with", r"plugin.*broken",
                     r"incompatible", r"conflict.*with"],
    },
    "privacy_security": {
        "label": "隐私安全担忧",
        "patterns": [r"privacy", r"security.*concern", r"data.*safe", r"send.*data",
                     r"leak", r"sensitive.*code"],
    },
    "debugging": {
        "label": "调试困难 / 错误难定位",
        "patterns": [r"hard.*debug", r"can.?t figure out", r"no error message",
                     r"cryptic.*error", r"unhelpful.*error"],
    },
    "ux_clunky": {
        "label": "交互体验差",
        "patterns": [r"clunky", r"ux.*bad", r"frustrating", r"annoying",
                     r"user experience", r"ui.*terrible"],
    },
    "reliability": {
        "label": "稳定性差 / 频繁崩溃",
        "patterns": [r"crash", r"unstable", r"downtime", r"outage",
                     r"503", r"500 error", r"bug"],
    },
    "cost_value": {
        "label": "性价比低 / 定价不合理",
        "patterns": [r"overpriced", r"not worth", r"too expensive", r"rip.?off",
                     r"better value", r"cheaper alternative"],
    },
    "customization": {
        "label": "自定义能力不足",
        "patterns": [r"can.?t customize", r"no config", r"inflexible",
                     r"one size fits all", r"wish.*could.*config"],
    },
}

# 期待功能模式库
FEATURE_PATTERNS = {
    "token_dashboard": {
        "label": "Token 使用仪表盘",
        "patterns": [r"token.*dashboard", r"token.*visuali", r"see.*token",
                     r"track.*token", r"token.*monitor", r"token.*breakdown"],
    },
    "code_review": {
        "label": "代码审查 / 防幻觉",
        "patterns": [r"code review", r"anti.?vibe", r"review.*ai", r"verify.*code",
                     r"sanity check", r"automated.*review"],
    },
    "notification": {
        "label": "完成通知 / 状态提示",
        "patterns": [r"notification", r"alert.*finish", r"status.*indicator",
                     r"usb.*claude", r"desk lamp", r"notified.*when.*done"],
    },
    "better_context": {
        "label": "代码库结构化理解",
        "patterns": [r"codebase.*understand", r"graph", r"knowledge graph",
                     r"structure.*code", r"map.*codebase", r"codebase.*map"],
    },
    "flexible_pricing": {
        "label": "灵活计费方案",
        "patterns": [r"pricing", r"cheaper", r"free.*tier", r"pay.*per",
                     r"affordab", r"better.*plan"],
    },
    "better_memory": {
        "label": "持久记忆 / 跨会话上下文",
        "patterns": [r"persistent.*memory", r"cross.*session", r"remember.*before",
                     r"long.*term.*memory", r"project.*context"],
    },
    "collaboration": {
        "label": "多人协作支持",
        "patterns": [r"collaborat", r"team.*feature", r"shared.*session",
                     r"multi.*user", r"pair.*program"],
    },
    "ide_integration": {
        "label": "IDE 深度集成",
        "patterns": [r"ide.*integrat", r"vscode", r"jetbrains", r"editor.*plugin",
                     r"lsp", r"extension"],
    },
    "auto_testing": {
        "label": "自动测试生成",
        "patterns": [r"auto.*test", r"generate.*test", r"testing.*automat",
                     r"tdd", r"test.*coverage"],
    },
    "cost_control": {
        "label": "成本控制 / 预算管理",
        "patterns": [r"budget", r"cost.*control", r"spending.*limit", r"cap.*cost",
                     r"cost.*alert", r"spending.*alert"],
    },
    "error_recovery": {
        "label": "自动错误恢复",
        "patterns": [r"auto.*recover", r"rollback", r"undo", r"revert",
                     r"safe.*mode", r"checkpoint"],
    },
    "multimodal": {
        "label": "多模态输入支持",
        "patterns": [r"screenshot", r"image.*input", r"voice", r"multimodal",
                     r"vision", r"audio"],
    },
}

MAX_PAIN_POINTS = 10
MAX_FEATURES = 10


def _match(text, patterns):
    t = text.lower()
    for p in patterns:
        if re.search(p, t):
            return True
    return False


def analyze_posts(posts):
    """
    动态聚类：只保留有匹配的类别，按数据量排序，限制上限。

    Returns:
        {
            "meta": {...},
            "pain_points": [{category_key, label, posts, count, ...}, ...],  # 已排序
            "features": [{category_key, label, posts}, ...],                  # 已排序
            "top10": [...],
        }
    """
    if not posts:
        return {
            "meta": {"total_posts": 0, "total_comments": 0, "avg_score": 0, "subreddits": []},
            "pain_points": [],
            "features": [],
            "top10": [],
        }

    # 痛点聚类 → 列表 → 排序
    pain_list = []
    for cat, cfg in PAIN_PATTERNS.items():
        matched = [p for p in posts if _match(p["title"] + " " + p["body"], cfg["patterns"])]
        if matched:
            matched.sort(key=lambda x: x["score"], reverse=True)
            total_score = sum(p["score"] for p in matched)
            pain_list.append({
                "key": cat,
                "label": cfg["label"],
                "posts": matched,
                "count": len(matched),
                "total_comments": sum(p["num_comments"] for p in matched),
                "avg_score": round(total_score / len(matched), 1),
                "top_score": matched[0]["score"],
            })

    # 按相关帖子数 × 最高赞数综合排序，取 top 10
    pain_list.sort(key=lambda x: x["count"] * (x["top_score"] + 1), reverse=True)
    pain_list = pain_list[:MAX_PAIN_POINTS]

    # 期待功能聚类
    feat_list = []
    for cat, cfg in FEATURE_PATTERNS.items():
        matched = [p for p in posts if _match(p["title"] + " " + p["body"], cfg["patterns"])]
        if matched:
            matched.sort(key=lambda x: x["score"], reverse=True)
            feat_list.append({
                "key": cat,
                "label": cfg["label"],
                "posts": matched[:5],
                "count": len(matched),
            })

    feat_list.sort(key=lambda x: x["count"] * (x["posts"][0]["score"] + 1), reverse=True)
    feat_list = feat_list[:MAX_FEATURES]

    # 统计
    total_comments = sum(p["num_comments"] for p in posts)
    avg_score = round(sum(p["score"] for p in posts) / len(posts), 1)
    subreddits = sorted(set(p.get("subreddit", "") for p in posts if p.get("subreddit")))
    top10 = sorted(posts, key=lambda x: x["score"], reverse=True)[:10]

    return {
        "meta": {
            "total_posts": len(posts),
            "total_comments": total_comments,
            "avg_score": avg_score,
            "subreddits": subreddits,
        },
        "pain_points": pain_list,
        "features": feat_list,
        "top10": top10,
    }
