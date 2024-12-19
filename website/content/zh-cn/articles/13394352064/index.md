---
title: '一个新 C++ language server 的设计与实现'
date: 2024-12-18 13:46:01
updated: 2024-12-18 15:50:22
series: ['clice dev diary']
series_order: 1
---

距离上一次发布博客已经过去几个月了，之所以这么久没有更新呢，是因为我这段时间一直忙于 [clice](https://github.com/clice-project/clice) —— 一个全新的 C++ 语言服务器 (language server)。

可能有的读者对语言服务器这个概念有些陌生。不过你肯定使用过 IDE，比如 Visual Studio 或者 CLion，体验过这些 IDE 提供的代码补全、跳转、重构等功能。在传统的 IDE 中，上述特性是由 IDE 的插件或者内置功能实现的，这种方式导致每种语言需要为每个编辑器单独开发支持，维护成本很高。而当初微软在发布 Visual Studio Code 时，希望能解决这个问题，于是提出了 [LSP(Language Server Protocol)](https://microsoft.github.io/language-server-protocol/) 这个概念。LSP 提出了标准的客户端-服务器模型。语言功能由一个独立的语言服务器提供，VSCode 只需要实现一个通用的客户端，与语言服务器通信即可。这种方法解耦了编辑器和语言支持，使得 VSCode 能轻松支持多种语言。例如，你想要查看一个`method`的`implementation`，那么你的编辑器就会向语言服务器发送一个`go to implementation`的请求，请求的具体内容呢，可能就是文件的路径和当前光标在源文件中的位置。语言服务器会对这个请求进行处理，同样返回给你一个文件位置一个坐标，编辑器从而根据这个结果打开对应的文件进行跳转。

clice 就是这样一个语言服务器，用于处理 C/C++ 相关代码的请求。这个名字来源于我的头像 alice，把首字母替换为代表 C/C++ 的 c 就得到了 clice。

经过了几个月的设计和开发，项目已经颇具雏形，但是预计离投入使用还需要几个月的时间来进行完善。这篇文章的主要内容是对 clice 的设计和实现进行介绍，也是我个人对于当前开发的一个阶段性总结。虽然是语言服务器相关的内容，但其实涉及到大量 C/C++ 编译相关知识的科普，感兴趣的读者可以继续往下阅读。

同时，如果你有任何功能上的请求/建议，欢迎评论区留言讨论。在下一阶段的开发中，我会尽可能考虑它们。

## Why a new language server? 

那么第一个问题，为什么要去开发一个新的语言服务器？重复造轮子有必要吗？

这个问题值得去认真回答。在这个项目之前，我自己也编写过或大或小的很多项目。但它们绝大多数都是 toy project，只是为了验证某个想法或者个人学习而编写的，并没有解决任何的实际问题。clice 并不是这样的，它确实打算解决现有的问题（具体的问题后面再说），而不是为了重写而重写。

在今年年初，我想参与到 llvm 项目的开发中。我想从我较为熟悉的地方，C++，也就是 clang 开始。但是，没需求的话，总不能干瞪源码吧。一般这种时候的正常流程是从一些 first issue 开始，一点点熟悉项目。但是我觉得这样很无聊，一上来我就想来干点大的，比如实现某个 C++ 新标准的特性。但是，我发现这里几乎没有我能插手的地方，新特性的实现几乎总是由几位 clang 的核心开发者完成。好吧，既然这里没什么机会，那就看看别的地方吧。注意力自然而然的转移到了 clangd 身上去了，毕竟我主要使用 vscode 进行开发，而 vscode 上最好用的 C++ 语言服务器就是 clangd 了。

当时我对 clangd 一无所知，只是发现它似乎对关键字的高亮渲染并不正确。然后呢我就开始一边阅读 clangd 的源码，一边翻翻 clangd 数量众多的 issue 看看有没有什么我能解决的。在翻了几百个 issue 过后，我发现这里的问题还真不少。当时我特别感兴趣的是一个有关模板内代码补全的 [issue](https://github.com/clangd/clangd/issues/443)，为什么我对这个感兴趣呢？熟悉我的读者可能知道，我算是一个资深的元编程玩家了，在这之前也写过很多相关的文章。那很自然的，我不仅仅好奇模板元它本身是如何运作的，也好奇 clang 作为一个编译器是如何实现相关的特性的，这个 issue 对我来说是一个很好的切入点。在花了几个星期摸索原型实现后，我初步解决了那个 issue，**但是，这时我发现根本没有人可以 review 相关的代码**！

一番调查过后，我发现 clangd 目前的情况很糟糕。让我们来捋一捋时间线，clangd 最初只是 llvm 内部一个简单的小项目，在功能性和易用性上都不出色。正如 MaskRay 在 [ccls](https://maskray.me/blog/2017-12-03-c++-language-server-cquery) 中的这篇博客中所说，clangd 在当时只能处理单个编译单元，跨编译单元的请求无法处理。这篇博客发布的时间是 2017 年，这也是为什么 MaskRay 选择编写 ccls 的一个原因。ccls 也是一个 C/C++ 语言服务器，在当时那个节点上是强于 clangd 的。但是，后来，Google 开始派人对 clangd 进行改进以满足他们内部的大型代码库需求。与此同时，LSP 标准的内容也在不断地扩充，clangd 在不断地跟进新标准的内容，但是 ccls 的作者似乎逐渐忙于其它事情没有太多的时间去维护 ccls。于是最后，总体上 clangd 已经超越了 ccls。事情的转折发生在大概 2023 年，clangd 对 Google 内部来说，似乎已经达到了一个高度可用的状态，原先负责 clangd 的几位员工也被调离去做其他事情了。目前来说，clangd 的 issue 主要只有  [HighCommander4](https://github.com/HighCommander4) 一个人在负责处理，纯粹出于热爱，并没有被任何人雇佣。由于并没有被专门雇佣来维护 clangd，所以他只能在有限的空闲时间来处理 issue，而且也仅限于答疑和十分有限的 review。正如他在这条 [评论](https://github.com/clangd/clangd/issues/1690#issuecomment-1619735578) 中提到的一样：

> The other part of the reason is lack of resources to pursue the ideas we do have, such as the idea mentioned above of trying to shift more of the burden to disk usage through more aggressive preamble caching. I'm a casual contributor, and the limited time I have to spend on clangd is mostly taken up by answering questions, some code reviews, and the occasional small fix / improvement; I haven't had the bandwidth to drive this type of performance-related experimentation.<br><br>另一部分原因是缺乏资源去实践我们已有的一些想法，例如上面提到的通过更积极的预编译缓存，将更多的负担转移到磁盘使用上的想法。我只是一个非正式的贡献者，我能投入到 clangd 上的时间非常有限，主要用于回答问题、进行一些代码审查以及偶尔的小修复或改进；我没有足够的精力来推动这种与性能相关的实验。 

既然如此，那么像为 clangd [初步支持 C++20 module](https://github.com/llvm/llvm-project/pull/66462) 这样的大型 PR 被拖了将近一年也就不奇怪了。意识到这个现状之后，我萌生了自己编写一个语言服务器的想法。我估计了一下项目大小，去除测试代码，大概 2w 行就能完成，是一个人花一段时间能完成的工作量，而且也有先例，例如 ccls 和 rust analyzer。另外一点就是 clangd 的代码已经上了年代了，尽管有非常多的注释，但是相关的逻辑仍然很绕，进行大范围修改所花费的时间可能还不如重写来得快。

于是说干就干，我对 clangd 的几百个 issue 进行了分类，看看有没有一些问题是因为 clangd 一开始的架构设计错误而导致很难解决，然后被搁置的。如果有的话，是否能在重新设计的时候就考虑这个问题来解决呢？我发现，确实有一些！于是接下来的时间里，我花了大概两个月的时间来学习研究 clang 里面相关的机制，摸索相关问题的解决方法，探索原型实现，在确定相关的问题基本都可以解决之后，正式开始了 clice 的开发。

## Important improvement 

前面说了那么多，还是先来看看 clice 到底解决了 clangd 中现存的哪些重大问题。主要侧重于功能介绍，至于实现原理会放在 Design 小节。除了这些重要的改进之外，当然也还有很多小功能上的的改进，这里就不一一列出了。

### Better template support 

那首先，就是更好的模板支持，这也是我最开始想要 clangd 支持的特性。具体来说目前在处理模板上有什么问题呢？

以代码补全为例，考虑如下的代码，`^`代表光标位置：

```cpp
template <typename T>
void foo(std::vector<T> vec) {
    vec.^
}
```

在 C++ 中，如果一个类型依赖于模板参数，那么在模板实例化之前，我们并不能对它做出任何准确的假设。例如这里的`vector`即可能是主模板也可能是`vector<bool>`的偏特化，选哪一个呢？对于代码编译来说，准确性永远是最重要的，不能使用任何可能导致错误的结果。但是对于语言服务器来说，提供更多可能的结果往往比什么都不提供更好，我们可以假设用户在更多时候使用主模板而不是偏特化，从而基于主模板来提供代码补全的结果。目前 clangd 也确实是这么做的，在上述情况下它会根据`vector`的主模板为你提供代码补全。

再考虑一个更加复杂的例子：

```cpp
template <typename T>
void foo(std::vector<std::vector<T>> vec2) {
    vec2[0].^
}
```

从用户的角度来说，这里也应该提供补全，毕竟`vec2[0]`的类型不也是`vector<T>`吗？和前面一个例子一样。但是 clangd 在这里却不会为你提供任何补全，问题出在哪里？根据 C++ 标准，`std::vector<T>`的`operator[]`返回的类型是`std::vector<T>::reference`，这其实是一个 [dependent name](https://en.cppreference.com/w/cpp/language/dependent_name)，它的结果似乎相当直接，就是`T&`。但是 libstdc++ 中它的定义却嵌套了十几层模板，似乎是为了兼容旧标准？那为什么 clangd 不能处理这种情况呢？

1. 它基于主模板假设，不考虑偏特化可能会使查找无法进行下去
2. 它只进行名称查找而不进行模板实例化，就算找到了最后的结果，也没法把它和最初的模板参数映射起来
3. 不考虑默认模板参数，无法处理由默认模板参数导致的依赖名


尽管我们可以对标准库的类型开洞来提供相关的支持，但是我希望用户的代码能和标准库的代码有相同的地位，那么我们就需要一种通用的算法来处理依赖类型。为了解决这个问题，我编写了一个伪实例化器（pseudo instantiator）。它能在没有具体类型的前提下对依赖类型进行实例化，从而达到化简的目的。比如上面这个例子里面的`std::vector<std::vector<T>::reference`就能被化简为`std::vector<T>&`，进一步就能为用户提供代码补全选项。

### Header context 

为了让 clangd 正常工作，用户往往需要提供一份`compile_commands.json`文件（后文简称 CDB 文件）。C++ 的传统编译模型的基本编译单元是一个源文件（例如`.c`和`.cpp`文件），`#include`只是把头文件的内容粘贴复制到源文件中对应的位置。而上述 CDB 文件里面就储存了各个源文件对应编译命令，当你打开一个源文件的时候，clangd 会使用其在 CDB 中对应的编译命令来编译这个文件。

那很自然的就有一个疑问，如果 CDB 文件里面只有源文件的编译命令，没有头文件的，那么 clangd 是如何处理头文件的呢？clangd 会把头文件当做一个源文件进行处理，然后呢，根据一些规则，比如使用对应目录下的源文件的编译命令作为该头文件的编译命令。这样的模型简单有效，但是却忽略了一些情况。

由于头文件是源文件的一部分，那么就会出现它的内容根据它在源文件中前面的内容不同而不同的情况。例如：

```cpp
// a.h
#ifdef TEST
struct X { ... };
#else
struct Y { ... };
#endif

// b.cpp
#define TEST
#include "a.h"

// c.cpp
#include "a.h"
```

显然，`a.h`在`b.cpp`和`c.cpp`中具有不同的状态，一个定义了`X`，一个定义了`Y`，如果简单的把`a.h`当做一个源文件进行处理，那么就只能看得到`Y`。

一个更极端的情况是 non-self-contained 头文件，例如：

```cpp
// a.h
struct Y { 
    X x;
};

// b.cpp
struct X {};
#include "a.h"
```

`a.h`自身不能被编译，但是嵌入到`b.cpp`中的时候就编译正常了。这种情况下 clangd 会在`a.h`中报错，找不到`X`的定义。显然这是因为它把`a.h`当成一个独立的源文件了。在 libstdc++ 中的代码中就有很多这样的头文件，现在流行的一些 C++ 的 header-only 的库也有些有这样的代码，clangd 目前无法处理它们。

clice 将会支持**头文件上下文 (header context)**，支持自动和用户主动切换头文件的状态，当然也会支持非自包含的头文件。我们想要实现如下的效果，以最开始那份代码为例。当你从`b.cpp`跳转到`a.h`的时候使用`b.cpp`作为`a.h`的上下文。同理，当你从`c.cpp`跳转到`a.h`的时候则使用`c.cpp`作为`a.h`的上下文。

### Fully C++20 module support 

C++20 引入了 [module](https://en.cppreference.com/w/cpp/language/modules) 这个新特性，用于加速编译。与传统的编译模型不同，模块单元之间可能具有依赖关系。这要求我们进行一些额外的处理，尽管为 clangd 初步支持`module`的 PR 已经合并了，但它处于相当早期的状态。

1. 不同文件之间不会共享预编译的模块，这导致了模块的重复编译
2. 其它配套的 LSP 设施没有及时跟进，比如为模块名提供高亮和跳转，还有提供类似头文件的补全
3. 只支持 clang 不支持其它的编译器


clice 将会提供编译器和构建系统无关的 C++20 module 支持，项目本身之后也会完全迁移到 module 上。

### Better index format 

有一些 ccls 的用户可能会抱怨，明明同样是预先索引整个项目。ccls 可以在打开文件的瞬间进行跳转，但是 clangd 仍需要等待文件解析完成才行。为什么会造成这种结果？这其实是 clangd 的索引格式设计缺陷导致的。什么是索引？由于 C/C++ 支持向前声明，于是声明和定义可能在不同的源文件，于是我们需要处理跨编译单元的符号关系。

但是解析文件是一个相当耗时的操作，如果等到需要查询的时候再去解析文件，那么查询的时间将会是一个天文数字。为了支持快速查找符号关系，language server 一般会索引整个项目。但是究竟采用何种格式储存相关的数据？这个并没有标准规定。

clice 充分参考了现有的索引设计，设计了一种更加高效的索引格式。也可以达到 ccls 的效果，如果预先索引了项目，不需要等待就能立马获取响应。

## Design 

这一小节将会更加具体的谈谈 clice 的设计与实现。

### Server 

首先 language server 也是一个 server，在这方面和一个传统的服务器没什么区别。使用事件驱动的编程模型，接受服务器的请求并进行处理。由于可以使用 C++20，那当然要体验一下使用无栈协程来进行异步编程了。clangd 的代码中有大量的回调函数，这部分代码可读性相当差。使用无栈协程可以避免类似的回调地狱出现。

比较值得注意的是，在库的选取方面，并没有选择现成的协程库，而是自己使用 C++20 的协程设施对 libuv 封装出了一个简单的协程库。原因有以下几点：

- llvm 项目是不使用异常的，我们尽量和它保证一致，直接封装 C 语言的库可以让我们更好的控制这一点
- language server 的事件模型相当简单，一对一连接。在主线程处理 IO 相关的请求，线程池负责耗时任务执行就完全足够了。在这个模型下，甚至不需要使用任何锁这样的同步原语来进行线程间通信。所以一般的网络库的模型对于 clice 来说过于复杂了


最后也成功在 C++ 中复刻类似 Python 和 JS 中的异步编程体验，非常的愉快和轻松。

### How it works? 

接下来我们来详细谈谈，clice 是如何处理某些特定的请求的。

首先当用户在编辑器中打开或者更新某个文件的时候，编辑器会发送相关的通知给 clice。clice 在收到请求后，会 parse 该文件。更具体的来说，会将该文件 parse 成 AST(Abstract Syntax Tree)。由于 C++ 的语法相当复杂，靠自己手写一个 parser 是不现实的，我们和 clangd 一样选择使用 clang 提供的接口来 parse 源文件。

在获取 AST 之后，对 AST 进行遍历收集我们感兴趣的信息即可。以`SemanticTokens`为例，我们需要遍历 AST 去为源码中的每个 token 添加语义信息，是`variable`还是`function`？是不是`const`？是不是`static`？等等。总之一切这些信息都可以从 AST 中获取。想要对这个有更深入理解的话，可以阅读我之前写过的一个关于 clang AST 的入门 [文章](https://www.ykiko.me/zh-cn/articles/669360731)。

绝大多数请求都可以通过类似上述的方式实现，比较特殊的是代码补全（CodeCompletion）和签名帮助（SignatureHelper）。由于补全点的语法可能并不完整，在常规的编译流程中，如果语法节点不完整，clang 可能会直接把它当做一个错误节点，甚至整个丢掉，又或者直接 fatal error 终止编译。无论如何，都是我们不能接受的。一般来说，为了实现代码补全的功能，需要 parser 开洞进行特殊的处理。clang 也不例外，它提供了一个特殊的 code completion 模式，通过继承`CodeCompleteConsumer`并重写其中相关的方法来获取相关的信息。

可以通过一个特殊的编译选项来体验这一功能：

```bash
-std=c++20  -fsyntax-only -Xclang -code-completion-at="example.cpp:1:3"
```

假设源文件是

```cpp
con
```

则预期输出是

```cpp
COMPLETION: const
COMPLETION: consteval
COMPLETION: constexpr
COMPLETION: constinit
```

可以发现结果就是四个 C++ 关键字的补全，并且没有任何的错误警告。

嗯，这就是整个流程了，是不是听起来相当简单。的确，这部分遍历 AST 的逻辑是相当清晰的。只是有很多 corner case 需要考虑，只需要慢慢堆时间实现功能然后慢慢迭代修 BUG 就行了。

### Incremental compilation 

由于用户可能频繁变更文件，如果每次都需要重新 parse 整个文件，当文件非常大的时候，parse 时间会非常慢，响应请求时间会非常长（考虑到`#include`就是粘贴复制，很容易就可以造出一个巨大的文件）。想象一下，如果写按下一个字母，过了几秒钟代码补全结果才出来，那么体验将会多么糟糕！

怎么办呢？答案就是增量编译 (Incremental Compilation)。也许你在学习 cmake 等构建工具的时候听说过这个词，但是它们是有一些区别的。构建工具所指的增量编译粒度是一个文件，只重新编译有变更的文件。但显然这对我们来说是不够的，LSP 的最基本请求单位就是文件，我们需要更细粒度的增量编译。

clang 提供了一种叫做 [Precompiled Header(PCH)](https://clang.llvm.org/docs/UsersManual.html#usersmanual-precompiled-headers) 的机制，可以用于将某一段代码在编译成 AST 之后序列化到磁盘上，然后在之后编译的时候进行复用。

例如

```cpp
#include <vector>
#include <string>
#include <iostream>

int main() {
    std::vector<int> vec;
    std::string str;
    std::cout << "Hello, World!" << std::endl;
}
```

我们可以将该文件代码的前三行编译成 PCH 缓存起来，这样即使用户频繁修改文件内容，但是只要不修改前三行，我们就可以直接复用 PCH 来进行编译，从而大大减少编译时间，这部分代码就叫 preamble。如果变更了 preamble 则需要重新生成一个新的 PCH 文件。现在你应该理解为什么在第一次打开文件的时候 clangd 会需要反应很久，但是之后的响应就会非常快了，正是这种 preamble 的优化在起作用。如果你希望优化项目的构建时间，也可以考虑使用 PCM，不仅 Clang，GCC 和 MSVC 也都支持类似的机制来进行细粒度的增量编译。

PCH 好是好，但是呢，它的依赖关系只能是线性的。你可以用一个 PCH 去构建一个新的 PCH，只要它位于另外一个文件的前面几行。但是你不能说，用两个 PCH 去构建一个新的 PCH。那如果有这种有向无环图的依赖关系怎么办呢？答案就是 C++20 加入的 module。C++20 加入的 module 基本就是 PCH Pro 版，实现原理是完全类似的，只是放开了依赖链的限制，允许一个 module 依赖其它几个 module。

至于关于如何支持 C++20 的 module 呢？话题有些大，值得单独开一个文章讨论，这里就不详细展开了。

## Conclusion 

嗯，暂时就先写到这里吧。其实还有很多话题没有谈到，但是细想过后，发现每个单独展开都能写一篇长文出来了。就留到日后慢慢补充吧，这篇文章就当开个头。我在项目的 issue 中也会定期更新一些进展，感兴趣的读者可以关注一下。