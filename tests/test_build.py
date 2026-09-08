"""build.py 的回归测试。

设计要点（对应 design.md §10 风险 5「分发即分叉」）：
生成物一旦被用户复制走就是快照，所以这里最硬的两条断言是
——版本号必须出现在每个生成物里，且模板占位符不许有漏渲染的。
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "source" / "meta_questions.yaml"
DIST = ROOT / "dist"
SKILL = ROOT / ".claude" / "skills" / "meta-questions" / "SKILL.md"
README = ROOT / "README.md"


@pytest.fixture(scope="module")
def src():
    return yaml.safe_load(SOURCE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def questions(src):
    return [q for s in src["segments"] for q in s["questions"]]


@pytest.fixture(scope="module")
def built():
    """跑一次真实 build，后续断言都对着真实产物做。"""
    r = subprocess.run(
        [sys.executable, str(ROOT / "build.py")],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert r.returncode == 0, f"build.py failed:\n{r.stdout}\n{r.stderr}"
    return r


# ── 真源自身的完整性 ────────────────────────────────────────
def test_source_shape(src, questions):
    assert len(src["segments"]) == 4, "四段结构是设计常量"
    assert len(questions) == 12
    ids = [q["id"] for q in questions]
    assert len(set(ids)) == len(ids), f"问题 id 重复: {ids}"


def test_every_question_is_complete(questions):
    for q in questions:
        for field in ("id", "zh", "en", "want", "why_zh"):
            assert q.get(field), f"{q.get('id')} 缺字段 {field}"


def test_every_segment_has_theory_anchor(src):
    for s in src["segments"]:
        assert s.get("anchor"), f"段 {s['id']} 没有理论锚"


def test_every_theory_row_has_url(src):
    for t in src["theory"]:
        assert t["url"].startswith("http"), f"理论根缺 URL: {t['dim_zh']}"


# ── 生成物 ─────────────────────────────────────────────────
def _generated_files():
    return [
        DIST / "quickstart.md",
        DIST / "staged" / "01_who_i_am.md",
        DIST / "staged" / "02_what_i_hold.md",
        DIST / "staged" / "03_whom_i_know.md",
        DIST / "staged" / "04_leverage.md",
        DIST / "staged" / "profile.template.md",
        SKILL,
        README,
    ]


def test_all_tiers_generated(built):
    for p in _generated_files():
        assert p.exists(), f"未生成: {p.relative_to(ROOT)}"


def test_version_stamped_everywhere(built, src):
    """分发即分叉：没有版本号就无法归因一份烂报告是哪一版的锅。"""
    for p in _generated_files():
        assert src["version"] in p.read_text(encoding="utf-8"), \
            f"{p.relative_to(ROOT)} 缺版本号 {src['version']}"


def test_no_unrendered_placeholders(built):
    for p in _generated_files():
        text = p.read_text(encoding="utf-8")
        leftovers = re.findall(r"\{(version|name|date|[a-z_]+_zh)\}", text)
        assert not leftovers, f"{p.relative_to(ROOT)} 有未渲染占位符: {set(leftovers)}"


def test_quickstart_contains_every_question(built, questions):
    text = (DIST / "quickstart.md").read_text(encoding="utf-8")
    for q in questions:
        assert q["zh"] in text, f"quickstart 漏了 {q['id']}"


def test_quickstart_contains_probe_rules(built, src):
    text = (DIST / "quickstart.md").read_text(encoding="utf-8")
    for rule in src["probe"]["rules_zh"]:
        assert rule in text, f"quickstart 漏了追问规则: {rule[:20]}…"


def test_staged_files_partition_the_questions(built, src):
    """四个分段文件合起来必须不重不漏地覆盖 12 问。"""
    seen = []
    for s in src["segments"]:
        p = DIST / "staged" / f"{s['n']:02d}_{s['id']}.md"
        text = p.read_text(encoding="utf-8")
        for q in s["questions"]:
            assert q["zh"] in text, f"{p.name} 漏了 {q['id']}"
            seen.append(q["id"])
        for other in src["segments"]:
            if other["id"] == s["id"]:
                continue
            for q in other["questions"]:
                assert q["zh"] not in text, f"{p.name} 串进了别段的 {q['id']}"
    assert len(seen) == 12


def test_readme_question_count_is_derived_not_hardcoded(built, questions):
    """CHARTER §4 D6：文档里的计数必须由真源现算，不许写死漂移。"""
    text = README.read_text(encoding="utf-8")
    m = re.search(r"<!--COUNT:questions-->(\d+)<!--/COUNT-->", text)
    assert m, "README 缺 COUNT 标记（计数必须由 build 注入）"
    assert int(m.group(1)) == len(questions)


def test_readme_carries_all_theory_urls(built, src):
    text = README.read_text(encoding="utf-8")
    for t in src["theory"]:
        assert t["url"] in text, f"README 漏了理论根 URL: {t['dim_zh']}"


def test_skill_has_valid_frontmatter(built):
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "skill 必须以 YAML frontmatter 开头"
    fm = yaml.safe_load(text.split("---")[1])
    assert fm.get("name") and fm.get("description")


def test_report_template_has_all_eight_sections(built, src):
    """报告第 8 节（你还没回答的问题）是元问题的判据落点，不许被裁掉。"""
    text = (DIST / "quickstart.md").read_text(encoding="utf-8")
    for sec in src["report"]["sections"]:
        assert sec["title_zh"] in text, f"报告模板漏了第 {sec['n']} 节"
    assert "你还没回答的问题" in text


def test_no_credentials_in_any_generated_file(built):
    """CHARTER §2 S1：生成物是要公开开源的，扫一遍凭证特征串。"""
    pattern = re.compile(r"(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})")
    for p in _generated_files():
        hit = pattern.search(p.read_text(encoding="utf-8"))
        assert not hit, f"{p.relative_to(ROOT)} 疑似含凭证: {hit.group(0)[:8]}…"


# ── 排版与分段正确性（测试只验"在不在"验不出这些，全靠人肉复查抓到后补钉）──
CJK = r"一-鿿　-〿＀-￯"


# 分隔符两边的空格是有意的排版，不算折行产物
SEPARATORS = "｜／·—"


def test_no_cjk_spacing_artifacts(built):
    """YAML 折行会把中文换行折成空格，读起来像断句错误。"""
    bad = re.compile(f"[{CJK}] [{CJK}]")
    for p in _generated_files():
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith(("|", "```", "- 形式", "<!--")):
                continue  # 表格与代码块里的空格是有意的
            for hit in bad.finditer(line):
                if any(c in SEPARATORS for c in hit.group(0)):
                    continue
                assert False, f"{p.relative_to(ROOT)}:{i} 中文间多余空格: …{hit.group(0)}…"


def test_staged_probe_rules_stay_in_their_own_segment(built, src):
    """分段文件里不许出现别段题号的追问规则——读者只看到本段 3 题，
    却读到「第 10 题若用户答…」，会直接懵掉。"""
    for s in src["segments"]:
        p = DIST / "staged" / f"{s['n']:02d}_{s['id']}.md"
        text = p.read_text(encoding="utf-8")
        own = {q["id"] for q in s["questions"]}
        for other_seg in src["segments"]:
            if other_seg["id"] == s["id"]:
                continue
            for q in other_seg["questions"]:
                if q["id"] in own:
                    continue
                num = int(q["id"].lstrip("q"))
                assert f"第 {num} 题" not in text, \
                    f"{p.name} 提到了不属于本段的第 {num} 题"


def test_per_question_probes_are_attached_to_their_question(built, src):
    """题目专属的追问提示必须挂在题目上，不能混进全局规则。"""
    for s in src["segments"]:
        for q in s["questions"]:
            if not q.get("probe_zh"):
                continue
            for target in (DIST / "quickstart.md",
                           DIST / "staged" / f"{s['n']:02d}_{s['id']}.md"):
                assert q["probe_zh"] in target.read_text(encoding="utf-8"), \
                    f"{target.name} 缺 {q['id']} 的专属追问提示"
