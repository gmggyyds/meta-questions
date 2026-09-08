#!/usr/bin/env python3
"""从唯一真源生成全部取用物。

    source/meta_questions.yaml   ← 唯一真源，只改这里
            │
            ├─→ dist/quickstart.md              档 A 单文件速食（粘进任意 AI）
            ├─→ dist/staged/01..05 + profile    档 B 分段 + 持久记忆 + 报告出口
            ├─→ .claude/skills/meta-questions/  档 C Claude Code skill
            ├─→ dist/stage_script.md            现场 15-20 分钟讲稿骨架
            └─→ README.md                       仓库门面

两条不可退让的性质：
1. **幂等**：输出只依赖真源，不依赖构建当天的日期。否则 CI 没法用
   `git diff --exit-code` 守「dist 与真源同步」。
2. **题号锚定 id**：显示编号由 `q7` 推出 7，不由列表位置推。真源里的
   现场讲稿引用了 Q1/Q6/Q7/Q10，位置编号会让重排题目静默打乱台上讲的内容。
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source" / "meta_questions.yaml"
DIST = ROOT / "dist"
STAGED = DIST / "staged"
SKILL_DIR = ROOT / ".claude" / "skills" / "meta-questions"

BANNER = "<!-- 生成物，勿手改。改 source/meta_questions.yaml 后跑 `python3 build.py` -->"
REPORT_FILE = "05_report.md"

# 中日韩字符范围。测试从这里 import，别在两处各写一份（会不同步）。
CJK = "一-鿿　-〿＀-￯"

WANT_LABELS = {
    "number": "数字",
    "name": "人名",
    "date": "时间",
    "story": "一段具体经过",
    "choice": "二选一",
}


class SourceError(ValueError):
    """真源被改坏。带上是哪一条坏了——否则 12 道题同名字段一片，没法定位。"""


# ── 读取与校验 ──────────────────────────────────────────────
def load() -> dict:
    src = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    validate(src)
    return src


def validate(src: dict) -> None:
    """build.py 独立执行时也要校验——不能只靠 pytest，那样直接跑 build 的人裸奔。"""
    for key in ("version", "released_on", "name", "segments", "report", "probe",
                "instructions", "profile", "skill", "theory", "stage"):
        if key not in src:
            raise SourceError(f"真源缺顶层字段 `{key}`")

    nums = [s.get("n") for s in src["segments"]]
    if nums != list(range(1, len(nums) + 1)):
        raise SourceError(
            f"segments 的 n 必须是连续的 1..{len(nums)}，实际是 {nums}。"
            "断档会让『下一段』指针指向不存在的文件。"
        )

    seen: set[int] = set()
    for seg in src["segments"]:
        for field in ("id", "title_zh", "subtitle_zh", "anchor", "questions"):
            if not seg.get(field):
                raise SourceError(f"段 `{seg.get('id', '?')}` 缺字段 `{field}`")
        for q in seg["questions"]:
            qid = q.get("id", "?")
            for field in ("id", "zh", "en", "want", "why_zh"):
                if not q.get(field):
                    raise SourceError(f"问题 `{qid}`（段 {seg.get('id')}）缺字段 `{field}`")
            if not re.fullmatch(r"q\d+", qid):
                raise SourceError(f"问题 id 必须形如 q1/q2…，实际是 `{qid}`")
            n = qnum(q)
            if n in seen:
                raise SourceError(f"问题编号 {n} 重复（id `{qid}`）")
            seen.add(n)
            for w in q["want"]:
                if w not in WANT_LABELS:
                    raise SourceError(f"问题 `{qid}` 的 want 含未知类型 `{w}`")

    if seen != set(range(1, len(seen) + 1)):
        raise SourceError(f"问题编号必须是连续的 1..{len(seen)}，实际是 {sorted(seen)}")


def qnum(q: dict) -> int:
    """显示编号来自 id，不来自列表位置。"""
    return int(q["id"][1:])


def segments(src: dict) -> list[dict]:
    return sorted(src["segments"], key=lambda s: s["n"])


def unfold_cjk(text: str) -> str:
    """YAML 的 `>-` 折行会把中文换行折成空格，渲染出来像断句错误。

    只吃掉中文与中文之间的那个空格，中英混排的空格必须留着。
    """
    return re.sub(f"(?<=[{CJK}]) (?=[{CJK}])", "", text)


def file_footer(src: dict) -> str:
    return src["report"]["footer_template"].format(
        name=src["name"], version=src["version"], date=src["released_on"]
    )


def report_footer(src: dict) -> str:
    """报告页脚的日期由 AI 当场填——写死构建日期会让 2027 年跑出来的报告印 2026。"""
    return src["report"]["report_footer_template"].format(
        name=src["name"], version=src["version"]
    )


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return path


# ── 可复用片段 ──────────────────────────────────────────────
def _probe_block(src: dict) -> str:
    rounds = src["probe"]["max_rounds"]
    lines = ["## 追问规则（你必须遵守）", ""]
    lines += [f"{i}. {r.format(max_rounds=rounds)}"
              for i, r in enumerate(src["probe"]["rules_zh"], 1)]
    return "\n".join(lines)


def _report_block(src: dict, *, guard: bool) -> str:
    lines = ["## 全部问完之后，输出这份报告", ""]
    if guard:
        lines += [src["instructions"]["report_guard_zh"], ""]
    for sec in src["report"]["sections"]:
        lines += [
            f"### 第 {sec['n']} 节 · {sec['title_zh']}",
            f"- 形式：{sec['form_zh']}",
            f"- 内容：{sec['content_zh']}",
            "",
        ]
    lines += [f"报告页脚固定写：`{report_footer(src)}`"]
    return "\n".join(lines)


def _question_lines(src: dict, seg: dict) -> list[str]:
    prefix = src["instructions"]["probe_hint_prefix_zh"]
    lines: list[str] = []
    for q in seg["questions"]:
        wants = "／".join(WANT_LABELS[w] for w in q["want"])
        lines += [
            f"**Q{qnum(q)}. {q['zh']}**",
            "",
            f"> *{q['why_zh']}*",
            "",
            f"> 需要的证据：{wants}",
            "",
        ]
        if q.get("probe_zh"):
            lines += [f"> {prefix} 追问条件：{q['probe_zh']}", ""]
    return lines


def _all_segments_block(src: dict) -> list[str]:
    out: list[str] = []
    for seg in segments(src):
        out += [f"### 第 {seg['n']} 段 · {seg['title_zh']}（{seg['subtitle_zh']}）", ""]
        out += _question_lines(src, seg)
    return out


# ── 档 A：单文件速食 ────────────────────────────────────────
def build_quickstart(src: dict) -> Path:
    ins = src["instructions"]
    out = [
        BANNER,
        f"# 元问题 · 单文件版 v{src['version']}",
        "",
        f"> {src['tagline_zh']}",
        "",
        "**怎么用**：",
        *[f"{i}. {s}" for i, s in enumerate(ins["usage_quickstart_zh"], 1)],
        "",
        "---",
        "",
        "## 你的角色",
        "",
        unfold_cjk(src["premise_zh"]),
        "",
        ins["role_zh"],
        "",
        ins["start_command_zh"],
        "",
        _probe_block(src),
        "",
        "---",
        "",
        "## 要问的问题（按顺序，一次一个）",
        "",
        *_all_segments_block(src),
        "---",
        "",
        _report_block(src, guard=True),
        "",
        "---",
        "",
        f"<sub>{file_footer(src)}</sub>",
    ]
    return write(DIST / "quickstart.md", "\n".join(out))


# ── 档 B：分段 + profile.md 记忆 + 报告出口 ─────────────────
def _profile_template(src: dict) -> str:
    prof = src["profile"]
    out = [
        BANNER,
        f"# profile.md — 我的元问题档案（模板 v{src['version']}）",
        "",
        *[f"> {line}" for line in prof["intro_zh"]],
        "",
        "## 基本",
        *[f"- {f}" for f in prof["basic_fields_zh"]],
        "",
    ]
    # 预置各段小节标题：AI 有地方可填，才不会一路追加到页脚后面
    for seg in segments(src):
        out += [f"## {seg['title_zh']}（待填）", ""]
    out += ["## 变更记录", "- <你开始的日期> 建档（模板 v" + src["version"] + "）", "",
            f"<sub>{file_footer(src)}</sub>"]
    return "\n".join(out)


def _staged_one(src: dict, seg: dict, nxt_label: str) -> Path:
    ins, prof = src["instructions"], src["profile"]
    usage = ins["usage_staged_first_zh"] if seg["n"] == 1 else ins["usage_staged_rest_zh"]
    out = [
        BANNER,
        f"# 第 {seg['n']} 段 · {seg['title_zh']} — v{src['version']}",
        "",
        f"> {seg['subtitle_zh']} ｜ 理论根：{seg['anchor']}",
        "",
        "## 怎么用",
        "",
        *[f"{i}. {s}" for i, s in enumerate(usage, 1)],
        f"{len(usage) + 1}. 答完本段后，让 AI 把结论写进 `profile.md`，然后再开{nxt_label}。",
        "",
        "## 你的角色",
        "",
        ins["role_staged_zh"],
        "",
        ins["start_command_zh"],
        "",
        _probe_block(src),
        "",
        "---",
        "",
        "## 本段的问题",
        "",
        *_question_lines(src, seg),
        "---",
        "",
        "## 本段结束后，写进 profile.md",
        "",
        prof["append_instruction_zh"],
        "",
        "```markdown",
        f"## {seg['title_zh']}",
        *prof["section_body_zh"],
        "```",
        "",
        f"<sub>{file_footer(src)}</sub>",
    ]
    return write(STAGED / f"{seg['n']:02d}_{seg['id']}.md", "\n".join(out))


def _staged_report(src: dict) -> Path:
    """档 B 的终点。没有它，认真做完四段的人走到最后一步没有文件可开。"""
    out = [
        BANNER,
        f"# 最后一步 · 生成报告 — v{src['version']}",
        "",
        "> 四段都答完了。这一步把 `profile.md` 变成一份可以拿去做决定的报告。",
        "",
        "## 怎么用",
        "",
        "1. 开一个新对话。",
        "2. 先把你的 `profile.md` 全文粘给 AI。",
        "3. 再把本文件粘给 AI。",
        "4. 把它输出的内容存成 `report.md`。",
        "",
        "## 你的角色",
        "",
        "你拿到的 `profile.md` 是这个人四段问答的全部证据。只用里面有的东西，"
        "不要补充、不要美化、不要替他编他没说过的资源和人。",
        "标着「证据不足」的项，在报告里如实写「证据不足」。",
        "",
        "---",
        "",
        _report_block(src, guard=False),
        "",
        f"<sub>{file_footer(src)}</sub>",
    ]
    return write(STAGED / REPORT_FILE, "\n".join(out))


def build_staged(src: dict) -> list[Path]:
    # 先清空：否则改了段号会留下旧文件，用户拿到两份重复的同一段
    if STAGED.exists():
        shutil.rmtree(STAGED)
    segs = segments(src)
    written = []
    for i, seg in enumerate(segs):
        if i + 1 < len(segs):
            n2 = segs[i + 1]
            nxt = f"第 {n2['n']} 段（`{n2['n']:02d}_{n2['id']}.md`）"
        else:
            nxt = f"最后一步生成报告（`{REPORT_FILE}`）"
        written.append(_staged_one(src, seg, nxt))
    written.append(_staged_report(src))
    written.append(write(STAGED / "profile.template.md", _profile_template(src)))
    return written


# ── 档 C：Claude Code skill ────────────────────────────────
def build_skill(src: dict) -> Path:
    qcount = sum(len(s["questions"]) for s in src["segments"])
    desc = src["skill"]["description_template_zh"].format(qcount=qcount)
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
        *[f"{i}. {s}" for i, s in enumerate(src["skill"]["steps_zh"], 1)],
        "",
        src["instructions"]["start_command_zh"],
        "",
        _probe_block(src),
        "",
        "## 问题清单",
        "",
        *_all_segments_block(src),
        "---",
        "",
        _report_block(src, guard=True),
        "",
        "---",
        "",
        "## profile.md 模板",
        "",
        "```markdown",
        _profile_template(src).replace(BANNER + "\n", ""),
        "```",
        "",
        f"<sub>{file_footer(src)}</sub>",
    ]
    return write(SKILL_DIR / "SKILL.md", "\n".join(out))


# ── 现场讲稿骨架 ───────────────────────────────────────────
def build_stage_script(src: dict) -> Path:
    st = src["stage"]
    by_num = {qnum(q): q for s in src["segments"] for q in s["questions"]}
    cited = sorted({int(m) for m in re.findall(r"Q(\d+)", " ".join(st["plan_zh"]))})
    out = [
        BANNER,
        f"# 现场讲稿骨架 · {st['duration_min']}–{st['max_duration_min']} 分钟 — v{src['version']}",
        "",
        "## 流程",
        "",
        *[f"{i}. {s}" for i, s in enumerate(st["plan_zh"], 1)],
        "",
        f"**互动**：{st['interaction_zh']}",
        "",
        "## 台上要念的题（由讲稿引用的 Q 号从真源现取，不手抄）",
        "",
    ]
    for n in cited:
        q = by_num[n]
        out += [f"**Q{n}.** {q['zh']}", "", f"> *{q['why_zh']}*", ""]
    out += [f"<sub>{file_footer(src)}</sub>"]
    return write(DIST / "stage_script.md", "\n".join(out))


# ── README ─────────────────────────────────────────────────
def build_readme(src: dict) -> Path:
    qcount = sum(len(s["questions"]) for s in src["segments"])
    secs = src["report"]["sections"]
    theory_rows = "\n".join(
        f"| {t['dim_zh']} | {t['theory']} | {t['who']} | [链接]({t['url']}) |" for t in src["theory"]
    )
    seg_rows = "\n".join(
        f"| {s['n']} | {s['title_zh']} / {s['title_en']} | {s['subtitle_zh']} | "
        f"{len(s['questions'])} | {s['anchor']} |"
        for s in segments(src)
    )
    # 章节名从真源现算，不硬编码——否则改了真源标题，README 会静默说谎
    sec_names = "、".join(s["title_zh"] for s in secs)
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

```bash
git clone <this repo> && cd {src['name']}
```
复制 [`dist/quickstart.md`](dist/quickstart.md) 全文 → 粘进 ChatGPT / Claude / Coze / 豆包 → 发送 → 老实回答。

## 你会拿到什么

一份 {len(secs)} 节的报告：{sec_names}。

最后一节叫**「{secs[-1]['title_zh']}」**——这是整套东西存在的理由。
一个好的元问题，判据不是 AI 答得多漂亮，是你答完之后**自己冒出了新问题**。

## 理论根

这不是拍脑袋想出来的三个维度。

| 维度 | 理论 | 出处 | 链接 |
|---|---|---|---|
{theory_rows}

## 改它

真源只有一个：[`source/meta_questions.yaml`](source/meta_questions.yaml)。

```bash
pip install -r requirements.txt

# 改完真源后重生成
python3 build.py

# 跑测试
python3 -m pytest tests/ -q
```

`dist/`、`README.md`、`.claude/skills/` 全是生成物，**手改会被下次 build 抹掉**，
CI 也会因为 `git diff` 不干净而失败。

## 一个提醒

你复制走的是**快照**。每个生成物页脚都印着版本号（当前 `v{src['version']}`），
报告页脚也会印。哪天报告出得不对，先看版本号——那是唯一能归因的东西。

## License

MIT

---

<sub>{file_footer(src)}</sub>
"""
    return write(ROOT / "README.md", out)


def main() -> None:
    src = load()
    made = [
        build_quickstart(src),
        *build_staged(src),
        build_skill(src),
        build_stage_script(src),
        build_readme(src),
    ]
    print(f"built {src['name']} v{src['version']} ({src['released_on']}) → {len(made)} files")
    for p in made:
        print(f"  {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
