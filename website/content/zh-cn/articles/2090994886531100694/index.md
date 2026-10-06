---
title: 从 import std 开始：现代 C++ 工具链最佳实践
date: "2026-10-07 02:40:30"
updated: "2026-10-07 03:01:55"
zhihu_article_id: "2090994886531100694"
zhihu_url: https://zhuanlan.zhihu.com/p/2090994886531100694
---

> TL;DR：我们做了一个开箱即用、可以交叉编译的 Clang 工具链 [xclang](https://github.com/clice-io/xclang)。一个 86～94 MB 的下载包带齐了 Linux、Windows 和 macOS 各自 x64 和 arm64 一共 6 个平台的 sysroot 和运行时，全平台统一使用 Clang + libc++，C++ 运行时静态链接进程序。`import std` 在 CMake 和 Bazel 里都能直接用，只要有 CMake 和 Ninja，几行 FetchContent 就能试。Apple 和微软的 SDK 由用户用 `xclang sdk fetch` 从官方下载，之后在任何平台上都能编译 macOS 和 MSVC 目标。Clang 和 lld 在所有平台上都做了 PGO + ThinLTO，编译 C++ 的速度在 Linux 和 macOS 上和 LLVM 官方发布版持平，在 Windows 上更快

去年 12 月我写过一篇 [打造优雅的 C++ 跨平台开发与构建 Workflow](https://www.ykiko.me/zh-cn/articles/1985940996270339378)，介绍了 clice 如何使用 pixi 锁死工具链的版本，在三个平台上得到一致的开发环境。不过那篇文章最后还剩了一个问题没解决：Windows 和 macOS 的 SDK 因为许可证的问题不能分发，所以在这两个平台上，开发者仍然需要自己安装 Visual Studio 或者 Xcode。当时我的结论是「这个问题暂时没有完美的替代方案」。

没想到不到一年，就把这个问题解决了。起因是 clice 要迁移到 C++20 模块，要 `import std`，而原来那套方案在这件事上开始拖后腿。于是我们自己做了一个开箱即用、可以交叉编译的 Clang 工具链：[xclang](https://github.com/clice-io/xclang)。一个下载包里带齐了 6 个平台的 sysroot 和运行时，全平台统一使用 Clang + libc++，`import std` 在 CMake 和 Bazel 里都能直接用，Apple 和微软的 SDK 则由用户自己从官方下载。从第一个提交到现在只过去了两周多，代码几乎全部是 agent 写的。

这篇文章就来聊聊它。文档在 [docs.clice.io/xclang](https://docs.clice.io/xclang/)，文中的数据基本都能在那里找到出处。既然标题叫「从 import std 开始」，那我们就从 `import std` 开始吧。

## import std

C++20 引入模块到现在已经好几年了，C++23 又把标准库做成了一个模块 `std`。很多人都知道 C++ 有模块，但是实际用过的人其实很少。它到底长什么样？现在能用了吗？

其实跑通一个 `import std` 的 demo 并不难，CMake 的文档、LLVM 和 GCC 都有现成的例子。难的是在实际项目里真正用起来。在 [语言服务器之外](https://www.ykiko.me/zh-cn/articles/2069934520514749368) 里我引用过一句话：「模块在编译器前端是已解决的问题，在其他所有方面都是未解决的问题」。clice 是一个规模不小的项目，为了它的模块迁移，我们踩了大量的 corner case。不过在说这些坑之前，还是先来看看它长什么样吧。

只要机器上有 CMake (3.28+) 和 Ninja，不需要预先安装任何编译器，你现在就可以试一下。新建一个目录，放入下面两个文件

```cmake
# CMakeLists.txt
cmake_minimum_required(VERSION 3.28)

set(XCLANG_VERSION 23.1.2.8)
include(FetchContent)
FetchContent_Declare(xclang
    GIT_REPOSITORY https://github.com/clice-io/xclang
    GIT_TAG ${XCLANG_VERSION})
FetchContent_MakeAvailable(xclang)
include(${xclang_SOURCE_DIR}/packages/cmake/xclang.cmake)

project(hello LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(xclang REQUIRED CONFIG)

add_executable(hello main.cpp)
target_link_libraries(hello PRIVATE xclang::std)
```

<br>

```cpp
// main.cpp
import std;

int main() {
    std::vector<std::string> targets{"windows", "linux", "macos"};
    std::ranges::sort(targets);
    try {
        throw std::runtime_error(std::format("{} targets, the first {}", targets.size(), targets[0]));
    } catch (const std::exception& e) {
        std::println("hello from xclang: {}", e.what());
    }
}
```

然后执行

```bash
cmake -G Ninja -B build
cmake --build build
./build/hello
```

就会输出 `hello from xclang: 3 targets, the first linux`，在 Windows、Linux 和 macOS 上都是一样的。

这里发生了什么呢？`project()` 之前的那几行通过 FetchContent 拉取了 xclang 仓库对应的 tag，然后 `xclang.cmake` 会根据当前的平台下载对应的工具链，用 release 里的 `SHA256SUMS` 校验之后解压到用户的缓存目录里（每个版本和平台只会下载一次），接下来 `project()` 就会使用这个工具链。`xclang::std` 就是标准库模块 `std`（还有 `std.compat`），把它当作一个普通的库链接上去，`import std` 就可以用了，不需要打开 CMake 的任何实验开关。想交叉编译的话，加一个 `-DXCLANG_TARGET=x86_64-w64-mingw32` 就行了，在 Linux 或者 macOS 上也能直接编译出 Windows 程序。

除了 CMake，Bazel 也可以直接使用，我们在自己的 registry [bazel.clice.io](https://bazel.clice.io/) 上也提供了对应的 module，`deps = ["@xclang//bazel:std"]` 就可以 `import std`，用 `--platforms` 切换目标平台。

那么在实际项目里用它，会遇到哪些问题呢？这里挑几个比较典型的说一说。

### Matching options

首先是编译选项。如果模块文件 (BMI) 的语言选项和 import 它的代码不一样，Clang 会直接拒绝加载，`-std`、GNU 扩展、`-fno-exceptions`、`-fno-rtti` 这些影响语义的选项都必须一致（宏、头文件路径和优化等级倒是可以不同）。比如你的某个 target 用的是 C++26，而 `std` 模块是按 C++23 编译的，那么就会报 `C++26 was disabled in precompiled file` 错误。

也就是说，预编译好的 `std` 模块基本没法用，只有选项和它完全一样的代码才能 import 它。所以 xclang 的做法是不预编译 `std`，每次构建的时候用这次构建的选项现编一份，作为一个库给你链接。在 CMake 里，`xclang::std` 使用的是调用 `find_package(xclang)` 的那个目录的设置（`CMAKE_CXX_STANDARD`、`CMAKE_CXX_FLAGS` 等等），所以这些选项最好在项目级别统一设置。如果某个 target 确实需要不同的选项，比如关闭异常，可以用 `xclang_add_std` 给它单独编译一份 `std`

```cmake
xclang_add_std(std_noexcept)
target_compile_options(std_noexcept PUBLIC -fno-exceptions)
```

> 注意，CMake 自己的 `import std` 支持在 CMake 4.4 里仍然需要设置 `CMAKE_EXPERIMENTAL_CXX_IMPORT_STD`，而且这个变量的值会随着 CMake 的版本变化。`xclang::std` 就是一个普通的库，只不过源文件刚好是模块接口，所以 CMake 3.28 自带的模块支持就够了

### Build caches

然后是构建缓存。实际项目基本离不开编译缓存，尤其是在 CI 上。最常用的 ccache 是根据源文件、命令行和包含的头文件来计算 key 的，但模块文件不在里面。命令行里只有模块文件的路径，而且 CMake 还是通过一个 response file (`@<source>.modmap`) 把它们传给编译器的。如果算 key 的时候不把模块文件的内容算进去，那么模块接口改了之后，import 它的文件照样会命中缓存，拿到的还是修改之前的目标文件。

听起来像是只存在于理论上的问题，那实际情况如何呢？我们用 CMake 给一个模块和 import 它的文件生成的编译命令，在 CI 上用两个版本的 ccache 各跑了三次：第一次直接编译，第二次原样再来一次，第三次把模块导出的常量从 1 改成 2

|               | 模块接口 | import 它的文件，未修改 | import 它的文件，接口修改之后            |
| ------------- | -------- | ----------------------- | ---------------------------------------- |
| ccache 4.13.6 | 不进缓存 | 命中缓存                | 命中缓存，用的是旧的目标文件，程序返回 1 |
| ccache 4.14.1 | 不进缓存 | 命中缓存                | 未命中，重新编译，程序返回 2             |

可以发现，4.13 及之前的版本会直接用旧的目标文件，编出来的程序是错的，而且没有任何提示。4.14 的结果虽然正确，但是模块接口完全不进缓存，每次构建都要把所有的模块接口重新编译一遍，而在一个已经模块化的项目里，这就是很大一部分的编译工作了。这个测试现在一直在 CI 上跑，只要哪个版本的 ccache 行为变了，它就会失败。

Bazel 就没有这个问题。它的每个 action 的 key 是所有输入的内容，而 import 一个模块的文件，输入里就包含这个模块文件。接口变了，模块文件就变了，key 也就跟着变了。不过这里还有一个坑，模块文件里会记录路径，如果路径是绝对的，同样的代码放在不同的目录下，编出来的模块文件就不一样，缓存也就没法在不同的机器之间共用。所以 xclang 的工具链编译模块的时候会加上 `-fmodule-file-home-is-cwd`，让路径都相对于 execution root，这样不管在哪里构建，模块文件都是逐字节相同的，所有机器都能共用一份缓存。clice 为了模块迁移，构建也已经换成了 Bazel。

### libc++

最后是标准库的选择。在 Linux 上，一个很自然的想法是继续用 Clang 编译，标准库则用系统里 GCC 的 libstdc++，毕竟它也提供了 `std` 模块。我们之前在这条路上踩了大量的坑，结论就是不要这样混用。原因其实也不复杂，模块还是一个很新的特性，各家编译器的实现都还有不少 bug，而 `std` 模块会导出整个标准库，标准库里又有大量复杂的模板，很容易就会踩到这些 bug。测试很难覆盖所有的组合，每家编译器测试得最充分的，还是和自己的标准库搭配的情况：libc++ 和 Clang 在同一个仓库里一起开发、一起测试，libstdc++ 则是 GCC 的一部分。一旦混用，就很容易撞上没人测过的 corner case。就目前来看，Clang 对模块的支持最好，配套的 libc++ 对 `std` 模块的支持也最完整。想在三个平台上稳定地 `import std`，最省心的路线就是**全平台统一使用 Clang + libc++**。更多的细节就不在这篇文章里展开了，后面我们会单独写一篇关于模块的文章。

## Background

### Three standard libraries

在那篇 workflow 文章里，clice 在三个平台上使用三套不同的 C++ 标准库：

- Windows：MSVC STL
- Linux：libstdc++
- macOS：libc++

当时这么做的出发点是兼容性，每个平台都用它最「原生」的工具链，可以尽早暴露代码里依赖某个实现细节的地方。只用头文件的时候这么做没问题，但是换成模块就不一样了。模块文件和编译器强绑定，`std` 模块更是要求编译器和标准库紧密配合，所以原来为了测试兼容性而保留的这三套标准库，现在反倒给迁移模块添了麻烦。

### Hermeticity

那篇文章里我们很在意的另一个性质是密封性 (hermeticity)，也就是构建只依赖声明过的输入，产物只依赖目标系统上一定存在的东西。pixi 在 Linux 上做到了一部分，借助 conda-forge 的 `sysroot_linux-64==2.17`，我们可以用新的编译器编译出能在老系统上运行的程序。但这还不够：

- Windows 和 macOS 上依然依赖本机安装的 Visual Studio 和 Xcode，每台机器上的版本都不一样
- conda-forge 的编译器是为了构建 conda 包而设计的，C++ 运行时以动态库的形式由 conda 环境提供，程序一旦离开这个环境，就得自己想办法带上 `libc++.so`
- 交叉编译基本无从谈起，每个平台的产物只能在这个平台的 CI 上构建

我们想要的是，程序在运行时只依赖操作系统自带并且不可再分发的那部分库（glibc，Windows 的系统 DLL，macOS 的 libSystem），其他的全部静态链接进去。实际上这也是 Rust 默认的做法。

### Why now?

那篇文章选择 pixi，很大程度上是因为人力不足。自己从源码构建 glibc、libstdc++ 和 LLVM，再处理各种 ABI 和版本问题，复杂度太高了，我们维护不起。而 conda-forge 上有专业的人帮我们构建好了，直接拿来用就好了。

不过现在有 agent 了。像构建一个 PGO 优化的 LLVM，为 6 个目标准备 sysroot，处理上游的 bug，写 CI 在 6 种机器上反复验证这些事情，目标都很明确，结果也能通过测试来验证，非常适合交给 agent 来做，人手也就不是问题了。

总结一下，我们的需求是：

- 全平台统一的 Clang + libc++，`import std` 开箱即用
- 支持 6 个平台，Linux、Windows 和 macOS 各自的 x64 和 arm64
- 能交叉编译，未来还会有更多的目标
- 程序的运行时依赖尽可能少，不依赖系统里可再分发的库
- 编译器本身要快
- 能接入我们用到的构建系统：CMake、Bazel，以及 Rust 的 cargo

目前并没有现成的工具链能同时满足这些需求，所以我们决定自己做一个。

## Design

### Compiler + sysroot

回忆一下那篇文章，一个完整的工具链由工具 (Tools)、运行时库 (Runtime) 和环境 (Environment) 三部分组成。Clang 本身就是一个交叉编译器，同一个 Clang 可以为 LLVM 支持的任何目标生成代码，所以交叉编译的麻烦其实主要在**目标平台的库**：C 标准库的头文件和库，C++ 标准库，编译器运行时。把这些东西放在一个模拟目标机器文件系统的目录里，就是 sysroot。

所以一个开箱即用的交叉编译工具链，核心就是两样东西：一个编译器，以及每个目标一份 sysroot 和预编译好的运行时。把它们打包在一起，再告诉编译器「编译这个目标的时候去哪里找这些东西」就好了。最后这一步 Clang 已经有现成的机制，就是配置文件。当你执行 `clang++ --target=aarch64-w64-mingw32` 的时候，Clang 会自动读取 `bin/` 下的 `aarch64-w64-mingw32.cfg`，里面写着这个目标的 sysroot、标准库和链接器。于是在 xclang 里，交叉编译就是加一个参数

```bash
clang++ --target=x86_64-unknown-linux-gnu  main.cpp -o main      # Linux x64
clang++ --target=aarch64-unknown-linux-gnu main.cpp -o main      # Linux arm64
clang++ --target=x86_64-w64-mingw32        main.cpp -o main.exe  # Windows x64
clang++ --target=arm64-apple-macos         main.cpp -o main      # macOS arm64
```

无论在 Linux、Windows 还是 macOS 上执行，结果都是一样的。zig cc、Android NDK 和 wasi-sdk 本质上都是这个原理，Rust 的 rustup 和 cross-rs 也是同样的思路，只是对象换成了 Rust 的标准库。

xclang 的发布包里有这些东西：

- `bin/llvm`：Clang、lld 和各种 binutils 合并成的一个程序 (multi-call binary)，其他的工具名都是指向它的链接，这样它们就不用各自带一份 LLVM 了
- 6 个目标的 sysroot：Linux 是 glibc 2.17（正是那篇文章里用的 conda-forge sysroot 包），Windows 是用 Clang 构建的 mingw-w64 (UCRT)，macOS 的 SDK 由用户提供
- 每个目标预编译好的 libc++、libc++abi、libunwind 和 compiler-rt（包括各种 sanitizer），以及一份 ASan 版的 libc++
- 每个目标一个配置文件

运行时都是静态链接进程序的。Linux 程序只需要 glibc 2.17 以上（CentOS 7 的版本，几乎所有还在使用的发行版都能运行），Windows 程序只需要 Windows 10 自带的 UCRT，macOS 程序只需要 macOS 13 以上的 libSystem。一个发布包压缩后是 86～94 MB，LLVM 官方的发布包则有 0.9～2 GB，而且只能编译本机。

> 注意，静态链接 libc++ 也是有代价的，每个共享库都会有自己的一份 libc++。在 Linux 和 macOS 上，一个共享库抛出的标准异常，在另一个共享库里只能用 `catch (...)` 捕获。所以它更适合发布单个可执行文件的场景

### Fetch on demand

zig cc 是这个方向上最有名的项目，一个 55 MB 的下载包就能支持几十个目标。它的做法是把多个版本的 glibc 头文件合并到一起，用宏来区分版本，并且把 libc++ 等运行时的源码打包进去，第一次用到某个目标的时候现场编译。那篇文章里我们就踩过这种设计的坑，合并的头文件会让 `__has_include` 误判，而强制现场构建 libc++ 也让 `import std` 没法用。

对于 macOS，zig 从 Apple 的 SDK 里抽取出 libc 的头文件，自己维护一套 `libSystem` 的桩，这样不需要 SDK 也能编译 macOS 程序（但是大部分 Framework 都用不了）。这个做法很聪明，但我觉得没有太大必要，对用户来说多执行一条下载命令其实没什么区别，而用 Apple 原版的 SDK，Framework 也都可以正常使用。

所以 xclang 的取舍是，常用的 6 个目标直接预编译好放在发布包里，没有首次编译的延迟，每个人下载到的文件都一模一样。其他目标做成单独的包，用到的时候再下载（还在计划中）。而 Apple 和微软的 SDK 不打包，由用户自己从官方下载。

### Vendor SDKs

再回到那篇文章留下的问题。Apple 和微软的许可证允许使用 SDK，但是不允许再分发，所以 xclang 不分发它们，只提供一个命令行工具，让用户自己从厂商的服务器上下载

```bash
xclang sdk fetch macos --accept-license     # Apple 的 Command Line Tools 里的 macOS SDK
xclang sdk fetch windows --accept-license   # MSVC 的 CRT/STL 和 Windows SDK
```

不加 `--accept-license` 的话，它只会打印厂商的许可条款然后退出。所有的版本都写死在一张表里，带 sha256 校验，还提供了和 GitHub Actions runner 镜像一致的预设，CI 里用的是什么版本，本地就能下载到什么版本。整个过程也不需要运行厂商的安装程序。macOS 的 SDK 在 Apple 的 Command Line Tools 包里，不需要 Apple ID，包的格式是 xar 套 pbzx 套 cpio，我们自己写了几百行代码来解包，所以在 Linux 和 Windows 上也能用。MSVC 的 CRT 和 STL 来自 Visual Studio 的 `.vsix` 组件包，Windows SDK 来自 NuGet，都是普通的 zip。

下载之后，`--target=arm64-apple-macos` 在 Linux 和 Windows 上就能直接编译 macOS 程序，Objective-C、Framework、dSYM 和 sanitizer 都可以用。`--target=x86_64-pc-windows-msvc` 则在任何平台上都能编译 MSVC ABI 的 Windows 程序。MSVC 目标默认使用微软叫做 hybrid CRT 的方式，VC 运行时和 STL 静态链接，只有 UCRT 是动态链接的（Windows 10 起它是系统组件），所以程序不需要用户安装任何 VC++ 运行库。这个命令行工具本身是用 Rust 写的，6 个平台的版本也都是拿 xclang 当 C 编译器和链接器编出来的。

> 注意，Apple 的许可条款限定在 Apple 的硬件上使用 SDK，在 Linux 或者 Windows 上用它编译 macOS 程序是否合规，需要用户自己判断

### PGO

编译器在一次构建中会被调用成千上万次，它本身快不快，很大程度上决定了构建要多久。所以 xclang 在每个平台上都用 PGO + ThinLTO 构建 Clang 和 lld。

PGO 的效果取决于训练集，所以训练的时候，我们尽量让插桩版的编译器跑它平时实际会跑的东西：

- 编译 sqlite、abseil 这样的真实代码，`-O0 -g` 和 `-O2` 都有
- 预编译头，以及编辑器场景下的 preamble 和代码补全请求（毕竟 clice 是语言服务器）
- C++20 模块，包括 libc++ 的 `std` 和 `std.compat`，magic_enum、Vulkan-Hpp 这些真实的模块，并且按 CMake 的方式做依赖扫描
- 通过 lld 做 ELF、ThinLTO 和 COFF 链接

整个训练大约调用了 1700 次编译器，跑了 23 分钟。

那么，这一份 profile 能不能用于所有的平台呢？这取决于插桩的方式。Clang 有两种插桩，**IR 插桩** (`-fprofile-generate`) 是在 LLVM IR 经过早期的优化 pass 之后计数的，它靠函数在这个阶段的控制流图算出的哈希来识别函数。问题在于这些 pass 会使用目标平台的代价模型 (cost model)，同一个函数在 x86_64 和 arm64 上的控制流是不一样的，所以在一个平台上采集的 profile 和另一个平台是对不上的。而**前端插桩** (`-fprofile-instr-generate`) 是在 Clang 的 AST 上计数的，函数的哈希由源码计算，同样的源码在任何目标上都会得到同样的哈希。

效果怎么样呢？在 23.1.2.1 之前我们做了一组对照实验。在 Linux x64 上采集的前端 profile，在 6 个平台上都只有 0 或 1 个函数对不上（总共大约 11.3 万个函数），而它带来的加速，和 6 个平台各自采集 IR profile 再合并起来的结果相比，差距在噪声范围以内。下表是编译 abseil / LLVM 的 `Sema` 的耗时，相对于不开 PGO，5 台 runner 取中位数

| 平台        | 前端插桩，Linux 的 profile | IR 插桩，6 份 profile 合并 |
| ----------- | -------------------------- | -------------------------- |
| Linux x64   | 0.725 / 0.727              | 0.722 / 0.721              |
| Linux arm64 | 0.814 / 0.800              | 0.826 / 0.844              |
| macOS arm64 | 0.905 / 0.818              | 0.895 / 0.864              |
| Windows x64 | 0.771 / 0.792              | 0.764 / 0.820              |

所以 xclang 选择了前端插桩（也就是 LLVM 的 `LLVM_BUILD_INSTRUMENTED=Frontend`）。训练只在一台 Linux runner 上跑一次，得到的 profile 用于构建所有平台的工具链，不需要为每个平台单独构建插桩版本、单独训练，也不需要模拟器。

不过前端插桩也有一个小问题。profile 是按函数的 mangled name 来查找的，而源码里的同一个类型在不同的 ABI 下 mangling 并不一样。`size_t` 和 `uint64_t` 在 Linux 上是 `unsigned long` (`m`)，在 Windows 上却是 `unsigned long long` (`y`)，macOS 上的 `uint64_t` 也是 `unsigned long long`。于是一个参数是 `size_t` 的函数，在 Windows 上的名字就和 Linux profile 里的不一样，也就拿不到任何计数。解决办法是一个 remapping 文件 (`-fprofile-remapping-file`)，告诉 Clang 这些 mangling 是等价的。在同一组实验里，加上它之后，macOS arm64 的耗时比从 0.896 / 0.923 降到了 0.794 / 0.845。

> 实际上 remapping 也不能覆盖所有的情况，比如 Windows 上有 230 个函数的模板实参是这些类型的整数字面量，就匹配不上，不过它们只占计数的 1.8%，影响已经很小了

## Comparison

### Similar projects

|                               | 开箱即用的目标                                          | 厂商 SDK                                        | 程序里的 C++ 运行时    | Linux 程序最低 glibc | 构建系统集成               | 编译器 PGO                                |
| ----------------------------- | ------------------------------------------------------- | ----------------------------------------------- | ---------------------- | -------------------- | -------------------------- | ----------------------------------------- |
| xclang                        | Linux / Windows（MinGW 和 MSVC）/ macOS，各 x64 + arm64 | 用户从厂商下载                                  | libc++ 静态链接        | 2.17                 | CMake、Bazel、conda、cargo | PGO + ThinLTO，所有平台                   |
| zig cc                        | 几十个，含 musl、BSD、WASI                              | macOS 自带派生文件；MSVC 依赖本机 Visual Studio | libc++ 静态链接        | 可按目标选择         | zig build、CC="zig cc"     | 未说明                                    |
| LLVM 官方发布                 | 仅本机                                                  | 无                                              | 本机运行时             | 构建机的版本         | 无                         | Linux/macOS PGO + ThinLTO，Windows 仅 PGO |
| llvm-mingw                    | 仅 Windows                                              | 不需要                                          | 默认 libc++ DLL        | 无 Linux 目标        | 任意                       | PGO + ThinLTO                             |
| conda-forge 编译器            | conda 支持的平台                                        | 依赖本机                                        | conda 环境提供的动态库 | 2.17                 | conda-build                | 未说明                                    |
| 发行版 Clang + GCC 交叉工具链 | 每个目标一套包                                          | 无                                              | libstdc++ 动态库       | 发行版的版本         | 任意                       | 取决于发行版                              |

zig 的目标更多，这是它多年积累下来的优势，xclang 打算通过按需下载来补上。xclang 这边则是 sanitizer 齐全（zig 没有 ASan），用的是原版的 Apple SDK，在任何平台上都能交叉编译 MSVC 目标，支持 `import std`，并且有现成的 CMake 和 Bazel 集成。llvm-mingw 和 xclang 的 MinGW 目标其实是同样的思路，只不过 xclang 同时还有 Linux 和 macOS 的目标。更详细的逐项对比可以看 [文档](https://docs.clice.io/xclang/guide/comparisons)。

### Compile speed

我们用 fmt 的测试（模板密集的 C++20）、lua 的 C 源码和预编译 libc++ 的 `std` 模块做基准测试，这些代码都不在训练集里。下表是 xclang 23.1.2.6 相对于 LLVM 23.1.2 官方发布版的耗时（越小越快，每个平台 5 台 runner 取中位数）

| 平台          | fmt (syntax / O0 / O2) | lua (syntax / O0 / O2) | std (O0 / O2) |
| ------------- | ---------------------- | ---------------------- | ------------- |
| Linux x64     | 1.035 / 1.009 / 1.069  | 1.118 / 1.062 / 1.109  | 1.013 / 1.022 |
| Linux arm64   | 1.000 / 0.976 / 1.042  | 1.082 / 1.011 / 1.075  | 0.970 / 0.994 |
| macOS arm64   | 0.902 / 0.935 / 1.014  | 1.169 / 0.971 / 0.959  | 0.980 / 0.890 |
| Windows x64   | 0.798 / 0.825 / 0.890  | 1.083 / 1.050 / 1.001  | 0.777 / 0.849 |
| Windows arm64 | 0.888 / 0.906 / 0.954  | 1.271 / 1.212 / 1.167  | 0.925 / 0.940 |

在 Linux 和 macOS 上，xclang 编译 C++ 的速度和 LLVM 官方的 PGO + ThinLTO 构建基本持平（Linux x64 的官方版本还额外做了 BOLT 优化），C 代码则最多要多花 17% 的时间。Windows 上的差距就比较明显了，官方版本是用 MSVC 构建的，只有 PGO 没有 LTO，xclang 编译 C++ 的耗时在 x64 上少 11%～22%，在 arm64 上少 5%～11%。在 macOS 上我们顺便测了 Apple 自己的 Clang，它编译 fmt 要比 xclang 多花 17%～29% 的时间。作为参照，同样的构建去掉 profile 之后，耗时是 LLVM 官方版本的 1.15～1.37 倍（23.1.2.1 时测得），可以发现 PGO 的作用还是相当大的。

> Windows 上 lua 偏慢，有一部分是启动开销。Windows 上创建符号链接需要额外的权限，所以 `clang++.exe` 是一个很小的启动器，由它再去启动 `llvm.exe`。lua 的源文件都很小，几十毫秒就编译完了，多启动一个进程是看得出来的，直接运行 `llvm.exe` 的话差距会小很多

### Build systems

前面已经展示过 CMake 的用法了，目前 xclang 支持的构建系统和包管理器有：

- pixi / conda：`xclang = "23.1.2.*"`，从 conda.clice.io 安装
- CMake：除了前面的 FetchContent，也可以通过 `find_package(xclang)` 使用已经安装好的工具链，用工具链文件和 `XCLANG_TARGET` 交叉编译
- Bazel：在 [http://bazel.clice.io](https://link.zhihu.com/?target=http://bazel.clice.io) 上提供 module。工具链按 sha256 下载，每个工具链文件都是声明过的输入，action 里不包含任何绝对路径，所以不管代码放在哪个目录，编出来的程序都是逐字节相同的。它为每个 host 和 target 都注册了工具链，用 `--platforms` 切换目标，还带了 `import std`、sanitizer、ThinLTO 缓存、GSYM/dSYM 调试符号等规则
- cargo：作为 Rust 交叉编译时的 C 编译器和链接器

## How we built it

### Numbers

xclang 从头到尾都是用 Opus 5.5 开发的。我主要负责定方向和做决定，代码、脚本、CI 和文档基本都是 agent 写的。从 9 月 21 日第一个提交到现在：

- 177 个提交，8 个正式版本，从 23.1.2.1 到 23.1.2.8
- 1 个 lead agent 负责拆分任务、审查和合并，它先后启动了 23 个 worker 会话，这些会话又派出了 294 个 subagent
- 9403 次工具调用，其中 7623 次是 shell 命令
- 278 次 CI 运行，一共 4988 个 job，累计大约 499 小时的 runner 时间，其中 75 次是完整的工具链构建流水线
- 大约 1.9 万行脚本、测试、CMake/Bazel 集成、Rust 命令行工具和 workflow，文档大约 4.2 万词
- 看板上一共 26 个目标 (objective)

整个开发是「我 + lead + 几个 worker」的结构。我和 lead 讨论方向，比如「MSVC 目标要做成一等公民」「全平台默认 libc++」「厂商 SDK 让用户自己下载」，lead 把它拆成可以独立完成的任务，写成任务描述交给 worker。每个 worker 在独立的 git worktree 和分支上工作，实现之后在 CI 上验证，遇到需要我决定的问题就直接在它的会话里问我。最后由 lead 审查、合并和发版。比较重的构建都是放到 CI 上跑的，本地只做一些轻量的工作，实验也都放在单独的 `exp/` 分支上。另外发过的版本不会再覆盖，哪怕只是重新构建一次，也会发成一个新的版本号。

### Experiments

这两周里 agent 做了大量的实验，很多设计都是做完实验才定下来的，前面 PGO 和 ccache 的数据就来自其中的两个实验。再举几个例子：

- ThinLTO 缓存：libclang 是以 ThinLTO bitcode 发布的，clice 在 Linux 上链接一次要 353 秒，打开链接器的缓存之后只要 6 秒左右。不过在 CI 上有一个很隐蔽的坑，GitHub Actions 恢复缓存的时候会重置文件的访问时间，于是 LLVM 按访问时间清理缓存的策略根本不会生效，缓存只会越来越大
- macOS 的链接器：第一个版本测试的时候就发现，arm64 上用 ThinLTO 一步编译链接的程序没法捕获自己抛出的异常。排查下来是 ld64.lld 处理空段 unwind 信息的 bug，打上补丁之后，macOS 目标在所有主机上就都统一使用 ld64.lld 了
- 发布包的体积：把各个工具合并成一个 `llvm` 程序之后，Windows x64 的包从 540 MB 降到了 82 MB。后来又发现解压之后的 800 MB 里有 155 MB 是重复的头文件，而 xz 并不能把它们压掉
- 可复现：每个发布包都会在两台机器上各打包一次，结果必须逐字节相同。交叉编译出来的程序也都会拿到真实的目标机器上去运行

### agent

说实话，在这类问题上，agent 已经比人强太多了。构建一次 LLVM 要两个小时左右，一个问题往往要反复试很多次才能定位，如果是我自己来做，大部分时间都会花在等 CI 上，而且我也不可能一直盯着，而 agent 可以 24 小时一直试下去。从工具调用的时间分布来看，9403 次调用里有将近一半发生在北京时间凌晨 0 点到 6 点，也就是我睡觉的时候。比如整个文档的重构，一共 37 页，并且每一条命令都要在 6 种机器上实际执行，就是在一个晚上完成的，第二天早上起来我只需要看结果就好了。

当然，这样并行地试错需要足够多的机器。GitHub 的免费版只允许同时运行 20 个 job（其中 macOS 只有 5 个），一次完整的发布要在 6 种机器上构建和测试，交叉编译之后还要拿到目标机器上运行，再加上几个 worker 同时在做实验，很容易就排起队来。所以我们买了 GitHub 企业版，并发提高到了 500 个（macOS 50 个），几十个 job 可以同时跑完，效率高了很多。对于需要反复试错的问题，agent 还可以直接租一台 GitHub Actions 的 runner（包括 Windows 和 macOS），直接在真机上调试。

### Upstream

做工具链免不了会撞上上游的 bug，目前 xclang 在 LLVM 上打了 8 个补丁，主要是这些：

- Clang 的模板偏序 (partial ordering) 和代码补全
- Clang 预处理器输出中 raw string 的行号
- MinGW 环境下 Windows driver 对 SetupAPI 的使用
- libc++ `std::format` 的缓冲区处理
- lld 在 Mach-O 上处理空段的 unwind 信息，也就是前面说的 arm64 上 ThinLTO 程序没法捕获异常的问题
- macOS 27 SDK 里新出现的 `arm64e.x1` 架构，旧版的 ld64.lld 读不了

另外 clice 那边还发现了 LLVM 在 Windows arm64 上崩溃时打印不出调用栈的问题，目前还在研究。

## Roadmap

xclang 想做的，其实就是 Clang 版的 rustup、cross-rs 和 cargo-zigbuild。接下来的计划有：

- 按需下载更多目标：6 个常用目标随工具链分发，其他目标做成单独的包，构建需要的时候再下载。计划中的有 musl（完全静态的 Linux 程序），在考虑的有更多的 Linux 架构（riscv64、loongarch64 等）、WebAssembly、Android、FreeBSD 和裸机目标
- 按需构建运行时：在构建中从源码编译 libc++，以支持预编译版本给不了的选项，比如 MemorySanitizer，libc++ 的 hardening 模式，自定义的 ABI namespace，以及 libc++ 和程序一起做 LTO
- MSVC 目标默认使用 libc++：这样 `import std` 在所有平台上用的就都是 libc++ 了，微软的 STL 作为可选项，留给需要和 MSVC 编译的 C++ 库交互的场景
- Bazel 支持 MSVC 目标，以及在 Linux 和 Windows 上编译 macOS 目标
- 更大的 PGO 训练集：目前的训练还不包括 Objective-C、clang-cl、Mach-O 链接等场景
- 跟进 LLVM 的版本：LLVM 23.1.3 发布后就会升级
- 还在研究中的有 Windows 7/XP（基于 YY-Thunks）、iOS 等 Apple 设备，以及 BOLT

每一项现在的状态（Supported、Planned、In research、Considered、Not planned）都写在 [roadmap](https://docs.clice.io/xclang/design/roadmap) 里了。

## Summary

那篇文章的结尾我说，希望有某种**标准化的工具链**，构建系统可以通过统一的接口来使用它，而不是为每个工具链硬编码编译选项。xclang 算是我们在这个方向上的一次尝试，用它的话，所有平台用的都是同一个 Clang 和同一个 libc++，切换目标只需要一个 `--target`。回头看，那篇文章里很多因为维护不起而没做的方案，现在有了 agent，其实都可以做了。

至于 clice，当然还在继续开发。接下来 clice 自己就要迁移到 C++20 模块了，这也是当初做 xclang 的起因。对于一个已有的大项目来说，手动迁移到模块是一件非常繁琐的事情，所以我们也在开发一些辅助工具，把这个迁移过程自动化。这其实和 [agent 时代的 clice](https://www.ykiko.me/zh-cn/articles/2034883949630059124) 里说的一样，clice 的核心是一套实时的编译系统，语言服务器只是它的一个消费者，所以除了语言服务器，clice 还会做更多这样的工具。后续的进展我也会继续在这里更新。

欢迎试用 xclang，有问题可以在 [GitHub](https://github.com/clice-io/xclang/issues) 上提 issue。感兴趣的话也欢迎加入我们的 QQ 交流群：[https://qm.qq.com/q/tSD3D81fpu](https://qm.qq.com/q/tSD3D81fpu)，感谢阅读！
