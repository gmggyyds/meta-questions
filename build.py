#!/usr/bin/env python3
"""从唯一真源生成三档取用物。

    source/meta_questions.yaml   ← 唯一真源，只改这里
            │
            ├─→ dist/quickstart.md              档 A 单文件速食（粘进任意 AI）
            ├─→ dist/staged/*.md + profile      档 B 分段 + 持久记忆
            ├─→ .claude/skills/meta-questions/  档 C Claude Code skill
            └─→ README.md                       仓库门面

生成物一律带版本号：用户复制走的是快照，没有版本号就无法归因。
"""
from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source" / "meta_questions.yaml"
DIST = ROOT / "dist"
SKILL_DIR = ROOT / ".claude" / "skills" / "meta-questions"

BANNER = "<!-- 生成物，勿手改。改 source/meta_questions.yaml 后跑 `python3 build.py` -->"


def load() -> dict:
    return yaml.safe_load(SOURCE.read_text(encoding="utf-8"))


_CJK = "\u4e00-\u9fff\u3000-\u303f\uff00-\uffef"


def unfold_cjk(text: str) -> str:
    """YAML 的 `>-` 折行会把中文换行折成空格，渲染出来像断句错误。

    只吃掉中文与中文之间的那个空格，中英混排的空格必须留着。
    """
    return re.sub(f"(?<=[{_CJK}]) (?=[{_CJK}])", "", text)


def stamp(src: dict) -> str:
    return src["report"]["footer_template"].format(
        name=src["name"], version=src["version"], date=_dt.date.today().isoformat()
    )


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return path


# ── 可复用片段 ──────────────────────────────────────────────
def _probe_block(src: dict) -> str:
    lines = ["## 追问规则（你必须遵守）", ""]
    lines += [f"{i}. {r}" for i, r in enumerate(src["probe"]["rules_zh"], 1)]
    lines += ["", f"追问上限：{src['probe']['max_rounds']} 次。"]
    return "\n".join(lines)


def _report_block(src: dict) -> str:
    lines = ["## 全部问完之后，输出这份报告", ""]
    for sec in src["report"]["sections"]:
        lines += [
            f"### 第 {sec['n']} 节 · {sec['title_zh']}",
            f"- 形式：{sec['form_zh']}",
            f"- 内容：{sec['content_zh']}",
            "",
        ]
    lines += [f"报告页脚固定写：`{stamp(src)}`"]
    return "\n".join(lines)


def _question_lines(seg: dict, numbered_from: int) -> tuple[list[str], int]:
    lines, n = [], numbered_from
    for q in seg["questions"]:
        lines += [f"**{n}. {q['zh']}**", "", f"> *{q['why_zh']}*", ""]
        if q.get("probe_zh"):
            lines += [f"> 追问：{q['probe_zh']}", ""]
        n += 1
    return lines, n


# ── 档 A：单文件速食 ────────────────────────────────────────
def build_quickstart(src: dict) -> Path:
    out = [
        BANNER,
        f"# 元问题 · 单文件版 v{src['version']}",
        "",
        f"> {src['tagline_zh']}",
        "",
        "**怎么用**：把这一整个文件复制，粘进 ChatGPT / Claude / Coze / 豆包 / 任意 AI 的对话框，发送。",
        "然后它会开始一个一个问你。老实答，别偷懒——报告的质量完全取决于你答得有多具体。",
        "",
        "---",
        "",
        "## 你的角色",
        "",
        unfold_cjk(src["premise_zh"]),
        "",
        "你是一个只负责取证的提问者。你要按下面的顺序，一次一个地问我问题；",
        "全部问完之前，不要给任何建议、不要总结、不要夸我。",
        "",
        _probe_block(src),
        "",
        "---",
        "",
        "## 要问的问题（按顺序，一次一个）",
        "",
    ]
    n = 1
    for seg in src["segments"]:
        out += [f"### 第 {seg['n']} 段 · {seg['title_zh']}（{seg['subtitle_zh']}）", ""]
        qlines, n = _question_lines(seg, n)
        out += qlines
    out += ["---", "", _report_block(src), "", "---", "", f"<sub>{stamp(src)}</sub>"]
    return write(DIST / "quickstart.md", "\n".join(out))


# ── 档 B：分段 + profile.md 记忆 ────────────────────────────
def build_staged(src: dict) -> list[Path]:
    written = []
    total = len(src["segments"])
    n = 1
    for seg in src["segments"]:
        nxt = (
            f"第 {seg['n'] + 1} 段（`{seg['n'] + 1:02d}_*.md`）"
            if seg["n"] < total
            else "报告生成（`report.md`）"
        )
        out = [
            BANNER,
            f"# 第 {seg['n']} 段 · {seg['title_zh']} — v{src['version']}",
            "",
            f"> {seg['subtitle_zh']} ｜ 理论根：{seg['anchor']}",
            "",
            "## 怎么用",
            "",
            "1. 如果你已经有 `profile.md`，先把它粘给 AI，说「这是我，我们继续」。",
            "2. 再把本文件粘给 AI。",
            f"3. 答完本段后，让 AI 把结论追加写进 `profile.md`，然后再开{nxt}。",
            "",
            "## 你的角色",
            "",
            "你是一个只负责取证的提问者。一次问一个问题，等我答完再问下一个。",
            "本段问完之前，不要给建议、不要总结、不要夸我。",
            "",
            _probe_block(src),
            "",
            "---",
            "",
            "## 本段的问题",
            "",
        ]
        qlines, n = _question_lines(seg, n)
        out += qlines
        out += [
            "---",
            "",
            "## 本段结束后，追加进 profile.md",
            "",
            "```markdown",
            f"## {seg['title_zh']}（v{src['version']} · 第 {seg['n']} 段）",
            "- 结论：<一句话>",
            "- 证据：<我给出的具体数字／名字／时间，原样抄录，不要改写>",
            "- 证据不足项：<追问 2 次仍没拿到的，列出来>",
            "```",
            "",
            f"<sub>{stamp(src)}</sub>",
        ]
        written.append(write(DIST / "staged" / f"{seg['n']:02d}_{seg['id']}.md", "\n".join(out)))

    tpl = [
        BANNER,
        f"# profile.md — 我的元问题档案（模板 v{src['version']}）",
        "",
        "> 这份文件存在你自己的电脑上，不上传任何地方。",
        "> 下次开一个新对话，把它粘给 AI 说「这是我，我们继续」，它就接得上。",
        "",
        "## 基本",
        "- 我现在做的事：",
        "- 开始日期：",
        "",
        "## 各段结论（由 AI 逐段追加）",
        "",
        "<!-- 第 1-4 段的结论按顺序追加到这里 -->",
        "",
        "## 变更记录",
        f"- {_dt.date.today().isoformat()} 建档（模板 v{src['version']}）",
        "",
        f"<sub>{stamp(src)}</sub>",
    ]
    written.append(write(DIST / "staged" / "profile.template.md", "\n".join(tpl)))
    return written


# ── 档 C：Claude Code skill ────────────────────────────────
def build_skill(src: dict) -> Path:
    desc = (
        "用 12 个元问题摸清用户的优势、资源与关系网，产出一份 AI Native 方向分析报告。"
        "触发词：元问题 / meta questions / 帮我盘一下我有什么 / 我该怎么用 AI / AI Native 诊断。"
    )
    out = [
        "---",
        "name: meta-questions",
        f"description: {desc}",
        f"version: {src['version']}",
        "---",
        "",
        BANNER,
        f"# 元问题 · Claude Code skill v{src['version']}",
        "",
        unfold_cjk(src["premise_zh"]),
        "",
        "## 执行步骤",
        "",
        "1. 先看当前目录有没有 `profile.md`。有 → 读它，跟用户确认「我记得你是…，对吗？」；没有 → 从模板新建。",
        "2. 按四段顺序提问，**一次一个**。每段结束把结论追加写进 `profile.md`。",
        "3. 四段问完 → 按报告模板生成 `report.md`。",
        "4. 第 7 节「海外对标」需要联网：**每条必须带 URL**，找不到就写「未找到」。禁止编造公司名、融资额或数据。",
        "",
        _probe_block(src),
        "",
        "## 问题清单",
        "",
    ]
    n = 1
    for seg in src["segments"]:
        out += [f"### 第 {seg['n']} 段 · {seg['title_zh']}（{seg['subtitle_zh']}）", ""]
        qlines, n = _question_lines(seg, n)
        out += qlines
    out += ["---", "", _report_block(src), "", f"<sub>{stamp(src)}</sub>"]
    return write(SKILL_DIR / "SKILL.md", "\n".join(out))


# ── README ─────────────────────────────────────────────────
def build_readme(src: dict) -> Path:
    qcount = sum(len(s["questions"]) for s in src["segments"])
    theory_rows = "\n".join(
        f"| {t['dim_zh']} | {t['theory']} | {t['who']} | [链接]({t['url']}) |" for t in src["theory"]
    )
    seg_rows = "\n".join(
        f"| {s['n']} | {s['title_zh']} / {s['title_en']} | {s['subtitle_zh']} | {len(s['questions'])} | {s['anchor']} |"
        for s in src["segments"]
    )
    out = f"""{BANNER}
# {src['name']} · 元问题

> {src['tagline_zh']}
> *{src['tagline_en']}*

**v{src['version']}** ｜ <!--COUNT:questions-->{qcount}<!--/COUNT--> 个问题 · {len(src['segments'])} 段 · 三档取用

{unfold_cjk(src['premise_zh'])}

---

## 为什么是这些问题

大多数人问 AI 的方式是「帮我做 X」。真正的瓶颈从来不在提示词技巧，
在于**你没说清楚自己手上有什么**。AI 不知道你的优势、你攒了三年的数据、
你认识那个能替你开门的人——它只能给你正确的废话。

这套元问题不产出答案，它产出**你自己的底牌清单**。答完之后，
「该问 AI 什么」这件事会自己浮出来。

## 四段结构

| # | 段 | 关注 | 题数 | 理论根 |
|---|---|---|---|---|
{seg_rows}

## 三档取用

| 档 | 文件 | 给谁 | 有记忆吗 |
|---|---|---|---|
| A 单文件速食 | [`dist/quickstart.md`](dist/quickstart.md) | 所有人。复制粘贴进任意 AI 就跑 | ❌ |
| B 分段 + 记忆 | [`dist/staged/`](dist/staged/) | 想认真做一遍的人。`profile.md` 存你自己电脑上 | ✅ |
| C Claude Code skill | [`.claude/skills/meta-questions/`](.claude/skills/meta-questions/) | Claude Code 用户。能读写文件、能联网找对标 | ✅ |

### 最快的用法

复制 [`dist/quickstart.md`](dist/quickstart.md) 全文 → 粘进 ChatGPT / Claude / Coze / 豆包 → 发送 → 老实回答。

## 你会拿到什么

一份 {len(src['report']['sections'])} 节的报告：从你的画像、不公平优势（VRIO 四格）、躺着没用的资源，
到杠杆缺口、AI Native 判定（重做 vs 提效）、下周能开始的三个动作、海外对标。

最后一节叫**「你还没回答的问题」**——这是整套东西存在的理由。
一个好的元问题，判据不是 AI 答得多漂亮，是你答完之后**自己冒出了新问题**。

## 理论根

这不是拍脑袋想出来的三个维度。

| 维度 | 理论 | 出处 | 链接 |
|---|---|---|---|
{theory_rows}

## 改它

真源只有一个：[`source/meta_questions.yaml`](source/meta_questions.yaml)。

```bash
# 改完真源后重生成三档
python3 build.py

# 跑测试
python3 -m pytest tests/ -q
```

`dist/`、`README.md`、`.claude/skills/` 全是生成物，**手改会被下次 build 抹掉**。

## 一个提醒

你复制走的是**快照**。每个生成物页脚都印着版本号（当前 `v{src['version']}`），
报告页脚也会印。哪天报告出得不对，先看版本号——那是唯一能归因的东西。

## License

MIT

---

<sub>{stamp(src)}</sub>
"""
    return write(ROOT / "README.md", out)


def main() -> None:
    src = load()
    made = [build_quickstart(src), *build_staged(src), build_skill(src), build_readme(src)]
    print(f"built {src['name']} v{src['version']} → {len(made)} files")
    for p in made:
        print(f"  {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
