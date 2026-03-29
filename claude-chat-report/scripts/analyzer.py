#!/usr/bin/env python3
"""
Claude Code Chat History Analyzer
Extracts user questions, tool usage, and session metadata from Claude Code JSONL files.
Output JSON for Claude to generate weekly-report-style summaries.
"""

import json
import os
import sys
import glob
import argparse
from datetime import datetime, timezone, timedelta
from collections import defaultdict

PROJECTS_DIR = os.path.expanduser("~/.claude/projects")


def parse_date(date_str):
    """Parse date string. Supports: YYYY-MM-DD, today, yesterday, Nd (N days ago), Nw (N weeks ago), this-week, last-week."""
    if not date_str:
        return None
    s = date_str.strip().lower()
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if s == "today":
        return midnight
    elif s == "yesterday":
        return midnight - timedelta(days=1)
    elif s == "this-week":
        return midnight - timedelta(days=midnight.weekday())  # Monday
    elif s == "last-week":
        return midnight - timedelta(days=midnight.weekday() + 7)
    elif s.endswith("d") and s[:-1].isdigit():
        return midnight - timedelta(days=int(s[:-1]))
    elif s.endswith("w") and s[:-1].isdigit():
        return midnight - timedelta(weeks=int(s[:-1]))
    else:
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse date: {date_str}")


def list_projects():
    """List all projects with stats."""
    if not os.path.isdir(PROJECTS_DIR):
        print(json.dumps({"error": "No projects directory"}))
        return
    projects = []
    for name in sorted(os.listdir(PROJECTS_DIR)):
        p = os.path.join(PROJECTS_DIR, name)
        if not os.path.isdir(p):
            continue
        jfiles = glob.glob(os.path.join(p, "*.jsonl"))
        if not jfiles:
            continue
        mtimes = [os.path.getmtime(f) for f in jfiles]
        projects.append({
            "dir_name": name,
            "readable_path": name.replace("-", "/"),
            "sessions": len(jfiles),
            "last_active": datetime.fromtimestamp(max(mtimes)).strftime("%Y-%m-%d %H:%M")
        })
    projects.sort(key=lambda x: x["last_active"], reverse=True)
    print(json.dumps(projects, indent=2, ensure_ascii=False))


def resolve_project(keyword):
    """Resolve project directory from keyword (exact or fuzzy)."""
    exact = os.path.join(PROJECTS_DIR, keyword)
    if os.path.isdir(exact):
        return keyword
    for name in os.listdir(PROJECTS_DIR):
        if keyword.lower() in name.lower():
            if os.path.isdir(os.path.join(PROJECTS_DIR, name)):
                return name
    return None


def extract(project_key, from_date=None, to_date=None):
    """Extract questions, tool usage, error patterns from a project."""
    proj_name = resolve_project(project_key)
    if not proj_name:
        print(json.dumps({"error": f"Project not found: {project_key}"}))
        return

    from_dt = parse_date(from_date) if from_date else None
    to_dt = parse_date(to_date) if to_date else None
    if to_dt:
        to_dt = to_dt.replace(hour=23, minute=59, second=59)

    proj_path = os.path.join(PROJECTS_DIR, proj_name)
    jfiles = sorted(glob.glob(os.path.join(proj_path, "*.jsonl")))

    sessions = []
    all_tool_usage = defaultdict(int)
    all_errors = []
    daily_activity = defaultdict(lambda: {"questions": 0, "sessions": set()})
    total_in_tok = 0
    total_out_tok = 0

    for jf in jfiles:
        sid = os.path.basename(jf).replace(".jsonl", "")
        questions = []
        tools = defaultdict(int)
        errors = []
        s_start = s_end = None
        in_tok = out_tok = 0

        try:
            with open(jf, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    ts_str = e.get("timestamp", "")
                    if not ts_str:
                        continue
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        continue

                    if from_dt and ts < from_dt:
                        continue
                    if to_dt and ts > to_dt:
                        continue

                    if not s_start or ts < s_start:
                        s_start = ts
                    if not s_end or ts > s_end:
                        s_end = ts

                    typ = e.get("type", "")

                    # User questions
                    if typ == "user" and not e.get("isMeta") and not e.get("isSidechain"):
                        msg = e.get("message", {})
                        content = msg.get("content", "")
                        text = ""
                        if isinstance(content, str):
                            text = content.strip()
                        elif isinstance(content, list):
                            parts = [i.get("text", "") for i in content if isinstance(i, dict) and i.get("type") == "text"]
                            text = "\n".join(parts).strip()
                        if len(text) > 3:
                            questions.append({
                                "time": ts.strftime("%Y-%m-%d %H:%M"),
                                "text": text[:800],
                                "length": len(text)
                            })
                            day = ts.strftime("%Y-%m-%d")
                            daily_activity[day]["questions"] += 1
                            daily_activity[day]["sessions"].add(sid)

                    # Assistant: tools + tokens
                    elif typ == "assistant":
                        msg = e.get("message", {})
                        usage = msg.get("usage", {})
                        if usage:
                            in_tok += usage.get("input_tokens", 0)
                            out_tok += usage.get("output_tokens", 0)
                        content = msg.get("content", [])
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "tool_use":
                                    tn = item.get("name", "unknown")
                                    tools[tn] += 1
                                    all_tool_usage[tn] += 1

                    # System errors
                    elif typ == "system":
                        level = e.get("level", "")
                        subtype = e.get("subtype", "")
                        content = e.get("content", "")
                        if level in ("error", "warning") or "error" in str(content).lower()[:200]:
                            if isinstance(content, str) and len(content) > 5:
                                errors.append({
                                    "time": ts.strftime("%Y-%m-%d %H:%M"),
                                    "level": level or subtype,
                                    "text": content[:300]
                                })
                                all_errors.append(errors[-1])

        except (OSError, IOError):
            continue

        if questions:
            sessions.append({
                "session_id": sid[:8],
                "start": s_start.strftime("%Y-%m-%d %H:%M") if s_start else "",
                "end": s_end.strftime("%Y-%m-%d %H:%M") if s_end else "",
                "duration_min": int((s_end - s_start).total_seconds() / 60) if s_start and s_end else 0,
                "question_count": len(questions),
                "questions": questions,
                "tools": dict(sorted(tools.items(), key=lambda x: -x[1])[:15]),
                "errors": errors[:10],
                "input_tokens": in_tok,
                "output_tokens": out_tok
            })

        total_in_tok += in_tok
        total_out_tok += out_tok

    sessions.sort(key=lambda s: s["start"])

    # Convert daily_activity sets to counts
    daily = {}
    for day, info in sorted(daily_activity.items()):
        daily[day] = {"questions": info["questions"], "sessions": len(info["sessions"])}

    result = {
        "project": proj_name,
        "readable_path": proj_name.replace("-", "/"),
        "time_range": {"from": from_date or "all", "to": to_date or "now"},
        "stats": {
            "total_sessions": len(sessions),
            "total_questions": sum(s["question_count"] for s in sessions),
            "total_input_tokens": total_in_tok,
            "total_output_tokens": total_out_tok,
            "total_errors": len(all_errors),
            "daily_activity": daily,
            "top_tools": dict(sorted(all_tool_usage.items(), key=lambda x: -x[1])[:20]),
        },
        "sessions": sessions,
        "errors_sample": all_errors[:20],
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def extract_all(from_date=None, to_date=None):
    """Extract summary across all projects."""
    if not os.path.isdir(PROJECTS_DIR):
        print(json.dumps({"error": "No projects directory"}))
        return
    project_summaries = []
    for name in sorted(os.listdir(PROJECTS_DIR)):
        p = os.path.join(PROJECTS_DIR, name)
        if not os.path.isdir(p) or not glob.glob(os.path.join(p, "*.jsonl")):
            continue
        # Quick scan: count questions in time range
        from_dt = parse_date(from_date) if from_date else None
        to_dt = parse_date(to_date) if to_date else None
        if to_dt:
            to_dt = to_dt.replace(hour=23, minute=59, second=59)

        q_count = 0
        s_count = 0
        first_ts = last_ts = None
        for jf in glob.glob(os.path.join(p, "*.jsonl")):
            has_q = False
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            e = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        ts_str = e.get("timestamp", "")
                        if not ts_str:
                            continue
                        try:
                            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        except (ValueError, TypeError):
                            continue
                        if from_dt and ts < from_dt:
                            continue
                        if to_dt and ts > to_dt:
                            continue
                        if not first_ts or ts < first_ts:
                            first_ts = ts
                        if not last_ts or ts > last_ts:
                            last_ts = ts
                        if e.get("type") == "user" and not e.get("isMeta") and not e.get("isSidechain"):
                            msg = e.get("message", {})
                            c = msg.get("content", "")
                            if isinstance(c, str) and len(c.strip()) > 3:
                                q_count += 1
                                has_q = True
                            elif isinstance(c, list):
                                texts = [i.get("text", "") for i in c if isinstance(i, dict) and i.get("type") == "text"]
                                if len("".join(texts).strip()) > 3:
                                    q_count += 1
                                    has_q = True
            except (OSError, IOError):
                continue
            if has_q:
                s_count += 1

        if q_count > 0:
            project_summaries.append({
                "dir_name": name,
                "readable_path": name.replace("-", "/"),
                "sessions": s_count,
                "questions": q_count,
                "first_active": first_ts.strftime("%Y-%m-%d") if first_ts else "",
                "last_active": last_ts.strftime("%Y-%m-%d") if last_ts else "",
            })

    project_summaries.sort(key=lambda x: x["questions"], reverse=True)
    print(json.dumps({
        "time_range": {"from": from_date or "all", "to": to_date or "now"},
        "projects": project_summaries,
        "total_questions": sum(p["questions"] for p in project_summaries),
        "total_sessions": sum(p["sessions"] for p in project_summaries),
    }, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Claude Code Chat History Analyzer")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list-projects", help="List available projects")

    ext = sub.add_parser("extract", help="Extract from one project")
    ext.add_argument("project", help="Project dir name or keyword")
    ext.add_argument("--from", dest="from_date")
    ext.add_argument("--to", dest="to_date")

    ea = sub.add_parser("extract-all", help="Summary across all projects")
    ea.add_argument("--from", dest="from_date")
    ea.add_argument("--to", dest="to_date")

    args = parser.parse_args()
    if args.command == "list-projects":
        list_projects()
    elif args.command == "extract":
        extract(args.project, args.from_date, args.to_date)
    elif args.command == "extract-all":
        extract_all(args.from_date, args.to_date)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
