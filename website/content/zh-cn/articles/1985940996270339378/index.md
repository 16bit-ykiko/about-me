---
title: 打造优雅的 C++ 跨平台开发与构建 Workflow
date: "2025-12-21 06:51:31"
updated: "2026-03-28 23:51:25"
zhihu_article_id: "1985940996270339378"
zhihu_url: https://zhuanlan.zhihu.com/p/1985940996270339378
---

C++ 的构建问题一直是热门话题，尤其在各种语言论战中，常常被当作反面教材。有趣的是，大多数 C++ 程序员往往是参与到现有系统的维护中，面对的是高度固化、无法改动的构建流程，真正需要从零搭建项目的人反倒是少数。

这就导致了一个尴尬的局面：当你真的需要从零搭建，想要寻找参考案例时，会发现根本没有所谓的最佳实践 (Best Practice)，只能搜到各种不成体系的 workaround，非常令人沮丧。

clice 也是一个从零开始的 C++ 项目，当然不可避免地，我们把前人踩过的坑几乎都踩了一遍。最近，我们总算摸索出了一套自认为比较优雅的 workflow。所以，我们想借此机会把这套方案分享一下，顺便科普一些 C++ 构建背后的原理和知识，希望对你有所帮助！

## Where does complexity come from?

在讨论解决方案之前，我们还是先来分析问题。C++ 的构建复杂度到底从何而来？如果有包管理那么所有问题就都解决了吗？

我认为复杂度主要来自于两个不同的维度，**工具链 (toolchain)** 与**构建系统 (build system)**。

### Toolchain

所以什么是工具链？除了编译器和链接器，它还包含更多被多数教程忽略的细节，我们可以通过一个简单的命令来拆解这些概念。

考虑如下文件，执行 `clang++ -std=c++23 main.cpp -o main`，即可获得可执行程序

```cpp
// main.cpp
#include <print>

int main () {
    std::println("Hello world!");
    return 0;
}
```

那首先，第一个疑问，我们都知道对于传统的 C/C++ 编译模型来说，分为编译 (compile) 和链接 (link) 两个过程。先调用编译器编译出中间的 `.obj` 文件，再使用链接器链接成 `executable`。为什么这里我们一个命令就搞定了？

这是因为 `clang++` 只是一个**驱动程序 (driver)**，它会帮你调用编译器和链接器完成全部的工作。如何验证这一点呢？`clang++` 有一个命令行选项 `-###` 可以用于仅输出底层要执行的命令，而不执行具体的任务。

例如，执行 `clang++ -### -std=c++23 main.cpp -o main`，我的 Linux 环境上输出如下（不重要的信息已使用 `...` 省略）：

```bash
"/usr/lib/llvm-20/bin/clang" "-cc1" ...
    "-triple" "x86_64-pc-linux-gnu"
    "-resource-dir" "/usr/lib/llvm-20/lib/clang/20"
    "-internal-isystem" "/usr/include/c++/14"
    "-internal-isystem" "/usr/include/x86_64-linux-gnu/c++/14"
    "-internal-isystem" "/usr/include/c++/14/backward"
    "-internal-isystem" "/usr/lib/llvm-20/lib/clang/20/include"
    "-internal-isystem" "/usr/local/include"
    "-internal-isystem" "/usr/x86_64-linux-gnu/include"
    "-internal-externc-isystem" "/usr/include/x86_64-linux-gnu"
    "-internal-externc-isystem" "/include"
    "-internal-externc-isystem" "/usr/include"
    ... "-std=c++23" ... "-o" "/tmp/main-a82bce.o" ... "main.cpp"

"/usr/bin/ld" ...
    "-dynamic-linker" "/lib64/ld-linux-x86-64.so.2" ...
    "/usr/lib/x86_64-linux-gnu/Scrt1.o"
    "/usr/lib/x86_64-linux-gnu/crti.o"
    "/usr/lib/gcc/x86_64-linux-gnu/14/crtbeginS.o"
    "/usr/lib/gcc/x86_64-linux-gnu/14/crtendS.o"
    "/usr/lib/x86_64-linux-gnu/crtn.o"
    "-L/usr/lib/gcc/x86_64-linux-gnu/14"
    "-L/usr/lib64"
    "-L/usr/lib/x86_64-linux-gnu"
    "-L/usr/lib/llvm-20/lib"
    "-L/usr/lib"
    "-lstdc++" "-lm" "-lgcc_s" "-lgcc" "-lc"
    "/tmp/main-a82bce.o"
```

可以发现 `clang++` 确实在底层分别调用编译器和链接器完成了任务。更值得注意的是，它注入了大量**隐式参数 (implicit flags) **！实际上 toolchain 中常常被忽略的部分就是这些隐式的编译参数。

> GNU 风格的编译器比如 `g++` 和 `clang++` 往往可以直接调用链接器并注入这些隐式参数。因此构建系统会直接调用它们而不是链接器完成链接，可以通过 `-fuse-ld` 这种选项来切换 driver 启动的链接器。这也可以解释为什么用 Clang 而不是 `clang++` 编译 C++ 程序会有很多 C++ 标准库的 undefined reference。实际上，在很多发行版上，Clang 和 `clang++` 都只是 `/usr/lib/llvm-20/bin/clang` 的符号链接，而这个二进制程序会根据程序名等参数注入不同的隐式参数。<br><br> 而 MSVC 风格的编译器比如 cl.exe 或者 Clang-cl 则更倾向于通过环境变量来传递这些隐式的状态（如 `INCLUDE`、`LIB` 和 `LIBPATH`）。因此，在使用这些编译器之前，通常必须先运行 Visual Studio 提供的初始化脚本 vcvarsall.bat 来「激活」当前终端的环境，或者直接在 Developer Command Prompt 中进行构建，否则编译器将因找不到标准库头文件或系统库而报错。这种情况下，构建系统一般也会直接调用链接器来完成链接。

一个完整的工具链可以认为由**工具 (Tools)**，**运行时库 (Runtime)** 和**环境 (Environment)** 三部分组成。

Tools 就是在构建过程中用到各种工具，包括

- Compiler Drivers：负责调度整个流程，例如 `g++` 和 `clang++`
- Translators：真正的编译器和汇编器，负责将 C++ 代码翻译成机器码，如 cc1 和 as
- Linkers：负责将碎片化的 `.o` 文件和库文件拼接在一起，例如 ld，lld 和 mold
- Binutils：负责归档、格式转换、符号处理等辅助工作，例如 ar, objcopy, strip, 和 nm

Runtime 就是上面选项里隐式链接的各种库，它们是必不可少的：

- C Runtime (CRT) Startup Objects：即日志中看到的 `Scrt1.o`, `crti.o`, `crtn.o` 等。操作系统加载程序后，跳转的第一个地址通常是 CRT 中的 `_start`。这些对象文件负责初始化栈、堆、运行全局构造函数（C++ 特性），最后才调用 `main`。并在 `main` 返回后执行清理工作
- C Standard Library：对应日志中的 `-lc`。也就是 C 标准库的实现，提供了 `malloc`, `printf`, `open` 等与操作系统内核交互的 POSIX 或系统 API 封装。常见的实现有 GNU 的 glibc 和 musl，Windows 上的 UCRT，还有 LLVM 社区正在开发的 LLVM libc
- C++ Standard Library：对应日志中的 `-lstdc++`，它提供 `std::vector`、`std::iostream` 等高层 C++ 标准库的实现。值得注意的是，它通常依赖于更底层的 Compiler Support Libraries 来实现异常和 RTTI 等功能，主要的实现有 libstdc++（GCC 标准库）、libc++（Clang 标准库）、MSVC STL
- Compiler Support Libraries：对应日志中的 `-lgcc_s`，是一类容易被忽视但至关重要的库，它们主要负责两件事
- - 内建函数 (Builtins)：处理目标 CPU 指令集无法直接支持的操作。例如在 32 位 CPU 上进行 64 位除法，或在不支持浮点的 CPU 上进行软浮点运算，编译器会将这些操作翻译成对 `__udivdi3` 等函数的调用
- 语言运行时支持 (Language Runtime Support)：C++ 中一些高级特性的实现，比如 Exception Handling（异常捕获与栈展开）通常由 `libunwind` 或 `libgcc_eh` 提供；而 C++ ABI（如 `dynamic_cast`、`RTTI`）则由 `libcxxabi` 或 `libsupc++` 提供。在 Windows MSVC 环境下，这些通常被统一封装在 `vcruntime140.dll` 中
- Sanitizer Runtimes：当你开启 `-fsanitize=address/thread/memory` 时链接的库（如 `libclang_rt.asan.so`）。它们通过在编译期插入桩代码 (Instrumentation)，并在运行时接管内存分配器 (malloc/free)，利用 Shadow Memory 技术来检测内存越界、数据竞争等未定义行为

Environment 就是编译执行的上下文，包括：

- Target Triple：对应日志中的 `-triple x86_64-pc-linux-gnu`。它定义了目标平台的详细「身份」，格式通常为 `<arch>-<vendor>-<sys>-<abi>`。它决定了编译器生成什么指令集（x86 vs ARM）、使用什么对象格式（ELF vs PE），以及调用约定的细节
- Cross Compilation (交叉编译)：这是现代构建中非常重要的概念。当 Host（运行编译器的机器）与 Target（运行产物的机器）不一致时，就是在进行交叉编译。这里的不一致不仅指 CPU 架构（如在 x86 上编译 ARM），也指操作系统甚至 C 运行时库的版本（例如，在运行 glibc 2.35 的系统上编译依赖 glibc 2.17 的产物）
- Sysroot (System Root)：为了解决交叉编译时的环境污染问题，Sysroot 应运而生。它是一个逻辑上的根目录，模拟了目标机器的文件系统结构。当你指定 `--sysroot=/path/to/sysroot` 时，编译器会忽略本机系统的 `/usr/include`，转而去 Sysroot 中寻找依赖

值得注意的是大部分的平台都会有一套默认的工具链，比如 Windows 的 MSVC 工具链，包含编译器，链接器，各种工具以及运行时库的一整套工具。Linux 上的 gnu 工具链，mac 上的 apple Clang 工具链。很多平台还不止一套，Windows 上还有 mingw 工具链，而且所有这些工具链还可以部分切换到 LLVM 的工具链。

### Build System

解决了单文件的 toolchain 问题，我们通过编译器驱动程序搞定了编译和链接。但现实世界中，项目往往包含成千上万个源文件。**构建系统 (Build System)** 的核心任务，就是解决如何高效、正确地指挥 toolchain 将这成千上万个文件组装成最终产物。

我们可以沿着时间线，从「复杂度」演进的视角来审视 C++ 构建系统的发展：

**1. 原始时代：脚本 (Shell Scripts)**

在最早期，构建项目就是写一个 Shell 脚本。逻辑非常粗暴：把所有 `.c` 文件列出来，写死编译器路径，直接调用。随着项目膨胀，每次修改一行代码都要全量重新编译几百个文件，等待时间从几秒变成几十分钟，开发体验极差。

**2. 构建系统的基石 (1976)**

为了解决重复编译的问题，Stuart Feldman 在贝尔实验室写出了 **Make**。通过引入了**依赖图 (Dependency Graph)** 和**增量构建 (Incremental Build)**。通过对比文件的时间戳 (mtime)，如果 `main.cpp` 的修改时间晚于 `main.o`，那就重编，否则跳过。这一简单的规则奠定了构建系统的基石。

**3. 移植性危机 (1990s)**

90 年代操作系统百花齐放（Solaris, HP-UX, Linux, BSD, Windows）。Make 虽然解决了自动化，但 Makefile 是不可移植的。不同 OS 的 Shell 命令、编译器参数、库路径完全不同。世界分裂成了两派：

- Unix 阵营 - Autotools (GNU)：著名的 `./configure && make`。它的核心思路是”探测”——在构建前运行大量脚本扫描系统环境（有没有 `unistd.h`？`libz` 在哪？），然后动态生成适配当前系统的 Makefile。
- IDE 阵营 (Visual Studio / Xcode)：Windows 和 Mac 选择了另一条路——将构建系统与编辑器深度绑定。Visual Studio 的 `.sln` 和 Xcode 的 `.xcodeproj` 提供了开箱即用的体验，但代价是牺牲了自动化和灵活性，且完全无法跨平台使用。

**4. 真正的跨平台 (CMake, 2000s)**

随着开源软件爆发，代码需要同时在 Linux 服务器和 Windows 桌面运行。为了结束”维护两套构建脚本”的噩梦，CMake 诞生了。CMake 不是构建工具，它是一个**元构建系统 (Meta-Build System)**，或者叫**构建系统生成器 (Generator)**。开发者编写抽象的 `CMakeLists.txt`，CMake 负责将其”翻译”成各平台的原生方言——在 Windows 上生成 `.sln`，在 Mac 上生成 `.xcodeproj`，在 Linux 上生成 `Makefile`。

**5. 现代工程化：规模与可复现的挑战 (2010s - Present)**

进入移动互联网与云原生时代，巨头（Google/Meta）的代码仓库膨胀到亿行级别（Monorepo），多语言混合编程成为常态。新的场景当然会带来新的问题：

- 构建速度：Makefile 的解析速度太慢，且不支持分布式。我们需要将编译任务分片发送到集群，也就是所谓的**分布式构建（Distributed Build）**，并且实现**远程缓存 (Remote Caching)**——如果同事 A 已经编译过 `base_lib`，同事 B 就应该直接下载缓存，而不是消耗本地 CPU 重新编译
- 环境一致性 (Hermetic Build)：本地能过，CI 或者其他机器挂了。这是现代开发最大的痛点，通常源于使用了宿主机系统目录（如 `/usr/include`）下版本不一致的依赖。现代构建追求**密封性 (Hermeticity)**——构建过程必须像运行在沙盒中，严格禁止访问未声明的系统库，确保**可复现构建 (Reproducible Build)**
- 多语言混合 (Polyglot)：一个现代项目往往 C++ 做后端，Python 做胶水，Rust 做安全组件，前端是 TypeScript。CMake 处理非 C/C++ 语言非常痛苦
- 依赖管理 (Dependency Management)：一个项目无论大型或者小型，往往都需要引入第三方库。然而 C++ 长期缺失像 Rust Cargo 或 Node npm 那样统一的包管理器。开发者不得不手动处理源码下载、编译参数匹配（Debug/Release, Static/Shared）以及复杂的 ABI 兼容性问题。传统的 git submodule 或系统级包管理器（如 apt/brew）在跨平台和多版本并存场景下往往力不从心

为了解决这些问题，很多新的工具涌现了出来：

- `Ninja`：新的构建后端，Make 的替代者，极快的构建速度
- `FetchContent/Conan/vcpkg`：旨在降低 CMake 引入依赖的难度
- `ccache/sccache`：基于编译输入（编译器版本/参数、预处理结果等）计算 cache key，实现跨项目/跨机器复用（sccache 还能做远程 cache）
- `distcc/icecream`：分布式构建，将编译任务分发到其他机器
- `Bazel/Buck2`：google 和 meta 基于内部场景编写的构建系统，在沙盒中执行构建，自带编译缓存，实现了良好的密封性和跨语言支持
- `Meson/XMake`：内置包管理的现代构建系统，使用 `python like dsl/lua` 作为构建语言，旨在比 CMake 提供更高的易用性

### Summary

到这里可以回答最开始的问题了，C++ 的构建复杂度从何而来？其实就来源于自由度带来的组合爆炸。C++ 有这么多的工具链，同时还有这么多的构建系统。很容易出现这套构建系统的配置在我的工具链能跑，换一套工具链就出错的情况。再加上各种隐式编译参数可能将问题藏匿其中，你可能根本没意识到。不过现在你大概有一个直观的认知了。

## Purpose

现在，我们可以来正式的讨论 clice 的构建问题了。首先要明确目标，我们想要达到什么样的目标？我们希望有如下三套环境用于构建。

- Develop：用于开发者本地进行开发，我们希望本地构建/编译速度尽可能快，减少因为等待编译而打断开发的次数。同时确保保留调试信息，能方便的使用调试器进行调试。确保开启 address sanitizer 这类消毒器，尽早捕获开发过程中产生的错误
- CI：用于在 GitHub Action 这类平台上自动构建，运行单元测试/集成测试保证可靠性。同样我们希望构建/编译速度尽可能快。尽可能测试不同的平台/环境，防止因为意外依赖一些平台特性，导致崩溃等情况。同时希望能保持和 Develop 的环境一致，能在本地复现 CI 中的错误
- Release：用于构建最终分发的二进制产物，我们希望产物的速度尽可能快，确保使用 LTO 来进行构建。希望在程序 crash 的时候在日志中打印出函数调用栈，用户在提 issue 等时候方便定位现场。同时分发给用户的程序二进制尽可能小，可以将调试信息剥离成单独的文件（这大概可以减少 2⁄3 的程序体积），在有需要的时候，再去根据相对地址来获取对应的符号，还希望运行时依赖尽快少，会静态链接整个程序

首先考虑 clice 的构建依赖，目前有 `llvm`, `libuv`, `spdlog`, `toml++`, `croaring`, `flatbuffers` 和 `cpptrace`。它使用 C++23 构建，依赖高版本的 C++ 编译器。并且在不同平台上使用不同的 C++ 标准库：

- Windows: MSVC stl
- Linux: libstdc++
- macOS: libc++

可以发现，clice 的依赖其实并不多，依赖管理的复杂度并不高。我们有两套构建系统，CMake 使用 `FetchContent` 来管理这些依赖。xmake 则通过自带的包管理 xrepo 来管理这些依赖。由于我们的依赖数量并不多，所以这里的复杂度并不高。CMake 和 xmake 都支持拉取源码并在本地现编现用（从源码构建依赖），可以满足我们对构建一致性的需求。并且大部分依赖的源文件数量都很少，对构建速度没有什么影响，除了 LLVM！

## Prebuilt Libraries

clice 依赖 Clang libraries 来解析 AST，即使只构建需要的 target，要构建的文件数量也多达 3000。在 GitHub CI 上构建需要平均两小时，而我们想要尽可能快速的 CI，需要考虑优化 LLVM 的构建速度，可以很容易想到两种方式：

1. GitHub Action 支持 cache，我们可以使用 ccache 缓存 LLVM 的构建结果在不同的 workflow 之间复用。但是这种方式并不稳定，尤其是 LLVM 的构建结果需要占用大量磁盘空间，很容易将 GitHub 的缓存占满
2. 提前编译好 LLVM 并将二进制发布在 GitHub Release，在构建的时候去下载就好了，这样不仅 CI 构建可以使用，如果有用户想要本地编译开发 clice 也可以使用

在一开始我们使用 GitHub Action 进行缓存，踩了坑之后果断切换到了维护预编译二进制的方案。但是构建预编译二进制并不是一件简单的事情，最大的问题就是 ABI 兼容性，C++ 的工具链/构建参数组合非常多，有很多选项会影响 ABI。关于 C++ ABI 的讨论可以参考 [彻底理解 C++ ABI](https://www.ykiko.me/zh-cn/articles/692886292)。

我们要支持 Windows，Linux，macOS 三个平台，每个平台要构建三种不同版本的产物以满足我们的需求：

- Debug + [Address Sanitizer](https://clang.llvm.org/docs/AddressSanitizer.html) 尽早的暴露代码中的 undefined behavior
- ReleaseWithDebInfo 测试开启优化下的代码行为
- ReleaseWithDebInfo + LTO 用于构建最终的二进制产物

其中 address sanitizer 依赖 compiler-rt，不同版本的 compiler-rt 不能混用，不同编译器的更不能，这就要求我们得锁死编译器版本。同时还有著名的 glibc 版本问题，在高版本 glibc 上构建的程序会由于依赖高版本的 glibc 符号无法运行在低版本的 glibc 上。而我们的 C++ 编译器版本又很高，一般支持它们的 Linux 发行版的 glibc 版本也很高，比如 ubuntu 24.04，如何解决预编译二进制 glibc 版本的问题？同时还要确保 CI 环境与本地开发环境一致。为了能够优雅的解决这个问题，我们进行了很多探索。

## Exploration

首先静态链接 glibc 是非常不推荐的行为，原因很复杂，可以参考 [Why is statically linking glibc discouraged?](https://stackoverflow.com/questions/57476533/why-is-statically-linking-glibc-discouraged) 这个讨论。与之相对的，另外一个 C 标准库 [musl ](https://github.com/kraj/musl) 对静态链接就十分友好，但是使用它也并非易事，也需要从头构建 C++ 标准库，runtime 等工作，还可能由潜在的性能下降，为了解决主流 Linux 发行版的问题，我们仍然先尝试解决 glibc 的问题。

### Docker

首先最容易想到的方案就是 Docker 了，借助 Docker 我们理论上可以统一不同平台的开发环境，只需要为每个平台提供对应的装好所有依赖的 Docker 镜像就好了。但是由于我们环境的特殊性，依赖高版本的 C++ 工具链，但是又想要低版本的 glibc，所以现成的 Linux 发行版的 C++ 工具链我们不能使用，因为他们的 libstdc++ 是使用高版本的 glibc 编译的。怎么解决呢？

一开始的解决方案是找一个低版本的 glibc，然后自己编译出低版本的 glibc。再使用这个低版本的 glibc 去编译高版本的 libstdc++，然后使用这两个产物去编译 LLVM 和 clice。我觉得这个方案复杂度太高了，容易出问题，而且我们对 glibc 和 libstdc++ 的编译选项都不太熟悉，可能会踩到一些坑。

除此之外，Docker 最大的痛点在于其原生跨平台体验不佳（尤其是在 Windows/macOS 上依赖虚拟机）。clice 要在 **Window, Linux, macOS 三个平台**上编译&运行，如果要维护镜像，肯定得这三个平台各一份，而我们又会经常更新工具链的配置和版本，导致构建镜像可能非常频繁，这样维护成本就变得非常高。根据我的观察，大部分用 Docker 来管理开发环境都是仅 Linux 的场景，也就是不考虑跨平台，那这种情况相对来说负担会轻很多。

总之这个方案理论可行，但是因为叠加成本太高，被我否决了，我打算去看看有没有其他更轻量的方式。

### Zig

[zig](https://ziglang.org/) 是一门新兴的编程语言，定位是 better C。为了增强与 C/C++ 的互操作性，zig 在源码层面直接集成了 Clang，通过 `zig cc/zig c++` 这两个命令，你可以将 zig 作为 C/C++ 编译器使用。并且 zig 直接将各个 target 的 sysroot 集成到了安装包中，使得我们能极为方便的进行交叉编译，可以在 [zig-bootstrap](https://codeberg.org/ziglang/zig-bootstrap) 来获取各个 target 的 支持情况。例如，使用如下命令进行交叉编译

```bash
zig c++ -target x86_64-linux-gnu.2.17 main.cpp -o main
```

生成的 main 就是使用 glibc 2.17 编译出来的了，无需任何额外的设置，这简直太方便了。由于 zig C++ 就是 Clang 的包装器，所以也是能用于编译 clice 的，这意味着我们有望通过 zig 来统一不同平台的开发环境的同时解决 glibc 的版本问题。

然而在实际尝试之后，我失败了，主要原因有如下几点：

- zig 把所有 glibc 版本的头文件都打包在一起，然后通过宏来控制是否使用某些头文件。但是 C++17 支持了使用 `__has_include` 来检测一个头文件是否存在，一个在低版本 glibc 本不应该存在的头文件，在 zig 打包的头文件里面却会存在。导致 `__has_include` 误判，进而导致编译失败
- zig 同样直接集成了 libc++ libunwind libcxxabi 等 LLVM 生态的 runtime，并现场编译使用，我尝试了各种方法想换到其他 runtime 都不行。后面看了源码，它直接强制注入编译参数，并且目前确实没有提供方法让你修改
- clice 在未来自身支持 C++20 module 的特性后，也打算将源码迁移到 module 上。而 zig 并不支持使用 `import std`，由于它强制隐式以非 module 的方式构建 libc++，我无法控制它使用我构建的 libc++ 模块
- zig 目前还不支持 Windows-MSVC 的交叉编译，并且 macOS 上强制使用自己的链接器，目前开启 LTO 会直接在命令行解析阶段报错

总之就是踩了很多坑，为了未来考虑，最后也是不打算使用 zig 了。不过如果你没遇到我们这些问题的话，还是可以用的，zig cc 确实是一个非常方便的交叉编译工具，尤其是当你需要将代码发布到多个不同平台的时候。但是 clice 其实并没有强烈的交叉编译需求，所以这点优势还不足以覆盖上面我们遇到的问题。

### Pixi

于是我仔细思考了我们的问题，现在的主要难点就是 Linux 上低版本的 glibc 和高版本的编译器之间的冲突。自己构建又太麻烦，如果有人专业的人构建好了，那我们直接拿来用不就解决了？抱着这样的想法，我开始搜索是否存在这样的东西，AI 告诉我可以使用 micromamba，它使用 conda-forge 的包，上面的软件大部分都是基于 glibc 2.17 编译的。

conda？我对它的印象只有在 Windows 上使用 Anaconda 来装深度学习的依赖，装了很久很久，启动还很慢。我还被告知过不要在公司里使用 conda，它是收费的。总之全是坏印象，难用还收费。但是抱着试一试的态度还是安装了一下，发现确实，它上面有 `sysroot_linux-64` 的包，直接指定版本 `==2.17` 就可以获取低版本的 glibc 了。而且它环境里面的高版本编译器会自动使用这个 sysroot，无需额外的参数配置，和 zig 有异曲同工之妙，都是开箱即用的。

> 仔细看了看 Anaconda 的收费 [政策](https://www.anaconda.com/legal)，conda 软件本身是开源的，conda-forge 这类由开源社区维护的 channel 上的包也是免费的，只有在使用默认的官方 default 源的时候才对商业公司收费。可以在这个博客 [Towards a Vendor-Lock-In-Free conda Experience](https://prefix.dev/blog/towards_a_vendor_lock_in_free_conda_experience) 找到相关的讨论。

更进一步，我发现了 [pixi](https://pixi.prefix.dev/latest/)，这是一个基于 conda-forge 的包管理器。它允许声明式的方式来安装 package。然后仔细查看了 conda-forge 的包，发现 Windows，Linux，macOS 的包都很齐全。于是我立马想到我们可以用 pixi 来统一不同平台的开发环境！同时解决 glibc 的问题。

编写如下的 `pixi.toml` 描述文件：

```bash
[workspace]
name = "clice"
version = "0.1.0"
channels = ["conda-forge"]
platforms = ["win-64", "linux-64", "osx-arm64"]

[dependencies]
python = ">=3.13"
cmake = ">=3.30"
ninja = "*"
clang = "==20.1.8"
clangxx = "==20.1.8"
lld = "==20.1.8"
llvm-tools = "==20.1.8"
compiler-rt = "==20.1.8"

[target.linux-64.dependencies]
sysroot_linux-64 = "==2.17"
gcc = "==14.2.0"
gxx = "==14.2.0"
```

使用 `pixi shell` 激活环境，即可在这三个平台上自动安装上面的 package。同时在 Linux 上自动安装低版本的 glibc sysroot 和高版本的 libstdc++，一个如此轻量级的工具，统一了不同平台的开发环境。这才是我心目中的完美解决方案！比 Docker 好太多了。

不仅解决了工具链一致性问题，pixi 还有很多其他锦上添花的实用功能，首先它同样能用于管理 Python 依赖（通过源码集成 uv 来管理 pypi 的依赖），而 clice 刚好使用 Python 进行一些集成测试，也能使用 pixi 顺便管理了（在这之前，我们还使用 uv 来安装和管理 Python，虽然 uv 挺好用的，但是如果能用一个工具搞定，我们不想装第二个）。

```bash
[feature.test.pypi-dependencies]
pytest = "*"
pytest-asyncio = ">=1.1.0"
pre-commit = ">=4.3.0"
```

除此之外，它拥有基于 [deno_task_shell](https://docs.deno.com/runtime/reference/cli/task/#task-runner) 的非常灵活的 task runner。之前我总是编写一些本地的 shell 脚本来方便我本地开发，但是从来不传到仓库里，因为没法在 Windows 上用。现在通过 `pixi` 的 `tasks` 可以很方便的定义一些跨平台的方便任务，也方便其他开发者使用，比如构建，运行单元测试，集成测试之类的。

```bash
[tasks.ci-cmake-configure]
args = ["build_type"]
cmd = ["cmake", "-B", "build", "-G", "Ninja",
    "-DCMAKE_BUILD_TYPE={{ build_type }}",
    "-DCMAKE_TOOLCHAIN_FILE=cmake/toolchain.cmake",
    "-DCLICE_ENABLE_TEST=ON",
    "-DCLICE_CI_ENVIRONMENT=ON",
]
```

除此之外，pixi 还支持灵活的环境组合，可以轻松为不同的环境定义不同的依赖，总之就是非常契合我们的需求。于是我立马使用 pixi 开始管理 clice 的开发环境。在能轻松的保证本地环境和 CI 环境一致之后，构建预编译二进制也就不是什么难事了。于是终于 clice 可以支持在 glibc 2.17 的操作系统上运行了。

## Summary

这篇文章主要讨论了 C++ 构建复杂度从何而来，以及在通过预编译二进制来加快 CI 构建速度的时候所遇到的一系列于工具链版本有关的构建问题，最后在不断地试错后发现可以使用 pixi 来锁死工具链版本从而降低复杂度。这套 workflow 的关键就是使用 pixi 来创建可复现的构建环境，实际的构建和包管理还是交给 CMake/xmake 来的。现在开发者可以轻松的复现 CI 环境，而 CI 的可靠性我们早就在无数次的测试中保证了，于是他们可以非常快速的配置环境进行开发，也降低了新的开发者贡献的门槛。

> 现在在 Linux 上可以做到不依赖任何系统里的工具链，全部使用 pixi 安装的工具链进行编译，可以说是完全可复现了。<br>但值得注意的是 Windows 和 macOS 由于 SDK 许可证的问题，并不是可分发的，目前还需要开发者电脑上装了相关的开发工具。也就是说，如果要在这两个平台上编译的话，开发者必须自行安装并配置系统原生的构建工具链 (如 Windows 的 MSVC/Windows SDK 或 macOS 的 Xcode Command Line Tools)。这个问题暂时没有完美的替代方案。或许等到 LLVM libc 正式发布并成熟后，我们可以统一切换到 LLVM 全套工具链，从而通过工具链自举来彻底消除对操作系统原生 SDK 的依赖。但在另一方面，这两个平台拥有更优异的 ABI 稳定性和 libc 兼容性。与 Linux 上常见的 glibc 版本依赖问题不同，Windows 和 macOS 即使在最新版本的系统上进行构建，通常也只需简单的配置，即可让产物兼容较低版本的操作系统。

那么 pixi 是银弹吗？显然不是。实际上它的隔离性和可复现性并不如 Docker 或者 nix 这样的方案，毕竟只是基于**环境变量**做了一些隔离。如果有人在构建脚本里硬编码了系统里的依赖，或者修改系统里的配置，那 pixi 当然是无能为力的了。但这是我们在易用性和可复现性之间的 trade-off，能以较低成本实现如此高的跨平台可复现性已经相当值得。

另外一点是，很多 C++ 开发者在意的包管理器话题在文章里却寥寥几笔带过，为什么呢？如前文所说，这里已经有了很多的 C++ 包管理工具，但是包管理的可用性取决于是否有足够可靠的人打包。C++ 混乱的工具链和构建系统注定了这样的结局，中心化的仓库一定无法满足大家形态各异的需求。不过对于个人开发来说使用 xmake 这样的工具已经十分够用了。

我个人的观点是，虽然中心化的包管理不太现实，但是指定一些标准来降低不同生态之间互相沟通的成本是非常可行并且有巨大价值的。举个例子，很多开发者在写构建系统的时候可能根本没有考虑不同工具链的问题，添加编译选项也都是硬编码的，换了一个工具链就出错了。遇到这种情况，打包的人就只能 patch 构建系统来解决，效率很低。如果这里有某种**标准化的工具链**，内容很简单就是主流工具链的交集，你想添加一个功能，比如开启 sanitize，不是通过直接在 CMake 字符串里添加编译选项，而是有一个标准化的接口，自动根据工具链不同选择不同的开关，那样不是很方便吗？

> xmake 中其实有 toolchain 的抽象，也有一些 set_policy 可以实现我上面提到的效果，虽然并不多。不过我想说的是这其实是一个上下游共同努力的过程，仅靠构建系统侧做抽象很容易遇到一些 corner case，这时候就需要上游能够及时修复相关工具链的错误了。

类似的，虽然包管理不能做到中心化的，但是不同构建系统的包是否能互相方便的使用呢？其实没什么难度，C++ 主要的引用方式还是 `include` + `lib`，很简单，关键是提供一些额外的元信息，确保 package 的可用性。目前有这样的标准存在 [Common Package Specification (CPS)](https://cps-org.github.io/cps/overview.html)，但是并不被 C++ 社区广泛承认。
