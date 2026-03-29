---
name: claude-chat-report
description: 总结 Claude Code 使用历史，生成周报风格的分析报告。输入项目名称（关键词模糊匹配）和时间范围，分析提问规律、工具使用、常见问题，输出可直接用作周报的 Markdown 报告并保存到当前目录。
---

# Claude Code 使用历史分析与周报生成

根据用户指定的项目和时间范围，分析 Claude Code 对话历史，生成有深度见解的周报风格总结。

## 数据提取脚本

脚本位于本 skill 的 `scripts/` 目录下：

```
ANALYZER="<this-skill-dir>/scripts/analyzer.py"
```

运行时将 `<this-skill-dir>` 替换为本 SKILL.md 所在目录的绝对路径。

## 参数解析

从用户输入中识别以下参数：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| 项目 | 关键词模糊匹配（如 `vibe-coding`、`super-agent`），或 `all` | 无，需用户选择 |
| 起始时间 | `today`、`yesterday`、`this-week`、`last-week`、`7d`、`2w`、`YYYY-MM-DD` | `this-week` |
| 结束时间 | 同上 | 当前时间 |
| 输出路径 | 报告保存位置 | 当前工作目录 |

如果用户没有指定项目，先运行 `list-projects` 列出可选项目让用户选择。

## 执行步骤

### Step 1: 获取数据

**列出项目：**
```bash
python3 $ANALYZER list-projects
```

**提取单个项目（支持关键词模糊匹配）：**
```bash
python3 $ANALYZER extract "<keyword>" --from "<from>" --to "<to>"
```

**提取所有项目概览：**
```bash
python3 $ANALYZER extract-all --from "<from>" --to "<to>"
```

如果用户指定了具体项目就用 `extract`，指定 `all` 或未指定则先用 `extract-all` 获取全景后再按需深入。

### Step 2: 分析数据并生成报告

仔细阅读提取的 JSON 数据，从以下维度进行**深度分析**，生成 Markdown 报告：

```markdown
# Claude Code 使用周报

> 时间范围：{from_date} ~ {to_date}
> 项目：{project_name}
> 生成时间：{now}

## 一、概览

| 指标 | 数值 |
|------|------|
| 会话数 | {sessions} |
| 提问数 | {questions} |
| 活跃天数 | {active_days} |
| 输入 Token | {input_tokens} |
| 输出 Token | {output_tokens} |

## 二、每日活跃度

按日期展示提问数和会话数的趋势，识别高峰和低谷日。
用简单的文本柱状图或表格呈现。

## 三、工作内容分析

根据提问内容归纳主要工作方向：
- 按主题分类（bug修复、新功能开发、配置调试、学习探索等）
- 每个主题列出关键提问和进展
- 评估各方向的投入程度（提问数占比）

## 四、提问模式洞察

- **高频主题**：反复出现的话题
- **提问风格**：具体问题 vs 开放式探索
- **深度 vs 广度**：深入一个问题 vs 跳跃多个话题
- **自主性趋势**：从"问怎么做"到"帮我做"的变化

## 五、工具使用分析

- 最常用工具 Top 5 及使用场景
- 工具使用合理性（如过多 Bash 而非专用工具）
- 优化建议

## 六、问题与风险

- **反复出现的错误**：从 errors 数据识别模式
- **未解决的问题**：从提问内容判断
- **效率瓶颈**：耗时长的会话、反复修改的场景

## 七、建议与改进

基于分析给出**具体可操作**的建议：
- 工作流程优化
- Claude Code 使用技巧
- 下周工作重点建议
```

### Step 3: 保存报告

保存到当前工作目录，文件名：`claude-weekly-{from_date}-{to_date}.md`

例如：`claude-weekly-2026-03-20-2026-03-27.md`

## 分析原则

- **有见解，不是流水账**：归纳工作方向和模式，不要逐条罗列提问
- **发现规律**：从重复关键词、相似问题中提取规律
- **可操作的建议**：具体到"建议用 Grep 替代 bash grep"，而非"建议优化工具使用"
- **数据驱动**：每个观点都有数据支撑（提问数、token 数、频次）
- **中文输出**：报告使用中文
- **周报风格**：可直接用于团队或上级汇报
