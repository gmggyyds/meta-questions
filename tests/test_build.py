"""build.py 的回归测试。

设计要点：
1. **分发即分叉**（design.md §10 风险 5）：生成物被复制走就是快照，
   所以每个文件必须带完整版本页脚。
2. **测试必须对着仓库里提交的生成物断言**，不能只对着「现场重建的」断言——
   否则有人手改 dist/ 后跑测试，不但抓不到，还会主动把证据抹掉。
   这一条由 test_dist_is_committed_up_to_date 守。
3. **假绿灯是最贵的 bug**：断言必须对得上真实渲染格式。
   （v0.1.0 曾有一条断言 `"第 N 题" not in text`，而渲染出的是 `**QN. …**`，
   该测试恒真、纯装饰，改坏代码也不会失败。）
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
from build import CJK, REPORT_FILE, SourceError, load, qnum, validate  # noqa: E402

SOURCE = ROOT / "source" / "meta_questions.yaml"
DIST = ROOT / "dist"
STAGED = DIST / "staged"
SKILL = ROOT / ".claude" / "skills" / "meta-questions" / "SKILL.md"
README = ROOT / "README.md"

SEPARATORS = "｜／·—"          # 分隔符两边的空格是有意的排版
EXPECTED_SEGMENTS = 4          # 设计常量
EXPECTED_QUESTIONS = 12
EXPECTED_REPORT_SECTIONS = 8
MUST_HAVE_PROBE = {"q7", "q8", "q9", "q10"}   # 这四条追问是取证机制的核心，不许静默消失


@pytest.fixture(scope="module")
def src():
    return yaml.safe_load(SOURCE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def questions(src):
    return [q for s in src["segments"] for q in s["questions"]]


@pytest.fixture(scope="module")
def on_disk(src):
    """跑任何 build 之前，先把仓库里**实际提交的**生成物字节存下来。

    没有这一步，`built` fixture 会先重建一遍 dist/，把手改痕迹抹掉——
    v0.1.0 的 up-to-date 检查就是这样变成假绿灯的。
    """
    return {p: (p.read_bytes() if p.exists() else None) for p in _generated_files(src)}


@pytest.fixture(scope="module")
def built(on_disk):
    r = subprocess.run([sys.executable, str(ROOT / "build.py")],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, f"build.py failed:\n{r.stdout}\n{r.stderr}"
    return r


def _generated_files(src):
    """从真源现算，不写死文件名——写死的话孤儿文件反而更容易蒙混过关。"""
    files = [DIST / "quickstart.md", DIST / "stage_script.md", SKILL, README,
             STAGED / REPORT_FILE, STAGED / "profile.template.md"]
    files += [STAGED / f"{s['n']:02d}_{s['id']}.md" for s in src["segments"]]
    return files


# ── 真源自身 ────────────────────────────────────────────────
def test_source_shape(src, questions):
    assert len(src["segments"]) == EXPECTED_SEGMENTS
    assert len(questions) == EXPECTED_QUESTIONS
    ids = [q["id"] for q in questions]
    assert len(set(ids)) == len(ids), f"问题 id 重复: {ids}"
    assert sorted(qnum(q) for q in questions) == list(range(1, EXPECTED_QUESTIONS + 1))


def test_every_question_is_complete(questions):
    for q in questions:
        for field in ("id", "zh", "en", "want", "why_zh"):
            assert q.get(field), f"{q.get('id')} 缺字段 {field}"


def test_core_probes_are_not_silently_dropped(questions):
    have = {q["id"] for q in questions if q.get("probe_zh")}
    assert MUST_HAVE_PROBE <= have, f"核心追问被删: {MUST_HAVE_PROBE - have}"


def test_every_segment_has_theory_anchor(src):
    for s in src["segments"]:
        assert s.get("anchor"), f"段 {s['id']} 没有理论锚"


def test_every_theory_row_has_url(src):
    for t in src["theory"]:
        assert t["url"].startswith("http"), f"理论根缺 URL: {t['dim_zh']}"


def test_report_has_exactly_eight_sections(src):
    assert len(src["report"]["sections"]) == EXPECTED_REPORT_SECTIONS
    assert src["report"]["sections"][-1]["title_zh"] == "你还没回答的问题", \
        "最后一节是元问题的判据落点，不许被换掉"


# ── 真源被改坏时必须炸，且炸得能定位 ────────────────────────
def _broken(mutate):
    src = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    mutate(src)
    return src


def test_validate_rejects_segment_number_gap():
    """v0.1.0 的真实缺陷：段号断档时 build 不报错，却生成指向不存在文件的引导语。"""
    def gap(s):
        s["segments"][-1]["n"] = 9
    with pytest.raises(SourceError, match="连续"):
        validate(_broken(gap))


def test_validate_rejects_missing_field_with_context():
    def drop(s):
        del s["segments"][0]["questions"][0]["why_zh"]
    with pytest.raises(SourceError) as e:
        validate(_broken(drop))
    assert "q1" in str(e.value), f"报错必须说明是哪道题，实际: {e.value}"


def test_validate_rejects_duplicate_question_number():
    def dup(s):
        s["segments"][0]["questions"][1]["id"] = "q1"
    with pytest.raises(SourceError, match="重复|连续"):
        validate(_broken(dup))


def test_validate_rejects_unknown_want_type():
    def bad(s):
        s["segments"][0]["questions"][0]["want"] = ["vibes"]
    with pytest.raises(SourceError, match="want"):
        validate(_broken(bad))


# ── 生成物 ─────────────────────────────────────────────────
def test_all_tiers_generated(built, src):
    for p in _generated_files(src):
        assert p.exists(), f"未生成: {p.relative_to(ROOT)}"


def test_no_orphan_files_in_dist(built, src):
    """改了段号会留下旧文件，用户拿到两份重复的同一段。"""
    expected = {p.name for p in _generated_files(src) if p.parent == STAGED}
    assert {p.name for p in STAGED.glob("*.md")} == expected


def test_full_footer_stamped_everywhere(built, src):
    """断言完整页脚串，不是只断言版本号——版本号在标题里本来就有，
    那样即使页脚模板被删光也照过（v0.1.0 的真实盲区）。"""
    expect = f"generated by {src['name']} v{src['version']}"
    for p in _generated_files(src):
        assert expect in p.read_text(encoding="utf-8"), \
            f"{p.relative_to(ROOT)} 缺完整页脚 `{expect}`"


def test_build_is_idempotent(built, src):
    """输出只能依赖真源。依赖 date.today() 的话跨天重跑会全文件改写，
    CI 就没法用 git diff 守「dist 与真源同步」。"""
    before = {p: p.read_bytes() for p in _generated_files(src)}
    subprocess.run([sys.executable, str(ROOT / "build.py")], check=True,
                   capture_output=True, cwd=ROOT)
    for p, b in before.items():
        assert p.read_bytes() == b, f"{p.relative_to(ROOT)} 重跑后变了，build 不幂等"


def test_dist_is_committed_up_to_date(src, on_disk):
    """对着仓库里**实际存在的**文件断言，而不是现场重建的。

    没有这条，有人手改 dist/ 后跑 pytest 会全绿，且改动被静默抹掉。
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "repo"
        (tmp / "source").mkdir(parents=True)
        shutil.copy(ROOT / "build.py", tmp / "build.py")
        shutil.copy(SOURCE, tmp / "source" / SOURCE.name)
        subprocess.run([sys.executable, str(tmp / "build.py")], check=True,
                       capture_output=True, cwd=tmp)
        stale = []
        for p, committed in on_disk.items():
            fresh = tmp / p.relative_to(ROOT)
            if not fresh.exists() or fresh.read_bytes() != committed:
                stale.append(str(p.relative_to(ROOT)))
        assert not stale, f"仓库里的生成物与真源不同步（被手改或忘了跑 build）: {stale}"


def test_no_unrendered_placeholders(built, src):
    for p in _generated_files(src):
        text = p.read_text(encoding="utf-8")
        leftovers = re.findall(r"\{[a-z_]+\}", text)
        assert not leftovers, f"{p.relative_to(ROOT)} 有未渲染占位符: {set(leftovers)}"


def test_quickstart_contains_every_question(built, questions):
    text = (DIST / "quickstart.md").read_text(encoding="utf-8")
    for q in questions:
        assert q["zh"] in text, f"quickstart 漏了 {q['id']}"


def test_probe_rules_agree_with_max_rounds(built, src):
    """规则正文里的次数必须由 max_rounds 现算，不能一处模板一处写死。"""
    rounds = src["probe"]["max_rounds"]
    for p in (DIST / "quickstart.md", SKILL):
        text = p.read_text(encoding="utf-8")
        assert f"最多追问 {rounds} 次" in text, f"{p.name} 的追问上限没跟上 max_rounds"
        for other in {1, 2, 3, 5} - {rounds}:
            assert f"最多追问 {other} 次" not in text, f"{p.name} 里有互相打架的上限"


def test_probe_rules_keep_the_count_templated(src):
    """次数必须以 {max_rounds} 模板存在真源里。

    一旦有人图省事把它写死成汉字，改 max_rounds 就会产出自相矛盾的提示词。
    """
    joined = " ".join(src["probe"]["rules_zh"] + src["probe"]["rules_en"])
    assert "{max_rounds}" in joined, "追问次数被写死了，不再跟随 max_rounds"
    assert not re.search(r"最多追问 \d+ 次", joined), \
        "真源里出现写死的次数，会和模板渲染出的值打架"


def test_start_command_and_report_guard_are_present(built, src):
    """两条护栏：不许一次抛出全部问题、不许提前写报告。"""
    for p in (DIST / "quickstart.md", SKILL):
        text = p.read_text(encoding="utf-8")
        assert src["instructions"]["start_command_zh"] in text, f"{p.name} 缺启动指令"
        assert src["instructions"]["report_guard_zh"] in text, f"{p.name} 缺报告护栏"
    for s in src["segments"]:
        text = (STAGED / f"{s['n']:02d}_{s['id']}.md").read_text(encoding="utf-8")
        assert src["instructions"]["start_command_zh"] in text


def test_staged_files_partition_the_questions(built, src):
    seen = []
    for s in src["segments"]:
        text = (STAGED / f"{s['n']:02d}_{s['id']}.md").read_text(encoding="utf-8")
        for q in s["questions"]:
            assert q["zh"] in text, f"第 {s['n']} 段漏了 {q['id']}"
            seen.append(q["id"])
        for other in src["segments"]:
            if other["id"] == s["id"]:
                continue
            for q in other["questions"]:
                assert q["zh"] not in text, f"第 {s['n']} 段串进了 {q['id']}"
    assert len(seen) == EXPECTED_QUESTIONS


def test_segment_probe_hints_stay_in_their_own_segment(built, src):
    """断言用的是真实渲染格式 `**QN.`。

    v0.1.0 这条写成了 `"第 N 题" not in text`，而 build 从不生成那个串 → 恒真。
    """
    for s in src["segments"]:
        text = (STAGED / f"{s['n']:02d}_{s['id']}.md").read_text(encoding="utf-8")
        own = {qnum(q) for q in s["questions"]}
        for other in src["segments"]:
            for q in other["questions"]:
                if qnum(q) in own:
                    continue
                assert f"**Q{qnum(q)}." not in text, \
                    f"第 {s['n']} 段出现了不属于它的 Q{qnum(q)}"


def test_question_numbering_identical_across_tiers(built, src):
    """三档的「段 → 题号」映射必须完全一致。

    一条堵死所有串号：题号锚在 id 上，重排 YAML 里的题目顺序不会改变编号。
    """
    truth = {s["n"]: sorted(qnum(q) for q in s["questions"]) for s in src["segments"]}
    assert sorted(n for v in truth.values() for n in v) == list(range(1, EXPECTED_QUESTIONS + 1))

    for tier in (DIST / "quickstart.md", SKILL):
        text = tier.read_text(encoding="utf-8")
        current, found = None, {}
        for line in text.splitlines():
            m = re.match(r"### 第 (\d+) 段 · ", line)
            if m:
                current = int(m.group(1)); found[current] = []
            m = re.match(r"\*\*Q(\d+)\. ", line)
            if m and current is not None:
                found[current].append(int(m.group(1)))
        assert found == truth, f"{tier.name} 的段→题号映射与真源不一致: {found}"

    for s in src["segments"]:
        text = (STAGED / f"{s['n']:02d}_{s['id']}.md").read_text(encoding="utf-8")
        nums = [int(m) for m in re.findall(r"^\*\*Q(\d+)\. ", text, re.M)]
        assert sorted(nums) == truth[s["n"]], f"第 {s['n']} 段题号与真源不一致: {nums}"


def test_staged_tier_is_self_contained(built, src):
    """档 B 里被引用到的每个文件都必须真实存在——
    v0.1.0 的第 4 段指向 `report.md`，而那个文件从来没被生成过。"""
    present = {p.name for p in STAGED.glob("*")}
    # 这两个是**用户自己产出**的文件，不该在仓库里存在；只要求有模板可依
    user_produced = {"profile.md": "profile.template.md", "report.md": REPORT_FILE}
    for p in STAGED.glob("*.md"):
        for ref in re.findall(r"`([0-9A-Za-z_.]+\.md)`", p.read_text(encoding="utf-8")):
            if ref in user_produced:
                assert user_produced[ref] in present, \
                    f"{ref} 被引用，但产出它的 {user_produced[ref]} 不存在"
                continue
            assert ref in present, f"{p.name} 引用了不存在的 {ref}"


def test_readme_question_count_is_derived_not_hardcoded(built, questions):
    text = README.read_text(encoding="utf-8")
    m = re.search(r"<!--COUNT:questions-->(\d+)<!--/COUNT-->", text)
    assert m, "README 缺 COUNT 标记"
    assert int(m.group(1)) == len(questions)


def test_readme_section_names_track_the_source(built, src):
    """README 正文曾把 7 个报告章节名写死，改真源后它会静默说谎。"""
    text = README.read_text(encoding="utf-8")
    for sec in src["report"]["sections"]:
        assert sec["title_zh"] in text, f"README 没跟上第 {sec['n']} 节改名"


def test_readme_carries_all_theory_urls(built, src):
    text = README.read_text(encoding="utf-8")
    for t in src["theory"]:
        assert t["url"] in text, f"README 漏了理论根 URL: {t['dim_zh']}"


def test_skill_has_valid_frontmatter_and_derived_count(built, src, questions):
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    fm = yaml.safe_load(text.split("---")[1])
    assert fm.get("name") and fm.get("description")
    assert str(len(questions)) in fm["description"], "skill 描述里的题数必须现算"
    assert str(src["version"]) == str(fm["version"])


def test_report_template_rendered_in_full(built, src):
    for p in (DIST / "quickstart.md", STAGED / REPORT_FILE, SKILL):
        text = p.read_text(encoding="utf-8")
        for sec in src["report"]["sections"]:
            assert sec["title_zh"] in text, f"{p.name} 漏了报告第 {sec['n']} 节"
        assert text.count("### 第 ") >= EXPECTED_REPORT_SECTIONS


def test_stage_script_quotes_questions_from_source(built, src):
    """现场讲稿引用的 Q 号必须从真源现取。手抄的话重排题目就会台上讲错。"""
    text = (DIST / "stage_script.md").read_text(encoding="utf-8")
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
            if line.lstrip().startswith(("```", "<!--")):
                continue
            for hit in bad.finditer(line):
                if any(c in SEPARATORS for c in hit.group(0)):
                    continue
                assert False, f"{p.relative_to(ROOT)}:{i} 中文间多余空格: …{hit.group(0)}…"


def test_no_credentials_in_any_generated_file(built, src):
    """这是要公开开源的仓，生成物里任何凭证特征串都是阻塞级。"""
    patterns = [
        r"sk-[A-Za-z0-9]{20,}", r"ghp_[A-Za-z0-9]{20,}", r"gho_[A-Za-z0-9]{20,}",
        r"glpat-[A-Za-z0-9_-]{20,}", r"xox[baprs]-[A-Za-z0-9-]{10,}",
        r"AKIA[0-9A-Z]{16}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"Bearer [A-Za-z0-9._-]{20,}",
    ]
    rx = re.compile("|".join(patterns))
    for p in _generated_files(src):
        hit = rx.search(p.read_text(encoding="utf-8"))
        assert not hit, f"{p.relative_to(ROOT)} 疑似含凭证: {hit.group(0)[:12]}…"


def test_source_loads_through_public_api():
    assert load()["version"]
