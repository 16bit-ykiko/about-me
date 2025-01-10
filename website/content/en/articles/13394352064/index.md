---
title: 'Design and Implementation of a New C++ Language Server'
date: 2024-12-18 21:46:01
updated: 2024-12-23 01:10:58
series: ['clice dev diary']
series_order: 1
---

It has been several months since the last blog post. The reason for the long hiatus is that I have been busy working on [clice](https://github.com/clice-project/clice) — a brand-new C++ language server.

Some readers might be unfamiliar with the concept of a language server. However, you have likely used IDEs like Visual Studio or CLion and experienced features such as code completion, navigation, and refactoring. In traditional IDEs, these features are implemented through plugins or built-in functionalities, which require separate development for each editor, leading to high maintenance costs. When Microsoft released Visual Studio Code, they aimed to solve this problem by introducing the [Language Server Protocol (LSP)](https://microsoft.github.io/language-server-protocol/). LSP proposes a standard client-server model where language features are provided by an independent language server, and VSCode only needs to implement a generic client to communicate with the language server. This approach decouples the editor from language support, allowing VSCode to easily support multiple languages. For example, if you want to view the implementation of a `method`, your editor sends a `go to implementation` request to the language server, which might include the file path and the cursor's position in the source file. The language server processes this request and returns a file location and coordinates, enabling the editor to open the corresponding file and navigate to the specified location.

clice is such a language server, designed to handle requests related to C/C++ code. The name "clice" is derived from my avatar "alice," with the first letter replaced by "c" to represent C/C++.

After several months of design and development, the project has taken shape, but it will likely take a few more months to refine before it can be put into use. This article primarily introduces the design and implementation of clice, serving as a personal summary of the current development stage. While the content is related to language servers, it also involves a lot of C/C++ compilation knowledge, so interested readers are encouraged to continue reading.

Additionally, if you have any feature requests or suggestions, feel free to leave a comment. I will do my best to consider them in the next phase of development.

## Why a New Language Server?

The first question is, why develop a new language server? Is it necessary to reinvent the wheel?

This question deserves a serious answer. Before this project, I had written many small or large projects. However, most of them were toy projects, created merely to validate an idea or for personal learning, without solving any real-world problems. clice is different; it aims to address existing issues (specific problems will be discussed later), not just to rewrite something for the sake of it.

At the beginning of this year, I wanted to contribute to the LLVM project. I thought I would start with something familiar, like C++ and Clang. However, without a specific need, I couldn't just stare at the source code. Normally, the process would involve starting with some "first issues" to gradually familiarize myself with the project. But I found that boring; I wanted to tackle something significant right away, like implementing a new C++ standard feature. However, I discovered that there was almost no room for me to contribute here, as new features were almost always implemented by a few core Clang developers. So, I shifted my focus to clangd, since I primarily use VSCode for development, and clangd is the best C++ language server for VSCode.

At the time, I knew nothing about clangd, except that it seemed to render keyword highlighting incorrectly. So, I started reading clangd's source code and browsing through its numerous issues to see if there was anything I could fix. After going through hundreds of issues, I found that there were indeed many problems. One issue that particularly caught my interest was related to code completion within templates ([issue](https://github.com/clangd/clangd/issues/443)). Why was I interested in this? Regular readers might know that I am a seasoned metaprogramming enthusiast and have written many articles on the topic. Naturally, I was curious not only about how template metaprogramming works but also about how Clang, as a compiler, implements related features. This issue seemed like a great entry point. After spending a few weeks prototyping a solution, I managed to address the issue, **but then I realized there was no one to review the code!**

Upon further investigation, I found that clangd's current state is quite dire. Let's go through the timeline: clangd started as a small project within LLVM, with limited functionality and usability. As MaskRay mentioned in his [ccls](https://maskray.me/blog/2017-12-03-c++-language-server-cquery) blog post, clangd at the time could only handle single compilation units, making it unable to process cross-compilation unit requests. This blog post was published in 2017, which is why MaskRay chose to develop ccls, another C/C++ language server that was superior to clangd at the time. However, later on, Google began assigning people to improve clangd to meet the needs of their large internal codebases. At the same time, the LSP standard was continuously expanding, and clangd kept up with the new standards, while ccls's author seemed to become increasingly busy with other matters and had less time to maintain ccls. Eventually, clangd surpassed ccls in overall capability. The turning point came around 2023 when clangd reached a highly usable state for Google's internal use, and the employees originally responsible for clangd were reassigned to other projects. Currently, clangd's issues are primarily handled by [HighCommander4](https://github.com/HighCommander4), who works on it out of passion and is not employed by anyone to do so. Since he is not officially hired to maintain clangd, he can only address issues in his limited free time, mostly answering questions and conducting occasional code reviews. As he mentioned in this [comment](https://github.com/clangd/clangd/issues/1690#issuecomment-1619735578):

> The other part of the reason is lack of resources to pursue the ideas we do have, such as the idea mentioned above of trying to shift more of the burden to disk usage through more aggressive preamble caching. I'm a casual contributor, and the limited time I have to spend on clangd is mostly taken up by answering questions, some code reviews, and the occasional small fix / improvement; I haven't had the bandwidth to drive this type of performance-related experimentation.

Given this situation, it's no surprise that large PRs like [preliminary support for C++20 modules in clangd](https://github.com/llvm/llvm-project/pull/66462) have been delayed for nearly a year. Realizing this, I began to consider developing my own language server. I estimated the project size to be around 20,000 lines of code (excluding tests), which is manageable for one person over a period of time, and there are precedents like ccls and rust-analyzer. Another point is that clangd's codebase is quite dated. Despite having extensive comments, the logic is still convoluted, and making large-scale modifications might take longer than rewriting from scratch.

So, I decided to proceed. I categorized clangd's hundreds of issues to see if some problems were due to clangd's initial architectural design flaws, making them difficult to resolve and thus left unresolved. If so, could these issues be addressed by redesigning from the start? I found that indeed, some issues fit this description! Over the next few months, I spent time studying Clang's related mechanisms, exploring solutions to these problems, and prototyping implementations. After confirming that these issues could be resolved, I officially began developing clice.

## Important Improvements

After all that, let's take a look at the major issues in clangd that clice aims to solve. This section focuses on feature introductions, while the implementation details will be covered in the Design section. In addition to these significant improvements, there are also many smaller feature enhancements, which won't be listed here.

### Better Template Support

First and foremost, better template support, which was my initial motivation for wanting clangd to support this feature. What exactly are the current issues with template handling?

Take code completion as an example. Consider the following code, where `^` represents the cursor position:

```cpp
template <typename T>
void foo(std::vector<T> vec) {
    vec.^
}
```

In C++, if a type depends on a template parameter, we cannot make any accurate assumptions about it before the template is instantiated. For example, here `vector` could be either the primary template or a partial specialization like `vector<bool>`. Which one should we choose? For code compilation, accuracy is always paramount; we cannot use any results that might lead to errors. However, for a language server, providing more possible results is often better than providing none. We can assume that users are more likely to use the primary template rather than a partial specialization, and thus provide code completion based on the primary template. Currently, clangd does this; in the above case, it provides code completion based on the primary template of `vector`.

Now consider a more complex example:

```cpp
template <typename T>
void foo(std::vector<std::vector<T>> vec2) {
    vec2[0].^
}
```

From the user's perspective, code completion should also be provided here, since the type of `vec2[0]` is also `vector<T>`, similar to the previous example. However, clangd does not provide any completion here. What's the issue? According to the C++ standard, the return type of `std::vector<T>::operator[]` is `std::vector<T>::reference`, which is a [dependent name](https://en.cppreference.com/w/cpp/language/dependent_name). Its result seems straightforward: `T&`. However, in libstdc++, its definition is nested within dozens of template layers, possibly for compatibility with older standards? So why can't clangd handle this situation?

1. It assumes the primary template and does not consider partial specializations, which might prevent the lookup from proceeding.
2. It only performs name lookup without template instantiation, so even if it finds the result, it cannot map it back to the original template parameters.
3. It does not consider default template parameters, making it unable to handle dependent names caused by default template parameters.

Although we could hack support for standard library types, I wanted user code to have the same status as standard library code, so we needed a generic algorithm to handle dependent types. To solve this, I developed a pseudo-instantiation mechanism. It can instantiate dependent types without specific types, thereby simplifying them. For example, in the above case, `std::vector<std::vector<T>>::reference` can be simplified to `std::vector<T>&`, allowing us to provide code completion options to the user.

### Header Context

For clangd to function properly, users often need to provide a `compile_commands.json` file (referred to as CDB file). The traditional C++ compilation model treats a source file (e.g., `.c` or `.cpp`) as the basic compilation unit, where `#include` simply pastes the contents of the header file into the source file at the corresponding location. The CDB file stores the compilation commands for each source file. When you open a source file, clangd uses the corresponding compilation command from the CDB to compile the file.

This naturally raises a question: if the CDB file only contains compilation commands for source files and not header files, how does clangd handle header files? clangd treats header files as source files and, based on certain rules, uses the compilation command of a corresponding source file in the same directory as the header file's compilation command. This model is simple and effective but overlooks some scenarios.

Since a header file is part of a source file, its content can vary depending on the preceding content in the source file. For example:

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

Clearly, `a.h` has different states in `b.cpp` and `c.cpp`—one defines `X`, and the other defines `Y`. If `a.h` is simply treated as a source file, only `Y` will be visible.

A more extreme case is non-self-contained header files, such as:

```cpp
// a.h
struct Y { 
    X x;
};

// b.cpp
struct X {};
#include "a.h"
```

`a.h` cannot be compiled on its own, but when embedded in `b.cpp`, it compiles correctly. In this case, clangd will report an error in `a.h`, stating that `X` is undefined. This is because it treats `a.h` as an independent source file. There are many such header files in libstdc++, and some popular C++ header-only libraries also contain such code, which clangd currently cannot handle.

clice will support **header context**, allowing automatic and user-initiated switching of header file states, and will also support non-self-contained header files. We aim to achieve the following effect, using the initial code as an example. When you navigate from `b.cpp` to `a.h`, `b.cpp` will be used as the context for `a.h`. Similarly, when navigating from `c.cpp` to `a.h`, `c.cpp` will be used as the context for `a.h`.

### Full C++20 Module Support

C++20 introduced [modules](https://en.cppreference.com/w/cpp/language/modules) to speed up compilation. Unlike the traditional compilation model, module units may have dependencies, requiring additional handling. Although a PR for preliminary support of modules in clangd has been merged, it is in a very early stage.

1. Precompiled modules are not shared between different files, leading to redundant module compilation.
2. Other LSP facilities have not kept up, such as highlighting and navigation for module names, and providing completions similar to header files.
3. Only Clang is supported, not other compilers.

clice will provide compiler and build-system-agnostic C++20 module support, and the project itself will eventually fully migrate to modules.

### Better Index Format

Some ccls users might complain that, despite pre-indexing the entire project, ccls can jump instantly upon opening a file, while clangd still needs to wait for file parsing to complete. Why is this the case? This is due to a design flaw in clangd's index format. What is an index? Since C/C++ supports forward declarations, declarations and definitions may reside in different source files, requiring handling of cross-compilation unit symbol relationships.

However, parsing files is a time-consuming operation. If we wait until a query is needed to parse the file, the query time would be astronomical. To support fast symbol relationship lookup, language servers generally pre-index the entire project. But what format should be used to store this data? There is no standard.

clice has thoroughly studied existing index designs and developed a more efficient index format. It can achieve the same effect as ccls: if the project is pre-indexed, responses can be obtained immediately without waiting.

## Design

This section will delve deeper into the design and implementation of clice.

### Server

First, a language server is still a server, not much different from a traditional server in this regard. It uses an event-driven programming model, accepting server requests and processing them. Since C++20 is available, it's natural to experience asynchronous programming using stackless coroutines. clangd's code contains numerous callback functions, making this part of the code quite unreadable. Using stackless coroutines can avoid such callback hell.

Notably, in terms of library selection, I did not choose an existing coroutine library but instead wrapped libuv using C++20's coroutine facilities to create a simple coroutine library. The reasons are as follows:

- The LLVM project does not use exceptions, and we aim to stay consistent with it. Directly wrapping a C library allows better control over this.
- The event model of a language server is quite simple, with one-to-one connections. Handling IO-related requests in the main thread and delegating time-consuming tasks to a thread pool is entirely sufficient. In this model, no synchronization primitives like locks are needed for inter-thread communication. Thus, the model of general network libraries is overly complex for clice.

Finally, I successfully replicated the asynchronous programming experience similar to Python and JS in C++, which was very pleasant and straightforward.

### How It Works

Next, let's discuss in detail how clice handles certain specific requests.

When a user opens or updates a file in the editor, the editor sends a notification to clice. Upon receiving the request, clice parses the file. More specifically, it parses the file into an AST (Abstract Syntax Tree). Given the complexity of C++ syntax, writing a parser from scratch is impractical. Like clangd, we chose to use Clang's provided interfaces to parse source files.

After obtaining the AST, we traverse it to collect information of interest. Take `SemanticTokens` as an example: we need to traverse the AST to add semantic information to each token in the source code—whether it's a `variable`, `function`, `const`, `static`, etc. All this information can be extracted from the AST. For a deeper understanding, you can read an introductory [article](https://www.ykiko.me/zh-cn/articles/669360731) I wrote about Clang's AST.

Most requests can be implemented similarly. Code completion (CodeCompletion) and signature help (SignatureHelper) are more special. Since the syntax at the completion point may be incomplete, in the regular compilation process, if a syntax node is incomplete, Clang might treat it as an error node, discard it entirely, or even terminate compilation with a fatal error. None of these outcomes are acceptable for us. Generally, to implement code completion, the parser needs special handling. Clang is no exception; it provides a special code completion mode, where you inherit `CodeCompleteConsumer` and override relevant methods to obtain the necessary information.

You can experience this functionality with a special compilation option:

```bash
-std=c++20  -fsyntax-only -Xclang -code-completion-at="example.cpp:1:3"
```

Assuming the source file is:

```cpp
con
```

The expected output is:

```cpp
COMPLETION: const
COMPLETION: consteval
COMPLETION: constexpr
COMPLETION: constinit
```

As you can see, the result is the completion of four C++ keywords, with no errors or warnings.

Yes, that's the entire process. It sounds quite simple, doesn't it? Indeed, the logic for traversing the AST is quite clear. However, there are many corner cases to consider, and it will take time to implement features