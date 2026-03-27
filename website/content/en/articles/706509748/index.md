---
title: St. Louis WG21 Meeting Review
date: "2024-07-01 18:46:56"
updated: "2024-07-01 19:35:56"
zhihu_article_id: "706509748"
zhihu_url: https://zhuanlan.zhihu.com/p/706509748
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

Due to a series of coincidences, I participated in last week's WG21 meeting (the C++ Standards Committee meeting). Although I often browse new proposals for the C++ standard, I never expected to one day actually attend a WG21 meeting and get real-time updates on the latest progress of the C++ standard. Of course, this was my first time attending, and I was very excited. I'm writing this to record my feelings and the progress of the meeting.

## How It Started

It all started this January when I was figuring out how to write an efficient `small_vector`. I looked at the LLVM source code for reference and found that it had a specialized implementation for types that are trivially destructible, using bitwise copy for operations like resizing. At the time, I didn't quite understand why this was possible. Later, I learned about the concept of `trivially copyable` and then the concept of `relocatable`. After reading a few related proposals, I wrote this [article](https://www.ykiko.me/en/articles/679782886) discussing `trivially relocatable`.

A few days later, a good friend of mine, [blueloveTH](https://github.com/blueloveTH), asked if I could write a lightweight `small_vector` for his project. The project is [pocketpy](https://github.com/pocketpy/pocketpy), a lightweight Python interpreter. I thought, what a coincidence! I had just been researching this very thing a few days ago. So, I spent a few hours and wrote a very lightweight [small_vector](https://github.com/pocketpy/pocketpy/pull/208) with support for `trivially relocatable` optimization. Coincidentally, this was also the project I applied to for this year's GSoC.

On May 1st, I received two emails. One was from the GSoC committee informing me that my application was accepted. The other was from Arthur O'Dwyer, the author of P1144 (trivially relocatable). I was very confused at the time. Why would he suddenly email me? I didn't know him at all. It turns out he regularly searches GitHub for C++ projects using the keyword `trivially relocatable` to exchange ideas with the project authors. He found the code in pocketpy, which is why he emailed us. It seems he also found the [article](https://www.ykiko.me/en/articles/679782886) on my personal blog discussing `trivially relocatable`. We had a brief exchange via email at first, and later we discussed some of the proposal's content on Slack.

At the end of our discussion, he invited me to attend this WG21 meeting. The reason was that the current situation for `trivially relocatable` in C++ was that the committee was planning to adopt a flawed proposal, P2786, instead of the more complete proposal, P1144. Arthur O'Dwyer hoped that we, as supporters of P1144, could express our approval. So, I wrote an email to ISO to apply to attend the meeting online as a guest. After three weeks with no reply, I was starting to think I wouldn't be able to attend. Then, three days before the meeting started, Herb Sutter finally replied to my email, saying he thought all emails had been answered but had somehow missed mine. He then said my application was approved and welcomed me to the meeting.

> There was a small mishap here. During the opening session, Herb Sutter was counting the number of participating countries. He did this by calling out each country, and attendees would raise their hands. When he called 'China,' I got a bit flustered and couldn't find the 'raise hand' button. In the end, when he saw no one raised their hand, he even commented that he was sure there was a participant from China in this meeting.

## How the C++ Standard Evolves

To make it easier to explain the meeting's progress later, I'll first briefly introduce how the C++ committee operates.

![](https://picx.zhimg.com/v2-a137c1b90d4aaa8058e217cd136d736f_r.jpg)

C++ has 23 study groups, from SG1 to SG23, each responsible for discussing different topics. For example, compile-time metaprogramming is discussed by the SG7 group.

After a proposal passes a study group, it is forwarded to either the EWG (Evolution Working Group) or the LEWG (Library Evolution Working Group) for review, depending on whether it concerns a language feature or a standard library feature. If the review is successful, it is then submitted to the CWG (Core Working Group) or LWG (Library Working Group) to refine the wording in the proposal so that it can be incorporated into the C++ standard.

Finally, proposals that pass CWG or LWG are voted on in a plenary session. If the vote passes, they are officially added to the C++ standard.

> The schedule for this St. Louis meeting was: opening session on Monday morning. In the afternoon, the various groups began discussing their respective agendas, all happening concurrently. I spent most of my time in the EWG meeting room. Guests are allowed to participate in group polls but cannot vote in the final plenary session.

## Meeting Progress

First, I'll briefly talk about the proposals that were confirmed to pass, and then discuss the current progress of some important proposals.

## Approved Proposals

For the core language, the main proposals that passed were:

- [constexpr placement new](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2024/p2747r2.html) supports using placement new directly in constant evaluation to call an object's constructor. Before this, one could only use `std::construct_at`, which is essentially a parenthesized version of placement new. For a detailed discussion on this, you can read my [blog post](https://www.ykiko.me/en/articles/683463723) on the history of `constexpr`.
- [deleting a pointer to an incomplete type should be ill-formed](https://wg21.link/P3144R2) deleting a pointer to an incomplete type will now result in a compile error instead of causing undefined behavior.
- [ordering of constraints involving fold expressions](https://isocpp.org/files/papers/P2963R3.pdf) clarifies the partial ordering rules for constraints involving fold expressions.
- [structured binding declaration as a condition](https://wg21.link/P0963R3) structured bindings can now be used in the condition of an `if` statement.

For the standard library, the main proposals that passed were:

- [inplace_vector](https://isocpp.org/files/papers/P0843R14.html) Note that `inplace_vector` is different from `small_vector`. The latter performs dynamic memory allocation when its SBO capacity is insufficient, while the former does not. It's like a dynamic array and can be conveniently used as a buffer.
- [std::is_virtual_base_of](https://wg21.link/P2985R0) used to determine if one class is a virtual base class of another.
- [std::optional range support](https://wg21.link/P3168R2) adds range support for `std::optional`.
- [std::execution](https://isocpp.org/files/papers/P2300R10.html) The long-debated `std::execution` has finally made it into the standard.

## Proposals with Significant Progress

I spent almost all my time in the EWG meeting room these past few days, so I'll mainly talk about some progress on the core language side.

On Monday afternoon and all of Tuesday, EWG was discussing Contracts. Compared to the last meeting in Tokyo, some consensus was reached on certain debates about Contracts, but there are still areas without consensus. I personally think the chances of it being included in C++26 are still slim.

On Wednesday morning, EWG discussed Reflection for C++26. It was ultimately passed with 0 votes against (including my own 'super favor' vote) and was forwarded to CWG for wording revisions to be included in the C++ standard. On Thursday and Friday, CWG reviewed a portion of the content, but the proposal is too large to be finished. If all goes well, it is expected to be officially added to C++26 after two or three more meetings. The voting results show that everyone believes C++ needs reflection, and it has a very high chance of being included in C++26.

On Friday morning, EWG mainly discussed `trivially relocatable`. In a previous meeting, [P2786](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2024/p2786r6.pdf) had already passed the EWG vote and was forwarded to CWG. However, it is incomplete and has many issues. Adding such a proposal to the standard would undoubtedly be detrimental to the development of C++. Since the last Tokyo meeting, several new proposals discussing `trivially relocatable` have emerged:

- [Issues with P2786](https://wg21.link/p3233r0)
- [Please reject P2786 and adopt P1144 ](https://wg21.link/p3236r1)
- [Analysis of interaction between relocation, assignment, and swap](https://wg21.link/p3278r0)

Clearly, they all took aim at P2786. After the authors of these proposals gave their presentations, a vote was held to decide whether to return P2786 from CWG to EWG, which means reconsidering the `trivially relocatable` model for C++26. In the end, P2786 was returned to EWG by an overwhelming majority. Of course, I voted 'super favor,' as this was the main reason I attended the meeting. As for P1144, we'll probably have to wait for the next meeting; it wasn't discussed this time.

The rest is progress on some smaller proposals. It's worth mentioning that many `constexpr`-related proposals passed EWG, namely:

- [Less transient constexpr allocation](https://wg21.link/p3032r2)
- [Allowing exception throwing in constant-evaluation](https://wg21.link/p3068r2)
- [Emitting messages at compile time](https://wg21.link/p2758r3)

However, it's hard to say what their chances are of passing CWG later. If you're interested in the latest progress of a specific proposal, you can just search for the proposal number in the [issues](https://github.com/cplusplus/papers/issues) on the ISO C++ GitHub, which will have detailed records of its latest progress.

## Some Impressions

That's it for the meeting progress. Now, I'd like to share some of my personal feelings.

First, regarding the vote on `trivially relocatable`, I actually felt a sudden sense of guilt after casting my vote. The reason is that before the final vote, the author of P2786 said:

> if other people want to make modifications and bring forward their own paper, you know, as an author, I am not going to say, 'No, don't; it's my paper.' If it's a good change, you know, that's good.

I could clearly hear his voice was trembling as he said this. Putting myself in his shoes, I think I can understand his feelings. He must have poured a lot of effort into this proposal, and having it withdrawn in such a dishonorable way is hard to accept. But in reality, the author of P1144 put in even more effort; the proposal is already at version R11 and is more complete, yet it has been consistently ignored. I find it hard to understand why this situation occurred.

Another thing was the situation during the plenary vote for the proposal [Structured Bindings can introduce a Pack](https://wg21.link/p1061r8), which is about introducing parameter packs in structured bindings:

```cpp
auto [x, ...pack] = std::tuple{1, 2, 3, 4};
```

It had already passed CWG, but during the plenary session, a compiler vendor pointed out at the last minute that some examples in the wording would cause a compiler crash with the proposal's reference implementation. As a result, it failed the final plenary vote.

A similar situation happened with `std::execution`. Before the plenary vote, someone argued that `std::execution` should not be added to C++26, claiming it is too complex and not mature enough, that the authors were just talking in the abstract without considering practical application scenarios. Furthermore, its heavy use of templates leads to very slow compilation speeds and frequently causes internal compiler errors. Although the final vote had more in favor than against, the C++ committee emphasizes achieving **consensus**, not simple majority rule. The ratio has to reach a certain threshold to pass. So, logically, the proposal shouldn't have passed in this meeting, but it did for **certain reasons**. I'm not sure about the exact details, as I wasn't paying close attention at that moment, so it's hard for me to say.

To be honest, I didn't gain much in terms of knowledge from attending this meeting, but I certainly broadened my horizons. Some of the debates felt no different from online arguments. From their respective perspectives, both sides' views are correct, which is reasonable. Not everything has an absolute right or wrong, and many problems don't have a perfect solution, especially in the field of software engineering. So, to get into the standard, compromises must be made. But where to compromise, and who compromises for whom? This is often accompanied by heated debates and is sometimes even decided by other external factors (outside of the issue itself).

If I have the chance in the future, I might attend again, preferably in person. But I definitely won't be attending every single session on time every day like I did this time (I was a bit too excited for my first time). I'll probably just listen in on the parts that interest me. I really, really want to see the moment reflection gets into C++26.

Alright, that's the end of the article. Thanks for reading.
