---
name: ykiko-zh-article
description: Writing or revising a Chinese article (Zhihu post / blog in website/content/zh-cn) in ykiko's own voice, or taking the "AI 味" out of a draft. Covers his style, the format spec, the AI-isms he has rejected, and the review loop.
---

# Writing a Chinese article as ykiko

Paths below (`website/`, `scripts/`, `FORMAT_SPEC.md`, `drafts/`) are relative to
his blog repository, `/home/ykiko/workspace/about-me`, wherever the article is
written from.

ykiko reads every draft and spots AI-written prose at once. The goal is that a
reader of his Zhihu column cannot tell the article apart from the ones he wrote
himself. Everything below comes from his articles in
`website/content/zh-cn/articles/*/index.md` and from his feedback on the xclang
post (2026-10, 2090994886531100694).

## Workflow

1. **Read him first.** Before drafting, read two or three recent articles in full
   (2069934520514749368, 2034883949630059124, 1985940996270339378) and quote from
   them, not from memory. A subagent's style report is a supplement, not a
   substitute; check its quotes against the files.
2. **Facts only from sources**: the project's docs and repo, numbers the user or
   lead gives, or ykiko himself. Ask him when unsure; never fill a gap with a
   plausible detail. A claim you inferred gets flagged to him when you hand over.
3. **Draft, then lint**: `python3 scripts/md_format.py <file>` (FORMAT_SPEC.md).
   Known false positives: project and tool names like `llvm-mingw`, `clang-cl`.
4. **AI-ism pass by subagents** before every hand-over: two independent
   reviewers, one checking against his articles, one reading as a native Chinese
   editor, each given the catalogue below and asked for line, quote, why, and a
   rewrite that keeps every fact. Merge their findings yourself; they also catch
   factual slips. Add a third, **fact-check** reviewer for any technical claim,
   command or example: it re-runs or re-derives each one (in the ODR trial it
   caught a link that fails under `-fvisibility=hidden`, a missing
   `-fuse-ld=lld`, AVX vs AVX2, DYLD_INSERT_LIBRARIES). Examples are compiled
   and run for real, with versions and commands recorded.
5. **Revisions**: keep snapshots the way he asks (e.g. `drafts/x.v1.md` untouched,
   later rounds in `x.vN.md`), tell him the diff command, and summarize each round
   in a few lines. Nothing is committed, pushed or published without his word.

## His voice

- **Long comma-chained sentences**, plain and colloquial, occasionally a short
  one to set the tone: 「显然不是。」「好消息是，这里存在转机。」
- **Ask, then answer at once**: 「为什么呢？」「怎么办呢？」「那么……呢？」「效果怎么样呢？」
- **Favourite words**: 其实 (by far), 实际上, 可以发现, 那么, 于是, 不过, 比如
  (not 例如 in recent posts), 就好了 / 就行了, 似乎, 或许, 大概, 注意.
  Colloquial connectives: 然后的话, 最近的话, 但是呢. Not used: 换言之, 总而言之,
  综上所述, 其次, 赋能, 闭环.
- **First person**: 我 for experience and opinions, 我们 for the team or when
  walking the reader through. Concrete personal detail beats abstraction
  (「如果是我自己来做……」, never 「人类工程师……」).
- **Opinions stated plainly**: 我觉得, 说实话, 显然不是, it depends, 「那肯定是
  不好用呀，所以没人用，好用早用了」. Hedges with 似乎/或许/大概.
- **English terms inline** without translation: corner case, trade-off,
  workaround, it works on my machine. New terms as **中文 (English)** on first use.
- **agent** in lower case; model names as he writes them (opus 4.6, fable5, Opus 5.5).
- **Defers detail**: 「这里就不一一展开了」「更多的细节就不在这篇文章里展开了，后面我们会单独写一篇……」

## Structure

- **Opening**: no greeting, no 「本文将……」. Knowledge articles (a C++ topic
  explained) go straight into the topic, no link to earlier posts and no
  chaining to them in the body (ykiko, ODR trial 10-08). Project updates may
  open with 「距离上篇 [文章](…) 又过了……」 or what a previous post left open; ask
  him when unsure.
- **Previous articles**: name them by title or 「那篇 workflow 文章」. 「上一篇文章」
  is ambiguous once a newer post exists.
- **Headings**: technical posts use English `##`/`###` (Background, Design,
  Summary, or questions like `Why now?`); essays use Chinese. No numbering, no
  slogans or metaphors in headings.
- **Ending**: no filler summary. Stop on an opinion or plan, then
  「感谢阅读！」, optionally the QQ group link
  (`https://qm.qq.com/q/tSD3D81fpu`) and where to file issues.
- **Scope**: lead with what the title promises. Leave out an FAQ whose answers
  the body already gives. Experiment or detail lists: three or four items of one
  or two sentences each; nine long items made him 「头皮发麻」.
- **Say each thing once.** Even after the AI-isms were gone, he found the
  published xclang post wordy because points came back again and again. Each
  claim or number lives in one place: the TL;DR may summarize, but the opening
  must not restate it; the Summary must not replay an earlier section (「回头看
  ……现在有了 agent 都可以做了」 repeated Why now); a Roadmap item must not
  re-explain the Design; a paragraph after a table must not read the table
  back. Cut sentences that restate the previous one (「也就是说……」 recaps,
  「接口变了，模块文件就变了，key 也就跟着变了」), transitions that announce the
  next part (「这里挑几个比较典型的说一说」「既然标题叫……那我们就从……开始吧」), and
  recaps of an earlier article the reader doesn't need. Before handing over, have
  a subagent list every repeated claim with its line numbers.

## Formatting

- FORMAT_SPEC.md: a space between CJK and ASCII/inline code/links; ASCII-only
  parentheses are half-width with a space before (`模块文件 (BMI)`), any CJK
  inside means full-width （）; ……, ——; canonical nouns (GCC, Clang, CMake, GitHub,
  macOS, ...).
- Quotes are 「」, never “”.
- **Bold** only for a term or a key phrase inside a sentence, never a standalone
  motto.
- Asides go in blockquotes starting 「注意，」 or 「实际上，」, often without a
  final 。.
- Lists: 「名词：长解释」, no final 。; several sentences per item is fine.
- A code block is often introduced without a colon: 「放入下面两个文件」「然后执行」.
- Tables only for real data. Emoji never; at most a few single ！.

## AI-isms he rejected (before → after, from the xclang post)

| pattern                                                  | rejected                                                                                                                       | became                                                                                                                                                                  |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| odd metaphor / idiom                                     | 文章最后留了一个尾巴                                                                                                           | 那篇文章最后还剩了一个问题没解决                                                                                                                                        |
|                                                          | 工具链再好用，接不进构建系统也白搭                                                                                             | (deleted)                                                                                                                                                               |
| 「不是 X，而是 Y」 reveal, staged 排比, abstract subject | 人类工程师最痛苦的不是写代码，而是等。改一行配置，等两个小时，看到一个错误，再改一行，再等两个小时。agent 不会疲惫，也不会分心 | 构建一次 LLVM 要两个小时左右，一个问题往往要反复试很多次才能定位，如果是我自己来做，大部分时间都会花在等 CI 上，而且我也不可能一直盯着，而 agent 可以 24 小时一直试下去 |
| rigor checklist recited to impress                       | 每个补丁都有一份说明，写清楚改了什么，为什么改，怎么验证的，以及上游的进展                                                     | 目前 xclang 在 LLVM 上打了 8 个补丁，主要是这些：                                                                                                                       |
|                                                          | 每一个都有任务拆分、决策记录和验收结果                                                                                         | (deleted)                                                                                                                                                               |
| rule-like absolutes (一律、从不、永远)                   | 另外还有几条从一开始就定下的规矩：重的构建一律放到 CI 上跑，从不在本地跑                                                       | 比较重的构建都是放到 CI 上跑的，本地只做一些轻量的工作                                                                                                                  |
| aphoristic closer / slogan                               | 维护成本已经不再是我们放弃一个更好方案的理由了                                                                                 | ……非常适合交给 agent 来做，人手也就不是问题了                                                                                                                           |
|                                                          | 而这恰恰是原来那套方案做不到的 / 一个编译器，所有目标                                                                          | (deleted) / 其实就是 Clang 版的 rustup                                                                                                                                  |
| 「并不只是 X」                                           | xclang 并不只是把编译器打了个包                                                                                                | 除了 CMake，Bazel 也可以直接使用                                                                                                                                        |
| vague closer                                             | 接下来 clice 能做的事情也会越来越多                                                                                            | a concrete plan, or nothing                                                                                                                                             |
| English calques                                          | 服务所有的 checkout / 都是相同的字节 / 对……做哈希 / 导入者 / 这意味着 / 把这些放在一起 / 为了做到这一点 / 认真地使用它         | 所有机器都能共用一份缓存 / 逐字节相同 / 算 key 的时候把……算进去 / import 它的文件 / 也就是说 / 总结一下 / 它的做法是 / 真正用起来                                       |
| dramatic adverbs                                         | 悄无声息地、恰恰、真正地、深度集成、所谓                                                                                       | 而且没有任何提示 / (deleted) / 现成的集成                                                                                                                               |
| personified tools                                        | 让编译器去做它平时真正要做的事情                                                                                               | 让插桩版的编译器跑它平时实际会跑的东西                                                                                                                                  |
| fragments for rhythm                                     | 大约 1700 次编译器调用，23 分钟，就得到了一份 profile。                                                                        | 整个训练大约调用了 1700 次编译器，跑了 23 分钟。                                                                                                                        |
| wrong collocation                                        | 从 0.896 提升到了 0.794 (time) / 无从下手 / 速度是构建时间的一部分                                                             | 耗时比从 0.896 降到了 0.794 / 没法用 / 它本身快不快，很大程度上决定了构建要多久                                                                                         |

Also avoid: symmetric triplets for cadence, 「简单总结：」 bullet recaps,
over-bulleted prose, a one-line paragraph that only dramatizes the previous one.

## Before handing a draft over

- [ ] Every fact traceable to a source; inferences flagged to him.
- [ ] `scripts/md_format.py` clean apart from known false positives.
- [ ] Two subagent AI-ism passes and a fact-check pass merged; grep for 尾巴, 不是.\*而是, 一律, 从不,
      永远, 恰恰, 悄无声息, 所谓, 服务, 相同的字节, 意味着, 上一篇.
- [ ] Title promise delivered early; no FAQ or detail list that repeats the body.
- [ ] A long project post (like the xclang one) may open with a `> TL;DR：…`
      blockquote: what it is and what the reader gets, four or five sentences.
      Knowledge articles get none (he removed it from the ODR trial).
- [ ] Snapshot saved as he asked; short change summary with the diff command.

## Publishing on Zhihu

- **Ask about the cover first.** He wants a cover (an anime girl) before
  publishing; publishing without one went live too early once. An image with
  subtitles is cleaned with Codex image generation
  (`codex exec --skip-git-repo-check -s workspace-write --image=<file> -` with
  the prompt on stdin; `-i` swallows the prompt), then crop black bars.
- **Column**: `zhihu_cli.py publish` run non-interactively publishes with no
  column. Pass the column through the client
  (`ZhihuClient.create_or_update_article(path, article_id=None, column=<ZhihuColumn>)`);
  clice posts go to 「clice 开发日记」 (`c_1852831599382646784`). An update
  re-sends `titleImage` from `zhihu_title_image_url` in the front matter, so
  record the cover URL there before updating.
- **Rendering quirks**: two code blocks with nothing between them merge into
  one, so put a line of text between; a bare domain (`bazel.clice.io`) is
  auto-linked as `http://`, so write `[x](https://x)`; tables drop bold and
  inline code.
- **After publishing** he edits on Zhihu himself. Local drafts are not kept;
  `uv run python scripts/zhihu_cli.py sync` brings the article into
  `website/content/zh-cn/articles/<id>/` (and runs the repo formatters).
  Verify the live version by fetching it (`fetch_article_html` + `Parser`) and
  diffing against the draft.
