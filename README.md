<!-- 生成物，勿手改。改 source/meta_questions.yaml 后跑 `python3 build.py` -->
<div align="center">

<h1>meta-questions</h1>

<p><b>在你问 AI 任何问题之前，先回答这些问题。</b></p>

<p><!--COUNT:questions-->12<!--/COUNT--> 个问题 · 摸清你的优势、资源与关系网 · 产出一份 AI Native 方向报告</p>

<p>
  <a href="https://github.com/gmggyyds/meta-questions/actions"><img alt="CI" src="https://github.com/gmggyyds/meta-questions/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="license" src="https://img.shields.io/badge/license-MIT-black">
  <img alt="dependencies" src="https://img.shields.io/badge/runtime%20deps-0-black">
  <img alt="works with" src="https://img.shields.io/badge/works%20with-ChatGPT%20·%20Claude%20·%20Coze%20·%20豆包-black">
</p>

<p>
  <a href="https://gmggyyds.github.io/meta-questions/"><b>▶ 30 秒试一下</b></a> ·
  <a href="https://gmggyyds.github.io/meta-questions/viewer.html?sample=1">看一份跑完的报告</a> ·
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

**最快**：打开 [落地页](https://gmggyyds.github.io/meta-questions/) → 点「复制提示词」→ 粘进任意 AI → 老实回答。

**或者**：

```bash
git clone https://github.com/gmggyyds/meta-questions
cd meta-questions
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

一份 8 节的报告：你的画像、你的不公平优势、躺着的资源、你的杠杆缺口、AI Native 判定、下周就能开始的三个动作、海外对标、你还没回答的问题。

<img src="assets/report.png" alt="示例报告" width="720">

最后一节叫 <b>「你还没回答的问题」</b> ——这是整套东西存在的理由。
一个好的元问题，判据不是 AI 答得多漂亮，是你答完之后**自己冒出了新问题**。

## 12 个问题

**1. 我是谁**　<sub>个人最大优势</sub>

- **Q1**　过去三年，有没有一件事，别人做要花 3 倍的时间或成本，你却做成了？说出具体的时间、金额和结果。
- **Q2**　你身上有没有一个别人觉得「你怎么会这个」的技能或经历？它当初是怎么来的？
- **Q3**　有没有一类问题，大家习惯性来找你问？最近一次是谁、问的什么？

**2. 我手里有什么**　<sub>现有资源 · VRIO</sub>

- **Q4**　列 3 样你已经花过钱、花过时间攒下来的东西（数据、库存、内容、账号、供应链关系、代码、现金流……），每样给一个数字。
- **Q5**　这 3 样里，哪一样是别人花钱也短期买不到的？为什么买不到？
- **Q6**　这 3 样里，哪一样现在基本躺着没用？躺了多久？为什么没用起来？

**3. 我认识谁**　<sub>身边的资源 · 弱关系</sub>

- **Q7**　谁能替你开一扇你自己敲不开的门？写出那扇门具体是什么。
- **Q8**　谁能在 24 小时内给你一个诚实的「这东西行不行」的判断？他为什么会诚实？
- **Q9**　谁手上有流量或名单，而且他有理由帮你分发？他的理由是什么？（「关系好」不算理由）

**4. 杠杆在哪**　<sub>AI 时代最大杠杆</sub>

- **Q10**　Swap Test：把 AI 从你现在做的这件事里完全拔掉，你是「变慢」，还是「整个模式垮掉」？只能二选一。
- **Q11**　如果 AI 明天免费、无限、且不会出错，你现在做的这件事应该长什么样？它会不会根本不该是现在这个形态？
- **Q12**　你现在缺的是哪一种杠杆——劳动力、资本、代码、还是媒体？你过去为什么没拿到它？AI 能不能绕过那个原因？

## 答完之后呢

报告躺在某个对话窗口里，两周后你自己都找不到。下次开新对话，AI 又完全不认识你。

**[the-great-me](https://github.com/gmggyyds/the-great-me)** 把这些答案变成一份存在你自己电脑上的账本：
以后的笔记、会议纪要、工单标个题号就持续归位，AI 做判断前先读它。数据不离开你的机器。

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
| 三维模型整体 | Effectuation — Bird-in-Hand Principle: Who I am / What I know / Whom I know | Saras D. Sarasvathy, UVA Darden | [→](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1278404) |
| 个人最大优势 | Who I am — tastes, abilities, expertise | Sarasvathy, Effectuation | [→](https://www.darden.virginia.edu/effectuation) |
| 手里的现有资源 | RBV / VRIO — Valuable, Rare, Inimitable, Organized | Jay Barney, 1991 / 1995 | [→](https://strategicmanagementinsight.com/tools/vrio/) |
| 身边的资源 | The Strength of Weak Ties — 56% of people found jobs via contacts they saw only occasionally | Mark Granovetter, 1973, AJS | [→](https://news.stanford.edu/stories/2023/07/strength-weak-ties) |
| AI 时代最大杠杆 | Four kinds of leverage — labour, capital, code, media. The last two are permissionless. | Naval Ravikant | [→](https://aydoo.services/en/articles/naval-ravikant-leverage/) |
| AI Native vs 旧业务+AI | The Swap Test — remove the AI: does the team slow down (enabled) or does the model collapse (native)? | CRV, The Founder's Guide to AI-Native, 2026 | [→](https://www.crv.com/content/what-is-ai-native) |
| 元问题方法本身 | Meta-prompting — ask the model what it needs to know, one question at a time, before it answers | Practitioner consensus | [→](https://whitebeardstrategies.com/blog/ask-ai-what-to-ask-ai-the-meta-prompting-advantage/) |
| 验收判据 | 元问题 = 能引起问题的问题；判据是答完之后你自己冒出了新问题 | 教育学定义 | [→](https://zhuanlan.zhihu.com/p/629895268) |

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

`dist/card.html` 是一张 A5 双面卡，浏览器直接打印就是成品。正面 12 题，背面用法 + 二维码。

<img src="assets/card.png" alt="A5 现场卡" width="720">

## 报告排版器

AI 给你的报告是 Markdown。[`viewer/index.html`](viewer/index.html) 把它排成能看、能打印、能存 PDF 的样子。
单文件、零外部依赖、不联网——双击就能用，[线上版在这](https://gmggyyds.github.io/meta-questions/viewer.html)。

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

- **单一真源**：12 个问题、追问规则、报告模板、UI 文案、skill 触发词，全在一个 YAML 里。
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

<div align="center"><sub>generated by meta-questions v0.2.0 · 2026-09-09</sub></div>
