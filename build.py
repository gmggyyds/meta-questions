#!/usr/bin/env python3
"""从唯一真源生成全部取用物（中英双语）。

    source/meta_questions.yaml   ← 唯一真源，只改这里
            │
            ├─→ dist/          中文：quickstart / staged / stage_script
            ├─→ dist/en/       English: quickstart / staged
            ├─→ .claude/skills/meta-questions[-en]/
            └─→ README.md / README.en.md

三条不可退让的性质：
1. **幂等**：输出只依赖真源，不依赖构建当天的日期。否则 CI 没法用
   `git diff --exit-code` 守「dist 与真源同步」。
2. **题号锚定 id**：显示编号由 `q7` 推出 7，不由列表位置推。真源里的现场讲稿
   引用了 Q1/Q6/Q7/Q10，位置编号会让重排题目静默打乱台上讲的内容。
3. **零硬编码文案**：所有面向读者的字句都在真源里（`ui` / `instructions` /
   `profile` / `skill`）。build.py 里出现中文字面量，就是第二真源。
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source" / "meta_questions.yaml"
DIST = ROOT / "dist"
SKILLS = ROOT / ".claude" / "skills"

BANNER = "<!-- 生成物，勿手改。改 source/meta_questions.yaml 后跑 `python3 build.py` -->"
REPORT_FILE = "05_report.md"
LANGS = ("zh", "en")

# 中日韩字符范围。测试从这里 import，别在两处各写一份（会不同步）。
CJK = "一-鿿　-〿＀-￯"


class SourceError(ValueError):
    """真源被改坏。带上是哪一条坏了——否则 12 道题同名字段一片，没法定位。"""


# ── 语言无关的取值 ──────────────────────────────────────────
def tr(obj: dict, key: str, lang: str):
    """取 `key_<lang>`，缺英文时退回中文（部署优于完美，但会被测试点名）。"""
    return obj.get(f"{key}_{lang}") or obj[f"{key}_zh"]


def ui(src: dict, lang: str) -> dict:
    return src["ui"][lang]


def qnum(q: dict) -> int:
    """显示编号来自 id，不来自列表位置。"""
    return int(q["id"][1:])


def segments(src: dict) -> list[dict]:
    return sorted(src["segments"], key=lambda s: s["n"])


def dist_dir(lang: str) -> Path:
    return DIST if lang == "zh" else DIST / lang


def staged_dir(lang: str) -> Path:
    return dist_dir(lang) / "staged"


def skill_dir(lang: str) -> Path:
    return SKILLS / ("meta-questions" if lang == "zh" else f"meta-questions-{lang}")


def readme_path(lang: str) -> Path:
    return ROOT / ("README.md" if lang == "zh" else f"README.{lang}.md")


# ── 读取与校验 ──────────────────────────────────────────────
def load() -> dict:
    src = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    validate(src)
    return src


def validate(src: dict) -> None:
    """build.py 独立执行时也要校验——不能只靠 pytest，那样直接跑 build 的人裸奔。"""
    for key in ("version", "released_on", "name", "segments", "report", "probe",
                "instructions", "profile", "skill", "theory", "stage", "ui"):
        if key not in src:
            raise SourceError(f"真源缺顶层字段 `{key}`")

    for lang in LANGS:
        if lang not in src["ui"]:
            raise SourceError(f"ui 块缺语言 `{lang}`")
    if set(src["ui"]["zh"]) != set(src["ui"]["en"]):
        diff = set(src["ui"]["zh"]) ^ set(src["ui"]["en"])
        raise SourceError(f"ui 中英键不对齐，差异: {sorted(diff)}")
    want_keys = set(src["ui"]["zh"]["want_labels"])
    if want_keys != set(src["ui"]["en"]["want_labels"]):
        raise SourceError("want_labels 中英键不对齐")

    nums = [s.get("n") for s in src["segments"]]
    if nums != list(range(1, len(nums) + 1)):
        raise SourceError(
            f"segments 的 n 必须是连续的 1..{len(nums)}，实际是 {nums}。"
            "断档会让『下一段』指针指向不存在的文件。"
        )

    seen: set[int] = set()
    for seg in src["segments"]:
        for field in ("id", "title_zh", "title_en", "subtitle_zh", "anchor", "questions"):
            if not seg.get(field):
                raise SourceError(f"段 `{seg.get('id', '?')}` 缺字段 `{field}`")
        for q in seg["questions"]:
            qid = q.get("id", "?")
            for field in ("id", "zh", "en", "want", "why_zh", "why_en"):
                if not q.get(field):
                    raise SourceError(f"问题 `{qid}`（段 {seg.get('id')}）缺字段 `{field}`")
            if not re.fullmatch(r"q\d+", qid):
                raise SourceError(f"问题 id 必须形如 q1/q2…，实际是 `{qid}`")
            if q.get("probe_zh") and not q.get("probe_en"):
                raise SourceError(f"问题 `{qid}` 有 probe_zh 却没有 probe_en")
            n = qnum(q)
            if n in seen:
                raise SourceError(f"问题编号 {n} 重复（id `{qid}`）")
            seen.add(n)
            for w in q["want"]:
                if w not in want_keys:
                    raise SourceError(f"问题 `{qid}` 的 want 含未知类型 `{w}`")

    if seen != set(range(1, len(seen) + 1)):
        raise SourceError(f"问题编号必须是连续的 1..{len(seen)}，实际是 {sorted(seen)}")

    for sec in src["report"]["sections"]:
        for field in ("title_zh", "title_en", "form_zh", "form_en", "content_zh", "content_en"):
            if not sec.get(field):
                raise SourceError(f"报告第 {sec.get('n', '?')} 节缺字段 `{field}`")


def unfold_cjk(text: str) -> str:
    """YAML 的 `>-` 折行会把中文换行折成空格，渲染出来像断句错误。

    只吃掉中文与中文之间的那个空格，中英混排的空格必须留着。
    """
    return re.sub(f"(?<=[{CJK}]) (?=[{CJK}])", "", text)


def file_footer(src: dict) -> str:
    return src["report"]["footer_template"].format(
        name=src["name"], version=src["version"], date=src["released_on"]
    )


def report_footer(src: dict, lang: str) -> str:
    """报告页脚的日期由 AI 当场填——写死构建日期会让 2027 年跑出来的报告印 2026。"""
    return src["report"]["footer_template"].format(
        name=src["name"], version=src["version"],
        date=ui(src, lang)["report_date_placeholder"],
    )


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return path


def numbered(items) -> list[str]:
    return [f"{i}. {s}" for i, s in enumerate(items, 1)]


# ── 可复用片段 ──────────────────────────────────────────────
def _probe_block(src: dict, lang: str) -> str:
    rounds = src["probe"]["max_rounds"]
    rules = tr(src["probe"], "rules", lang)
    return "\n".join([f"## {ui(src, lang)['probe_rules']}", ""]
                     + numbered(r.format(max_rounds=rounds) for r in rules))


def _report_block(src: dict, lang: str, *, guard: bool) -> str:
    u = ui(src, lang)
    lines = [f"## {u['report_heading']}", ""]
    if guard:
        lines += [tr(src["instructions"], "report_guard", lang), ""]
    for sec in src["report"]["sections"]:
        lines += [
            f"### {u['report_section'].format(n=sec['n'], title=tr(sec, 'title', lang))}",
            f"- {u['form_label']}: {tr(sec, 'form', lang)}",
            f"- {u['content_label']}: {unfold_cjk(tr(sec, 'content', lang))}",
            "",
        ]
    return "\n".join(lines + [f"{u['footer_instruction']}: `{report_footer(src, lang)}`"])


def _question_lines(src: dict, seg: dict, lang: str) -> list[str]:
    u = ui(src, lang)
    prefix = tr(src["instructions"], "probe_hint_prefix", lang)
    lines: list[str] = []
    for q in seg["questions"]:
        wants = u["want_join"].join(u["want_labels"][w] for w in q["want"])
        text = q["zh"] if lang == "zh" else q["en"]
        lines += [
            f"**Q{qnum(q)}. {text}**", "",
            f"> *{unfold_cjk(tr(q, 'why', lang))}*", "",
            f"> {u['evidence_needed']}: {wants}", "",
        ]
        if q.get("probe_zh"):
            lines += [f"> {prefix} {u['probe_condition']}: {tr(q, 'probe', lang)}", ""]
    return lines


def _all_segments_block(src: dict, lang: str) -> list[str]:
    u = ui(src, lang)
    out: list[str] = []
    for seg in segments(src):
        out += [f"### {u['segment_label'].format(n=seg['n'], title=tr(seg, 'title', lang), subtitle=tr(seg, 'subtitle', lang))}", ""]
        out += _question_lines(src, seg, lang)
    return out


# ── 档 A：单文件速食 ────────────────────────────────────────
def build_quickstart(src: dict, lang: str) -> Path:
    u, ins = ui(src, lang), src["instructions"]
    out = [
        BANNER,
        f"# {u['quickstart_title']} v{src['version']}",
        "",
        f"> {tr(src, 'tagline', lang)}",
        "",
        f"**{u['how_to_use']}**",
        "",
        *numbered(tr(ins, "usage_quickstart", lang)),
        "",
        "---",
        "",
        f"## {u['your_role']}",
        "",
        unfold_cjk(tr(src, "premise", lang)),
        "",
        tr(ins, "role", lang),
        "",
        tr(ins, "start_command", lang),
        "",
        _probe_block(src, lang),
        "",
        "---",
        "",
        f"## {u['questions_heading']}",
        "",
        *_all_segments_block(src, lang),
        "---",
        "",
        _report_block(src, lang, guard=True),
        "",
        "---",
        "",
        f"<sub>{file_footer(src)}</sub>",
    ]
    return write(dist_dir(lang) / "quickstart.md", "\n".join(out))


# ── 档 B：分段 + profile.md 记忆 + 报告出口 ─────────────────
def _profile_template(src: dict, lang: str) -> str:
    u, prof = ui(src, lang), src["profile"]
    out = [
        BANNER,
        f"# {u['profile_title'].format(version='v' + src['version'])}",
        "",
        *[f"> {line}" for line in tr(prof, "intro", lang)],
        "",
        f"## {u['basics']}",
        *[f"- {f}" for f in tr(prof, "basic_fields", lang)],
        "",
    ]
    # 预置各段小节标题：AI 有地方可填，才不会一路追加到页脚后面
    for seg in segments(src):
        out += [f"## {tr(seg, 'title', lang)}{u['pending_suffix']}", ""]
    out += [f"## {u['changelog']}",
            u["changelog_line"].format(version="v" + src["version"]), "",
            f"<sub>{file_footer(src)}</sub>"]
    return "\n".join(out)


def _staged_one(src: dict, seg: dict, lang: str, nxt_label: str) -> Path:
    u, ins, prof = ui(src, lang), src["instructions"], src["profile"]
    usage = tr(ins, "usage_staged_first" if seg["n"] == 1 else "usage_staged_rest", lang)
    steps = list(usage) + [u["next_step"].format(nxt=nxt_label)]
    out = [
        BANNER,
        f"# {u['staged_title'].format(n=seg['n'], title=tr(seg, 'title', lang))} — v{src['version']}",
        "",
        f"> {u['theory_line'].format(subtitle=tr(seg, 'subtitle', lang), anchor=seg['anchor'])}",
        "",
        f"## {u['how_to_use']}",
        "",
        *numbered(steps),
        "",
        f"## {u['your_role']}",
        "",
        tr(ins, "role_staged", lang),
        "",
        tr(ins, "start_command", lang),
        "",
        _probe_block(src, lang),
        "",
        "---",
        "",
        f"## {u['section_questions']}",
        "",
        *_question_lines(src, seg, lang),
        "---",
        "",
        f"## {u['write_to_profile']}",
        "",
        tr(prof, "append_instruction", lang),
        "",
        "```markdown",
        f"## {tr(seg, 'title', lang)}",
        *tr(prof, "section_body", lang),
        "```",
        "",
        f"<sub>{file_footer(src)}</sub>",
    ]
    return write(staged_dir(lang) / f"{seg['n']:02d}_{seg['id']}.md", "\n".join(out))


def _staged_report(src: dict, lang: str) -> Path:
    """档 B 的终点。没有它，认真做完四段的人走到最后一步没有文件可开。"""
    u = ui(src, lang)
    out = [
        BANNER,
        f"# {u['report_step_title']} — v{src['version']}",
        "",
        f"> {u['report_step_intro']}",
        "",
        f"## {u['how_to_use']}",
        "",
        *numbered(u["report_step_usage"]),
        "",
        f"## {u['your_role']}",
        "",
        unfold_cjk(u["report_step_role"]),
        "",
        "---",
        "",
        _report_block(src, lang, guard=False),
        "",
        f"<sub>{file_footer(src)}</sub>",
    ]
    return write(staged_dir(lang) / REPORT_FILE, "\n".join(out))


def build_staged(src: dict, lang: str) -> list[Path]:
    # 先清空：否则改了段号会留下旧文件，用户拿到两份重复的同一段
    d = staged_dir(lang)
    if d.exists():
        shutil.rmtree(d)
    u, segs = ui(src, lang), segments(src)
    written = []
    for i, seg in enumerate(segs):
        if i + 1 < len(segs):
            n2 = segs[i + 1]
            nxt = u["next_segment"].format(n=n2["n"], file=f"{n2['n']:02d}_{n2['id']}.md")
        else:
            nxt = u["next_report"].format(file=REPORT_FILE)
        written.append(_staged_one(src, seg, lang, nxt))
    written.append(_staged_report(src, lang))
    written.append(write(d / "profile.template.md", _profile_template(src, lang)))
    return written


# ── 档 C：Claude Code skill ────────────────────────────────
def build_skill(src: dict, lang: str) -> Path:
    u = ui(src, lang)
    qcount = sum(len(s["questions"]) for s in src["segments"])
    desc = tr(src["skill"], "description_template", lang).format(qcount=qcount)
    # frontmatter 必须用 yaml 序列化：英文 description 里的 "Triggers:" 会让
    # 手拼的 `description: ...` 直接解析失败（中文版用全角冒号所以躲过了）
    front = yaml.safe_dump(
        {"name": skill_dir(lang).name, "description": desc, "version": src["version"]},
        allow_unicode=True, sort_keys=False, width=10 ** 6,
    ).rstrip()
    out = [
        "---",
        front,
        "---",
        "",
        BANNER,
        f"# {u['skill_title']} v{src['version']}",
        "",
        unfold_cjk(tr(src, "premise", lang)),
        "",
        f"## {u['execution_steps']}",
        "",
        *numbered(tr(src["skill"], "steps", lang)),
        "",
        tr(src["instructions"], "start_command", lang),
        "",
        _probe_block(src, lang),
        "",
        f"## {u['questions_heading']}",
        "",
        *_all_segments_block(src, lang),
        "---",
        "",
        _report_block(src, lang, guard=True),
        "",
        "---",
        "",
        f"## {u['profile_template_heading']}",
        "",
        "```markdown",
        _profile_template(src, lang).replace(BANNER + "\n", ""),
        "```",
        "",
        f"<sub>{file_footer(src)}</sub>",
    ]
    return write(skill_dir(lang) / "SKILL.md", "\n".join(out))


# ── 现场讲稿骨架（只出中文，它是给 Sam 台上用的）──────────
def build_stage_script(src: dict) -> Path:
    st, u = src["stage"], ui(src, "zh")
    by_num = {qnum(q): q for s in src["segments"] for q in s["questions"]}
    cited = sorted({int(m) for m in re.findall(r"Q(\d+)", " ".join(st["plan_zh"]))})
    out = [
        BANNER,
        f"# 现场讲稿骨架 · {st['duration_min']}–{st['max_duration_min']} 分钟 — v{src['version']}",
        "",
        "## 流程",
        "",
        *numbered(st["plan_zh"]),
        "",
        f"**互动**：{st['interaction_zh']}",
        "",
        "## 台上要念的题（由讲稿引用的 Q 号从真源现取，不手抄）",
        "",
    ]
    for n in cited:
        q = by_num[n]
        out += [f"**Q{n}.** {q['zh']}", "", f"> *{unfold_cjk(q['why_zh'])}*", ""]
    return write(DIST / "stage_script.md", "\n".join(out + [f"<sub>{file_footer(src)}</sub>"]))


# ── GitHub Pages 落地页（二维码的落点）──────────────────────
LANDING_CSS = """
  :root{--bg:#faf8f5;--card:#fff;--ink:#1c1a17;--muted:#7d746a;--line:#e8e2d9;--accent:#b4532a;--soft:#f5ece6}
  @media(prefers-color-scheme:dark){:root{--bg:#16140f;--card:#201d17;--ink:#ece7df;--muted:#9c948a;--line:#332e26;--accent:#e08a5c;--soft:#2b241d}}
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--ink);font-size:17px;line-height:1.7;
       font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",Roboto,sans-serif;
       -webkit-font-smoothing:antialiased;padding:0 0 64px}
  .wrap{max-width:640px;margin:0 auto;padding:0 20px}
  .top{display:flex;justify-content:flex-end;padding:14px 20px 0;max-width:640px;margin:0 auto}
  .top button{background:none;border:1px solid var(--line);color:var(--muted);border-radius:8px;
              padding:5px 12px;font:inherit;font-size:13px;cursor:pointer}
  h1{font-size:40px;letter-spacing:.04em;margin:26px 0 10px;font-weight:800}
  .tag{color:var(--muted);font-size:17px;margin-bottom:26px}
  .cta{display:block;width:100%;padding:19px;border:0;border-radius:14px;background:var(--accent);
       color:#fff;font:inherit;font-size:19px;font-weight:700;cursor:pointer;transition:.15s}
  .cta:active{transform:scale(.985)}
  .cta.ok{background:#2f7d4f}
  h2{font-size:14px;letter-spacing:.12em;color:var(--accent);margin:36px 0 12px;font-weight:700}
  ol{margin-left:20px} ol li{margin:8px 0}
  .qs{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px 22px}
  .grp{font-size:13px;letter-spacing:.08em;color:var(--accent);font-weight:700;margin:16px 0 7px}
  .grp:first-child{margin-top:0}
  .qi{display:flex;gap:9px;font-size:15px;line-height:1.6;margin:6px 0;color:var(--ink)}
  .qi b{color:var(--accent);flex:0 0 30px;font-variant-numeric:tabular-nums}
  .note{color:var(--muted);font-size:14px;margin-top:26px;padding-top:18px;border-top:1px solid var(--line)}
  .links{margin-top:14px;font-size:14px;display:flex;gap:18px;flex-wrap:wrap}
  a{color:var(--accent)}
"""


def build_landing(src: dict) -> Path:
    """二维码落在这里，不落仓库根目录：现场大多数人用手机。"""
    quickstart = (DIST / "quickstart.md").read_text(encoding="utf-8")
    payload = {
        lang: {
            **src["landing"][lang],
            # 剥掉 banner：那句「生成物，勿手改」是给贡献者看的，
            # 用户粘进 ChatGPT 第一行就读到它，纯噪音
            "prompt": (dist_dir(lang) / "quickstart.md")
                      .read_text(encoding="utf-8").replace(BANNER + "\n", "", 1).lstrip(),
            "groups": [
                {"t": f"{s['n']}. {tr(s, 'title', lang)} · {tr(s, 'subtitle', lang)}",
                 "qs": [{"n": qnum(q), "x": q["zh"] if lang == "zh" else q["en"]}
                        for q in s["questions"]]}
                for s in segments(src)
            ],
        }
        for lang in LANGS
    }
    data = json.dumps(payload, ensure_ascii=False)
    repo, viewer = src["links"]["repo"], "viewer.html"
    html = f"""<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{src['landing']['zh']['hero']} · {src['landing']['en']['hero']}</title>
<meta name="description" content="{src['landing']['zh']['tagline']}">
<style>{LANDING_CSS}</style></head><body>
<div class="top"><button id="lang">EN</button></div>
<div class="wrap">
  <h1 id="hero"></h1>
  <p class="tag" id="tag"></p>
  <button class="cta" id="copy"></button>
  <h2 id="stepsTitle"></h2>
  <ol id="steps"></ol>
  <h2 id="qsTitle"></h2>
  <div class="qs" id="qs"></div>
  <p class="note" id="privacy"></p>
  <p class="note" style="border:0;padding-top:6px;font-size:12px">{file_footer(src)}</p>
  <p class="links">
    <a href="{viewer}?sample=1" id="peek"></a>
    <a href="{viewer}" id="viewer"></a>
    <a href="{repo}" id="more"></a>
  </p>
</div>
<script>
const D = {data};
let lang = (navigator.language||'zh').toLowerCase().startsWith('zh') ? 'zh' : 'en';
const $ = i => document.getElementById(i);
function paint(){{
  const d = D[lang];
  document.documentElement.lang = lang;
  $('lang').textContent = lang === 'zh' ? 'EN' : '中文';
  $('hero').textContent = d.hero; $('tag').textContent = d.tagline;
  $('copy').textContent = d.copy_btn; $('copy').classList.remove('ok');
  $('stepsTitle').textContent = d.steps_title;
  $('steps').innerHTML = d.steps.map(s => '<li>' + s + '</li>').join('');
  $('qsTitle').textContent = d.questions_title;
  $('qs').innerHTML = d.groups.map(g => '<div class="grp">' + g.t + '</div>' +
    g.qs.map(q => '<div class="qi"><b>Q' + q.n + '</b><span>' + q.x + '</span></div>').join('')).join('');
  $('privacy').textContent = d.privacy;
  $('peek').textContent = d.peek; $('viewer').textContent = d.viewer; $('more').textContent = d.more;
  // 标题不跟随语言：跟随会在英文下变成 "Meta-Questions · Meta-Questions"
}}
$('lang').onclick = () => {{ lang = lang === 'zh' ? 'en' : 'zh'; paint(); }};
$('copy').onclick = async () => {{
  const text = D[lang].prompt;
  try {{ await navigator.clipboard.writeText(text); }}
  catch (e) {{
    // iOS Safari / 非安全上下文的兜底：临时 textarea + execCommand
    const ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    document.execCommand('copy'); document.body.removeChild(ta);
  }}
  $('copy').textContent = D[lang].copied; $('copy').classList.add('ok');
  setTimeout(() => {{ $('copy').textContent = D[lang].copy_btn; $('copy').classList.remove('ok'); }}, 2600);
}};
paint();
</script></body></html>
"""
    # viewer 一并复制进 docs/：手工 cp 的副本必然漂移（lesson 2026-08-06）
    (ROOT / "docs").mkdir(exist_ok=True)
    shutil.copyfile(ROOT / "viewer" / "index.html", ROOT / "docs" / "viewer.html")
    (ROOT / "docs" / "examples").mkdir(exist_ok=True)
    shutil.copyfile(ROOT / "examples" / "sample_report.md",
                    ROOT / "docs" / "examples" / "sample_report.md")
    _ = quickstart
    return write(ROOT / "docs" / "index.html", html)


# ── 现场实体卡（A5 双面，印刷用）────────────────────────────
CARD_CSS = """
  @page { size: A5; margin: 0; }
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei",-apple-system,sans-serif;
       background:#eee;color:#1c1a17;-webkit-font-smoothing:antialiased}
  .page{width:148mm;height:210mm;padding:13mm 12mm;background:#faf8f5;position:relative;
        display:flex;flex-direction:column;page-break-after:always;overflow:hidden}
  .page.back{background:#1c1a17;color:#f4efe8}
  h1{font-size:26pt;letter-spacing:.06em;font-weight:800;line-height:1}
  .tag{font-size:10.5pt;color:#8a7f74;margin-top:3.5mm;line-height:1.55}
  .rule{height:2px;background:#b4532a;width:16mm;margin:5mm 0 4mm}
  .sec{margin-bottom:3.2mm}
  .sec h2{font-size:9pt;color:#b4532a;letter-spacing:.1em;font-weight:700;margin-bottom:1.4mm}
  .q{display:flex;gap:2mm;font-size:8.4pt;line-height:1.42;margin-bottom:1.1mm}
  .q b{color:#b4532a;font-weight:700;flex:0 0 6.5mm;font-variant-numeric:tabular-nums}
  .note{margin-top:auto;font-size:8.5pt;color:#8a7f74;border-top:1px solid #e3ddd4;padding-top:3mm}
  .back h1{font-size:17pt;color:#f4efe8}
  .back ol{margin:5mm 0 0 5mm;font-size:9.5pt;line-height:1.62}
  .back li{margin-bottom:2.6mm}
  .back code{background:#2e2820;padding:.5mm 1.4mm;border-radius:1mm;font-size:8.6pt}
  .hl{margin-top:6mm;border:1px solid #b4532a;border-radius:2mm;padding:4mm}
  .hl .lab{font-size:7.5pt;letter-spacing:.14em;color:#e08a5c;font-weight:700}
  .hl .q10{font-size:10.5pt;line-height:1.5;margin-top:2mm}
  .qr{margin-top:auto;display:flex;gap:5mm;align-items:flex-end;padding-top:5mm}
  .qr svg{width:30mm;height:30mm;background:#faf8f5;padding:1.6mm;border-radius:1.5mm;flex:0 0 auto}
  .qrtxt{font-size:8pt;line-height:1.55;color:#a8a096}
  .qrtxt .u{font-family:ui-monospace,Menlo,monospace;font-size:7.2pt;color:#e08a5c;word-break:break-all}
  @media screen{ body{padding:16px;display:flex;gap:16px;flex-wrap:wrap;justify-content:center}
                 .page{box-shadow:0 3px 20px rgba(0,0,0,.18);border-radius:3px} }
"""


def _qr_svg(url: str) -> str:
    """二维码。缺 segno 直接炸，不降级。

    降级成占位框有两个害处：① 装没装 segno 会产出不同的 card.html，破坏幂等，
    「dist 与真源同步」的 CI 守卫直接失效；② 占位框可能被当成成品拿去印刷。
    """
    import io

    try:
        import segno
    except ImportError as e:
        raise SourceError(
            "生成现场卡需要 segno（二维码）。跑 `pip install -r requirements.txt`。"
            "这里不做降级：占位二维码印出来就是废卡。"
        ) from e
    buf = io.BytesIO()   # segno 的 svg writer 写的是 bytes，不是 str
    segno.make(url, error="m").save(buf, kind="svg", svgclass=None, omitsize=True,
                                    xmldecl=False, svgns=True, dark="#1c1a17", light="#faf8f5")
    return buf.getvalue().decode("utf-8")


def build_card(src: dict) -> Path:
    c, segs = src["card"], segments(src)
    url = src["links"]["pages"]   # 落地页，不是仓库根目录
    front_secs = "".join(
        '<div class="sec"><h2>' + f"{s['n']}. {s['title_zh']} · {s['subtitle_zh']}" + "</h2>"
        + "".join(f'<div class="q"><b>Q{qnum(q)}</b><span>{q["zh"]}</span></div>'
                  for q in s["questions"])
        + "</div>"
        for s in segs
    )
    steps = "".join(
        "<li>" + re.sub(r"`([^`]+)`", r"<code>\1</code>", st) + "</li>" for st in c["back_steps"]
    )
    q10 = next(q for s in segs for q in s["questions"] if qnum(q) == c["back_highlight_q"])
    html = f"""<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<title>{c['front_title']} · 现场卡 v{src['version']}</title>
<style>{CARD_CSS}</style></head><body>
<div class="page front">
  <h1>{c['front_title']}</h1>
  <div class="tag">{c['front_tagline']}</div>
  <div class="rule"></div>
  {front_secs}
  <div class="note">{c['front_note']}</div>
</div>
<div class="page back">
  <h1>{c['back_title']}</h1>
  <ol>{steps}</ol>
  <div class="hl">
    <div class="lab">{c['back_highlight_label']}</div>
    <div class="q10">Q{qnum(q10)}　{q10['zh']}</div>
  </div>
  <div class="qr">
    {_qr_svg(url)}
    <div class="qrtxt">{c['back_privacy']}<br><span class="u">{url}</span><br>
      {c['back_footer']}<br><span style="font-size:6.5pt">{file_footer(src)}</span></div>
  </div>
</div>
</body></html>
"""
    return write(DIST / "card.html", html)


# ── README ─────────────────────────────────────────────────
README_ZH = """{banner}<div align="center">

<h1>meta-questions</h1>

<p><b>{tagline_zh}</b></p>

<p><!--COUNT:questions-->{qcount}<!--/COUNT--> 个问题 · 摸清你的优势、资源与关系网 · 产出一份 AI Native 方向报告</p>

<p>
  <a href="{repo}/actions"><img alt="CI" src="{repo}/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="license" src="https://img.shields.io/badge/license-MIT-black">
  <img alt="dependencies" src="https://img.shields.io/badge/runtime%20deps-0-black">
  <img alt="works with" src="https://img.shields.io/badge/works%20with-ChatGPT%20·%20Claude%20·%20Coze%20·%20豆包-black">
</p>

<p>
  <a href="{pages}"><b>▶ 30 秒试一下</b></a> ·
  <a href="{pages}viewer.html?sample=1">看一份跑完的报告</a> ·
  <a href="README.en.md">English</a>
</p>

</div>

---

## 为什么

大多数人问 AI 的方式是「帮我做 X」。

同一个问题，问一个不了解你的 AI 和问一个了解你的 AI，答案质量差得很远。差别不在提示词技巧，
在于**它知不知道你手上有什么**——你的优势、你攒了三年的数据、你认识的那个能替你开门的人。
它不知道，就只能给你一个对所有人都成立的答案。对所有人都成立的答案，对你没有用。

这套元问题不产出答案。它产出**你自己的底牌清单**。答完之后，「该问 AI 什么」自己会浮出来。

## 30 秒试一下

**最快**：打开 [落地页]({pages}) → 点「复制提示词」→ 粘进任意 AI → 老实回答。

**或者**：

```bash
git clone {repo}
cd {name}
# 打开 dist/quickstart.md，全文复制，粘进 ChatGPT / Claude / Coze / 豆包
```

不需要装任何东西，不需要 API key。提示词跑在你自己的 AI 账号里。

## 它长什么样

下面是真实跑出来的一段（ChatGPT，未删改）：

```text
你 ▸ <粘贴 dist/quickstart.md 全文>

AI ▸ 过去三年，有没有一件事，别人做要花 3 倍的时间或成本，你却做成了？
     说出具体的时间、金额和结果。

你 ▸ 我以前做过一个项目，比同行快很多，效果挺好的。

AI ▸ 具体一点：这个项目是什么？你用了多久、花了多少钱，
     同行通常要多久或多少钱，最后结果是多少？          ← 答得虚，它会打回来

你 ▸ 2024 年 3 月，我用 6 天做完一个跨境选品数据管道，同行外包报价 8 万、
     工期 6 周。上线后类目选品命中率从 3 成提到 7 成。

AI ▸ 你身上有没有一个别人觉得「你怎么会这个」的技能或经历？它当初是怎么来的？
```

一次一题，答不具体就追问，全部问完才出报告。这三条都写进提示词里了。

## 你会拿到什么

一份 {nsec} 节的报告：{sec_names}。

<img src="assets/report.png" alt="示例报告" width="720">

最后一节叫**「{last_sec}」**——这是整套东西存在的理由。
一个好的元问题，判据不是 AI 答得多漂亮，是你答完之后**自己冒出了新问题**。

## {qcount} 个问题

{q_list}

## 三档取用

| 档 | 用什么 | 给谁 | 记得住你吗 |
|---|---|---|---|
| **A 单文件** | [`dist/quickstart.md`](dist/quickstart.md) | 所有人。复制粘贴，30 秒 | ❌ |
| **B 分段 + 记忆** | [`dist/staged/`](dist/staged/) | 想认真做一遍的人。`profile.md` 存你自己电脑上，下次接着聊 | ✅ |
| **C Claude Code skill** | [`.claude/skills/meta-questions/`](.claude/skills/meta-questions/) | Claude Code 用户。能读写文件、能联网找对标 | ✅ |

英文版在 [`dist/en/`](dist/en/)。

## 这不是拍脑袋想的三个维度

| 维度 | 理论 | 出处 | |
|---|---|---|---|
{theory_rows}

## 它不做什么

诚实一点，省得你浪费时间：

- **不替你做决定。** 它给的是判断依据和方向，不是「你应该去做 X」。
- **不联网的 AI 跑不了第 7 节（海外对标）。** 提示词里写了自检：没有检索能力就只写「未找到」，
  一个公司名都不许编。这是刻意的——凭记忆产出的 URL 幻觉率最高。
- **你答得敷衍，报告就是废的。** 追问器最多追两次，追不到就在报告里标「证据不足」，不会替你编。
- **不收集任何数据。** 没有后端，没有账号，没有云端同步。你的答案不会离开你的电脑。
  好处是你可以放心写真实数字；代价是换台设备要自己带 `profile.md`。
- **不是提示词技巧教程。** 这里没有「10 个让 AI 更聪明的咒语」。

## 现场卡

`dist/card.html` 是一张 A5 双面卡，浏览器直接打印就是成品。正面 {qcount} 题，背面用法 + 二维码。

<img src="assets/card.png" alt="A5 现场卡" width="720">

## 报告排版器

AI 给你的报告是 Markdown。[`viewer/index.html`](viewer/index.html) 把它排成能看、能打印、能存 PDF 的样子。
单文件、零外部依赖、不联网——双击就能用，[线上版在这]({pages}viewer.html)。

## 改它

真源只有一个：[`source/meta_questions.yaml`](source/meta_questions.yaml)。

```bash
pip install -r requirements.txt
python3 build.py             # 改完真源后重生成全部产物
python3 -m pytest tests/ -q  # 回归测试
```

`dist/`、`docs/`、`README*.md`、`.claude/skills/` 全是生成物，**手改会被下次 build 抹掉**，
CI 也会因为 `git diff` 不干净而失败。build.py 里不许出现任何面向读者的文案——
出现了就是第二真源，早晚漂移。

<details>
<summary>为什么这么设计</summary>

- **单一真源**：{qcount} 个问题、追问规则、报告模板、UI 文案、skill 触发词，全在一个 YAML 里。
  中英对照由 `validate()` 强制，缺一半会直接炸。
- **幂等**：输出只依赖真源，不依赖构建当天的日期。否则 CI 没法用 `git diff --exit-code` 守同步。
- **题号锚定 id**：显示编号由 `q7` 推出 7，不由列表位置推。重排 YAML 里的题目顺序不会静默打乱编号。
- **分发即分叉**：你复制走的是快照。每个生成物页脚都印版本号，报告页脚也印。
  报告出得不对，先看版本号——那是唯一能归因的东西。
- **二维码缺 segno 直接炸，不降级**：降级会让装没装库产出不同的 card.html；
  更要命的是占位二维码可能被拿去印刷。

</details>

## FAQ

<details>
<summary>要不要付费？要不要 API key？</summary>

都不要。这是一段提示词，跑在你已有的 AI 账号里。
</details>

<details>
<summary>可以用中文答吗？</summary>

可以。中英文各一套完整的提示词，用哪个都行，回答语言随你。
</details>

<details>
<summary>「元问题」是什么意思？</summary>

meta- 是「关于……的」。元问题就是**关于问题的问题**：你现在问 AI 的这个问题，
本身是不是对的问题？教育学里对它的定义更直接——**能引起问题的问题**，
判据是答完之后你自己冒出了新问题。所以报告最后一节是三个反问，不是三条结论。
</details>

<details>
<summary>我可以拿去改、拿去教课、拿去商用吗？</summary>

MIT，随便。改了之后建议把版本号一起改掉，不然事后没法归因。
</details>

## License

MIT

---

<div align="center"><sub>{footer}</sub></div>
"""

README_EN = """{banner}<div align="center">

<h1>meta-questions</h1>

<p><b>{tagline_en}</b></p>

<p><!--COUNT:questions-->{qcount}<!--/COUNT--> questions · map your edge, your assets and your network · get an AI-Native direction report</p>

<p>
  <a href="{repo}/actions"><img alt="CI" src="{repo}/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="license" src="https://img.shields.io/badge/license-MIT-black">
  <img alt="dependencies" src="https://img.shields.io/badge/runtime%20deps-0-black">
  <img alt="works with" src="https://img.shields.io/badge/works%20with-ChatGPT%20·%20Claude%20·%20any%20chat-black">
</p>

<p>
  <a href="{pages}"><b>▶ Try it in 30 seconds</b></a> ·
  <a href="{pages}viewer.html?sample=1">See a finished report</a> ·
  <a href="README.md">中文</a>
</p>

</div>

---

## Why

Most people ask AI to "do X for me".

Ask the same question of a model that knows nothing about you, then of one that does,
and the answers are not in the same league. The gap is not prompting skill. It is that
**the model does not know what you already hold** — your edge, the three years of data
you accumulated, the one person who can open a door for you. Not knowing, all it can
return is an answer that is true for everybody. An answer true for everybody is useless
to you.

This set produces no answers. It produces **an inventory of your own cards**.
Once you have that, what to ask AI surfaces on its own.

## Try it in 30 seconds

**Fastest**: open the [landing page]({pages}) → tap "Copy the prompt" → paste into any AI → answer honestly.

**Or**:

```bash
git clone {repo}
cd {name}
# open dist/en/quickstart.md, copy all of it, paste into ChatGPT / Claude / any chat
```

Nothing to install. No API key. It runs in the AI account you already have.

## What it looks like

A real exchange, unedited (ChatGPT):

```text
you ▸ <pasted all of dist/en/quickstart.md>

AI  ▸ In the past three years, was there something that would have cost someone
      else 3x the time or money, but you pulled off? Give the actual timeline,
      the actual amount, the actual outcome.

you ▸ I did a project once, it went pretty well and much faster than others.

AI  ▸ What was the project, when did you do it, how long did it take you versus
      others, and what measurable outcome did you get?      <- vague answers get pushed back

you ▸ March 2024, six days, competitor quoted 80k RMB and six weeks.
      Hit rate went from 30% to 70%.

AI  ▸ Do you have a skill or experience that makes people say 'wait, how do you
      know that?' Where did it come from?
```

One question at a time. Vague answers get probed. No report until every question is answered.
All three rules are written into the prompt.

## What you get

A {nsec}-section report: {sec_names}.

<img src="assets/report.png" alt="sample report" width="720">

The last section is **"{last_sec}"** — and that is the whole point.
A good meta-question is not judged by how well the AI answered.
It is judged by whether **you walked away with new questions of your own**.

## The {qcount} questions

{q_list}

## Three ways to use it

| Tier | What | For whom | Remembers you |
|---|---|---|---|
| **A Single file** | [`dist/en/quickstart.md`](dist/en/quickstart.md) | Everyone. Copy, paste, 30 seconds | ❌ |
| **B Sectioned + memory** | [`dist/en/staged/`](dist/en/staged/) | People doing this properly. `profile.md` stays on your machine | ✅ |
| **C Claude Code skill** | [`.claude/skills/meta-questions-en/`](.claude/skills/meta-questions-en/) | Claude Code users. Reads and writes files, can search the web | ✅ |

## These three dimensions are not invented

| Dimension | Theory | Source | |
|---|---|---|---|
{theory_rows}

## What it does not do

Being upfront so you do not waste your time:

- **It will not decide for you.** It gives you the evidence and a direction, not "you should do X".
- **Section 7 (comparable cases abroad) needs web access.** The prompt makes the model
  self-check: no search, then it writes "not found" and names no companies. Deliberate —
  URLs produced from memory are the highest-hallucination output there is.
- **Vague answers produce a worthless report.** The probe gives up after two tries and
  marks the item "insufficient evidence" rather than inventing something.
- **It collects nothing.** No backend, no account, no cloud sync. Your answers never leave
  your machine. Upside: you can write real numbers. Cost: bring your own `profile.md` across devices.
- **It is not a prompt-engineering tutorial.** No "10 magic words to make AI smarter" here.

## Print card

`dist/card.html` is a two-sided A5 card. Print it from the browser and it is done.

<img src="assets/card.png" alt="A5 card" width="720">

## Report viewer

The report your AI produces is Markdown. [`viewer/index.html`](viewer/index.html) renders it
into something readable, printable and saveable as PDF. Single file, zero external
dependencies, no network — double-click it, or use the [hosted one]({pages}viewer.html).

## Changing it

There is exactly one source of truth: [`source/meta_questions.yaml`](source/meta_questions.yaml).

```bash
pip install -r requirements.txt
python3 build.py             # regenerate everything after editing the source
python3 -m pytest tests/ -q  # regression tests
```

`dist/`, `docs/`, `README*.md` and `.claude/skills/` are generated. **Hand edits get wiped by
the next build**, and CI fails on a dirty `git diff`. No reader-facing copy is allowed inside
build.py — the moment it appears there, you have a second source of truth and it will drift.

<details>
<summary>Design notes</summary>

- **One source**: the {qcount} questions, the probe rules, the report template, the UI copy and
  the skill trigger words all live in one YAML. `validate()` enforces zh/en parity and fails loudly.
- **Idempotent**: output depends only on the source, never on the build date. Otherwise CI cannot
  use `git diff --exit-code` to guard that `dist/` matches the source.
- **Numbering anchored to id**: `q7` renders as 7. Reordering the YAML never silently renumbers.
- **Distribution is forking**: what you copy is a snapshot. Every artifact and every report carries
  a version in its footer. When a report comes out wrong, the version is the only thing that traces it.
- **Missing segno fails the build, no fallback**: degrading would make card.html differ by environment,
  and a placeholder QR code could get sent to a printer.

</details>

## FAQ

<details>
<summary>Do I need to pay? Do I need an API key?</summary>

Neither. It is a prompt. It runs in the AI account you already have.
</details>

<details>
<summary>What does "meta-question" mean?</summary>

meta- means "about". A meta-question is **a question about your questions**: is the thing
you are asking AI even the right thing to ask? The pedagogy literature puts it more directly —
**a question that gives rise to questions**, judged by whether you walked away with new ones
of your own. That is why the last report section is three questions back at you, not three conclusions.
</details>

<details>
<summary>Can I fork it, teach from it, use it commercially?</summary>

MIT. Go ahead. If you change the content, change the version too — otherwise nobody can trace it later.
</details>

## License

MIT

---

<div align="center"><sub>{footer}</sub></div>
"""


def _question_list(src: dict, lang: str) -> str:
    out = []
    for seg in segments(src):
        # 理论锚交给下面的理论表，行内只留副标题——否则第 2 段会显示成
        # 「现有资源 · VRIO · RBV / VRIO — Barney」，VRIO 出现两次
        out.append(f"**{seg['n']}. {tr(seg, 'title', lang)}**　<sub>{tr(seg, 'subtitle', lang)}</sub>")
        out.append("")
        for q in seg["questions"]:
            out.append(f"- **Q{qnum(q)}**　{q['zh'] if lang == 'zh' else q['en']}")
        out.append("")
    return "\n".join(out).rstrip()


def build_readme(src: dict, lang: str) -> Path:
    secs = src["report"]["sections"]
    tmpl = README_ZH if lang == "zh" else README_EN
    theory_rows = "\n".join(
        f"| {tr(t, 'dim', lang)} | {t['theory']} | {t['who']} | [→]({t['url']}) |"
        for t in src["theory"]
    )
    joiner = "、" if lang == "zh" else ", "
    return write(readme_path(lang), tmpl.format(
        banner=BANNER + "\n", name=src["name"], version=src["version"],
        repo=src["links"]["repo"], pages=src["links"]["pages"],
        tagline_zh=src["tagline_zh"], tagline_en=src["tagline_en"],
        qcount=sum(len(s["questions"]) for s in src["segments"]),
        nseg=len(src["segments"]), nsec=len(secs),
        premise=unfold_cjk(tr(src, "premise", lang)),
        q_list=_question_list(src, lang), theory_rows=theory_rows,
        sec_names=joiner.join(tr(s, "title", lang) for s in secs),
        last_sec=tr(secs[-1], "title", lang),
        footer=file_footer(src),
    ))


def main() -> None:
    src = load()
    made: list[Path] = []
    for lang in LANGS:
        made.append(build_quickstart(src, lang))
        made += build_staged(src, lang)
        made.append(build_skill(src, lang))
        made.append(build_readme(src, lang))
    made.append(build_stage_script(src))
    made.append(build_landing(src))
    made.append(build_card(src))
    print(f"built {src['name']} v{src['version']} ({src['released_on']}) → {len(made)} files")
    for p in made:
        print(f"  {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
