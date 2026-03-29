# claude-code-chat-report

Claude Code 使用历史分析工具，可以通过 **skill** 的形式运行，读取本地对话历史，生成周报风格的 Markdown 分析报告。

## 功能

- 按项目和时间范围筛选对话历史
- 统计会话数、提问数、活跃天数、Token 用量
- 分析工作内容、提问模式、工具使用习惯
- 识别反复出现的错误和效率瓶颈
- 输出可直接用于团队汇报的 Markdown 周报

## 安装

将 skill 目录链接或复制到你当前项目的 `.claude/skills/` 下：

```bash
ln -s /path/to/claude-code-chat-report/claude-chat-report \
      /your/project/.claude/skills/claude-chat-report
```

## 使用

在 Claude Code 中直接调用 skill：

```
/claude-chat-report
```

按提示输入项目关键词和时间范围，报告将保存到当前目录，文件名格式为：

```
claude-weekly-{from_date}-{to_date}.md
```

### 时间范围格式

| 输入 | 含义 |
|------|------|
| `today` | 今天 |
| `yesterday` | 昨天 |
| `this-week` | 本周（周一至今） |
| `last-week` | 上周 |
| `7d` | 最近 7 天 |
| `2w` | 最近 2 周 |
| `YYYY-MM-DD` | 指定日期 |

## 项目结构

```
claude-chat-report/
├── SKILL.md          # skill 定义，描述 Claude 的分析和报告生成行为
└── scripts/
    └── analyzer.py   # 数据提取脚本，读取 ~/.claude/projects/ 下的 JSONL 对话文件
```

### analyzer.py 子命令

```bash
# 列出所有项目
python3 analyzer.py list-projects

# 提取单个项目（支持关键词模糊匹配）
python3 analyzer.py extract "<keyword>" --from "this-week" --to "today"

# 跨项目汇总
python3 analyzer.py extract-all --from "last-week"
```

## 相关项目

如果需要将对话历史导出为完整网页（HTML 格式，支持代码高亮、工具调用展示），推荐可以使用：

**[daaain/claude-code-log](https://github.com/daaain/claude-code-log)**. 该项目可将 Claude Code 的 JSONL 对话文件渲染为可浏览的静态网页，适合存档或分享完整对话记录。
