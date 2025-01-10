---
title: 'Recap of the St. Louis WG21 Meeting'
date: 2024-07-02 02:46:56
updated: 2024-07-02 03:35:56
---

Due to a series of coincidences, I had the opportunity to attend last week's WG21 meeting (the C++ Standards Committee meeting). Although I frequently browse new proposals for the C++ standard, I never imagined that one day I would actually participate in a WG21 meeting and get real-time updates on the latest developments in the C++ standard. Of course, this was my first time attending, and I was very excited. Here, I’ll document my impressions and the progress of the meeting.

## The Backstory

The story began in January of this year when I was pondering how to write an efficient `small_vector`. I referred to the LLVM source code and found that it specialized implementations for types that are trivially destructible, using bitwise copy for operations like expansion. At the time, I didn’t understand why this was possible. Later, I learned about the concept of trivially copyable and further delved into the concept of relocatable. After reading several related proposals, I wrote this [article](https://www.ykiko.me/zh-cn/articles/679782886) discussing trivially relocatable.

A few days later, a friend of mine, [blueloveTH](https://github.com/blueloveTH), asked if I could help write a lightweight `small_vector` for his project. This project is [pocketpy](https://github.com/pocketpy/pocketpy), a lightweight Python interpreter. I thought, what a coincidence! I had just researched this topic a few days prior, so I spent a few hours writing a very lightweight [small_vector](https://github.com/pocketpy/pocketpy/pull/208) that supports trivially relocatable optimizations. Coincidentally, this project is also the one I applied to participate in for this year’s GSoC.

On May 1st, I received two emails: one from the GSoC committee informing me that my application had been accepted, and the other from Arthur O'Dwyer, the author of P1144 (trivially relocatable). I was puzzled at first—why would he suddenly email me? We didn’t know each other. It turned out that he periodically searches for C++ projects related to trivially relocatable on GitHub and exchanges ideas with the authors. He found the code in pocketpy and thus sent us an email. He also seemed to have found my personal blog post discussing trivially relocatable [here](https://www.ykiko.me/zh-cn/articles/679782886/). We initially exchanged a few emails and later discussed some content of the proposal on Slack.

At the end of our discussion, he invited me to attend this WG21 meeting. The reason was that the current state of trivially relocatable in C++ is such that the committee is considering adopting an unreliable proposal, P2786, instead of the more comprehensive P1144. Arthur O'Dwyer hoped that supporters of P1144 could express their approval. Later, I sent an email to ISO applying to participate as a guest (guest) online. After three weeks without a reply, I almost thought I wouldn’t be able to attend. However, three days before the meeting, Herb Sutter finally replied, saying that he thought all emails had been replied to, but somehow mine was missed. He then informed me that my application had been approved and welcomed me to the meeting.

> There was a small hiccup here. During the opening event, Herb Sutter was counting the number of participating countries. The method was to call out each country one by one, and if someone was participating, they would raise their hand. When he called out China, I was a bit excited and couldn’t find the hand-raising button. Finally, when he noticed no one raised their hand, he mentioned that he remembered there was a Chinese participant in this meeting.

## How the C++ Standard Evolves

To make it easier to introduce the meeting progress later, let me briefly explain how the C++ committee operates.

![](https://picx.zhimg.com/v2-a137c1b90d4aaa8058e217cd136d736f_r.jpg)

C++ has 23 study groups, SG1 to SG23, each responsible for discussing different topics. For example, compile-time metaprogramming is discussed by SG7.

After a proposal is discussed and passed by a study group, depending on whether it pertains to language features or standard library features, it is reviewed by EWG (Evolution Working Group) or LEWG (Library Evolution Working Group). If approved, it is then submitted to CWG (Core Working Group) or LWG (Library Working Group) to refine the wording of the proposal so that it can be incorporated into the C++ standard.

Finally, proposals that pass CWG or LWG are voted on in a plenary session. If the vote passes, they are officially added to the C++ standard.

> The process of this St. Louis meeting was as follows: the opening event was on Monday morning. In the afternoon, each study group began discussing their respective agendas simultaneously. I mainly stayed in the EWG meeting room. Guests could participate in group voting but not in the final plenary session voting.

## Meeting Progress

First, let’s briefly discuss the proposals that were confirmed to pass, and then talk about the current progress of some important proposals.

## Passed Proposals

In terms of core language, the following proposals were passed:

- [constexpr placement new](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2024/p2747r2.html) supports directly using placement new to call object constructors during constant evaluation. Previously, only `std::construct_at` could be used, which is a specialized version of placement new with parentheses. For a detailed discussion on this, you can read my [blog](https://www.ykiko.me/zh-cn/articles/683463723) on the history of constexpr development.
- [deleting a pointer to an incomplete type should be ill-formed](https://wg21.link/P3144R2) Now, deleting a pointer to an incomplete type will result in a compilation error instead of undefined behavior.
- [ordering of constraints involving fold expressions](https://isocpp.org/files/papers/P2963R3.pdf) clarifies the partial ordering rules for constraints involving fold expressions.
- [structured binding declaration as a condition](https://wg21.link/P0963R3) Structured bindings can now be used in the condition of an if statement.

In terms of the standard library, the following proposals were passed:

- [inplace_vector](https://isocpp.org/files/papers/P0843R14.html) Note that inplace_vector is different from small_vector; the latter performs dynamic memory allocation when the SBO capacity is insufficient, while the former does not. It is equivalent to a dynamic array and can be conveniently used as a buffer.
- [std::is_virtual_base_of](https://wg21.link/P2985R0) Used to determine if a class is a virtual base class of another class.
- [std::optional range support](https://wg21.link/P3168R2) Supports range operations for optional.
- [std::execution](https://isocpp.org/files/papers/P2300R10.html) The long-debated std::execution has finally been included in the standard.

## Proposals with Significant Progress

I spent most of my time in the EWG meeting room, so I’ll mainly discuss some progress in core language aspects.

On Monday afternoon and all day Tuesday, EWG discussed Contracts. Compared to the last Tokyo meeting, some consensus was reached on certain disputes regarding Contracts, but there are still unresolved issues. Personally, I think the hope of including it in C++26 is still slim.

On Wednesday morning, EWG discussed Reflection for C++26. It was passed with 0 votes against (including my super favor vote) and handed over to CWG for wording revisions to be included in the C++ standard. On Thursday and Friday, CWG reviewed part of the content, but the proposal is too extensive and wasn’t fully reviewed. If everything goes smoothly, it is expected to be officially added to C++26 in two to three more meetings. The voting results show that everyone believes C++ needs reflection, and reflection is very likely to be included in C++26.

On Friday morning, EWG mainly discussed trivially relocatable. In previous meetings, [P2786](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2024/p2786r6.pdf) had already passed EWG voting and was handed over to CWG. However, it is not perfect and has many issues. Including such a proposal in the standard would undoubtedly be detrimental to the development of C++. Since the last Tokyo meeting, several new proposals discussing trivially relocatable have emerged:

- [Issues with P2786](https://wg21.link/p3233r0)
- [Please reject P2786 and adopt P1144 ](https://wg21.link/p3236r1)
- [Analysis of interaction between relocation, assignment, and swap](https://wg21.link/p3278r0)

Clearly, they all pointed fingers at P2786. After the authors of these proposals presented, a vote was needed to decide whether to return P2786 from CWG back to EWG, essentially reconsidering the trivially relocatable model that C++26 would adopt. In the end, P2786 was returned to EWG with an overwhelming majority. Of course, I voted super favor, as this was the main reason I attended this meeting. As for P1144, it might have to wait until the next meeting, as it wasn’t discussed this time.

The rest are some minor proposal progresses. Notably, many proposals related to constexpr passed EWG, including:

- [Less transient constexpr allocation](https://wg21.link/p3032r2)
- [Allowing exception throwing in constant-evaluation](https://wg21.link/p3068r2)
- [Emitting messages at compile time](https://wg21.link/p2758r3)

However, it’s still uncertain how likely they are to pass CWG. If you’re interested in the latest progress of a specific proposal, you can search for the proposal number in the ISO C++ GitHub [issues](https://github.com/cplusplus/papers/issues), where the latest progress of each proposal is recorded in detail.

## Some Personal Reflections

Now that the meeting progress is covered, let me share some personal reflections.

First, regarding the trivially relocatable vote, after voting, I suddenly felt a sense of guilt. The reason was that before the final vote, the author of P2786 said:

> If other people want to make modifications and bring forward their own paper, you know, as an author, I am not going to say, 'No, don't; it's my paper.' If it's a good change, you know, that's good.

I could clearly hear the emotion in his voice when he said this. Putting myself in his shoes, I can understand his feelings. He must have poured a lot of effort into this proposal, and having it withdrawn in such an unceremonious manner is hard to accept. But in reality, the author of P1144 has invested even more effort, with the proposal already at version R11, and the content itself is more comprehensive, yet it has been consistently overlooked. I find it hard to understand why this situation has arisen.

Another point is about the plenary session voting. The proposal [Structured Bindings can introduce a Pack](https://wg21.link/p1061r8), which supports introducing parameter packs in structured bindings:

```cpp
auto [x, ...pack] = std::tuple{1, 2, 3, 4};
```

It had already passed CWG, but during the plenary session, a compiler vendor pointed out that some examples in the wording of the proposal’s reference implementation could cause the compiler to crash. As a result, the plenary session vote did not pass.

A similar situation occurred with std::execution. Before the plenary session vote, someone pointed out that std::execution should not be included in C++26, as it is overly complex and not mature enough. The authors were merely theorizing without considering practical application scenarios. Additionally, heavy use of templates leads to very slow compilation speeds and frequent internal compiler errors. Although the final vote result was more in favor than against, the C++ committee emphasizes **consensus** rather than majority rule. A certain proportion must be reached for a proposal to pass, so theoretically, this proposal should not have passed this meeting. However, due to **certain reasons**, it was ultimately passed. I didn’t pay close attention to the specifics, so I can’t say for sure.

Honestly, attending this meeting didn’t yield much in terms of knowledge, but it did broaden my horizons. Some debates felt no different from online arguments. From each side’s perspective, both viewpoints are correct, which is reasonable. Not everything has a clear right or wrong, and many problems don’t have perfect solutions, especially in software engineering. To be included in the standard, compromises must be made. Where to compromise and who compromises to whom often involves intense debates and sometimes even factors outside the issue itself.

If I have the opportunity in the future, I might attend again, preferably in person. However, I definitely won’t attend every single meeting punctually like I did this time (it was my first time, so I was excited). I might mainly focus on the parts I’m interested in. I’m really looking forward to seeing reflection included in C++26.

That’s it for this article. Thank you for reading.