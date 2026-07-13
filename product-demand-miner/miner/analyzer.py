"""
Product-demand analysis.

The analyzer keeps the original report contract while using broader, product-
agnostic signals. It still supports AI-coding specific categories, but it no
longer depends on them to produce useful pain-point and demand clusters.
"""

import re
from collections import defaultdict

PAIN_PATTERNS = {
    "pricing_value": {
        "label": "价格 / 性价比压力",
        "patterns": [r"too expensive", r"overpriced", r"not worth", r"pricing", r"price",
                     r"cost", r"charge", r"billing", r"subscription", r"plan", r"refund",
                     r"paywall", r"free tier", r"cheaper", r"affordab"],
    },
    "reliability_stability": {
        "label": "稳定性 / 可用性问题",
        "patterns": [r"bug", r"broken", r"crash", r"unstable", r"doesn.?t work",
                     r"not working", r"fails?", r"failure", r"outage", r"error",
                     r"timeout", r"stuck", r"hang", r"regression"],
    },
    "workflow_friction": {
        "label": "流程割裂 / 使用摩擦",
        "patterns": [r"workflow", r"friction", r"annoying", r"tedious", r"manual",
                     r"copy.?paste", r"switching", r"context switch", r"too many steps",
                     r"hard to manage", r"cumbersome"],
    },
    "learning_setup": {
        "label": "上手门槛 / 配置复杂",
        "patterns": [r"hard to learn", r"steep learning", r"confusing", r"setup",
                     r"install", r"configuration", r"docs?", r"documentation",
                     r"unclear", r"overwhelming", r"onboarding"],
    },
    "integration_compatibility": {
        "label": "集成 / 兼容性不足",
        "patterns": [r"integration", r"compatible", r"incompatible", r"plugin",
                     r"extension", r"api", r"sdk", r"connect", r"import", r"export",
                     r"doesn.?t support", r"works with"],
    },
    "trust_safety_control": {
        "label": "信任 / 安全 / 可控性担忧",
        "patterns": [r"privacy", r"security", r"safe", r"trust", r"leak",
                     r"sensitive", r"permission", r"access", r"control", r"audit",
                     r"compliance", r"risk"],
    },
    "quality_accuracy": {
        "label": "结果质量 / 准确性不稳定",
        "patterns": [r"inaccurate", r"wrong", r"bad output", r"quality", r"inconsistent",
                     r"unreliable", r"hallucinat", r"made up", r"mistake",
                     r"doesn.?t understand", r"misunderstood"],
    },
    "performance_scale": {
        "label": "性能 / 规模化瓶颈",
        "patterns": [r"slow", r"latency", r"performance", r"scale", r"scaling",
                     r"large project", r"big codebase", r"takes forever", r"lag",
                     r"memory", r"resource", r"cpu", r"quota", r"limit"],
    },
    "missing_capability": {
        "label": "关键能力缺失",
        "patterns": [r"missing", r"lack", r"no support", r"wish", r"need", r"would love",
                     r"feature request", r"should have", r"can.?t", r"unable to"],
    },
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

FEATURE_PATTERNS = {
    "automation_orchestration": {
        "label": "自动化工作流 / 编排能力",
        "patterns": [r"automate", r"automation", r"workflow", r"orchestrat", r"pipeline",
                     r"agent", r"schedule", r"trigger", r"batch", r"hands.?off"],
    },
    "visibility_analytics": {
        "label": "数据看板 / 可视化监控",
        "patterns": [r"dashboard", r"analytics", r"visuali", r"monitor", r"tracking",
                     r"metrics", r"insight", r"report", r"breakdown", r"visibility"],
    },
    "review_validation": {
        "label": "审核 / 校验 / 质量控制",
        "patterns": [r"review", r"validate", r"verify", r"check", r"approval",
                     r"quality control", r"guardrail", r"test", r"evaluation",
                     r"benchmark", r"sanity"],
    },
    "collaboration_sharing": {
        "label": "协作 / 分享 / 团队流程",
        "patterns": [r"collaborat", r"team", r"share", r"handoff", r"comment",
                     r"permission", r"workspace", r"multi.?user", r"role"],
    },
    "integration_extension": {
        "label": "集成扩展 / API 连接",
        "patterns": [r"integration", r"api", r"sdk", r"plugin", r"extension",
                     r"webhook", r"connect", r"export", r"import", r"native support"],
    },
    "personalization_control": {
        "label": "个性化 / 控制面板",
        "patterns": [r"custom", r"customi", r"config", r"setting", r"preference",
                     r"template", r"rule", r"policy", r"control", r"fine.?tune"],
    },
    "memory_context": {
        "label": "上下文记忆 / 项目知识库",
        "patterns": [r"context", r"memory", r"knowledge", r"history", r"remember",
                     r"resume", r"state", r"session", r"long.?term"],
    },
    "pricing_flexibility": {
        "label": "灵活计费 / 成本控制",
        "patterns": [r"pricing", r"budget", r"cost control", r"usage", r"spend",
                     r"cap", r"limit", r"pay.?as.?you.?go", r"free tier"],
    },
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
TOP_FALLBACK_POSTS = 8

PAIN_SIGNAL_PATTERNS = [
    r"\b(problem|issue|bug|broken|frustrating|annoying|pain|struggle|hard|difficult)\b",
    r"\b(can.?t|cannot|unable|fails?|failed|doesn.?t work|not working)\b",
    r"\b(expensive|overpriced|slow|confusing|missing|lack|limitation|risk)\b",
]

DEMAND_SIGNAL_PATTERNS = [
    r"\b(wish|need|want|would love|feature request|should have|looking for)\b",
    r"\b(add|support|integrate|automate|dashboard|export|import|customi[sz]e)\b",
    r"\b(better|improve|improvement|alternative|solution)\b",
]

STOPWORDS = {
    "about", "after", "again", "agent", "also", "because", "being", "build",
    "built", "cannot", "claude", "codex", "could", "first", "from", "have",
    "html", "http", "https", "into", "just", "like", "more", "need", "over",
    "show", "that", "their",
    "there", "these", "thing", "this", "using", "with", "without", "would",
    "your", "what", "when", "where", "which", "while",
}


def _match(text, patterns):
    t = text.lower()
    for p in patterns:
        if re.search(p, t):
            return True
    return False


def _text(post):
    return f"{post.get('title', '')} {post.get('body', '')}".strip()


def _post_weight(post):
    return max(post.get("score", 0), 0) + max(post.get("num_comments", 0), 0) * 0.35 + 1


def _cluster_score(posts):
    return sum(_post_weight(post) for post in posts)


def _top_terms(posts, limit=4):
    counts = defaultdict(int)
    for post in posts:
        text = _text(post).lower()
        for word in re.findall(r"[a-z][a-z0-9_\-]{3,}", text):
            if word in STOPWORDS:
                continue
            counts[word] += 1
    return [word for word, _ in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:limit]]


def _make_fallback_label(prefix, posts):
    terms = _top_terms(posts)
    if terms:
        return f"{prefix}: {' / '.join(terms[:3])}"
    return prefix


def _build_pain_item(key, label, matched):
    matched.sort(key=lambda post: _post_weight(post), reverse=True)
    total_score = sum(post.get("score", 0) for post in matched)
    return {
        "key": key,
        "label": label,
        "posts": matched,
        "count": len(matched),
        "total_comments": sum(post.get("num_comments", 0) for post in matched),
        "avg_score": round(total_score / len(matched), 1),
        "top_score": matched[0].get("score", 0),
    }


def _build_feature_item(key, label, matched):
    matched.sort(key=lambda post: _post_weight(post), reverse=True)
    return {
        "key": key,
        "label": label,
        "posts": matched[:5],
        "count": len(matched),
    }


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

    pain_list = []
    for cat, cfg in PAIN_PATTERNS.items():
        matched = [p for p in posts if _match(_text(p), cfg["patterns"])]
        if matched:
            pain_list.append(_build_pain_item(cat, cfg["label"], matched))

    fallback_pain = [
        p for p in posts
        if _match(_text(p), PAIN_SIGNAL_PATTERNS)
    ]
    if fallback_pain:
        pain_list.append(_build_pain_item(
            "market_pain_signals",
            _make_fallback_label("高信号痛点讨论", fallback_pain),
            fallback_pain[:TOP_FALLBACK_POSTS],
        ))

    pain_list.sort(key=lambda item: item["count"] * _cluster_score(item["posts"]), reverse=True)
    pain_list = pain_list[:MAX_PAIN_POINTS]

    feat_list = []
    for cat, cfg in FEATURE_PATTERNS.items():
        matched = [p for p in posts if _match(_text(p), cfg["patterns"])]
        if matched:
            feat_list.append(_build_feature_item(cat, cfg["label"], matched))

    fallback_demand = [
        p for p in posts
        if _match(_text(p), DEMAND_SIGNAL_PATTERNS)
    ]
    if fallback_demand:
        feat_list.append(_build_feature_item(
            "market_demand_signals",
            _make_fallback_label("高信号需求讨论", fallback_demand),
            fallback_demand[:TOP_FALLBACK_POSTS],
        ))

    feat_list.sort(key=lambda item: item["count"] * _cluster_score(item["posts"]), reverse=True)
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
