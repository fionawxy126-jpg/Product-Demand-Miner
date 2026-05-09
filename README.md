# Reddit 调研工具

搜索 Reddit 上 AI coding 相关帖子，导出 CSV 和摘要。

## 使用步骤

```bash
# 1. 安装依赖
pip3 install praw

# 2. 打开脚本，填入你的 Reddit API 凭证
#    需要填写: CLIENT_ID, CLIENT_SECRET, USERNAME, PASSWORD

# 3. 运行
python3 reddit_research.py
```

## 输出文件

- `reddit_posts.csv` — 所有帖子数据
- `summary.md` — 自动生成的调研摘要

## Reddit API 凭证申请

1. 访问 https://www.reddit.com/prefs/apps
2. 点底部 "create app"
3. 类型选 "script"
4. redirect uri 填 `http://localhost:8080`
5. 拿到 client_id 和 client_secret
