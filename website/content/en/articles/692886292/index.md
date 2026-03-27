---
title: Thoroughly Understanding C++ ABI
date: "2024-04-16 18:19:38"
updated: "2025-12-24 05:15:12"
zhihu_article_id: "692886292"
zhihu_url: https://zhuanlan.zhihu.com/p/692886292
zhihu_column_id: c_1656510843973046272
zhihu_column_title: 魅力C++
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

Application Binary Interface, or ABI as we commonly call it, is a concept that feels both familiar and unfamiliar. Familiar in what sense? It's often discussed when troubleshooting, frequently mentioned in articles, and sometimes we even have to deal with compatibility issues it causes. Unfamiliar in what sense? If someone asks you what an ABI is, you'll find that you know what it's about, but describing it in precise language is quite difficult. In the end, you might just resort to saying, as [WIKI](https://en.wikipedia.org/wiki/Application_binary_interface) does: an ABI is an interface between two binary program modules. Is there a problem with that? No, as a general description, it's sufficient. But it can feel a bit hollow.

This situation is not uncommon in the field of Computer Science. The author encountered the exact same situation in a previous article discussing [reflection](https://www.ykiko.me/en/articles/669358870). Fundamentally, CS is not a discipline that strives for absolute rigor; many concepts lack strict definitions and are more often conventional understandings. So, instead of getting bogged down in definitions, let's look at what these so-called binary interfaces actually are and what factors affect their stability.

## CPU & OS

The final executable file ultimately runs on a specific operating system on a specific CPU. If the CPU instruction sets are different, it will certainly lead to binary incompatibility. For example, programs on [ARM](https://en.wikipedia.org/wiki/ARM_architecture_family) cannot run **directly** on x64 processors (unless some virtualization technology is used). What if the instruction sets are compatible? For instance, x64 processors are compatible with the x86 instruction set. Does that mean an x86 program can definitely run on an x64 operating system? This is where the operating system comes into play. Specifically, factors such as **Object File Format**, **Data Representation**, **Function Calling Convention**, and **Runtime Library** must be considered. These points can be regarded as ABI regulations at the operating system level. We will discuss the fourth point in a dedicated section later. Below, taking the x64 platform as an example, we will discuss the first three points.

> x64, x86-64, x86_64, AMD64, and Intel 64 all refer to the 64-bit version of the x86 instruction set.

**There are two main common ABIs on the x64 platform**:

- [Windows x64 ABI](https://learn.microsoft.com/en-us/cpp/build/x64-software-conventions?view=msvc-170) for 64-bit Windows operating systems
- [x86-64 System V ABI](https://gitlab.com/x86-psABIs/x86-64-ABI) for 64-bit Linux and various UNIX-like operating systems

Calling a function from a dynamic library can be simply viewed as the following three steps:

- Parse the dynamic library according to a certain format.
- Look up the function address from the parsed result based on the symbol name.
- Pass function parameters and call the function.

### Object File Format

How to parse a dynamic library? This is where the ABI's regulations on Object File Format come into play. If you want to write your own linker, the final executable file must meet the format requirements of the corresponding platform. Windows x64 uses the [PE32+](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format) executable file format, which is the `64`-bit version of PE32 (Portable Executable 32-bit). The System V ABI uses the [ELF (Executable Linkable Format)](https://en.wikipedia.org/wiki/Executable_and_Linkable_Format) executable file format. By using parsing libraries (or writing your own if interested), such as [pe-parse](https://github.com/trailofbits/pe-parse) and [elfio](https://github.com/serge1/ELFIO), to parse actual executable files and obtain their symbol tables, we can get the mapping between function names and function addresses.

### Data Representation

After obtaining the function address, the next step is how to call it. Before calling, parameters must be passed, right? When passing parameters, special attention must be paid to the consistency of Data Representation. What does this mean?

Suppose I compile the following file into a dynamic library:

```cpp
struct X{
    int a;
    int b;
};

int foo(X x){
    return x.a + x.b;
}
```

Then, a subsequent version upgrade changes the structure content, and the structure definition seen in the user's code becomes:

```cpp
struct X{
    int a;
    int b;
    int c;
};
```

And then it still tries to link to the dynamic library compiled from the old version code and call its function:

```cpp
int main(){
    int n = foo({1, 2, 3});
    printf("%d\n", n);
}
```

Will it succeed? Of course, it will fail. This type of error can be considered a so-called ODR (One Definition Rule) violation. More examples will be discussed in later sections.

The above situation is an ODR violation caused by the user actively changing the code. But what if I don't actively change the code, can I ensure the stability of the structure layout? This is guaranteed by the Data Representation in the ABI. For example, it specifies the size and alignment of basic types. Windows x64 specifies `long` as `32` bits, while System V specifies `long` as `64` bits. It also specifies the size and alignment of `struct` and `union`, and so on.

> Note that the C language standard still does not specify an ABI. For the System V ABI, it is primarily written using C language terminology and concepts, so it can be considered to provide an ABI for the C language. The Windows x64 ABI does not have a very clear boundary between C and C++.

### Function Calling Convention

Next, we come to the step of passing function parameters. We know that a function is just a piece of binary data. Executing a function simply means jumping to the function's entry address, executing that piece of code, and then jumping back when finished. Parameter passing is nothing more than finding a place to store data, **so that this location can be accessed to retrieve data both before and after the call**. What locations can be chosen? There are mainly four options:

- global (global variables)
- heap (heap)
- register (registers)
- stack (stack)

Using global variables for parameter passing sounds magical, but in practice, when writing code, parameters that need to be passed repeatedly, such as `config`, are often changed to global variables. However, it's clear that not all parameters are suitable for global variable passing, and thread safety needs to be considered even more carefully.

Using the heap for parameter passing also seems incredible, but in fact, C++20's stackless coroutines store coroutine states (function parameters, local variables) on the heap. However, for ordinary function calls, if dynamic memory allocation is required every time parameters are passed, it is indeed a bit extravagant.

So we mainly consider using registers and the stack for parameter passing. Having more options is always good, but not here. If the caller thinks parameters should be passed via registers, it stores the parameters in registers. But the callee thinks parameters should be passed via the stack, so it retrieves data from the stack. Inconsistency arises, and it's very likely that garbage values are read from the stack, leading to logical errors in the code and program crashes.

How to ensure that the caller and callee pass parameters to the same location? I believe you've already guessed: this is where the Function Calling Convention comes into play.

Specifically, the calling convention specifies the following:

- Order of function parameter passing: left-to-right or right-to-left?
- Method of function parameter and return value passing: via stack or registers?
- Which registers remain unchanged before and after the caller's call?
- Who is responsible for cleaning up the stack frame: the caller or the callee?
- How to handle C language [variadic](https://en.cppreference.com/w/c/variadic) functions?
- `...`

In `32`-bit programs, there were many calling conventions, such as `__cdecl`, `__stdcall`, `__fastcall`, `__thiscall`, etc., and programs at that time suffered greatly from compatibility issues. In `64`-bit programs, unification has largely been achieved. There are mainly two calling conventions, those specified by the Windows x64 ABI and the x86-64 System V ABI respectively (though they don't have formal names). **It needs to be emphasized that the function parameter passing method is only related to the calling convention, not to the code optimization level. You wouldn't want code compiled with different optimization levels to fail when linked together, would you?**

Introducing specific regulations can be tedious. Interested readers can refer to the relevant sections of the corresponding documentation. Below, we mainly discuss some more interesting topics.

> Note: The following discussions only apply when function calls actually occur. If a function is fully inlined, the act of passing function parameters does not happen. Currently, C++ code inlining optimization mainly occurs within the same compilation unit (single file). For code across compilation units, LTO (Link Time Optimization) must be enabled. Code across dynamic libraries cannot be inlined yet.

- **Passing struct values smaller than 16 bytes is more efficient than passing by reference.**

This statement has been around for a long time, but I've never found the basis for it. Finally, while researching calling conventions recently, I found the reason. First, if the struct size is less than or equal to `8` bytes, it can be directly placed into a `64`-bit register for parameter passing. **Passing parameters via registers involves fewer memory accesses than passing by reference**, making it more efficient, which is fine. What about `16` bytes? The System V ABI allows a `16`-byte struct to be split into two `8`-byte parts and then passed using registers separately. In this case, passing by value is indeed more efficient than passing by reference. Observe the following [code](https://godbolt.org/z/5Ph34x1cR):

```cpp
#include <cstdio>

struct X {
    size_t x;
    size_t y;
};

extern void f(X);
extern void g(const X&);

int main() {
    f({1, 2}); // pass by value
    g({1, 2}); // pass by reference
}
```

The generated code is as follows:

```x86asm
main:
        sub     rsp, 24
        mov     edi, 1
        mov     esi, 2
        call    f(X)
        movdqa  xmm0, XMMWORD PTR .LC0[rip]
        mov     rdi, rsp
        movaps  XMMWORD PTR [rsp], xmm0
        call    g(X const&)
        xor     eax, eax
        add     rsp, 24
        ret
.LC0:
        .quad   1
        .quad   2
```

> The System V ABI specifies that the first six integer parameters can be passed using `rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9` registers, respectively. The Windows x64 ABI specifies that the first four integer parameters can be passed using `rcx`, `rdx`, `r8`, `r9` registers, respectively. If registers are exhausted, parameters are passed via the stack. Integer parameters include `char`, `short`, `int`, `long`, `long long`, and other basic integer types, plus pointer types. Floating-point parameters and SIMD type parameters have dedicated registers, which are not covered in detail here.

It can be seen that `1` and `2` are passed to function `f` via registers `edi` and `esi` respectively, while `g` is passed the address of a temporary variable. However, this is only for the System V ABI. For the Windows x64 ABI, **if the size of a struct is greater than 8 bytes, it can only be passed by reference.** The same code, compiled on Windows, yields the following result:

```x86asm
main:
        sub     rsp, 56
        lea     rcx, QWORD PTR [rsp+32]
        mov     QWORD PTR [rsp+32], 1
        mov     QWORD PTR [rsp+40], 2
        call    void f(X)
        lea     rcx, QWORD PTR [rsp+32]
        mov     QWORD PTR [rsp+32], 1
        mov     QWORD PTR [rsp+40], 2
        call    void g(X const &)
        xor     eax, eax
        add     rsp, 56
        ret     0
```

It can be seen that the code generated for both function calls is exactly the same. This means that for the Windows x64 ABI, whether a struct larger than `8` bytes is passed by reference or by value, the generated code is identical.

- **`unique_ptr` and `raw_ptr` have exactly the same efficiency.**

Well, before this, I always firmly believed this, after all, `unique_ptr` is just a simple wrapper around a raw pointer. It wasn't until I watched the thought-provoking CPPCON talk [There are no zero-cost abstractions](https://www.bilibili.com/video/BV1qp421y75W/?spm_id_from=333.999.0.0) that I realized I was completely taking it for granted. Here, we won't discuss the extra overhead caused by exceptions (destructors requiring the compiler to generate additional code for stack frame cleanup). Let's just discuss whether a C++ object (smaller than `8` bytes) can be passed via registers. For a completely [trivial](https://en.cppreference.com/w/cpp/language/classes#Trivial_class) type, it's fine; it behaves almost exactly like a C language struct. But what if it's not trivial?

For example, if a custom copy constructor is defined, can it still be placed in a register? Logically, it cannot. Why? We know that C++ allows us to take the address of function parameters. If an integer parameter is passed via a register, where does the result of taking its address come from? Let's experiment and find out:

```cpp
#include <cstdio>

extern void f(int&);

int g(int x) {
    f(x);
    return x;
}
```

The corresponding assembly generated is as follows:

```x86asm
g(int):
        sub     rsp, 24
        mov     DWORD PTR [rsp+12], edi
        lea     rdi, [rsp+12]
        call    f(int&)
        mov     eax, DWORD PTR [rsp+12]
        add     rsp, 24
        ret
```

It can be seen that the value in `edi` (used to pass the first integer parameter) is copied to the address `rsp+12`, which is on the stack, and then this address is passed to `f`. This means that if a function parameter is passed via a register, and its address is needed in some situations, the compiler will copy this parameter to the stack. **However, users cannot observe these copy processes, because their copy constructors are trivial. Any optimization that does not affect the final execution result of the code complies with the as-if rule.**

Now, if this object has a user-defined copy constructor, and assuming the parameter is passed via a register, it might lead to additional copy constructor calls, and the user can observe this side effect. This is clearly unreasonable, so objects with user-defined copy constructors are not allowed to be passed via registers. What about passing via the stack? In fact, similar copying dilemmas would also be encountered. Therefore, such objects can ultimately only be passed by reference. **Note that explicitly marking a copy constructor as `delete` also counts as a user-defined copy constructor.**

So for `unique_ptr`, it can only be passed by reference. Regardless of whether you write the function signature as `void f(unique_ptr<int>)` or `void f(unique_ptr<int>&)`, the binary code generated at the parameter passing point will be the same. However, raw pointers can be safely passed via registers. In summary, the efficiency of `unique_ptr` and raw pointers is not exactly the same.

> In reality, the actual situation of whether a non-trivial C++ object can be passed via registers is more complex. Relevant details can be found in the corresponding sections of the respective ABIs, and are not described in detail here. Furthermore, it is not entirely clear whether the rules for how C++ objects are passed belong to the operating system's ABI or the C++ compiler's ABI.

## C++ Standard

Finally, we've covered the guarantees at the operating system level. Since it leans towards the low-level, involving a lot of assembly, it might be difficult for readers not so familiar with assembly. However, the following content is basically unrelated to assembly, so you can read it with confidence.

We all know that the C++ standard does not explicitly specify an ABI, but it's not entirely without rules. It does have some requirements for compiler implementations, such as:

- Struct member addresses increase according to their declaration order ([explanation](https://en.cppreference.com/w/c/language/struct#Explanation)), which ensures that compilers do not reorder struct members.
- Structs satisfying the [Standard Layout](https://en.cppreference.com/w/cpp/language/data_members#Standard-layout) constraint must be layout-compatible with corresponding C structs.
- Structs satisfying the [Trivially Copyable](https://en.cppreference.com/w/cpp/types/is_trivially_copyable) constraint can be copied using `memmove` or `memcpy` to obtain an identical new object.
- `...`

Furthermore, as C++ continues to release new versions, if I compile the same code using a new standard and an old standard respectively, will the results be the same (ignoring the impact of using macros to control C++ versions for conditional compilation)? This depends on the C++ standard's guarantees for ABI compatibility. In fact, the C++ standard strives to ensure **backward compatibility**. That is, for two pieces of code, the code compiled with the old standard and the new standard should be exactly the same.

However, there are a very few exceptions (I could only find these; feel free to add more in the comments):

- C++17 made `noexcept` part of the function type, which affects the mangling name generated for the function.
- C++20 introduced `no_unique_address`, which MSVC still doesn't directly support because it would cause an ABI break.

More often, new C++ versions introduce new language features along with new ABIs, without affecting old code. For example, two new features added in C++23:

### Explicit Object Parameter

Before C++23, there was no **legal** way to get the address of a member function. The only thing we could do was get a member pointer (for what a member pointer is, you can refer to this [article](https://www.ykiko.me/en/articles/659510753)):

```cpp
struct X {
    void f(int);
};

auto p = &X::f;
// p is a pointer to member function of X
// type of p is void (X::*)(int)
```

To use a member function as a callback, you could only wrap it with a lambda expression:

```cpp
struct X {
    void f(int);
};

using Fn = void(*)(X*, int);
Fn p = [](A* self, int x) { self->f(x); };
```

This is actually quite cumbersome and unnecessary, and this wrapping layer might lead to additional function call overhead. To some extent, this is a historical issue; on `32`-bit systems, the calling convention for member functions was somewhat special (the well-known `thiscall`), and C++ did not have calling convention-related content, so a member function pointer was created. Old code cannot be changed for ABI compatibility, but new code can. C++23 added explicit object parameters, so we can now clearly define how `this` is passed, and even use pass-by-value:

```cpp
struct X {
    // The 'this' here is just a marker to distinguish it from old syntax
    void f(this X self, int x); // pass by value
    void g(this X& self, int x); // pass by reference
};
```

Functions marked with explicit `this` can also directly obtain their function addresses, just like ordinary functions:

```cpp
auto f = &X::f; // type of f is void(*)(X, int)
auto g = &X::g; // type of g is void(*)(X*, int)
```

So new code can adopt this writing style, which only brings benefits and no drawbacks.

### Static Operator()

Some function objects in the standard library have no members other than an `operator()`, such as `std::hash`:

```cpp
template <class T>
struct hash {
    std::size_t operator()(T const& t) const;
};
```

Although this is an empty struct, because `operator()` is a member function, it has an implicit `this` parameter. In the case of non-inlined calls, a useless null pointer still needs to be passed. This problem was solved in C++23, where `static operator()` can be directly defined to avoid this issue:

```cpp
template <class T>
struct hash {
    static std::size_t operator()(T const& t);
};
```

`static` means this is a static function, and its usage remains the same as before:

```cpp
std::hash<int> h;
std::size_t n = h(42);
```

However, `hash` is just an example here. In reality, standard library code will not be modified for ABI compatibility. New code can use this feature to avoid unnecessary `this` passing.

## Compiler Specific

Now for the main event: the implementation-defined parts. This section seems to be the most criticized content. But is that really the case? Let's look at it piece by piece.

### De Facto Standard

Some abstractions in C++ ultimately need to be implemented, and if the standard doesn't specify how to implement them, then this part is left to the compiler's discretion. For example:

- Name mangling rules (for implementing function overloading and template functions)
- Layout of complex types (e.g., those with virtual inheritance)
- Virtual function table layout
- RTTI implementation
- Exception handling
- `...`

If compilers implement these parts differently, then the binary products compiled by different compilers will naturally be incompatible and cannot be mixed.

> In the 1990s, which was the golden age of C++ development, various vendors were dedicated to implementing their own compilers and expanding their user base, competing for users. Due to this competition, it was common for different compilers to use different ABIs. As time progressed, most of them have exited the historical stage, either stopping updates or only maintaining existing versions, no longer keeping up with new C++ standards. After the wave, only GCC, Clang, and MSVC remain as the three major compilers.

Today, the C++ compiler ABI has largely been unified, with only two main ABIs:

- Itanium C++ ABI, with publicly available [documentation](https://itanium-cxx-abi.github.io/cxx-abi/abi.html)
- MSVC C++ ABI, which does not have official documentation, but there is an unofficial [version](https://link.zhihu.com/?target=http://www.openrce.org/articles/files/jangrayhood.pdf) available

> Although named Itanium C++ ABI, it is actually a cross-architecture ABI for C++. Almost all C++ compilers except MSVC use it, although there are slight differences in exception handling details. Historically, C++ compilers handled the C++ ABI in their own ways. When Intel heavily promoted Itanium, they wanted to avoid incompatibility issues, so they created a standardized ABI for all C++ vendors on Itanium. Later, for various reasons, GCC needed to modify its internal ABI, and given that it already supported the Itanium ABI (for Itanium processors), they chose to extend the ABI definition to all architectures instead of creating their own. Since then, all major compilers except MSVC have adopted the cross-architecture Itanium ABI, and even though the Itanium processor itself no longer receives maintenance, the ABI is still maintained.

On Linux platforms, both GCC and Clang use the Itanium ABI, so code compiled by these two compilers is interoperable and can be linked together and run. On Windows platforms, the situation is slightly more complex. The default MSVC toolchain uses its own ABI. However, in addition to the MSVC toolchain, GCC has also been ported to Windows, known as the [MinGW](https://www.mingw-w64.org/) toolchain, which still uses the Itanium ABI. These two ABIs are incompatible, and code compiled by them cannot be directly linked together. Clang on Windows can control which of these two ABIs to use via compilation options.

> Note: Since MinGW runs on Windows, its generated code's calling convention naturally tries to comply with the Windows x64 ABI, and the final executable file format is also PE32+. However, the C++ ABI it uses is still the Itanium ABI, and there is no necessary connection between the two.

Considering the huge C++ codebase, these two C++ ABIs have largely stabilized and will not change further. **Therefore, we can now actually say that C++ compilers have stable ABIs.** How about that, isn't it different from the mainstream view online? But the facts are indeed right here.

> MSVC has guaranteed ABI stability from its [2015](https://learn.microsoft.com/en-us/cpp/porting/binary-compat-2015-2017?view=msvc-170) version onwards. GCC started using the Itanium ABI from 3.4 and has guaranteed ABI stability since then.

### Workaround

Although the basic ABI no longer changes, upgrading compiler versions can still lead to ABI breaks in compiled libraries. Why?

This is not difficult to understand. First, compilers are also software, and all software can have bugs. Sometimes, to fix bugs, some ABI breaks are forced (usually explained in detail in the release notes of new versions). For example, GCC has a compilation option [-fabi-version](https://gcc.gnu.org/onlinedocs/gcc/C_002b_002b-Dialect-Options.html#index-fabi-version) specifically to control these different versions. Some of its contents are as follows:

- Version `7` first appeared in G++ 4.8, treating `nullptr_t` as a built-in type and correcting the name encoding of lambda expressions in default argument scope.
- Version `8` first appeared in G++ 4.9, correcting the substitution behavior of function types with function CV qualifiers.
- Version `9` first appeared in G++ 5.2, correcting the alignment of `nullptr_t`.

Additionally, users might have written some special code to work around compiler bugs, which we generally call a workaround. When the bug is fixed, these workarounds might have an adverse effect, leading to ABI incompatibility.

### Important Options

In addition, compilers provide a series of options to control their behavior, and these options may affect the ABI, such as:

- `-fno-strict-aliasing`: Disable strict aliasing
- `-fno-exceptions`: Disable exceptions
- `-fno-rtti`: Disable RTTI
- `...`

When linking libraries compiled with different options, compatibility issues must be especially considered. For example, if your code disables strict aliasing, but a dependent external library enables strict aliasing, pointer propagation errors are very likely to occur, leading to program errors.

I recently encountered this situation. I was writing Python wrappers for some LLVM functions using [pybind11](https://github.com/pybind/pybind11). Pybind11 requires RTTI to be enabled, but LLVM's default build disables exceptions and RTTI, so the code couldn't link together. Initially, I compiled a version of LLVM with RTTI enabled, which caused binary bloat. Later, I realized this was unnecessary. I wasn't actually using RTTI information for LLVM types; it was just that because they were written in the same file, the compiler thought I was using it. So, I solved it by compiling the LLVM-dependent part of the code into a separate dynamic library and then linking it with the pybind11-dependent part of the code.

## Runtime & Library

This subsection mainly discusses the ABI stability of libraries that a C++ program depends on. **Ideally, for an executable program, replacing an old version of a dynamic library with a new version should not affect its operation.**

The three major C++ compilers each have their own standard libraries:

- MSVC corresponds to [msvc stl](https://github.com/microsoft/STL)
- GCC corresponds to [libstdc++](https://github.com/gcc-mirror/gcc/tree/master/libstdc%2B%2B-v3)
- Clang corresponds to [libc++](https://github.com/llvm/llvm-project/tree/main/libcxx)

As we mentioned earlier, the C++ standard tries to ensure ABI backward compatibility. Even with major updates like C++98 to C++11, the ABI of old code was not significantly affected, and there are no documented ABI Break Change wording changes at all.

However, for the C++ standard library, the situation is somewhat different. From C++98 to C++11, the standard library underwent a major ABI Break Change. The standard library modified the requirements for some container implementations, such as `std::string`. This led to the widely used COW implementation no longer conforming to the new standard, so a new implementation had to be adopted in C++11. This resulted in an ABI break between C++98 and C++11 standard libraries. However, since then, the standard library's ABI has generally been relatively stable, and each implementation tries to ensure this. Refer to the relevant pages for [stl](https://learn.microsoft.com/en-us/cpp/porting/binary-compat-2015-2017?view=msvc-170), [libstdc++](https://gcc.gnu.org/onlinedocs/libstdc++/manual/abi.html), and [libc++](https://libcxx.llvm.org/DesignDocs/ABIVersioning.html) for detailed information.

Additionally, since RTTI and Exception can generally be turned off, these two features might be handled by separate runtime libraries, such as MSVC's [vcruntime](https://docs.microsoft.com/en-us/cpp/c-runtime-library/crt-library-features?view=msvc-170) and libc++'s [libcxxabi](https://libcxxabi.llvm.org/).

> It's worth mentioning that libcxxabi also includes support for static local variable initialization, primarily involving the functions `__cxa_guard_acquire` and `__cxa_guard_release`. These are used to ensure that static local variables are initialized only once at runtime. If you are curious about the specific implementation, you can consult the relevant source code.

There are also runtime libraries responsible for some low-level functions, such as [libgcc](https://gcc.gnu.org/onlinedocs/gccint/Libgcc.html) and [compiler-rt](https://compiler-rt.llvm.org/).

Besides the standard library, C++ programs generally also need to link to the C runtime:

- On Windows, [CRT](https://learn.microsoft.com/en-us/cpp/c-runtime-library/compatibility?view=msvc-170) must be linked.
- On Linux, depending on the distribution and compilation environment used, it might link to [glibc](https://www.gnu.org/software/libc/) or [musl](https://musl.libc.org/).

The C runtime, in addition to providing the implementation of the C standard library, is also responsible for program initialization and cleanup. It is responsible for calling the `main` function and managing the program's startup and termination process, including performing necessary initialization and cleanup tasks. For most software running on an operating system, linking to it is essential.

The ideal state is naturally to upgrade these corresponding runtime library versions when upgrading the compiler to avoid unnecessary trouble. However, in actual projects, dependencies can be very complex, potentially triggering a chain reaction.

## User Code

Finally, let's talk about ABI issues caused by changes in user code itself. If you want to distribute your library in binary form, then ABI compatibility becomes very important once the user base reaches a certain size.

In the first subsection discussing calling conventions, we mentioned ABI incompatibility caused by changes in struct definitions. So, what if you want to ensure ABI compatibility while also leaving room for future expansion? The answer is to handle it at runtime:

```cpp
struct X{
    size_t x;
    size_t y;
    void* reserved;
};
```

A `void*` pointer is used to reserve space for future extensions. Based on it, different versions can be distinguished, for example:

```cpp
void f(X* x) {
    Reserved* r = static_cast<Reserved*>(x->reserved);
    if (r->version == ...) {
        // do something
    } else if (r->version == ...) {
        // do something else
    }
}
```

This way, new features can be added without affecting existing code.

When exposing interfaces, special attention should be paid to types with custom destructors in function parameters. Suppose we want to expose `std::vector` as a return value. For example, compile the simple code below into a dynamic library, and use the `\MT` option to statically link the Windows CRT.

```cpp
__declspec(dllexport) std::vector<int> f() {
    return {1, 2, 3};
}
```

Then we write a source file, link it to the dynamic library just compiled, and call this function:

```cpp
#include <vector>

std::vector<int> f();

int main() {
    auto vec = f();
}
```

Compile and run, and it crashes directly. If we recompile the dynamic library with `\MT` disabled and then run it, everything works fine. It's strange, why would a dependent dynamic library statically linking CRT cause the code to crash?

Thinking about the code above, it's not hard to find that `vec`'s construction actually happens inside the dynamic library, while its destruction happens inside the `main` function. More precisely, memory is allocated inside the dynamic library and freed inside the `main` function. However, each CRT has its own `malloc` and `free` (similar to memory between different processes). **You cannot free memory allocated by CRT A with CRT B.** This is the root of the problem. So, after not statically linking to CRT, everything is fine; they all use the same `malloc` and `free`. This applies not only to Windows CRT but also to glibc or musl on Linux. Example code is available [here](https://github.com/16bit-ykiko/about-me/tree/main/code/crt-fault); feel free to try it yourself.

### extern "C"

The situation described above can occur for any C++ type with a custom destructor. **For various reasons, constructor and destructor calls crossing dynamic library boundaries break the RAII contract, leading to serious errors.**

How to solve this? Naturally, function parameters and return values should not use types with destructors, but only POD types.

For example, the above example needs to be changed to:

```cpp
using Vec = void*;

__declspec(dllexport) Vec create_Vec() {
    return new std::vector<int>;
}

__declspec(dllexport) void destroy_Vec(Vec vec) {
    delete static_cast<std::vector<int>*>(vec);
}
```

And then usage would be like this:

```cpp
using Vec = void*;

Vec create_Vec();
void destroy_Vec(Vec vec);

int main() {
    Vec vec = create_Vec();
    destroy_Vec(vec);
}
```

In fact, we are encapsulating it in a C-style RAII manner. Furthermore, if you want to solve the linking problem between C and C++ due to different mangling, you can use `extern "C"` to decorate the function:

```cpp
extern "C" {
    Vec create_Vec();
    void destroy_Vec(Vec vec);
}
```

This way, C language can also use the exported functions mentioned above.

However, if the codebase is large, encapsulating all functions into such an API is clearly unrealistic. In that case, C++ types must be exposed in the exported interfaces, and dependencies must be carefully managed (e.g., all dependent libraries are statically linked). The specific choice depends on the project size and complexity.

## Conclusion

Here, we have finally discussed the main factors affecting the ABI of C++ programs. It is clear that the C++ standard, compiler vendors, and runtime libraries are all striving to maintain ABI stability. The C++ ABI is not as bad or unstable as many people claim. For small projects, static linking with source code almost eliminates any compatibility issues. For large, long-standing projects, due to complex dependencies, upgrading certain library versions might cause program crashes. **But this is not C++'s fault. Managing large projects goes beyond the language level itself; one cannot expect to solve these problems by simply changing programming languages.** In fact, learning software engineering is about learning how to deal with immense complexity and how to ensure the stability of complex systems.

The article ends here. Thank you for reading. The author's expertise is limited, and this article covers a wide range of topics. Please feel free to leave comments and discuss any errors.

Some other references:

- [An Overview of ABI in Different Platforms](https://www.agner.org/optimize/calling_conventions.pdf)
- [Windows x64 ABI](https://learn.microsoft.com/en-us/cpp/build/x64-software-conventions?view=msvc-170)
- [System V x64 ABI](https://gitlab.com/x86-psABIs/x86-64-ABI)
- [Itanium C++ ABI](https://itanium-cxx-abi.github.io/cxx-abi/abi.html)
- [MinGW x64 Software Convention](https://sourceforge.net/p/mingw-w64/wiki2/MinGW%20x64%20Software%20convention/)
- [MacOS x64 ABI](https://developer.apple.com/documentation/xcode/writing-64-bit-intel-code-for-apple-platforms)
- [ARM ABI](https://developer.arm.com/Architectures/Application%20Binary%20Interface)
- [Windows ARM64 ABI](https://learn.microsoft.com/en-us/cpp/build/arm64-windows-abi-conventions?view=msvc-170)
- [RISCV ABI](https://d3s.mff.cuni.cz/files/teaching/nswi200/202324/doc/riscv-abi.pdf)
- [Go Internal ABI](https://go.googlesource.com/go/+/refs/heads/dev.regabi/src/cmd/compile/internal-abi.md)
