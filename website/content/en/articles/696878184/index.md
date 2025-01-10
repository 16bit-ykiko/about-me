---
title: 'Is the Singleton Pattern in C++ Truly "Singleton"?'
date: 2024-05-10 02:08:28
updated: 2024-05-14 22:43:35
---

**Singleton Pattern** is a common design pattern often used in scenarios requiring object uniqueness, such as configuration systems, logging systems, and database connection pools. But does the Singleton Pattern truly guarantee a singleton? What consequences might arise if uniqueness is not ensured?

Since this article is written, the answer is clearly no. There have been many discussions on Zhihu, such as [Does the C++ Singleton Pattern across DLLs cause issues?](https://www.zhihu.com/question/425920019/answer/2254241454) and [Singleton Pattern BUG in Mixed Use of Dynamic and Static Libraries](https://zhuanlan.zhihu.com/p/354694011). However, most of these discussions only provide solutions after encountering problems, which are scattered and lack systematic analysis of the root causes. Therefore, I wrote this article to delve into this issue in detail.

## Clarifying the Problem

First, we need to clarify the problem under discussion. Taking a common C++11 Singleton Pattern implementation as an example:

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

We set the default constructor to `private` and explicitly `delete` the copy constructor and assignment operator, ensuring users can only obtain the pre-created object through the `instance` function and cannot create an object themselves via the constructor. Using a static local variable ensures thread safety during initialization.

However, a singleton object is essentially no different from a regular global variable. In C++, both have [static storage duration](https://en.cppreference.com/w/cpp/language/storage_duration), and the compiler treats them similarly (with some differences in initialization). The Singleton Pattern merely uses language-level techniques to prevent users from accidentally creating multiple objects.

Thus, the problem we are discussing can be equated to: **Are global variables in C++ unique?**

## A Definition

First, we need to distinguish between variable declaration and definition. We know that variable definitions generally cannot be written in header files. Otherwise, if the header file is included by multiple source files, multiple definitions will result, causing a `multiple definition of variable` error during linking. Therefore, we usually declare variables in header files using `extern` and define them in the corresponding source files.

How does the compiler handle global variable definitions?

Suppose we define a global variable:

```cpp
int x = 1;
```

This does not generate any instructions. The compiler adds a symbol `x` to the symbol table of the compilation unit (each source file). It reserves `4` bytes of space in static storage (possibly in the bss segment or rdata segment, etc.) for the symbol `x`. Depending on the initialization method ([static initialization](https://en.cppreference.com/w/cpp/language/initialization#Static_initialization) or [dynamic initialization](https://en.cppreference.com/w/cpp/language/initialization#Dynamic_initialization)), the data in this memory is filled accordingly.

Since there is only one definition, this case is certainly globally unique.

## Multiple Definitions

We know that C++ does not have an official build system. Different libraries use different build systems, making them inconvenient to use together (currently, cmake is the de facto standard). This situation has led to the increasing popularity of header-only libraries, which are easy to use by simply including them. But header-only means all code is written in header files. How can variables be defined in header files and directly included by multiple source files without causing linking errors?

Before C++17, there was no direct way. However, there were indirect methods. Considering that `inline` functions or template function definitions can appear in multiple source files, and the C++ standard guarantees they have the same address (related discussions can be found in [Where Does C++ Code Bloat Occur?](https://www.ykiko.me/zh-cn/articles/686296374)). Thus, defining static local variables within these functions effectively allows variable definitions in header files:

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

After C++17, we can directly use `inline` to mark variables, allowing their definitions to appear in multiple source files. Using this, we can directly define variables in header files:

```cpp
inline int x = 1;
```

We know that marking a variable as `static` also allows its definition to appear in multiple source files. What is the difference between `inline` and `static`? The key difference is that `static` marked variables have internal linkage, with each compilation unit having its own instance, and addresses taken in different compilation units are different. In contrast, `inline` marked variables have external linkage, and the C++ standard guarantees that the address of the same `inline` variable taken in different compilation units is the same.

## Truly Singleton?

Practice is the sole criterion for testing truth. Let's experiment to see if the C++ standard is truthful.

Sample code:

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

First, compile these two source files into an executable and test on Windows (MSVC) and Linux (GCC):

```bash
# Windows:
addreress of x in main: 00007FF7CF84C000
addreress of x in src: 00007FF7CF84C000
# Linux:
addreress of x in main: 0x404018
addreress of x in src: 0x404018
```

The addresses are indeed the same. Next, compile `src.cpp` into a dynamic library and link `main.cpp` to this library, then compile and run. Let's see if, as many say, it fails when encountering dynamic libraries. Note that on Windows, `foo` must be explicitly marked with `__declspec(dllexport)`, otherwise the dynamic library will not export this symbol.

```bash
# Windows:
addreress of x in main: 00007FF72F3FC000
addreress of x in src: 00007FFC4D91C000
# Linux:
addreress of x in main: 0x404020
addreress of x in src: 0x404020
```

Oh no, why are the results different on Windows and Linux?

## Symbol Export

Initially, I thought it was simply due to the default symbol export rules of dynamic libraries. GCC exports all symbols by default when compiling dynamic libraries, while MSVC does the opposite, exporting no symbols by default, requiring manual export. Clearly, only when a symbol is exported can the linker "see" it and then merge symbols from different dynamic libraries.

With this in mind, I tried to find ways to customize symbol export on GCC and eventually found [Visibility - GCC Wiki](https://gcc.gnu.org/wiki/Visibility). Using `-fvisibility=hidden` during compilation makes symbols default to hidden (not exported). Then, use `__attribute__((visibility("default")))` or its C++ equivalent `[[gnu::visibility("default")]]` to explicitly mark symbols for export. Thus, I modified the code:

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

Note, I only exported `foo` for function calls; neither `inline` variable was exported. Compile and run:

```bash
addreress of x in main: 0x404020
addreress of x in src: 0x7f5a45513010
```

As expected, the addresses are different. This verifies that symbol export is a necessary condition for the linker to merge symbols, but not sufficient. If changing the default symbol export rules on Windows could make `inline` variables have the same address, sufficiency would be verified. Excitedly, I began to try, only to find things were not so simple.

Noting that GCC on Windows (MinGW64 toolchain) still exports all symbols by default, the variable addresses should be the same. The result:

```bash
addreress of x in main: 00007ff664a68130
addreress of x in src: 00007ffef4348110
```

The results are different. I didn't understand and thought it was a compiler bug. Switching to MSVC, I found that CMake provides a [CMAKE_WINDOWS_EXPORT_ALL_SYMBOLS](https://cmake.org/cmake/help/latest/prop_tgt/WINDOWS_EXPORT_ALL_SYMBOLS.html) option, which automatically exports all symbols (via dumpbin). Trying this, compiling and running, the result:

```bash
addreress of x in main: 00007FF60B11C000
addreress of x in src: 00007FFEF434C000
```

Oh, the results are still different. I realized my guess was wrong. After much research, I couldn't find why. Later, I got the answer by asking in the C++ group on TG.

Simply put, ELF does not distinguish which `.so` a symbol comes from; it uses the first loaded one, so multiple `inline` variables use the first loaded one. However, the PE file's symbol table specifies which `dll` a symbol is imported from, meaning if a variable is `dllexport`ed, the dll will always use its own variable. Even if multiple `dll`s `dllexport` the same variable, they cannot be merged; the format of dlls on Windows inherently prevents this.

The issue of symbol resolution during dynamic library linking is actually much more complex, with many other scenarios, such as actively loading dynamic libraries via `dlopen` and other functions. If time permits, I may write a dedicated article to analyze this issue; for now, I won't elaborate further.

## What If Not Unique?

Why ensure the uniqueness of "singleton" variables? Here, I use the C++ standard library as an example.

We know that [type_info](https://en.cppreference.com/w/cpp/types/type_info) can distinguish different types at runtime, and the standard library's `std::function` and `std::any` rely on it for type erasure. Its `constructor` and `operator=` are `deleted`, and we can only obtain the corresponding `type_info` object reference via `typeid(T)`, with object creation handled by the compiler.

Doesn't this fully conform to the Singleton Pattern? The next question is, how does the compiler determine if two `type_info` objects are the same? A typical implementation is as follows:

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

The above code is straightforward. If `type_info` addresses are guaranteed unique, directly compare `__mangled_name` (it's `const char*`, so pointer comparison). Otherwise, compare addresses first, then type names. Specific to the three major standard library implementations:

- [libstdc++](https://github.com/gcc-mirror/gcc/blob/master/libstdc%2B%2B-v3/libsupc%2B%2B/tinfo.cc#L39) uses `__GXX_MERGED_TYPEINFO_NAMES` to control enabling.
- [libc++](https://github.com/llvm/llvm-project/blob/main/libcxx/include/typeinfo#L197) uses `_LIBCPP_TYPEINFO_COMPARATION_IMPLEMENTATION` to decide the approach (actually, there's a special BIT_FLAG mode).
- msvc stl (crt/src/vcruntime/std_type_info.cpp) always uses the second method due to the aforementioned Windows dll limitations.

The purpose of this example is to illustrate that the uniqueness of singleton variable addresses affects how we write code. If not unique, we might be forced to write defensive code, potentially impacting performance, and if not written, it could directly cause logical errors.

## Solutions

Merely raising problems is not enough; solutions are needed. How to ensure singleton uniqueness?

On Linux, it's simple. If the same variable appears in multiple dynamic libraries, ensure all these dynamic libraries set this symbol to be externally visible. The compiler's default behavior is external visibility, so this issue is generally not a concern.

On Windows, it's more complicated. Ensure only one dll uses `dllexport` to export this symbol, and all other dlls must use `dllimport`. This is often tricky; you might forget which dll is responsible for exporting the symbol. What to do? Use a dedicated dll to manage all singleton variables, meaning this dll is responsible for `dllexport`ing all singleton variables, while other dlls only `dllimport`. Adding and modifying variables are done in this dll, making management easier.

This concludes the article. Honestly, I'm not sure if the above discussion covers all scenarios. If there are errors, please leave a comment for discussion.