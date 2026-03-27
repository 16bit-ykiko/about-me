---
title: Is the singleton pattern in C++ truly a 'singleton'?
date: "2024-05-09 18:08:28"
updated: "2024-05-14 14:43:35"
zhihu_article_id: "696878184"
zhihu_url: https://zhuanlan.zhihu.com/p/696878184
zhihu_column_id: c_1767778500918935552
zhihu_column_title: ABI 二三事
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

**Singleton Pattern** is a common design pattern, often applied in scenarios such as configuration systems, logging systems, and database connection pools, where object uniqueness must be ensured. But can the Singleton Pattern truly guarantee a single instance? What are the consequences if uniqueness is not guaranteed?

Since I've written this article, the answer is definitely no. There have been many related discussions on Zhihu, such as [Will C++ Singleton Pattern across DLLs cause problems?](https://www.zhihu.com/question/425920019/answer/2254241454) and [Singleton Pattern BUG when mixing dynamic and static libraries](https://zhuanlan.zhihu.com/p/354694011). However, most of them just post solutions after encountering problems, which are scattered and lack a systematic analysis of the root causes. Therefore, I wrote this article to discuss this issue in detail.

## Clarifying the Problem

First, let's clarify the problem we are discussing, taking a common C++11 Singleton Pattern implementation as an example:

```cpp
class Singleton {
public:
    Singleton(const Singleton&) = delete;
    Singleton& operator=(const Singleton&) = delete;

    static Singleton& instance() {
        static Singleton instance;
        return instance;
    }

private:
    Singleton() = default;
};
```

We set the default constructor to `private` and explicitly `delete` the copy constructor and assignment operator, so users can only obtain our pre-created object through the `instance` function and cannot create an object themselves via a constructor. The use of a static local variable is to ensure thread-safe initialization of this variable.

However, in reality, a singleton object is no different from a regular global variable. In C++, both belong to [static storage duration](https://en.cppreference.com/w/cpp/language/storage_duration), and the compiler treats them similarly (with slight differences in initialization methods). The so-called Singleton Pattern merely uses language-level mechanisms to prevent users from accidentally creating multiple objects.

So, the problem we are discussing can actually be equivalent to: **Are global variables in C++ unique?**

## A Single Definition

First, we need to distinguish between variable declaration and definition. As we all know, variable definitions generally cannot be written in header files. Otherwise, if the header file is included by multiple source files, multiple definitions will occur, leading to a `multiple definition of variable` error during linking. Therefore, we usually use `extern` to declare variables in header files and then define them in the corresponding source files.

So, how does the compiler handle global variable definitions?

Suppose we define a global variable

```cpp
int x = 1;
```

This actually doesn't generate any instructions; the compiler will add a symbol `x` to the symbol table of the compilation unit's (each source file's) compiled output. It reserves `4` bytes of space for the symbol `x` in static storage (the specific implementation might be the bss section or rdata section, etc.). The way this memory block is filled with data depends on the initialization method ([static initialization](https://en.cppreference.com/w/cpp/language/initialization#Static_initialization) or [dynamic initialization](https://en.cppreference.com/w/cpp/language/initialization#Dynamic_initialization)).

Since there is only one definition, this situation is certainly globally unique.

## Multiple Definitions

As we all know, C++ doesn't have an official build system, and different libraries using different build systems make it inconvenient to use them together (CMake is the de facto standard currently). This situation has made header-only libraries increasingly popular; `include` and use, who doesn't like that? However, header-only also means all code is written in header files. How can one define variables in header files such that they can be directly included by multiple source files without causing linking errors?

Before C++17, there was no direct way. But there were some indirect methods, considering that `inline` functions or template functions can have their definitions appear in multiple source files, and the C++ standard guarantees they have the same address (for related discussion, refer to [Where exactly does C++ code bloat occur?](https://www.ykiko.me/en/articles/686296374)). Thus, by defining static local variables within these functions, it effectively becomes equivalent to defining variables in header files.

```cpp
inline int& x() {
    static int x = 1;
    return x;
}

template<typename T = void>
int& y() {
    static int y = 1;
    return y;
}
```

After C++17, we can directly use `inline` to mark variables, allowing their definitions to appear in multiple source files. Using it, we can directly define variables in header files.

```cpp
inline int x = 1;
```

We know that marking a variable as `static` also allows its definition to appear in multiple source files. So, what's the difference between `inline` and `static`? The key difference is that `static` variables have internal linkage; each compilation unit has its own instance, and their addresses will differ across compilation units. Conversely, `inline` variables have external linkage, and the C++ standard guarantees that the address of the same `inline` variable will be identical across different compilation units.

## Truly a Singleton?

Practice is the sole criterion for testing truth. Let's experiment to see if the C++ standard is deceiving us.

Example code is as follows

```cpp
// src.cpp
#include <cstdio>
inline int x = 1;

void foo() {
    printf("addreress of x in src: %p\n", &x);
}

// main.cpp
#include <cstdio>
inline int x = 1;
extern void foo();

int main() {
    printf("addreress of x in main: %p\n", &x);
    foo();
}
```

Let's start simple: compile these two source files together into a single executable, and try it on Windows (MSVC) and Linux (GCC) respectively.

```bash
# Windows:
addreress of x in main: 00007FF7CF84C000
addreress of x in src: 00007FF7CF84C000
# Linux:
addreress of x in main: 0x404018
addreress of x in src: 0x404018
```

We can see that the addresses are indeed the same. Next, let's try compiling `src.cpp` into a dynamic library, and `main.cpp` links to this library, then compile and run. Let's see if it fails when dynamic libraries are involved, as many people claim. Note that on Windows, `__declspec(dllexport)` must be explicitly added to `foo`, otherwise the dynamic library will not export this symbol.

```bash
# Windows:
addreress of x in main: 00007FF72F3FC000
addreress of x in src: 00007FFC4D91C000
# Linux:
addreress of x in main: 0x404020
addreress of x in src: 0x404020
```

Oh no, why are the situations different for Windows and Linux?

## Symbol Export

Initially, I simply thought it was a problem with the dynamic library's default symbol export rules. Because when GCC compiles dynamic libraries, it exports all symbols by default. MSVC, on the other hand, does the opposite; it exports no symbols by default, and all must be exported manually. Clearly, only when a symbol is exported can the linker 'see' it and then merge symbols from different dynamic libraries.

With this idea, I tried to find ways to customize symbol export on GCC and eventually found [Visibility - GCC Wiki](https://gcc.gnu.org/wiki/Visibility). When compiling, using `-fvisibility=hidden` makes all symbols hidden (not exported) by default. Then, use `__attribute__((visibility("default")))` or its C++ equivalent `[[gnu::visibility("default")]]` to explicitly mark symbols that need to be exported. So I modified the code

```cpp
// src.cpp
#include <cstdio>
inline int x = 1;

[[gnu::visibility("default")]]
void foo () {
    printf("addreress of x in src: %p\n", &x);
}

// main.cpp
#include <cstdio>
inline int x = 1;

extern void foo();

int main() {
    printf("addreress of x in main: %p\n", &x);
    foo();
}
```

Note that I only exported `foo` for function calls; neither of the `inline` variables were exported. Compile and run

```bash
addreress of x in main: 0x404020
addreress of x in src: 0x7f5a45513010
```

As we expected, the addresses are indeed different. This verifies that: symbol export is a necessary condition for the linker to merge symbols, but not a sufficient one. If, on Windows, changing the default symbol export rules could lead to `inline` variables having the same address, then sufficiency would be verified. When I excitedly started trying, I found that things were not that simple.

I noticed that GCC on Windows (MinGW64 toolchain) still exports all symbols by default, so according to my hypothesis, the variable addresses should be the same. The results of the attempt are as follows

```bash
addreress of x in main: 00007ff664a68130
addreress of x in src: 00007ffef4348110
```

It can be seen that the results are not the same. I didn't understand why and considered it a compiler bug. I then switched to MSVC and found that CMake provides a [CMAKE_WINDOWS_EXPORT_ALL_SYMBOLS](https://cmake.org/cmake/help/latest/prop_tgt/WINDOWS_EXPORT_ALL_SYMBOLS.html) option, which, when enabled, automatically exports all symbols (implemented via dumpbin). So I tried it, compiled and ran, and the results are as follows

```bash
addreress of x in main: 00007FF60B11C000
addreress of x in src: 00007FFEF434C000
```

Oh, the results are still different. I realized my hypothesis was flawed. But after searching for a long time, I couldn't find out why. Later, I asked in a C++ group on TG and finally got the answer.

Simply put, in ELF, it doesn't distinguish which `.so` a symbol comes from; it uses whichever is loaded first. So, when encountering multiple `inline` variables, it uses the first one loaded. However, the symbol table of `PE` files specifies which `dll` a certain symbol is imported from. This means that as long as a variable is `dllexport`ed, that DLL will definitely use its own variable. Even if multiple `dll`s simultaneously `dllexport` the same variable, they cannot be merged; the DLL format on Windows restricts this from happening.

The problem of symbol resolution during dynamic library linking can actually be much more complex, with many other scenarios, such as actively loading dynamic libraries via functions like `dlopen`. If I have time later, I might write a dedicated article to analyze this issue, so I won't elaborate further here.

## What if Not Unique?

Why is it necessary to ensure the uniqueness of 'singleton' variables? Let's take the C++ standard library as an example.

As we all know, [type_info](https://en.cppreference.com/w/cpp/types/type_info) can be used to distinguish different types at runtime, and type-erasure facilities like `std::function` and `std::any` in the standard library rely on it for implementation. Its `constructor` and `operator=` are `deleted`, so we can only obtain a reference to the corresponding `type_info` object via `typeid(T)`, with object creation handled by the compiler.

Well, doesn't that perfectly fit the Singleton Pattern? The next question is, how does the compiler determine if two `type_info` objects are the same? A typical implementation is as follows

```cpp
#if _PLATFORM_SUPPORTS_UNIQUE_TYPEINFO
    bool operator==(const type_info& __rhs) const {
      return __mangled_name == __rhs.__mangled_name;
    }
#else
    bool operator==(const type_info& __rhs) const {
      return __mangled_name == __rhs.__mangled_name ||
             strcmp(__mangled_name, __rhs.__mangled_name) == 0;
    }
#endif
```

The code above is easy to understand: if the address of `type_info` is guaranteed to be unique, then directly comparing `__mangled_name` is sufficient (since it's `const char*`, it's a pointer comparison). Otherwise, compare the addresses first, then the type names. Specifically, for the implementations of the three major standard libraries:

- [libstdc++](https://github.com/gcc-mirror/gcc/blob/master/libstdc%2B%2B-v3/libsupc%2B%2B/tinfo.cc#L39) uses `__GXX_MERGED_TYPEINFO_NAMES` to control whether it's enabled.
- [libc++](https://github.com/llvm/llvm-project/blob/main/libcxx/include/typeinfo#L197) uses `_LIBCPP_TYPEINFO_COMPARATION_IMPLEMENTATION` to determine the approach (there's also a special BIT_FLAG mode).
- msvc stl (crt/src/vcruntime/std_type_info.cpp) always uses the second approach due to the aforementioned DLL limitations on Windows.

The purpose of this example is to illustrate that the uniqueness of a singleton variable's address affects how we write our code. If it's not unique, we might be forced to write defensive code, which could impact performance, and if not written, it could even directly lead to logical errors.

## Solution

Just raising problems isn't enough; they need to be solved. How can we ensure singleton uniqueness?

On Linux, it's simple: if the same variable appears in multiple dynamic libraries, you just need to ensure that all these dynamic libraries make this symbol externally visible. And the compiler's default behavior is to make symbols externally visible, so there's generally no need to worry about this issue.

What about Windows? It's very troublesome. You must ensure that only one DLL uses `dllexport` to export this symbol, and all other DLLs must use `dllimport`. This is often not easy to do; you might forget which DLL is responsible for exporting this symbol as you write code. What to do then? The solution is to use a dedicated DLL to manage all singleton variables. This means this DLL is responsible for `dllexport`ing all singleton variables, and all other DLLs simply `dllimport` them. Subsequent additions and modifications are then made within this DLL, making it easier to manage.

This concludes the article. Honestly, I'm not sure if the discussion above covers all scenarios. If there are any errors, feel free to leave a comment for discussion.
