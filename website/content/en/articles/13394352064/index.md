---
series:
  - clice dev diary
series_order: 1
title: Design and Implementation of a New C++ Language Server
date: "2024-12-18 13:46:01"
updated: "2025-11-27 06:12:20"
zhihu_article_id: "13394352064"
zhihu_url: https://zhuanlan.zhihu.com/p/13394352064
zhihu_column_id: c_1852831599382646784
zhihu_column_title: clice 开发日记
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

It's been several months since my last blog post. The reason for this long hiatus is that I've been busy working on [clice](https://github.com/clice-project/clice) – a brand new C++ language server.

Some readers might be unfamiliar with the concept of a language server. However, you've certainly used IDEs like Visual Studio or CLion and experienced features such as code completion, navigation, and refactoring. In traditional IDEs, these features were implemented by IDE plugins or built-in functionalities. This approach meant that each language required separate support development for every editor, leading to high maintenance costs. When Microsoft released Visual Studio Code, they aimed to solve this problem and thus introduced the [LSP (Language Server Protocol)](https://microsoft.github.io/language-server-protocol/) concept. LSP proposes a standard client-server model. Language features are provided by an independent language server, and VSCode only needs to implement a generic client to communicate with it. This method decouples the editor from language support, allowing VSCode to easily support multiple languages. For example, if you want to view the `implementation` of a `method`, your editor will send a `go to implementation` request to the language server. The specific content of this request might include the file path and the current cursor position in the source file. The language server processes this request and returns a file location and coordinates, which the editor then uses to open the corresponding file and navigate.

clice is precisely such a language server, designed to handle requests related to C/C++ code. The name comes from my avatar, Alice; by replacing the initial 'A' with 'C' (representing C/C++), I got clice.

After several months of design and development, the project has taken shape, but it is expected to require a few more months for refinement before it can be put into use. The main purpose of this article is to introduce the design and implementation of clice, serving as my personal interim summary of the current development. Although it's about language servers, it actually involves a lot of popular science knowledge related to C/C++ compilation. Interested readers can continue reading.

Meanwhile, if you have any feature requests or suggestions, feel free to leave a comment and discuss. I will try my best to consider them in the next phase of development.

## Why a new language server?

So, the first question is, why develop a new language server? Is it necessary to reinvent the wheel?

This question deserves a serious answer. Before this project, I had written many projects, big and small. However, most of them were toy projects, written merely to validate an idea or for personal learning, and didn't solve any real-world problems. clice is different; it genuinely aims to solve existing issues (more on specific problems later), rather than being a rewrite for the sake of rewriting.

Earlier this year, I wanted to get involved in the development of the LLVM project. I wanted to start with something I was relatively familiar with, C++, specifically Clang. But without a specific need, I couldn't just stare at the source code. The usual process in such cases is to start with some "first issues" and gradually familiarize oneself with the project. However, I found that boring; I wanted to tackle something significant right away, like implementing a feature from a new C++ standard. But I found there was little room for me to contribute; new features were almost always implemented by a few core Clang developers. Alright, since there wasn't much opportunity there, I looked elsewhere. My attention naturally shifted to clangd, as I primarily use VSCode for development, and clangd is the best C++ language server available for VSCode.

At the time, I knew nothing about clangd, except that it seemed to incorrectly highlight keywords. So, I started reading clangd's source code while browsing through its numerous issues to see if there was anything I could solve. After going through hundreds of issues, I found quite a few problems. I was particularly interested in an [issue](https://github.com/clangd/clangd/issues/443) related to code completion within templates. Why was I interested in this? Readers familiar with my work might know that I'm an experienced metaprogramming enthusiast, and I've written many related articles before. Naturally, I was curious not only about how template metaprogramming itself works but also how Clang, as a compiler, implements related features. This issue seemed like an excellent entry point for me. After spending a few weeks exploring a prototype implementation, I initially resolved that issue, **but then I realized there was no one available to review the related code**!

After some investigation, I found that clangd's current situation is quite dire. Let's trace the timeline: clangd initially started as a simple small project within LLVM, not excelling in functionality or usability. As MaskRay mentioned in his [ccls](https://maskray.me/blog/2017-12-03-c++-language-server-cquery) blog post, clangd at the time could only handle single compilation units, and cross-compilation unit requests were unmanageable. This blog post was published in 2017, which was one reason MaskRay chose to write ccls. ccls was also a C/C++ language server and was superior to clangd at that point. However, later, Google began assigning people to improve clangd to meet the needs of their internal large codebases. Concurrently, the LSP standard was continuously expanding, and clangd kept pace with the new standard's content, while the author of ccls seemed to gradually become busy with other things and had less time to maintain ccls. Consequently, clangd eventually surpassed ccls overall. The turning point occurred around 2023; clangd seemed to have reached a highly usable state for Google internally, and the employees originally responsible for clangd were reassigned to other tasks. Currently, clangd's issues are primarily handled by only [HighCommander4](https://github.com/HighCommander4), purely out of passion, without being employed by anyone for this role. Since he isn't specifically hired to maintain clangd, he can only address issues in his limited free time, and his contributions are restricted to answering questions and very limited reviews. As he mentioned in this [comment](https://github.com/clangd/clangd/issues/1690#issuecomment-1619735578):

> The other part of the reason is lack of resources to pursue the ideas we do have, such as the idea mentioned above of trying to shift more of the burden to disk usage through more aggressive preamble caching. I'm a casual contributor, and the limited time I have to spend on clangd is mostly taken up by answering questions, some code reviews, and the occasional small fix / improvement; I haven't had the bandwidth to drive this type of performance-related experimentation.

Given this situation, it's no surprise that a large PR like [initial C++20 module support for clangd](https://github.com/llvm/llvm-project/pull/66462) has been delayed for nearly a year. After realizing this state of affairs, I conceived the idea of writing my own language server. I estimated the project size, excluding test code, to be around 20,000 lines, which is a manageable workload for one person over a period, and there are precedents like ccls and rust-analyzer. Another point is that clangd's codebase is quite old; despite numerous comments, the underlying logic is still very convoluted, and making extensive modifications might take longer than a complete rewrite.

So, I got to work. I categorized hundreds of clangd issues to see if any were difficult to solve due to initial architectural design flaws and subsequently shelved. If so, could these problems be addressed during a redesign? I found that there indeed were some! Consequently, over the next two months, I dedicated myself to studying Clang's internal mechanisms, exploring solutions to related problems, and prototyping implementations. After confirming that these issues could largely be resolved, I officially began developing clice.

## Important improvement

Having said all that, let's first look at which significant existing problems in clangd clice actually solves. The focus here will be on feature introduction; the implementation principles will be covered in the Design section. Besides these important improvements, there are, of course, many minor functional enhancements, which I won't list individually here.

### Better template support

First and foremost, there's better template support, which was the feature I initially wanted clangd to support. Specifically, what are the current problems with handling templates?

Taking code completion as an example, consider the following code, where `^` represents the cursor position:

```cpp
template <typename T>
void foo(std::vector<T> vec) {
    vec.^
}
```

In C++, if a type depends on template parameters, we cannot make any accurate assumptions about it before template instantiation. For example, `vector` here could be the primary template or a partial specialization like `vector<bool>`. Which one should be chosen? For code compilation, accuracy is always paramount; no results that could lead to errors can be used. However, for a language server, providing more possible results is often better than providing nothing at all. We can assume that users more often use the primary template rather than partial specializations, and thus provide code completion results based on the primary template. Currently, clangd indeed does this, offering code completion based on the primary `vector` template in the situation described above.

Consider a more complex example:

```cpp
template <typename T>
void foo(std::vector<std::vector<T>> vec2) {
    vec2[0].^
}
```

From a user's perspective, completion should also be provided here, as the type of `vec2[0]` is also `vector<T>`, just like in the previous example. However, clangd doesn't offer any completion here. What's the problem? According to the C++ standard, the return type of `std::vector<T>`'s `operator[]` is `std::vector<T>::reference`, which is actually a [dependent name](https://en.cppreference.com/w/cpp/language/dependent_name). Its result seems quite straightforward: `T&`. But in libstdc++, its definition is nested through a dozen layers of templates, seemingly for compatibility with older standards? So why can't clangd handle this situation?

1.  It relies on primary template assumptions, and not considering partial specializations might prevent the lookup from proceeding.
2.  It only performs name lookup without template instantiation, so even if the final result is found, it cannot be mapped back to the original template parameters.
3.  It doesn't consider default template parameters, making it unable to handle dependent names caused by them.

Although we could create "holes" for standard library types to provide relevant support, I want user code to have the same standing as standard library code. Therefore, we need a generic algorithm to handle dependent types. To solve this problem, I developed a pseudo instantiator. It can instantiate dependent types without concrete types, thereby achieving simplification. For example, `std::vector<std::vector<T>>::reference` in the example above can be simplified to `std::vector<T>&`, which then allows providing code completion options to the user.

### Header context

For clangd to function correctly, users often need to provide a `compile_commands.json` file (hereinafter referred to as CDB). The basic compilation unit in C++'s traditional compilation model is a source file (e.g., `.c` and `.cpp` files), and `#include` simply pastes the contents of a header file into the corresponding location in the source file. The aforementioned CDB file stores the compilation commands for each source file. When you open a source file, clangd uses its corresponding compilation command from the CDB to compile that file.

Naturally, a question arises: since the CDB only contains compilation commands for source files, not header files, how does clangd handle header files? In fact, clangd treats header files as source files and then, based on certain rules, uses the compilation command of a source file in the corresponding directory as the compilation command for that header file. This model is simple and effective but overlooks some situations.

Since header files are part of source files, their content can vary depending on the preceding content in the source file. For example:

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

Clearly, `a.h` has different states in `b.cpp` and `c.cpp`; one defines `X`, and the other defines `Y`. If `a.h` is simply treated as a source file, only `Y` will be visible.

A more extreme case is non-self-contained header files, for example:

```cpp
// a.h
struct Y {
    X x;
};

// b.cpp
struct X {};
#include "a.h"
```

`a.h` itself cannot be compiled, but it compiles normally when embedded in `b.cpp`. In this scenario, clangd would report an error in `a.h`, stating that `X`'s definition cannot be found. This is clearly because it treats `a.h` as an independent source file. Many such header files exist in libstdc++ code, and some popular C++ header-only libraries also contain similar code, which clangd currently cannot handle.

clice will support **header context**, allowing automatic and user-initiated switching of header file states, and naturally, it will also support non-self-contained header files. We aim to achieve the following effect, using the initial code example: when you jump from `b.cpp` to `a.h`, `b.cpp` will be used as the context for `a.h`. Similarly, when you jump from `c.cpp` to `a.h`, `c.cpp` will be used as the context for `a.h`.

### Fully C++20 module support

C++20 introduced the [module](https://en.cppreference.com/w/cpp/language/modules) feature to accelerate compilation. Unlike traditional compilation models, module units can have dependencies on each other. This requires additional handling. Although the PR for initial `module` support in clangd has been merged, it is still in a very early state.

1.  Precompiled modules are not shared between different files, leading to redundant module compilation.
2.  Other accompanying LSP features have not kept pace, such as providing highlighting and navigation for module names, or offering completion similar to header files.
3.  Only Clang is supported, not other compilers.

clice will provide compiler- and build-system-agnostic C++20 module support, and the project itself will fully migrate to modules later.

### Better index format

Some ccls users might complain that even though both pre-index the entire project, ccls allows instant navigation upon opening a file, while clangd still requires waiting for the file to be parsed. Why does this happen? This is actually due to a design flaw in clangd's index format. What is an index? Since C/C++ supports forward declarations, declarations and definitions can be in different source files, so we need to handle symbol relationships across compilation units.

However, parsing files is a very time-consuming operation. If we wait to parse files until a query is needed, the query time would be astronomical. To support fast lookup of symbol relationships, language servers generally pre-index the entire project. But what format should be used to store the relevant data? There is no standard for this.

clice has thoroughly referenced existing index designs and developed a more efficient index format. It can also achieve the same effect as ccls: if a project is pre-indexed, responses can be obtained immediately without waiting.

## Design

This section will discuss the design and implementation of clice in more detail.

### Server

First, a language server is also a server, and in this regard, it's no different from a traditional server. It uses an event-driven programming model to receive and process server requests. Since C++20 is available, it's natural to experience asynchronous programming using stackless coroutines. clangd's code contains a large number of callback functions, making that part of the code quite difficult to read. Using stackless coroutines can avoid similar callback hell.

It's worth noting that regarding library selection, I didn't choose an off-the-shelf coroutine library. Instead, I used C++20's coroutine facilities to wrap libuv and create a simple coroutine library myself. The reasons are as follows:

- The LLVM project does not use exceptions. We try to maintain consistency with this, and directly wrapping C libraries allows us better control over this aspect.
- The event model of a language server is quite simple, with one-to-one connections. Handling I/O-related requests on the main thread and using a thread pool for time-consuming tasks is entirely sufficient. In this model, there's no need for synchronization primitives like locks for inter-thread communication. Therefore, the models of general network libraries are overly complex for clice.

Finally, I successfully replicated an asynchronous programming experience similar to Python and JavaScript in C++, which was very pleasant and effortless.

### How it works?

Next, let's discuss in detail how clice handles certain specific requests.

First, when a user opens or updates a file in the editor, the editor sends relevant notifications to clice. Upon receiving the request, clice parses the file. More specifically, it parses the file into an AST (Abstract Syntax Tree). Since C++ grammar is quite complex, writing a parser from scratch is impractical. Like clangd, we choose to use the interfaces provided by Clang to parse source files.

After obtaining the AST, we traverse it to collect the information we are interested in. Taking `SemanticTokens` as an example, we need to traverse the AST to add semantic information to each token in the source code: Is it a `variable` or a `function`? Is it `const`? Is it `static`? And so on. In short, all this information can be obtained from the AST. For a deeper understanding of this, you can read an introductory [article](https://www.ykiko.me/en/articles/669360731) I previously wrote about Clang AST.

Most requests can be implemented in a similar manner as described above. Code Completion and Signature Helper are somewhat special. Since the syntax at the completion point might be incomplete, in a regular compilation process, if a syntax node is incomplete, Clang might treat it as an error node, discard it entirely, or even terminate compilation with a fatal error. In any case, these outcomes are unacceptable to us. Generally, to implement code completion, the parser needs to make "holes" for special handling. Clang is no exception; it provides a special code completion mode, which obtains relevant information by inheriting `CodeCompleteConsumer` and overriding its related methods.

You can experience this feature with a special compilation option:

```bash
-std=c++20  -fsyntax-only -Xclang -code-completion-at="example.cpp:1:3"
```

Assuming the source file is

```cpp
con
```

Then the expected output is

```cpp
COMPLETION: const
COMPLETION: consteval
COMPLETION: constexpr
COMPLETION: constinit
```

It can be seen that the result is the completion of four C++ keywords, without any errors or warnings.

Well, that's the whole process. Doesn't it sound quite simple? Indeed, the logic for traversing the AST in this part is quite clear. It's just that there are many corner cases to consider; it simply requires gradually investing time to implement features and then iteratively fixing bugs.

### Incremental compilation

Since users might frequently change files, if the entire file needs to be re-parsed every time, parsing can be very slow for large files, leading to very long response times (considering that `#include` is just copy-pasting, it's easy to create a huge file). Imagine how terrible the experience would be if you typed a letter and had to wait several seconds for code completion results to appear!

What to do then? The answer is Incremental Compilation. You might have heard this term when learning about build tools like CMake, but there are some differences. Incremental compilation for build tools operates at the granularity of a file, recompiling only changed files. However, this is clearly insufficient for us; the most basic request unit for LSP is a file, and we need finer-grained incremental compilation.

Clang provides a mechanism called [Precompiled Header (PCH)](https://clang.llvm.org/docs/UsersManual.html#usersmanual-precompiled-headers), which can be used to serialize a segment of code to disk after compiling it into an AST, and then reuse it during subsequent compilations.

For example:

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

We can compile the first three lines of this file's code into a PCH and cache it. This way, even if the user frequently modifies the file content, as long as those first three lines are unchanged, we can directly reuse the PCH for compilation, significantly reducing compilation time. This part of the code is called the preamble. If the preamble is changed, a new PCH file needs to be regenerated. Now you should understand why clangd takes a long time to respond when a file is opened for the first time, but subsequent responses are very fast; it's precisely this preamble optimization at work. If you want to optimize your project's build time, you can also consider using PCM; not only Clang, but GCC and MSVC also support similar mechanisms for fine-grained incremental compilation.

PCH is good, but its dependencies can only be linear. You can use one PCH to build a new PCH, as long as it's located in the first few lines of another file. However, you cannot use two PCHs to build a new PCH. So what if there's a directed acyclic graph of dependencies? The answer is C++20 modules. C++20 modules are essentially a "PCH Pro" version; their implementation principle is entirely similar, but they relax the limitations of dependency chains, allowing a module to depend on several other modules.

As for how to support C++20 modules? That's a broad topic, deserving a separate article for discussion, so I won't elaborate on it here.

## Conclusion

Well, I'll stop here for now. There are actually many topics I haven't covered, but upon reflection, each one could easily become a lengthy article on its own. I'll save them for future additions; consider this article an introduction. I also regularly update progress in the project's issues, so interested readers can follow along.
