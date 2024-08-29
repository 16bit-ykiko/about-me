---
title: 'St. Louis WG21 会议回顾'
date: 2024-07-01 18:46:56
updated: 2024-07-01 19:35:56
---

因为某些机缘巧合参与了上周的 WG21 会议（C++ 标准委员会会议）。虽然我经常浏览 C++ 标准的新提案，但是确实没想到有一天真的能参加 WG21 会议，实时了解 C++ 标准的最新进展。当然，这也是第一次参加，非常激动，在这里记录一下自己的感受和会议的进展。

## 起因 

事情的起因是，今年一月份，当时我正在琢磨怎么写一个高效的`small_vector`。去参考了下 llvm 的源码，发现里面对满足 trivially destructible 的类型特化了实现，采用 bitwise copy 进行扩容之类的操作。当时不太理解为什么呢能这么做呢。后来了解到 trivially copyable 这个概念，进一步了解到了 relocatable 的概念。又阅读了几篇相关的提案，于是就有了这篇讨论 trivially relocatable 的 [文章](https://www.ykiko.me/zh-cn/articles/679782886)。

没过几天，我的的一个好友 [blueloveTH](https://github.com/blueloveTH) ，他就问我能不能帮他的项目写一个轻量级的`small_vector`呢？这个项目就是 [pocketpy](https://github.com/pocketpy/pocketpy)，一个轻量级的 Python 解释器。那我一想，这不巧了吗，我前几天刚刚研究过这个东西，于是花了几个小时就写好了一个支持 trivially relocatable 优化的非常轻量的 [small_vector](https://github.com/pocketpy/pocketpy/pull/208)。很巧的是，这个项目也是我今年 GSoC 申请参加的项目。

五月一号那天，我收到了两封邮件，一份是 GSoC 委员会告知申请通过的邮件。另一份就是来自 P1144(trivially relocatable) 作者 Arthur O'Dwyer 的邮件。我当时很困惑，他怎么突然给我发邮件呢，我和他并不认识啊。原来他会在 Github 上定期使用 trivially relocatable 作为关键字搜索相关的 C++ 项目，并和项目的作者交流一些想法。因为搜索到了 pocketpy 里面的代码，所以就给我们发了邮件，他好像也搜到了我个人博客中那篇讨论 trivially relocatable [文章](https://www.ykiko.me/zh-cn/articles/679782886/)。一开始通过邮件简单的交流了一下，后来我们又在 slack 上讨论了提案里面的一些内容。

在讨论结束的时候，他邀请我参加这次的 WG21 会议。原因是当时 C++ 中关于 trivially relocatable 现状是，委员会打算采用一个不靠谱的提案 P2786，而不是更完整的提案 P1144。Arthur O'Dwyer 希望我们这些 P1144 的支持者，能表达一些赞成。后来我就写了一封邮件给 ISO 申请作为游客 (guest) 线上参与会议，过了三个星期都没回复，我本来都快以为参加不了了。结果在会议开始前三天，Hurb Sutter 终于给我回复了一封邮件说：他以为所有的邮件都已经回复了，但不知怎么的忘记了我的，然后说我的申请通过了，欢迎参与会议。

>  这里有一点小乌龙，后来在开幕活动的时候 Hurb Sutter 在统计参与的国家个数。具体方式就是一个个国家喊，有参与的话就举个手。喊到 China 的时候，我有点激动，一直没找到举手键。最后，他发现没有人举手的时候还说，他明明记得这次会议有中国人参与的。 

## C++ 标准演进方式 

为了之后方便介绍会议进展，先简单介绍一下 C++ 委员会的运作方式。

![](https://picx.zhimg.com/v2-a137c1b90d4aaa8058e217cd136d736f_r.jpg)

C++ 有 SG1~SG23 一共 23 个研究小组，分别负责讨论不同的主题。例如编译时元编程就是由 SG7 小组负责讨论的。

在小组讨论通过之后，根据提案内容是有关语言特性还是标准库特性，分别交给 EWG(Evolution Working Group) 和 LEWG(Library Evolution Working Group) 进行审核。如果审核通过，再进一步提交给 CWG(Core Working Group) 和 LWG(Library Working Group) 来修正提案中的相关措辞，使得其能纳入到 C++ 标准中。

最后，通过 CWG 或 LWG 的提案会在全体会议上 (plenary) 进行投票，如果投票通过，就会正式加入到 C++ 标准中。

>  这次 St. Louis 会议的流程是，周一早上开幕活动。下午的时候，各小组就开始分别讨论自己的议程了，都是同时进行的。而我主要待在 EWG 会议室里面，然后 guest 是可以参与小组投票的，但是不能参与最后的全体会议投票。 

## 会议进展 

先简单说说确定通过的提案，然后谈谈一些重要提案现在的进展。

## 通过的提案 

核心语言方面主要通过了下面这几个提案：

- [constexpr placement new](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2024/p2747r2.html) 支持在常量求值中直接使用 placement new 来调用对象的构造函数，在此之前只能使用`std::construct_at`，而它相当于于 placement new 的一个小括号特化版本。关于这一点的详细讨论，可以阅读一下我这篇介绍 constexpr 发展史的 [博客](https://www.ykiko.me/zh-cn/articles/683463723)
- [deleting a pointer to an incomplete type should be ill-formed](https://wg21.link/P3144R2) 现在 delete 一个不完整类型的指针会直接编译错误，而不是导致未定义行为
- [ordering of constraints involving fold expressions](https://isocpp.org/files/papers/P2963R3.pdf) 明确了涉及到折叠表达式的约束的偏序规则
- [structured binding declaration as a condition](https://wg21.link/P0963R3) 结构化绑定现在可以用于 if 语句的条件中


标准库方面主要通过了下面这几个提案：

- [inplace_vector](https://isocpp.org/files/papers/P0843R14.html) 注意 inplace_vector 与 small_vector 不同，后者在 SBO 的容量不足的时候会进行动态内存分配，而前者则不会。它相当于一个 dynamic array，可以方便的当做 buffer 使用。
- [std::is_virtual_base_of](https://wg21.link/P2985R0) 用于判断一个类是否是另一个类的虚基类
- [std::optional range support](https://wg21.link/P3168R2) 支持 optional 的 range 操作
- [std::execution](https://isocpp.org/files/papers/P2300R10.html) 争论了很久的 std::execution 终于进入标准


## 有重大进展的提案 

这几天我基本上一直待在 EWG 会议室，所以就主要说说核心语言方面的一些进展。

周一下午和周二一整天，EWG 都在讨论 Contract。相比于上次的 Tokyo 会议，就 Contract 的某些争论达成了一些共识，但是仍然还有没有达成共识的地方。我个人认为加入 C++26 的希望仍然不大。

周三上午，EWG 在讨论 Reflection for C++26。最后以 0 票反对的结果（其中也有我的一票 super favor）通过，移交给 CWG 进行措辞的修改以纳入 C++ 标准。周四和周五 CWG 已经 review 了一部分内容，但是提案内容太多了，没有 review 完。如果一切顺利的话，预计再过两到三次会议可以正式加入 C++26。从投票结果可以看出，所有人都认为 C++ 需要反射，反射非常有希望加入 C++26。

周五上午，EWG 主要在讨论 trivially relocatable。在之前的会议中 [P2786](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2024/p2786r6.pdf) 已经通过了 EWG 投票被移交给 CWG 了。然而，它并不完善，有很多问题，这样的提案加入标准无疑是对 C++ 发展有害的。自上次 Tokyo 会议之后，出现几份新的讨论 trivially relocatable 的提案：

- [Issues with P2786](https://wg21.link/p3233r0)
- [Please reject P2786 and adopt P1144 ](https://wg21.link/p3236r1)
- [Analysis of interaction between relocation, assignment, and swap](https://wg21.link/p3278r0)


显然，它们都把矛头指向了 P2786。在这几份提案作者演讲结束后，需要投票来决定是否要将 P2786 从 CWG 返回到 EWG，也就是重新考虑 C++26 将会采用的 trivially relocatable 模型。最后以压倒性的优势，P2786 被返回到了 EWG，当然我投的是 super favor，毕竟这就是我参加这次会议的主要目的。至于 P1144，可能要等下次会议了，这次会议并没有讨论它。

剩下的就是一些小的提案进展了，值得一提的是有许多有关 constexpr 的提案都通过了 EWG，它们分别是：

- [Less transient constexpr allocation](https://wg21.link/p3032r2)
- [Allowing exception throwing in constant-evaluation](https://wg21.link/p3068r2)
- [Emitting messages at compile time](https://wg21.link/p2758r3)


但是之后通过 CWG 的希望有多大还不好说。如果对某个提案的最新进展感兴趣的话，直接在 ISO C++ Github 的 [issues](https://github.com/cplusplus/papers/issues) 里面搜索提案号就可以了，里面会详细记录对应提案的最新进展。

## 一些感受 

会议进展说完了，现在来说说个人的一些感受。

首先就是关于 trivially relocatable 的投票，其实在投完之后，我突然有一种负罪感。原因是，在最后的投票之前 P2786 的作者说：

>  if other people want to make modifications and bring forward their own paper, you know, as an author, I am not going to say, 'No, don't; it's my paper.' If it's a good change, you know, that's good. 

我可以明显听出他说这段话的时候是带着哭腔的。换位思考一下，我想我也可以理解他的心情，他肯定倾注了很多心血在这份提案上，以如此不光彩的方式撤回提案实在是让人难以接受。但其实 P1144 的作者付出了更多心血，提案版本都已经出到了 R11，内容本身也更完善，但却一直被忽视。我很难理解为什么会出现这样的局面。

另外就是全体会议投票上的一些情况，[Structured Bindings can introduce a Pack](https://wg21.link/p1061r8) 这个提案，也就是支持结构化绑定的时候引入参数包

```cpp
auto [x, ...pack] = std::tuple{1, 2, 3, 4};
```

本来它都通过 CWG 了，但在全体会议上，一位编译器供应商临时指出了措辞中的某些示例在该提案中的参考实现会导致编译器崩溃。于是最后全体会议投票就没有通过。

类似的情况发生在 std::execution 上，在全体会议投票之前，有人指出 std::execution 不应该加入 C++26，它过于复杂且不够成熟，作者们只是在空谈，没有考虑过实际的应用场景。此外，重度使用模板导致编译速度十分缓慢，经常造成编译器 internal compiler error。虽然最后投票的结果是赞同大于反对，但是 C++ 委员会强调的是达成**共识 (consensus)**，而不是少数服从多数，比例要达到一定程度才算通过，所以按理说该提案这次会议是不该通过的，但是最后由于**某些原因**还是通过了。具体咋回事，我当时没太注意听，也不太好说。

说实话，这次参会，知识性的收获不多，见识倒是涨了不少。有些争论我感觉和平常网络上对线也没啥区别，从各自的角度来看，双方的观点都是对的，这也很合理，不是所有的事情都有绝对的对与错，很多问题都没有一个完美的解决方案，在软件工程领域尤其如此。那为了加入标准，总要做出一些妥协，究竟在哪些地方妥协，谁向谁妥协呢？往往伴随着一些激烈的争论，甚至由一些其它的场外（问题本身之外）的因素决定。

之后如果有机会的话可能还会继续参加，最好能线下参加一次。不过肯定不会像这次会议一样，几乎每天都准时准点的出席每一场会议了（第一次参加有点激动）。可能主要听听感兴趣的部分，我实在太想看到反射进入 C++26 的那一刻了

好了，到这里文章就结束了，感谢阅读。