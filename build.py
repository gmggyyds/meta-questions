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
<title>{src['landing']['zh']['hero']} · Meta-Questions</title>
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
    <a href="examples/sample_report.md" id="peek"></a>
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
  document.title = d.hero + ' · Meta-Questions';
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
README_ZH = """{banner}
# {name} · 元问题

> {tagline_zh}
> *{tagline_en}*

**v{version}** ｜ <!--COUNT:questions-->{qcount}<!--/COUNT--> 个问题 · {nseg} 段 · 三档取用
｜ [English](README.en.md)

{premise}

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

先看看跑完长什么样：[`examples/sample_report.md`](examples/sample_report.md)。

## 你会拿到什么

一份 {nsec} 节的报告：{sec_names}。

最后一节叫**「{last_sec}」**——这是整套东西存在的理由。
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
python3 build.py            # 改完真源后重生成
python3 -m pytest tests/ -q
```

`dist/`、`README*.md`、`.claude/skills/` 全是生成物，**手改会被下次 build 抹掉**，
CI 也会因为 `git diff` 不干净而失败。

## 一个提醒

你复制走的是**快照**。每个生成物页脚都印着版本号（当前 `v{version}`），
报告页脚也会印。哪天报告出得不对，先看版本号——那是唯一能归因的东西。

## License

MIT

---

<sub>{footer}</sub>
"""

README_EN = """{banner}
# {name}

> {tagline_en}

**v{version}** ｜ <!--COUNT:questions-->{qcount}<!--/COUNT--> questions · {nseg} sections · three ways to use it
｜ [中文](README.md)

{premise}

---

## Why these questions

Most people ask AI to "do X for me". The bottleneck was never prompting skill.
It is that **you never said what you already have**. The model does not know your
edge, the three years of data you accumulated, or the one person who can open a
door for you — so all it can give back is correct, useless advice.

This set produces no answers. It produces **an inventory of your own cards**.
Once you have that, what to ask AI surfaces on its own.

## Four sections

| # | Section | Focus | Questions | Grounded in |
|---|---|---|---|---|
{seg_rows}

## Three ways to use it

| Tier | Files | For whom | Remembers you |
|---|---|---|---|
| A Single file | [`dist/en/quickstart.md`](dist/en/quickstart.md) | Everyone. Paste into any AI and go | ❌ |
| B Sectioned + memory | [`dist/en/staged/`](dist/en/staged/) | People doing this properly. `profile.md` stays on your machine | ✅ |
| C Claude Code skill | [`.claude/skills/meta-questions-en/`](.claude/skills/meta-questions-en/) | Claude Code users. Reads and writes files, can search the web | ✅ |

### Fastest path

Copy all of [`dist/en/quickstart.md`](dist/en/quickstart.md) → paste into ChatGPT / Claude / any chat → send → answer honestly.

## What you get

A {nsec}-section report: {sec_names}.

The last section is **"{last_sec}"** — and that is the whole point.
A good meta-question is not judged by how well the AI answered.
It is judged by whether **you walked away with new questions of your own**.

## Where this comes from

These three dimensions are not invented.

| Dimension | Theory | Source | Link |
|---|---|---|---|
{theory_rows}

## Changing it

There is exactly one source of truth: [`source/meta_questions.yaml`](source/meta_questions.yaml).

```bash
pip install -r requirements.txt
python3 build.py            # regenerate after editing the source
python3 -m pytest tests/ -q
```

`dist/`, `README*.md` and `.claude/skills/` are generated. **Hand edits get wiped
by the next build**, and CI fails on a dirty `git diff`.

## One warning

What you copy is a **snapshot**. Every generated file carries a version in its
footer (currently `v{version}`), and so does every report. When a report comes out
wrong, check the version first — it is the only thing that lets you trace it.

## License

MIT

---

<sub>{footer}</sub>
"""


def build_readme(src: dict, lang: str) -> Path:
    secs = src["report"]["sections"]
    tmpl = README_ZH if lang == "zh" else README_EN
    theory_rows = "\n".join(
        f"| {tr(t, 'dim', lang)} | {t['theory']} | {t['who']} | [link]({t['url']}) |"
        for t in src["theory"]
    )
    seg_rows = "\n".join(
        f"| {s['n']} | {tr(s, 'title', lang)} | {tr(s, 'subtitle', lang)} | "
        f"{len(s['questions'])} | {s['anchor']} |"
        for s in segments(src)
    )
    joiner = "、" if lang == "zh" else ", "
    return write(readme_path(lang), tmpl.format(
        banner=BANNER, name=src["name"], version=src["version"],
        tagline_zh=src["tagline_zh"], tagline_en=src["tagline_en"],
        qcount=sum(len(s["questions"]) for s in src["segments"]),
        nseg=len(src["segments"]), nsec=len(secs),
        premise=unfold_cjk(tr(src, "premise", lang)),
        seg_rows=seg_rows, theory_rows=theory_rows,
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
