"""
Small local heuristics for turning matched evidence into reportable claims.
"""


def infer_core_issue(post):
    """Infer a concise issue description from the representative post."""
    text = (post["title"] + " " + post.get("body", "")[:200]).lower()

    issues = [
        (["prompt", "instruction", "error on", "misunderstood"],
         "用户指令不够精确，AI 生成大量代码后发现方向错误，需要推倒重来"),
        (["billing", "charged", "cost me", "hidden fee", "hermes", "silently"],
         "存在隐性扣费或计费不透明的问题，用户在不知情的情况下被额外收费"),
        (["token", "ccusage", "visibility"],
         "用户无法清晰了解 token 消耗的具体去向和分布，缺乏透明度"),
        (["pro plan", "paywall", "locked", "no longer", "price"],
         "产品订阅计划突然变更，核心功能被移到更高价位，用户感到被欺骗"),
        (["limit", "quota", "rate limit", "allowance", "throttl"],
         "订阅额度不足以支撑正常使用频率，用户被迫降低使用量或寻找替代方案"),
        (["loop", "stuck", "infinite", "overnight", "burning", "spiraled"],
         "AI Agent 进入死循环或失控状态，持续消耗资源无法自行停止"),
        (["memory", "context", "forget", "claude.md", "amnesia"],
         "AI 在长会话中遗忘之前约定的上下文或指令，导致行为不一致"),
        (["hallucinat", "made up", "fabricat", "nonexistent"],
         "AI 编造不存在的 API、库或事实，导致生成的代码无法运行"),
        (["data loss", "lost code", "deleted", "destroyed", "wiped", "nuked"],
         "AI 操作导致用户代码或数据被意外删除或覆盖，造成不可逆损失"),
        (["slow", "performance", "latency", "hang", "timeout"],
         "工具响应速度慢或频繁超时，严重影响开发效率"),
        (["crash", "unstable", "downtime", "outage", "bug"],
         "工具频繁崩溃或出现稳定性问题，无法可靠地完成工作"),
        (["privacy", "security", "data safe", "leak", "sensitive"],
         "用户担心代码和数据的隐私安全，对数据传输和存储方式缺乏信任"),
    ]

    for keywords, desc in issues:
        if any(k in text for k in keywords):
            return desc

    return "用户在使用过程中遇到了影响体验的关键问题"
