<!-- 生成物，勿手改。改 source/meta_questions.yaml 后跑 `python3 build.py` -->
<div align="center">

<h1>meta-questions</h1>

<p><b>Answer these before you ask AI anything.</b></p>

<p><!--COUNT:questions-->12<!--/COUNT--> questions · map your edge, your assets and your network · get an AI-Native direction report</p>

<p>
  <a href="https://github.com/gmggyyds/meta-questions/actions"><img alt="CI" src="https://github.com/gmggyyds/meta-questions/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="license" src="https://img.shields.io/badge/license-MIT-black">
  <img alt="dependencies" src="https://img.shields.io/badge/runtime%20deps-0-black">
  <img alt="works with" src="https://img.shields.io/badge/works%20with-ChatGPT%20·%20Claude%20·%20any%20chat-black">
</p>

<p>
  <a href="https://gmggyyds.github.io/meta-questions/"><b>▶ Try it in 30 seconds</b></a> ·
  <a href="https://gmggyyds.github.io/meta-questions/viewer.html?sample=1">See a finished report</a> ·
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

**Fastest**: open the [landing page](https://gmggyyds.github.io/meta-questions/) → tap "Copy the prompt" → paste into any AI → answer honestly.

**Or**:

```bash
git clone https://github.com/gmggyyds/meta-questions
cd meta-questions
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

A 8-section report: Who you are, Your unfair advantage, What is sitting idle, Your leverage gap, AI-Native verdict, Three things he can start next week, Comparable cases abroad, The questions you have not answered yet.

<img src="assets/report.png" alt="sample report" width="720">

The last section is **"The questions you have not answered yet"** — and that is the whole point.
A good meta-question is not judged by how well the AI answered.
It is judged by whether **you walked away with new questions of your own**.

## The 12 questions

**1. Who I Am**　<sub>Your unfair edge</sub>

- **Q1**　In the past three years, was there something that would have cost someone else 3x the time or money, but you pulled off? Give the actual timeline, the actual amount, the actual outcome.
- **Q2**　Do you have a skill or experience that makes people say 'wait, how do you know that?' Where did it come from?
- **Q3**　Is there a kind of question people habitually bring to you? Who came last, and what did they ask?

**2. What I Hold**　<sub>Existing assets · VRIO</sub>

- **Q4**　List 3 things you have already paid for — in money or in time (data, inventory, content, accounts, supplier relationships, code, cash flow). Attach a number to each.
- **Q5**　Which of those three could someone NOT buy quickly, even with money? Why not?
- **Q6**　Which of the three is currently sitting idle? For how long? Why has it not been put to work?

**3. Whom I Know**　<sub>Your network · weak ties</sub>

- **Q7**　Who can open a door you cannot knock on yourself? Name the door, specifically.
- **Q8**　Who would give you an honest 'this will not work' within 24 hours? What makes them honest with you?
- **Q9**　Who holds an audience or a list, and has a REASON to distribute for you? State the reason. ('We're friends' is not a reason.)

**4. Where the Leverage Is**　<sub>Leverage in the AI era</sub>

- **Q10**　The Swap Test: remove AI entirely from what you are doing. Do you slow down, or does the whole model collapse? Pick one.
- **Q11**　If AI were free, infinite and never wrong tomorrow — what should this thing look like? Should it even exist in its current shape?
- **Q12**　Which leverage are you missing — labour, capital, code, or media? Why did you not get it before? Can AI route around that reason?

## And after you answer them?

The report sits in a chat window, and in two weeks you will not find it again.
Open a new conversation and the model knows nothing about you all over again.

**[the-great-me](https://github.com/gmggyyds/the-great-me)** turns those answers into a ledger on your own machine:
notes, meeting minutes and tickets keep filing themselves into the twelve slots, and your
AI reads it before it judges anything. The data never leaves your machine.

## Three ways to use it

| Tier | What | For whom | Remembers you |
|---|---|---|---|
| **A Single file** | [`dist/en/quickstart.md`](dist/en/quickstart.md) | Everyone. Copy, paste, 30 seconds | ❌ |
| **B Sectioned + memory** | [`dist/en/staged/`](dist/en/staged/) | People doing this properly. `profile.md` stays on your machine | ✅ |
| **C Claude Code skill** | [`.claude/skills/meta-questions-en/`](.claude/skills/meta-questions-en/) | Claude Code users. Reads and writes files, can search the web | ✅ |

## These three dimensions are not invented

| Dimension | Theory | Source | |
|---|---|---|---|
| The three dimensions | Effectuation — Bird-in-Hand Principle: Who I am / What I know / Whom I know | Saras D. Sarasvathy, UVA Darden | [→](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1278404) |
| Your edge | Who I am — tastes, abilities, expertise | Sarasvathy, Effectuation | [→](https://www.darden.virginia.edu/effectuation) |
| What you hold | RBV / VRIO — Valuable, Rare, Inimitable, Organized | Jay Barney, 1991 / 1995 | [→](https://strategicmanagementinsight.com/tools/vrio/) |
| Who you know | The Strength of Weak Ties — 56% of people found jobs via contacts they saw only occasionally | Mark Granovetter, 1973, AJS | [→](https://news.stanford.edu/stories/2023/07/strength-weak-ties) |
| Leverage | Four kinds of leverage — labour, capital, code, media. The last two are permissionless. | Naval Ravikant | [→](https://aydoo.services/en/articles/naval-ravikant-leverage/) |
| AI-Native vs AI-Enabled | The Swap Test — remove the AI: does the team slow down (enabled) or does the model collapse (native)? | CRV, The Founder's Guide to AI-Native, 2026 | [→](https://www.crv.com/content/what-is-ai-native) |
| The method | Meta-prompting — ask the model what it needs to know, one question at a time, before it answers | Practitioner consensus | [→](https://whitebeardstrategies.com/blog/ask-ai-what-to-ask-ai-the-meta-prompting-advantage/) |
| How to tell it worked | 元问题 = 能引起问题的问题；判据是答完之后你自己冒出了新问题 | 教育学定义 | [→](https://zhuanlan.zhihu.com/p/629895268) |

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
dependencies, no network — double-click it, or use the [hosted one](https://gmggyyds.github.io/meta-questions/viewer.html).

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

- **One source**: the 12 questions, the probe rules, the report template, the UI copy and
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

<div align="center"><sub>generated by meta-questions v0.2.0 · 2026-09-09</sub></div>
