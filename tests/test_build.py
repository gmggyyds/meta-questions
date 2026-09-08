"""build.py 的回归测试（中英双语）。

三条设计原则，都是踩过才写下来的：

1. **分发即分叉**：生成物被复制走就是快照，每个文件必须带完整版本页脚。
2. **对着仓库里提交的生成物断言**，不能只对着现场重建的。否则有人手改 dist/ 后
   跑测试，不但抓不到，还会主动把证据抹掉——由 on_disk 快照 + 
   test_dist_is_committed_up_to_date 守。
3. **假绿灯是最贵的 bug**：断言必须对得上真实渲染格式。v0.1.0 曾有一条断言
   `"第 N 题" not in text`，而渲染出的是 `**QN. …**`，该测试恒真、纯装饰。
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from build import (  # noqa: E402
    BANNER, CJK, LANGS, REPORT_FILE, SourceError,
    dist_dir, load, qnum, readme_path, skill_dir, staged_dir, tr, ui, validate,
)

DOCS = ROOT / "docs"

SOURCE = ROOT / "source" / "meta_questions.yaml"

SEPARATORS = "｜／·—"          # 分隔符两边的空格是有意的排版
EXPECTED_SEGMENTS = 4          # 设计常量
EXPECTED_QUESTIONS = 12
EXPECTED_REPORT_SECTIONS = 8
MUST_HAVE_PROBE = {"q7", "q8", "q9", "q10"}   # 取证机制的核心，不许静默消失


@pytest.fixture(scope="module")
def src():
    return yaml.safe_load(SOURCE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def questions(src):
    return [q for s in src["segments"] for q in s["questions"]]


def _generated_files(src):
    """从真源现算，不写死文件名——写死的话孤儿文件反而更容易蒙混过关。"""
    files = [ROOT / "dist" / "stage_script.md", ROOT / "dist" / "card.html",
             DOCS / "index.html", DOCS / "viewer.html"]
    for lang in LANGS:
        files += [dist_dir(lang) / "quickstart.md", skill_dir(lang) / "SKILL.md",
                  readme_path(lang), staged_dir(lang) / REPORT_FILE,
                  staged_dir(lang) / "profile.template.md"]
        files += [staged_dir(lang) / f"{s['n']:02d}_{s['id']}.md" for s in src["segments"]]
    return files


@pytest.fixture(scope="module")
def on_disk(src):
    """跑任何 build 之前，先把仓库里**实际提交的**生成物字节存下来。"""
    return {p: (p.read_bytes() if p.exists() else None) for p in _generated_files(src)}


@pytest.fixture(scope="module")
def built(on_disk):
    r = subprocess.run([sys.executable, str(ROOT / "build.py")],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, f"build.py failed:\n{r.stdout}\n{r.stderr}"
    return r


# ── 真源自身 ────────────────────────────────────────────────
def test_source_shape(src, questions):
    assert len(src["segments"]) == EXPECTED_SEGMENTS
    assert len(questions) == EXPECTED_QUESTIONS
    ids = [q["id"] for q in questions]
    assert len(set(ids)) == len(ids), f"问题 id 重复: {ids}"
    assert sorted(qnum(q) for q in questions) == list(range(1, EXPECTED_QUESTIONS + 1))


@pytest.mark.parametrize("lang", LANGS)
def test_every_question_is_complete_in_both_languages(questions, lang):
    for q in questions:
        for field in ("id", "want"):
            assert q.get(field), f"{q.get('id')} 缺字段 {field}"
        assert q.get("zh" if lang == "zh" else "en"), f"{q['id']} 缺 {lang} 问题正文"
        assert q.get(f"why_{lang}"), f"{q['id']} 缺 why_{lang}"


def test_core_probes_exist_in_both_languages(questions):
    have = {q["id"] for q in questions if q.get("probe_zh")}
    assert MUST_HAVE_PROBE <= have, f"核心追问被删: {MUST_HAVE_PROBE - have}"
    for q in questions:
        if q.get("probe_zh"):
            assert q.get("probe_en"), f"{q['id']} 有中文追问却没有英文"


def test_ui_strings_are_aligned_across_languages(src):
    zh, en = src["ui"]["zh"], src["ui"]["en"]
    assert set(zh) == set(en), f"ui 中英键不对齐: {set(zh) ^ set(en)}"
    assert set(zh["want_labels"]) == set(en["want_labels"])


@pytest.mark.parametrize("lang", LANGS)
def test_report_sections_complete(src, lang):
    secs = src["report"]["sections"]
    assert len(secs) == EXPECTED_REPORT_SECTIONS
    for s in secs:
        for f in ("title", "form", "content"):
            assert s.get(f"{f}_{lang}"), f"报告第 {s['n']} 节缺 {f}_{lang}"
    assert secs[-1]["title_zh"] == "你还没回答的问题", "最后一节是判据落点，不许被换掉"


def test_every_theory_row_has_url(src):
    for t in src["theory"]:
        assert t["url"].startswith("http"), f"理论根缺 URL: {t['dim_zh']}"


# ── 真源被改坏时必须炸，且炸得能定位 ────────────────────────
def _broken(mutate):
    s = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    mutate(s)
    return s


def test_validate_rejects_segment_number_gap():
    with pytest.raises(SourceError, match="连续"):
        validate(_broken(lambda s: s["segments"][-1].__setitem__("n", 9)))


def test_validate_rejects_missing_field_with_context():
    with pytest.raises(SourceError) as e:
        validate(_broken(lambda s: s["segments"][0]["questions"][0].pop("why_zh")))
    assert "q1" in str(e.value), f"报错必须说明是哪道题，实际: {e.value}"


def test_validate_rejects_duplicate_question_number():
    with pytest.raises(SourceError, match="重复|连续"):
        validate(_broken(lambda s: s["segments"][0]["questions"][1].__setitem__("id", "q1")))


def test_validate_rejects_unknown_want_type():
    with pytest.raises(SourceError, match="want"):
        validate(_broken(lambda s: s["segments"][0]["questions"][0].__setitem__("want", ["vibes"])))


def test_validate_rejects_unaligned_ui(src):
    with pytest.raises(SourceError, match="ui"):
        validate(_broken(lambda s: s["ui"]["en"].pop("how_to_use")))


def test_validate_rejects_probe_without_translation():
    with pytest.raises(SourceError, match="probe_en"):
        validate(_broken(lambda s: [q.pop("probe_en") for seg in s["segments"]
                                    for q in seg["questions"] if q.get("probe_en")][0:1]))


# ── 生成物 ─────────────────────────────────────────────────
def test_all_tiers_generated(built, src):
    for p in _generated_files(src):
        assert p.exists(), f"未生成: {p.relative_to(ROOT)}"


@pytest.mark.parametrize("lang", LANGS)
def test_no_orphan_files_in_staged(built, src, lang):
    expected = {p.name for p in _generated_files(src) if p.parent == staged_dir(lang)}
    assert {p.name for p in staged_dir(lang).glob("*.md")} == expected


def test_full_footer_stamped_everywhere(built, src):
    """断言完整页脚串，不是只断言版本号——版本号在标题里本来就有。"""
    expect = f"generated by {src['name']} v{src['version']}"
    for p in _generated_files(src):
        # viewer 是纯工具（不含任何题目内容），它的漂移由「与 viewer/index.html
        # 逐字节相同」那条守，不要求带内容版本号
        if p.name == "viewer.html":
            continue
        assert expect in p.read_text(encoding="utf-8"), \
            f"{p.relative_to(ROOT)} 缺完整页脚 `{expect}`"


def test_build_is_idempotent(built, src):
    before = {p: p.read_bytes() for p in _generated_files(src)}
    subprocess.run([sys.executable, str(ROOT / "build.py")], check=True,
                   capture_output=True, cwd=ROOT)
    for p, b in before.items():
        assert p.read_bytes() == b, f"{p.relative_to(ROOT)} 重跑后变了，build 不幂等"


def test_dist_is_committed_up_to_date(src, on_disk):
    """对着仓库里**实际存在的**文件断言，而不是现场重建的。"""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "repo"
        (tmp / "source").mkdir(parents=True)
        shutil.copy(ROOT / "build.py", tmp / "build.py")
        shutil.copy(SOURCE, tmp / "source" / SOURCE.name)
        shutil.copytree(ROOT / "viewer", tmp / "viewer")
        shutil.copytree(ROOT / "examples", tmp / "examples")
        subprocess.run([sys.executable, str(tmp / "build.py")], check=True,
                       capture_output=True, cwd=tmp)
        stale = [str(p.relative_to(ROOT)) for p, committed in on_disk.items()
                 if not (tmp / p.relative_to(ROOT)).exists()
                 or (tmp / p.relative_to(ROOT)).read_bytes() != committed]
        assert not stale, f"仓库里的生成物与真源不同步（被手改或忘了跑 build）: {stale}"


def test_no_unrendered_placeholders(built, src):
    """只查 .md：HTML/JS/CSS 里的 {n}、{tag} 是语言语法，不是模板占位符。"""
    for p in _generated_files(src):
        if p.suffix != ".md":
            continue
        leftovers = re.findall(r"\{[a-z_]+\}", p.read_text(encoding="utf-8"))
        assert not leftovers, f"{p.relative_to(ROOT)} 有未渲染占位符: {set(leftovers)}"


@pytest.mark.parametrize("lang", LANGS)
def test_quickstart_contains_every_question(built, src, questions, lang):
    text = (dist_dir(lang) / "quickstart.md").read_text(encoding="utf-8")
    for q in questions:
        assert (q["zh"] if lang == "zh" else q["en"]) in text, f"{lang} quickstart 漏了 {q['id']}"


@pytest.mark.parametrize("lang", LANGS)
def test_probe_rules_agree_with_max_rounds(built, src, lang):
    rounds = src["probe"]["max_rounds"]
    needle = f"最多追问 {rounds} 次" if lang == "zh" else f"at most {rounds} times"
    for p in (dist_dir(lang) / "quickstart.md", skill_dir(lang) / "SKILL.md"):
        text = p.read_text(encoding="utf-8")
        assert needle in text, f"{p} 的追问上限没跟上 max_rounds"


def test_probe_rules_keep_the_count_templated(src):
    """次数必须以 {max_rounds} 模板存在真源里，不能写死。"""
    joined = " ".join(src["probe"]["rules_zh"] + src["probe"]["rules_en"])
    assert "{max_rounds}" in joined, "追问次数被写死了，不再跟随 max_rounds"
    assert not re.search(r"最多追问 \d+ 次|at most \d+ times", joined), \
        "真源里出现写死的次数，会和模板渲染出的值打架"


@pytest.mark.parametrize("lang", LANGS)
def test_start_command_and_report_guard_are_present(built, src, lang):
    """两条护栏：不许一次抛出全部问题、不许提前写报告。真实模型测试证明缺了会失效。"""
    start = tr(src["instructions"], "start_command", lang)
    guard = tr(src["instructions"], "report_guard", lang)
    for p in (dist_dir(lang) / "quickstart.md", skill_dir(lang) / "SKILL.md"):
        text = p.read_text(encoding="utf-8")
        assert start in text, f"{p} 缺启动指令"
        assert guard in text, f"{p} 缺报告护栏"
    for s in src["segments"]:
        text = (staged_dir(lang) / f"{s['n']:02d}_{s['id']}.md").read_text(encoding="utf-8")
        assert start in text


@pytest.mark.parametrize("lang", LANGS)
def test_section_seven_demands_a_visible_url(built, src, lang):
    """真实测试发现：模型会把网址藏在链接文字后面，用户存成纯文本就丢了。"""
    sec7 = next(s for s in src["report"]["sections"] if s["n"] == 7)
    content = tr(sec7, "content", lang)
    assert "https://" in content, "第 7 节必须给出「完整网址长什么样」的示例"
    marker = "纯文本" if lang == "zh" else "plain text"
    assert marker in content, "第 7 节必须说明为什么要写出完整网址"


@pytest.mark.parametrize("lang", LANGS)
def test_staged_files_partition_the_questions(built, src, lang):
    seen = []
    for s in src["segments"]:
        text = (staged_dir(lang) / f"{s['n']:02d}_{s['id']}.md").read_text(encoding="utf-8")
        for q in s["questions"]:
            body = q["zh"] if lang == "zh" else q["en"]
            assert body in text, f"{lang} 第 {s['n']} 段漏了 {q['id']}"
            seen.append(q["id"])
        for other in src["segments"]:
            if other["id"] == s["id"]:
                continue
            for q in other["questions"]:
                assert (q["zh"] if lang == "zh" else q["en"]) not in text, \
                    f"{lang} 第 {s['n']} 段串进了 {q['id']}"
    assert len(seen) == EXPECTED_QUESTIONS


@pytest.mark.parametrize("lang", LANGS)
def test_segment_probe_hints_stay_in_their_own_segment(built, src, lang):
    """断言用的是真实渲染格式 `**QN.`（v0.1.0 那版断言的串根本不会被生成）。"""
    for s in src["segments"]:
        text = (staged_dir(lang) / f"{s['n']:02d}_{s['id']}.md").read_text(encoding="utf-8")
        own = {qnum(q) for q in s["questions"]}
        for other in src["segments"]:
            for q in other["questions"]:
                if qnum(q) in own:
                    continue
                assert f"**Q{qnum(q)}." not in text, \
                    f"{lang} 第 {s['n']} 段出现了不属于它的 Q{qnum(q)}"


@pytest.mark.parametrize("lang", LANGS)
def test_question_numbering_identical_across_tiers(built, src, lang):
    """三档的「段 → 题号」映射必须完全一致。题号锚在 id 上，重排真源不会改变编号。"""
    truth = {s["n"]: sorted(qnum(q) for q in s["questions"]) for s in src["segments"]}
    seg_re = re.compile(r"^### .*?(\d+)")
    for tier in (dist_dir(lang) / "quickstart.md", skill_dir(lang) / "SKILL.md"):
        current, found = None, {}
        for line in tier.read_text(encoding="utf-8").splitlines():
            if line.startswith("### ") and (m := seg_re.match(line)):
                current = int(m.group(1)); found.setdefault(current, [])
            elif (m := re.match(r"\*\*Q(\d+)\. ", line)) and current is not None:
                found[current].append(int(m.group(1)))
        found = {k: v for k, v in found.items() if v}
        assert found == truth, f"{tier.name}({lang}) 段→题号映射与真源不一致: {found}"
    for s in src["segments"]:
        text = (staged_dir(lang) / f"{s['n']:02d}_{s['id']}.md").read_text(encoding="utf-8")
        nums = [int(m) for m in re.findall(r"^\*\*Q(\d+)\. ", text, re.M)]
        assert sorted(nums) == truth[s["n"]], f"{lang} 第 {s['n']} 段题号不一致: {nums}"


@pytest.mark.parametrize("lang", LANGS)
def test_staged_tier_is_self_contained(built, src, lang):
    """档 B 里被引用的每个文件都必须存在——v0.1.0 的第 4 段指向从未生成的 report.md。"""
    d = staged_dir(lang)
    present = {p.name for p in d.glob("*")}
    user_produced = {"profile.md": "profile.template.md", "report.md": REPORT_FILE}
    for p in d.glob("*.md"):
        for ref in re.findall(r"`([0-9A-Za-z_.]+\.md)`", p.read_text(encoding="utf-8")):
            if ref in user_produced:
                assert user_produced[ref] in present, f"{ref} 被引用但产出它的文件不存在"
                continue
            assert ref in present, f"{p.name} 引用了不存在的 {ref}"


@pytest.mark.parametrize("lang", LANGS)
def test_readme_count_is_derived_and_sections_track_source(built, src, questions, lang):
    text = readme_path(lang).read_text(encoding="utf-8")
    m = re.search(r"<!--COUNT:questions-->(\d+)<!--/COUNT-->", text)
    assert m and int(m.group(1)) == len(questions), "README 计数必须由真源现算"
    for sec in src["report"]["sections"]:
        assert tr(sec, "title", lang) in text, f"README({lang}) 没跟上第 {sec['n']} 节改名"
    for t in src["theory"]:
        assert t["url"] in text, f"README({lang}) 漏了理论根 URL"


def test_readmes_link_to_each_other(built):
    assert "README.en.md" in readme_path("zh").read_text(encoding="utf-8")
    assert "README.md" in readme_path("en").read_text(encoding="utf-8")


@pytest.mark.parametrize("lang", LANGS)
def test_skill_frontmatter(built, src, questions, lang):
    text = (skill_dir(lang) / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    fm = yaml.safe_load(text.split("---")[1])
    assert fm["name"] == skill_dir(lang).name
    assert str(len(questions)) in fm["description"], "skill 描述里的题数必须现算"
    assert str(src["version"]) == str(fm["version"])


@pytest.mark.parametrize("lang", LANGS)
def test_report_template_rendered_in_full(built, src, lang):
    for p in (dist_dir(lang) / "quickstart.md", staged_dir(lang) / REPORT_FILE,
              skill_dir(lang) / "SKILL.md"):
        text = p.read_text(encoding="utf-8")
        for sec in src["report"]["sections"]:
            assert tr(sec, "title", lang) in text, f"{p.name}({lang}) 漏了报告第 {sec['n']} 节"


@pytest.mark.parametrize("lang", LANGS)
def test_report_footer_leaves_the_date_to_the_model(built, src, lang):
    """写死构建日期会让 2027 年跑出来的报告印 2026。"""
    placeholder = ui(src, lang)["report_date_placeholder"]
    text = (dist_dir(lang) / "quickstart.md").read_text(encoding="utf-8")
    assert placeholder in text, "报告页脚必须留日期占位给模型当场填"


def test_stage_script_quotes_questions_from_source(built, src):
    """现场讲稿引用的 Q 号必须从真源现取。手抄的话重排题目就会台上讲错。"""
    text = (ROOT / "dist" / "stage_script.md").read_text(encoding="utf-8")
    by_num = {qnum(q): q for s in src["segments"] for q in s["questions"]}
    cited = {int(m) for m in re.findall(r"Q(\d+)", " ".join(src["stage"]["plan_zh"]))}
    assert cited, "讲稿没有引用任何题号"
    for n in cited:
        assert n in by_num, f"讲稿引用了不存在的 Q{n}"
        assert by_num[n]["zh"] in text, f"讲稿没带上 Q{n} 的原文"


# ── 排版与安全 ─────────────────────────────────────────────
def test_no_cjk_spacing_artifacts(built, src):
    bad = re.compile(f"[{CJK}] [{CJK}]")
    for p in _generated_files(src):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith(("```", "<!--", "|")):
                continue
            for hit in bad.finditer(line):
                if any(c in SEPARATORS for c in hit.group(0)):
                    continue
                assert False, f"{p.relative_to(ROOT)}:{i} 中文间多余空格: …{hit.group(0)}…"


def test_no_credentials_in_any_generated_file(built, src):
    """这是要公开开源的仓，生成物里任何凭证特征串都是阻塞级。"""
    rx = re.compile("|".join([
        r"sk-[A-Za-z0-9]{20,}", r"ghp_[A-Za-z0-9]{20,}", r"gho_[A-Za-z0-9]{20,}",
        r"glpat-[A-Za-z0-9_-]{20,}", r"xox[baprs]-[A-Za-z0-9-]{10,}",
        r"AKIA[0-9A-Z]{16}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"Bearer [A-Za-z0-9._-]{20,}",
    ]))
    for p in _generated_files(src):
        hit = rx.search(p.read_text(encoding="utf-8"))
        assert not hit, f"{p.relative_to(ROOT)} 疑似含凭证: {hit.group(0)[:12]}…"


def test_source_loads_through_public_api():
    assert load()["version"]


# ── 现场卡 / 落地页 / 报告排版器 ────────────────────────────
def test_card_carries_every_question_and_a_real_qr(built, src, questions):
    """占位二维码印出来就是废卡，所以这里断言的是真的有 <svg> 码点。"""
    text = (ROOT / "dist" / "card.html").read_text(encoding="utf-8")
    for q in questions:
        assert q["zh"] in text, f"现场卡漏了 {q['id']}"
    assert "<svg" in text and text.count("<path") + text.count("<rect") > 0, "卡上没有真二维码"
    assert src["links"]["pages"] in text, "卡上的网址必须是落地页，不是仓库根目录"
    assert "noqr" not in text, "卡上出现了二维码占位框"


def test_card_qr_points_at_the_landing_page_not_the_repo(src):
    """现场大多数人用手机。二维码落到仓库根目录 = 要在 GitHub 移动端点四层才拿得到提示词。"""
    assert src["links"]["pages"].rstrip("/") != src["links"]["repo"].rstrip("/")


def test_landing_prompt_matches_quickstart_without_the_banner(built, src):
    """落地页那个复制按钮是全场唯一的入口。它给出的东西必须就是 quickstart 本身。"""
    landing = (DOCS / "index.html").read_text(encoding="utf-8")
    for lang in LANGS:
        body = (dist_dir(lang) / "quickstart.md").read_text(encoding="utf-8")
        stripped = body.replace(BANNER + "\n", "", 1).lstrip()
        assert BANNER not in stripped
        # 内嵌的是 JSON 字面量，取其中一段特征句做锚点即可
        probe = stripped.splitlines()[0]
        assert json_escaped(probe) in landing, f"落地页里的 {lang} 提示词与 quickstart 不一致"
    assert BANNER.replace('"', '\\"') not in landing, "落地页把 banner 一起复制给用户了"


def json_escaped(s: str) -> str:
    import json as _json
    return _json.dumps(s, ensure_ascii=False)[1:-1]


def test_landing_lists_every_question(built, questions):
    landing = (DOCS / "index.html").read_text(encoding="utf-8")
    for q in questions:
        assert json_escaped(q["zh"]) in landing, f"落地页漏了 {q['id']}"


def test_docs_viewer_is_an_exact_copy_of_the_source(built):
    """手工 cp 的副本必然漂移（lesson 2026-08-06），所以它由 build 复制并在这里逐字节核对。"""
    assert (DOCS / "viewer.html").read_bytes() == (ROOT / "viewer" / "index.html").read_bytes()


def test_viewer_has_no_external_dependencies(built):
    """现场 wifi 不可靠；引第三方脚本还多一个供应链面。"""
    text = (ROOT / "viewer" / "index.html").read_text(encoding="utf-8")
    for host in ("cdn.", "unpkg", "jsdelivr", "googleapis", "//code."):
        assert host not in text, f"报告排版器引了外部资源: {host}"


def test_landing_and_card_have_no_external_dependencies(built):
    for p in (DOCS / "index.html", ROOT / "dist" / "card.html"):
        text = p.read_text(encoding="utf-8")
        for host in ("cdn.", "unpkg", "jsdelivr", "googleapis"):
            assert host not in text, f"{p.name} 引了外部资源: {host}"
