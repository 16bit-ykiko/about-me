---
title: Building an Elegant C++ Cross-Platform Development and Build Workflow
date: "2025-12-20 22:51:31"
updated: "2026-03-27 14:29:52"
zhihu_article_id: "1985940996270339378"
zhihu_url: https://zhuanlan.zhihu.com/p/1985940996270339378
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

C++ build issues have always been a hot topic, especially in various language wars, where they are often used as a negative example. Interestingly, most C++ programmers are often involved in maintaining existing systems, facing highly solidified, unchangeable build processes. The number of people who actually need to set up a project from scratch is in the minority.

This leads to an awkward situation: when you really need to build from scratch and want to find reference cases, you'll find that there is no so-called Best Practice, only various unsystematic workarounds, which is very frustrating.

clice is also a C++ project started from scratch, and inevitably, we've made almost all the same mistakes our predecessors did. Recently, we've finally figured out a workflow that we consider quite elegant. So, we want to take this opportunity to share this solution and, by the way, popularize some of the principles and knowledge behind C++ builds. We hope it will be helpful to you!

## Where does complexity come from?

Before discussing solutions, let's first analyze the problem. Where does the complexity of C++ builds actually come from? If there were a package manager, would all problems be solved?

I believe the complexity mainly comes from two different dimensions: the **toolchain** and the **build system**.

### Toolchain

So what is a toolchain? Besides the compiler and linker, it also includes more details that are overlooked by most tutorials. We can break down these concepts with a simple command.

Consider the following file. Executing `clang++ -std=c++23 main.cpp -o main` will give you an executable program.

```cpp
// main.cpp
#include <print>

int main () {
    std::println("Hello world!");
    return 0;
}
```

So, the first question is, we all know that the traditional C/C++ compilation model is divided into two processes: compile and link. First, the compiler is called to compile intermediate `.obj` files, and then the linker is used to link them into an `executable`. Why did we get it done with just one command here?

This is because clang++ is just a **driver**; it will call the compiler and linker for you to complete all the work. How can we verify this? clang has a command-line option `-###` that can be used to only output the underlying commands to be executed, without actually executing the tasks.

For example, executing `clang++ -### -std=c++23 main.cpp -o main` on my Linux environment produces the following output (unimportant information has been omitted with `...`):

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

You can see that clang++ indeed calls the compiler and linker underneath to complete the tasks. What's more noteworthy is that it injects a large number of **implicit flags**! In fact, the often-ignored part of the toolchain is these implicit compilation parameters.

> GNU-style compilers like g++ and clang++ can often directly call the linker and inject these implicit parameters. Therefore, build systems will call them directly instead of the linker to perform linking. You can use options like `-fuse-ld` to switch the linker launched by the driver. This also explains why compiling C++ programs with clang instead of clang++ results in many undefined references to the C++ standard library. In fact, on many distributions, both clang and clang++ are just symbolic links to `/usr/lib/llvm-20/bin/clang`, and this binary program injects different implicit parameters based on the program name and other arguments.<br><br> On the other hand, MSVC-style compilers like cl.exe or clang-cl tend to pass these implicit states (such as `INCLUDE`, `LIB`, and `LIBPATH`) through environment variables. Therefore, before using these compilers, you usually must first run the initialization script vcvarsall.bat provided by Visual Studio to "activate" the current terminal's environment, or build directly in the Developer Command Prompt. Otherwise, the compiler will report errors because it cannot find standard library headers or system libraries. In this case, the build system will generally also call the linker directly to perform linking.

A complete toolchain can be considered to consist of three parts: **Tools**, **Runtime**, and **Environment**.

Tools are the various utilities used during the build process, including:

- Compiler Drivers: Responsible for orchestrating the entire process, such as g++ and clang++.
- Translators: The actual compilers and assemblers responsible for translating C++ code into machine code, such as cc1 and as.
- Linkers: Responsible for piecing together fragmented `.o` files and library files, such as ld, lld, and mold.
- Binutils: Responsible for auxiliary tasks like archiving, format conversion, and symbol processing, such as ar, objcopy, strip, and nm.

Runtime refers to the various libraries implicitly linked in the options above. They are essential:

- C Runtime (CRT) Startup Objects: These are the `Scrt1.o`, `crti.o`, `crtn.o`, etc., seen in the log. After the operating system loads the program, the first address it jumps to is usually `_start` in the CRT. These object files are responsible for initializing the stack, heap, running global constructors (a C++ feature), and finally calling `main`. They also perform cleanup work after `main` returns.
- C Standard Library: Corresponds to `-lc` in the log. This is the implementation of the C standard library, providing POSIX or system API wrappers that interact with the operating system kernel, such as `malloc`, `printf`, and `open`. Common implementations include GNU's glibc and musl, UCRT on Windows, and the developing llvm libc from the LLVM community.
- C++ Standard Library: Corresponds to `-lstdc++` in the log. It provides implementations of high-level C++ standard library features like `std::vector` and `std::iostream`. It's worth noting that it usually depends on lower-level Compiler Support Libraries to implement features like exceptions and RTTI. The main implementations are libstdc++ (gcc's standard library), libc++ (clang's standard library), and MSVC STL.
- Compiler Support Libraries: Corresponds to `-lgcc_s` in the log. This is a class of easily overlooked but crucial libraries. They are mainly responsible for two things:
  - Builtins: Handling operations that the target CPU's instruction set cannot directly support. For example, performing a 64-bit division on a 32-bit CPU, or soft-float operations on a CPU without floating-point support. The compiler translates these operations into calls to functions like `__udivdi3`.
  - Language Runtime Support: The implementation of some advanced C++ features. For example, Exception Handling (exception catching and stack unwinding) is usually provided by `libunwind` or `libgcc_eh`; while the C++ ABI (for features like `dynamic_cast`, `RTTI`) is provided by `libcxxabi` or `libsupc++`. In the Windows MSVC environment, these are usually encapsulated together in `vcruntime140.dll`.

- Sanitizer Runtimes: These are the libraries (like `libclang_rt.asan.so`) linked when you enable `-fsanitize=address/thread/memory`. They work by inserting instrumentation code at compile time and taking over the memory allocator (malloc/free) at runtime, using Shadow Memory technology to detect undefined behaviors like memory out-of-bounds and data races.

Environment is the context in which the compilation is executed, including:

- Target Triple: Corresponds to `-triple x86_64-pc-linux-gnu` in the log. It defines the detailed "identity" of the target platform, usually in the format `<arch>-<vendor>-<sys>-<abi>`. It determines what instruction set the compiler generates (x86 vs ARM), what object format to use (ELF vs PE), and the details of calling conventions.
- Cross Compilation: This is a very important concept in modern builds. When the Host (the machine running the compiler) is different from the Target (the machine running the product), you are cross-compiling. This difference is not just about CPU architecture (e.g., compiling for ARM on x86), but can also be about the operating system or even the C runtime library version (e.g., compiling a product that depends on glibc 2.17 on a system running glibc 2.35).
- Sysroot (System Root): To solve the problem of environment pollution during cross-compilation, Sysroot was created. It is a logical root directory that simulates the file system structure of the target machine. When you specify `--sysroot=/path/to/sysroot`, the compiler will ignore the host system's `/usr/include` and look for dependencies in the Sysroot instead.

It's worth noting that most platforms have a default toolchain, such as the MSVC toolchain on Windows, which includes a complete set of tools like the compiler, linker, various utilities, and runtime libraries. There's the GNU toolchain on Linux and the Apple Clang toolchain on Mac. Many platforms have more than one; Windows also has the MinGW toolchain, and all these toolchains can be partially switched to the LLVM toolchain.

### Build System

Having solved the toolchain problem for a single file, we've managed compilation and linking using the compiler driver. But in the real world, projects often contain thousands of source files. The core task of a **Build System** is to figure out how to efficiently and correctly direct the toolchain to assemble these thousands of files into the final product.

We can examine the development of C++ build systems from the perspective of "complexity" evolution over time:

1. The Primitive Era: Shell Scripts

In the very beginning, building a project meant writing a Shell script. The logic was very crude: list all `.c` files, hardcode the compiler path, and call it directly. As the project grew, every time a single line of code was modified, hundreds of files had to be recompiled from scratch. The waiting time went from a few seconds to tens of minutes, resulting in a terrible development experience.

2. The Cornerstone of Build Systems (1976)

To solve the problem of redundant compilation, Stuart Feldman at Bell Labs created **Make**. It introduced the **Dependency Graph** and **Incremental Build**. By comparing file timestamps (mtime), if `main.cpp`'s modification time is later than `main.o`'s, it gets recompiled; otherwise, it's skipped. This simple rule laid the foundation for build systems.

**3. The Portability Crisis (1990s)**

In the 90s, operating systems blossomed (Solaris, HP-UX, Linux, BSD, Windows). Although Make solved automation, Makefiles were not portable. Different OSs had completely different Shell commands, compiler flags, and library paths. The world split into two camps:

- Unix Camp - Autotools (GNU): The famous `./configure && make`. Its core idea is "probing"—running a large number of scripts before the build to scan the system environment (is there a `unistd.h`? where is `libz`?), and then dynamically generating a Makefile adapted to the current system.
- IDE Camp (Visual Studio / Xcode): Windows and Mac chose another path—deeply integrating the build system with the editor. Visual Studio's `.sln` and Xcode's `.xcodeproj` provided an out-of-the-box experience, but at the cost of sacrificing automation and flexibility, and being completely non-cross-platform.

4. True Cross-Platform (CMake, 2000s)

With the explosion of open-source software, code needed to run on both Linux servers and Windows desktops. To end the nightmare of "maintaining two sets of build scripts," CMake was born. CMake is not a build tool; it's a **Meta-Build System**, or a **Generator**. Developers write an abstract `CMakeLists.txt`, and CMake is responsible for "translating" it into the native dialect of each platform—generating `.sln` files on Windows, `.xcodeproj` on Mac, and `Makefile` on Linux.

5. Modern Engineering: The Challenges of Scale and Reproducibility (2010s - Present)

Entering the era of mobile internet and cloud-native, giants (Google/Meta) saw their code repositories swell to hundreds of millions of lines (Monorepo), and polyglot programming became the norm. New scenarios naturally brought new problems:

- Build Speed: Makefile's parsing speed is too slow and doesn't support distribution. We need to shard compilation tasks and send them to a cluster, which is known as **Distributed Build**, and implement **Remote Caching**—if colleague A has already compiled `base_lib`, colleague B should just download the cache instead of wasting local CPU to recompile.
- Environment Consistency (Hermetic Build): It works on my machine, but fails on CI or other machines. This is the biggest pain point in modern development, usually caused by using dependencies from host system directories (like `/usr/include`) with inconsistent versions. Modern builds pursue **Hermeticity**—the build process must be like running in a sandbox, strictly prohibiting access to undeclared system libraries to ensure **Reproducible Build**.
- Polyglot: A modern project often uses C++ for the backend, Python for glue code, Rust for security components, and TypeScript for the frontend. CMake is very painful to use for non-C/C++ languages.
- Dependency Management: Whether a project is large or small, it often needs to introduce third-party libraries. However, C++ has long lacked a unified package manager like Rust's Cargo or Node's npm. Developers have to manually handle source code downloads, matching build parameters (Debug/Release, Static/Shared), and complex ABI compatibility issues. Traditional git submodules or system-level package managers (like apt/brew) are often inadequate in cross-platform and multi-version scenarios.

To solve these problems, many new tools have emerged:

- `Ninja`: A new build backend, a replacement for Make, with extremely fast build speeds.
- `FetchContent/Conan/vcpkg`: Aim to reduce the difficulty of introducing dependencies in CMake.
- `ccache/sccache`: Calculate a cache key based on compilation inputs (compiler version/flags, preprocessed results, etc.) to achieve cross-project/cross-machine reuse (sccache can also do remote caching).
- `distcc/icecream`: Distributed build, distributing compilation tasks to other machines.
- `Bazel/Buck2`: Build systems written by Google and Meta based on their internal scenarios. They execute builds in a sandbox, come with a built-in build cache, and achieve good hermeticity and cross-language support.
- `Meson/XMake`: Modern build systems with built-in package management, using `python like dsl/lua` as the build language, aiming to provide higher usability than CMake.

### Summary

Now we can answer the question from the beginning: where does the complexity of C++ builds come from? It actually comes from the combinatorial explosion caused by freedom. C++ has so many toolchains and so many build systems. It's easy for a build system configuration that works with my toolchain to fail with another. Add to that the various implicit compiler flags that can hide problems, and you might not even realize it. But now you probably have an intuitive understanding.

## Purpose

Now, we can formally discuss clice's build issues. First, we need to clarify our goals. What do we want to achieve? We hope to have the following three environments for building.

- Develop: For developers' local development. We want the local build/compile speed to be as fast as possible to reduce interruptions caused by waiting for compilation. We also need to ensure debug information is preserved for easy debugging. We must enable sanitizers like the address sanitizer to catch errors early in the development process.
- CI: For automatic builds on platforms like Github Actions, running unit/integration tests to ensure reliability. We also want the build/compile speed to be as fast as possible. We want to test on different platforms/environments as much as possible to prevent crashes due to accidental reliance on platform-specific features. We also hope to keep the CI environment consistent with the Develop environment so that CI errors can be reproduced locally.
- Release: For building the final distributable binary product. We want the product to be as fast as possible, ensuring it's built with LTO. We want the program to print a function call stack in the logs when it crashes, to help locate the scene when users file issues. We also want the binary distributed to users to be as small as possible, so we want to strip debug information into a separate file (this can reduce the program size by about 2/3). When needed, we can use the relative addresses to get the corresponding symbols. We also want as few runtime dependencies as possible and will statically link the entire program.

First, let's consider clice's build dependencies. Currently, they are `llvm`, `libuv`, `spdlog`, `toml++`, `croaring`, `flatbuffers`, and `cpptrace`. It is built with C++23 and depends on a high-version C++ compiler. It uses different C++ standard libraries on different platforms:

- Windows: msvc stl
- Linux: libstdc++
- macOS: libc++

As you can see, clice doesn't actually have many dependencies, so the complexity of dependency management is not high. We have two build systems: CMake uses `FetchContent` to manage these dependencies, while XMake uses its built-in package manager, xrepo. Since our number of dependencies is small, the complexity here is not high. Both CMake and XMake support pulling source code and building it locally (building dependencies from source), which meets our need for build consistency. Most dependencies have very few source files and have little impact on build speed, except for LLVM!

## Prebuilt Libraries

clice depends on the clang libraries to parse the AST. Even if we only build the necessary targets, the number of files to build is as high as 3,000. Building on Github CI takes an average of two hours. Since we want CI to be as fast as possible, we need to consider optimizing LLVM's build speed. Two methods easily come to mind:

1. Github Actions supports caching. We can use ccache to cache LLVM's build results and reuse them between different workflows. However, this method is not stable, especially since LLVM's build results take up a lot of disk space, which can easily fill up Github's cache.
2. Pre-compile LLVM and publish the binaries on Github Releases. Then, just download them during the build. This way, not only can CI builds use them, but users who want to compile and develop clice locally can also use them.

At first, we used Github Actions for caching, but after running into problems, we decisively switched to maintaining pre-compiled binaries. However, building pre-compiled binaries is not a simple matter. The biggest problem is ABI compatibility. The combinations of C++ toolchains/build parameters are numerous, and many options can affect the ABI. For a discussion on C++ ABI, you can refer to [Thoroughly Understanding C++ ABI](https://www.ykiko.me/en/articles/692886292).

We need to support three platforms: Windows, Linux, and macOS. For each platform, we need to build three different versions of the product to meet our needs:

- Debug + [Address Sanitizer](https://clang.llvm.org/docs/AddressSanitizer.html) to expose undefined behavior in the code as early as possible.
- ReleaseWithDebInfo to test code behavior with optimizations enabled.
- ReleaseWithDebInfo + LTO to build the final binary product.

The address sanitizer depends on compiler-rt. Different versions of compiler-rt cannot be mixed, let alone those from different compilers. This means we have to lock down the compiler version. There is also the infamous glibc version problem: a program built on a high-version glibc will fail to run on a low-version glibc due to dependencies on high-version glibc symbols. And our C++ compiler version is very high, and the Linux distributions that support them generally have high glibc versions too, like Ubuntu 24.04. How do we solve the glibc version problem for pre-compiled binaries? We also need to ensure that the CI environment is consistent with the local development environment. To solve this problem elegantly, we did a lot of exploration.

## Exploration

First, statically linking glibc is a highly discouraged practice for complex reasons, which you can read about in this discussion: [Why is statically linking glibc discouraged?](https://stackoverflow.com/questions/57476533/why-is-statically-linking-glibc-discouraged). In contrast, another C standard library, [musl](https://github.com/kraj/musl), is very friendly to static linking. But using it is not easy either; it requires building the C++ standard library, runtime, etc., from scratch, and there might be potential performance degradation. To solve the problem for mainstream Linux distributions, we still tried to solve the glibc problem first.

### Docker

The most obvious solution is Docker. With Docker, we can theoretically unify the development environment across different platforms by providing a corresponding Docker image with all dependencies installed for each platform. However, due to the special nature of our environment—we depend on a high-version C++ toolchain but want a low-version glibc—we cannot use the C++ toolchains from existing Linux distributions, because their libstdc++ is compiled with a high-version glibc. How to solve this?

The initial solution was to find a low-version glibc, then compile a low-version glibc ourselves. Then use this low-version glibc to compile a high-version libstdc++, and then use these two products to compile LLVM and clice. I felt this solution was too complex and prone to problems. Moreover, we are not very familiar with the compilation options for glibc and libstdc++, so we might run into some pitfalls.

Besides, Docker's biggest pain point is its poor native cross-platform experience (especially on Windows/macOS where it relies on a VM). clice needs to be compiled and run on **Windows, Linux, and macOS**. If we were to maintain images, we would need one for each of these three platforms. And since we frequently update the toolchain configuration and version, building images could become very frequent, making the maintenance cost very high. From my observation, most people who use Docker to manage development environments are in Linux-only scenarios, meaning they don't consider cross-platform. In that case, the burden is much lighter.

In short, this solution is theoretically feasible, but because the cumulative cost was too high, I rejected it. I decided to look for other, more lightweight methods.

### Zig

[zig](https://ziglang.org/) is an emerging programming language, positioned as a "better C". To enhance interoperability with C/C++, zig integrates clang directly at the source code level. Using the `zig cc`/`zig c++` commands, you can use zig as a C/C++ compiler. Furthermore, zig directly integrates the sysroot for various targets into its installation package, making it extremely convenient for us to perform cross-compilation. You can check the support for various targets at [zig-bootstrap](https://codeberg.org/ziglang/zig-bootstrap). For example, use the following command for cross-compilation:

```bash
zig c++ -target x86_64-linux-gnu.2.17 main.cpp -o main
```

The generated `main` will be compiled with glibc 2.17, without any extra setup. This is incredibly convenient. Since `zig c++` is just a wrapper for clang, it can also be used to compile clice. This meant we hoped to use zig to unify the development environments across different platforms while solving the glibc version problem.

However, after actually trying it, I failed. The main reasons are as follows:

- Zig bundles the header files for all glibc versions together and uses macros to control whether certain headers are used. But C++17 supports using `__has_include` to detect if a header file exists. A header that shouldn't exist in a low-version glibc does exist in Zig's bundled headers. This causes `__has_include` to misjudge, leading to compilation failures.
- Zig also directly integrates runtimes from the LLVM ecosystem like libc++, libunwind, and libcxxabi, and compiles them on the fly. I tried various methods to switch to other runtimes, but none worked. After looking at the source code, it directly forces the injection of compilation parameters, and there is currently no way to modify them.
- In the future, after clice itself supports C++20 modules, we also plan to migrate the source code to modules. But Zig does not support `import std`. Since it implicitly forces the non-module build of libc++, I cannot control it to use the libc++ module I built.
- Zig currently does not support cross-compilation for windows-msvc, and on macOS, it forces the use of its own linker. Currently, enabling LTO will cause an error right at the command-line parsing stage.

In short, we ran into many problems. For the sake of the future, I decided not to use Zig in the end. However, if you don't encounter the problems we did, it's still usable. `zig cc` is indeed a very convenient cross-compilation tool, especially when you need to release your code to multiple different platforms. But clice doesn't have a strong need for cross-compilation, so this advantage is not enough to outweigh the problems we encountered.

### Pixi

So I thought carefully about our problem. The main difficulty now is the conflict between the low-version glibc and the high-version compiler on Linux. Building it ourselves is too much trouble. If some professionals have already built it, can't we just use their work to solve the problem? With this idea in mind, I started searching for such a thing. AI told me I could use micromamba, which uses packages from conda-forge, where most of the software is compiled against glibc 2.17.

Conda? My impression of it was only from using Anaconda on Windows to install deep learning dependencies, which took a very long time to install and was slow to start. I was also told not to use conda at work because it's a paid service. In short, all bad impressions: hard to use and costs money. But I decided to give it a try anyway and found that indeed, it has a `sysroot_linux-64` package. Simply specifying the version `==2.17` gets you the low-version glibc. And the high-version compilers in its environment automatically use this sysroot without any extra configuration, which is just as convenient as Zig—out of the box.

> After a closer look at Anaconda's pricing [policy](https://www.anaconda.com/legal), the conda software itself is open-source, and packages on channels maintained by the open-source community, like conda-forge, are also free. Only when using the official default source does it charge commercial companies. You can find related discussions in this blog post: [Towards a Vendor-Lock-In-Free conda Experience](https://prefix.dev/blog/towards_a_vendor_lock_in_free_conda_experience).

Taking it a step further, I discovered [pixi](https://pixi.prefix.dev/latest/), a package manager based on conda-forge. It allows installing packages in a declarative way. Then I carefully checked the packages on conda-forge and found that the packages for Windows, Linux, and macOS are all very complete. So I immediately thought, we can use pixi to unify the development environments across different platforms! And solve the glibc problem at the same time.

Write the following `pixi.toml` description file:

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

Activate the environment with `pixi shell`, and it will automatically install the above packages on these three platforms. At the same time, it automatically installs the low-version glibc sysroot and high-version libstdc++ on Linux. Such a lightweight tool that unifies development environments across different platforms. This is the perfect solution in my mind! Much better than Docker.

Not only does it solve the toolchain consistency problem, but pixi also has many other nice-to-have practical features. First, it can also be used to manage Python dependencies (by integrating uv from source to manage pypi dependencies). Since clice happens to use Python for some integration tests, we can use pixi to manage that as well (before this, we were using uv to install and manage Python; although uv is quite good, if we can get it done with one tool, we don't want to install a second).

```bash
[feature.test.pypi-dependencies]
pytest = "*"
pytest-asyncio = ">=1.1.0"
pre-commit = ">=4.3.0"
```

In addition, it has a very flexible task runner based on [deno_task_shell](https://docs.deno.com/runtime/reference/cli/task/#task-runner). I used to write some local shell scripts to facilitate my local development, but I never committed them to the repository because they couldn't be used on Windows. Now, with `pixi`'s `tasks`, I can easily define some cross-platform convenience tasks, which is also convenient for other developers, such as building, running unit tests, integration tests, and so on.

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

Besides, pixi also supports flexible environment combinations, allowing you to easily define different dependencies for different environments. In short, it fits our needs perfectly. So I immediately started using pixi to manage clice's development environment. After being able to easily ensure that the local environment and the CI environment are consistent, building pre-compiled binaries is no longer a difficult task. And so, finally, clice can run on operating systems with glibc 2.17.

## Summary

This article mainly discussed where the complexity of C++ builds comes from, and the series of toolchain version-related build problems encountered when trying to speed up CI builds with pre-compiled binaries. Finally, after continuous trial and error, we found that we can use pixi to lock down the toolchain version, thereby reducing complexity. The key to this workflow is to use pixi to create a reproducible build environment, while the actual building and package management are still handled by CMake/XMake. Now, developers can easily reproduce the CI environment, and we have already ensured the reliability of CI through countless tests. Thus, they can configure the environment very quickly for development, which also lowers the barrier for new developers to contribute.

> Now on Linux, we can compile without relying on any system toolchain, using only the toolchain installed by pixi, which can be said to be completely reproducible.<br>But it's worth noting that due to SDK licensing issues, Windows and macOS are not distributable, and developers still need to have the relevant development tools installed on their computers. That is, to compile on these two platforms, developers must install and configure the system's native build toolchain themselves (such as MSVC/Windows SDK on Windows or Xcode Command Line Tools on macOS). There is currently no perfect alternative for this problem. Perhaps when LLVM libc is officially released and mature, we can switch to the full LLVM toolchain, thereby completely eliminating the dependency on the operating system's native SDK through toolchain bootstrapping. On the other hand, these two platforms have superior ABI stability and libc compatibility. Unlike the common glibc version dependency problems on Linux, even when building on the latest versions of Windows and macOS, the product can usually be made compatible with lower versions of the operating system with simple configuration.

So, is pixi a silver bullet? Obviously not. In fact, its isolation and reproducibility are not as good as solutions like Docker or Nix, as it's just based on **environment variables** for some isolation. If someone hardcodes a system dependency in a build script or modifies the system configuration, pixi is of course powerless. But this is our trade-off between ease of use and reproducibility. Achieving such a high degree of cross-platform reproducibility at a low cost is already quite worthwhile.

Another point is that the topic of package managers, which many C++ developers care about, was only briefly mentioned in the article. Why? As mentioned earlier, there are already many C++ package management tools, but the usability of a package manager depends on whether there are enough reliable people to package things. The chaotic state of C++ toolchains and build systems dictates this outcome: a centralized repository will never be able to meet everyone's diverse needs. However, for personal development, using a tool like XMake is already quite sufficient.

My personal view is that although a centralized package manager is not very realistic, defining some standards to reduce the cost of communication between different ecosystems is very feasible and has great value. For example, many developers may not even consider different toolchains when writing a build system, and they hardcode compilation options. When you switch to a different toolchain, it breaks. In this situation, the person packaging it can only patch the build system to solve the problem, which is very inefficient. If there were some kind of **standardized toolchain** here—the content would be simple, just the intersection of mainstream toolchains—and you wanted to add a feature, like enabling sanitizers, instead of directly adding compilation options in a CMake string, you would have a standardized interface that automatically selects the correct switch for different toolchains. Wouldn't that be convenient?

> XMake actually has a toolchain abstraction and some `set_policy` options that can achieve the effect I mentioned above, although there aren't many. But what I want to say is that this is actually a process of joint effort between upstream and downstream. Relying solely on the build system side to do abstraction can easily encounter some corner cases, and at that point, it requires the upstream to be able to fix the relevant toolchain errors in a timely manner.

Similarly, although package management cannot be centralized, can packages from different build systems be used conveniently with each other? It's actually not that difficult. The main way C++ uses dependencies is still `include` + `lib`, which is simple. The key is to provide some extra metadata to ensure the usability of the package. There is currently such a standard, the [Common Package Specification (CPS)](https://cps-org.github.io/cps/overview.html), but it is not widely recognized by the C++ community.
