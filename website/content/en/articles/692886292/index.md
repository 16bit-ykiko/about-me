---
title: 'Understanding C++ ABI in Depth'
date: 2024-04-17 02:19:38
updated: 2024-12-22 19:05:57
---

The Application Binary Interface, commonly referred to as ABI, is a concept that feels both familiar and alien. Familiar because it often comes up in discussions and articles, and sometimes we have to deal with compatibility issues it causes. Alien because if someone asks you what ABI is, you might find it hard to describe it in precise terms. Eventually, you might resort to quoting [WIKI](https://en.wikipedia.org/wiki/Application_binary_interface): ABI is the interface between two binary program modules. Is there a problem with this definition? Not really, as a general description, it suffices. But it feels somewhat hollow.

This situation is not uncommon in the field of Computer Science. The author previously wrote an article discussing [reflection](https://www.ykiko.me/zh-cn/articles/669358870) and encountered the same issue. At its core, CS is not a discipline that strives for rigor; many concepts lack strict definitions and are more about conventional wisdom. Therefore, instead of obsessing over definitions, let's focus on practical aspects and explore what these so-called binary interfaces are and what factors affect their stability.

## CPU & OS 

Ultimately, executable files run on specific CPUs and operating systems. If the CPU instruction sets differ, binary incompatibility is inevitable. For example, programs compiled for [ARM](https://en.wikipedia.org/wiki/ARM_architecture_family) cannot **directly** run on x64 processors (unless virtualization techniques are used). What if the instruction sets are compatible? For instance, x64 processors are compatible with x86 instruction sets. Can x86 programs run on x64 operating systems? This depends on the operating system, specifically factors like **Object File Format**, **Data Representation**, **Function Calling Convention**, and **Runtime Library**. These can be considered as ABI specifications at the operating system level. We'll discuss the fourth point in a later section. Below, we'll focus on the first three points using the x64 platform as an example.

> x64, x86-64, x86_64, AMD64, and Intel 64 all refer to the 64-bit version of the x86 instruction set.

**There are mainly two sets of ABIs on the x64 platform**:

- [Windows x64 ABI](https://learn.microsoft.com/en-us/cpp/build/x64-software-conventions?view=msvc-170) for 64-bit Windows operating systems
- [x86-64 System V ABI](https://gitlab.com/x86-psABIs/x86-64-ABI) for 64-bit Linux and other UNIX-like operating systems

Calling a function from a dynamic library can be simplified into three steps:

- Parse the dynamic library in a specific format
- Look up the function address from the parsed result based on the symbol name
- Pass function parameters and call the function

### Object File Format 

How to parse the dynamic library? This is where the ABI's specification of the Object File Format comes into play. If you want to write a linker, the generated executable must comply with the format requirements of the target platform. Windows x64 uses the [PE32+](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format) format, a 64-bit version of the PE32 (Portable Executable 32-bit) format. System V ABI uses the [ELF (Executable Linkable Format)](https://en.wikipedia.org/wiki/Executable_and_Linkable_Format) format. By using parsing libraries like [pe-parse](https://github.com/trailofbits/pe-parse) and [elfio](https://github.com/serge1/ELFIO), you can parse actual executable files to obtain the symbol table, which maps function names to their addresses.

### Data Representation 

After obtaining the function address, the next step is to call the function. Before calling, parameters need to be passed. Here, consistency in Data Representation is crucial. What does this mean?

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

Later, the structure changes due to version upgrades, and the user code sees the structure definition as:

```cpp
struct X{
    int a;
    int b;
    int c;
};
```

Then, the user tries to link the old version of the dynamic library and call the function:

```cpp
int main(){
    int n = foo({1, 2, 3});
    printf("%d\n", n);
}
```

Will this succeed? Of course not. This error can be seen as a violation of the One Definition Rule (ODR), more examples of which will be discussed in later sections.

The above scenario involves user-initiated code changes leading to ODR violations. What if I don't change the code? Can I ensure the stability of the structure layout? This is where the ABI's Data Representation comes into play. For example, it specifies the size and alignment of basic types: Windows x64 specifies `long` as 32-bit, while System V specifies `long` as 64-bit. It also specifies the size and alignment of `struct` and `union`.

> Note that the C language standard does not specify ABI. For System V ABI, it primarily uses C language terminology and concepts, so it can be considered as providing an ABI for C. The Windows x64 ABI does not make a clear distinction between C and C++.

### Function Calling Convention 

Next, we come to function parameter passing. We know that a function is just a block of binary data. Executing a function means jumping to its entry address, executing the code, and then jumping back. Passing parameters simply means finding a place to store data so that it can be accessed before and after the call. Where can this data be stored? There are four main options:

- Global variables
- Heap
- Registers
- Stack

Using global variables to pass parameters sounds magical, but in practice, we often turn frequently passed parameters into global variables, like `config`. However, not all parameters are suitable for global variables, especially when considering thread safety.

Using the heap to pass parameters also seems unconventional, but C++20's stackless coroutines store coroutine states (function parameters, local variables) on the heap. However, for ordinary function calls, dynamic memory allocation for each parameter is a bit extravagant.

Therefore, we mainly consider using registers and the stack for parameter passing. Having more options is usually good, but not here. If the caller decides to use registers to pass parameters, it stores the parameters in registers. But if the callee expects parameters to be passed via the stack, it retrieves data from the stack. This inconsistency can lead to reading garbage values, causing logical errors and program crashes.

How to ensure that the caller and callee agree on where to pass parameters? You might have guessed it: this is where the Function Calling Convention comes into play.

Specifically, the calling convention specifies:

- The order of function parameter passing: left to right or right to left?
- How function parameters and return values are passed: via stack or registers?
- Which registers remain unchanged before and after the call?
- Who is responsible for cleaning up the stack frame: caller or callee?
- How to handle C's [variadic](https://en.cppreference.com/w/c/variadic) functions?
- `...`

In 32-bit programs, there are many calling conventions like `__cdecl`, `__stdcall`, `__fastcall`, `__thiscall`, etc., leading to significant compatibility issues. In 64-bit programs, this has largely been unified. There are mainly two calling conventions: those specified by Windows x64 ABI and x86-64 System V ABI (though they don't have formal names). **It's important to note that function parameter passing is only related to the calling convention, not the code optimization level. You wouldn't want code compiled with different optimization levels to fail to link and run together.**

Discussing specific rules is somewhat boring, so interested readers can refer to the relevant sections of the documentation. Below, we'll discuss some interesting topics.

> Note: The following discussions only apply when function calls actually occur. If a function is fully inlined, the parameter passing behavior does not occur. Currently, C++ code inlining mainly happens within the same compilation unit (single file). For cross-compilation unit code, LTO (Link Time Optimization) must be enabled. Cross-dynamic library code cannot currently be inlined.

- **Passing structures smaller than 16 bytes by value is more efficient than by reference**

This has been a long-standing claim, but I never found evidence for it. Recently, while studying calling conventions, I found the reason. First, if the structure size is less than or equal to 8 bytes, it can be directly passed in a 64-bit register. **Passing parameters via registers involves fewer memory accesses than passing by reference**, making it more efficient. What about 16 bytes? System V ABI allows splitting a 16-byte structure into two 8-byte parts and passing them via registers. In this case, passing by value is indeed more efficient than passing by reference. Observe the following [code](https://godbolt.org/z/5Ph34x1cK):

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

The generated assembly code is as follows:

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

> System V ABI specifies that the first six integer parameters can be passed using `rdi`, `rsi`, `rdx`, `rcx`, `r8`, and `r9` registers. Windows x64 ABI specifies that the first four integer parameters can be passed using `rcx`, `rdx`, `r8`, and `r9` registers. If registers are exhausted, parameters are passed via the stack. Integer parameters include basic integer types like `char`, `short`, `int`, `long`, `long long`, and pointer types. Floating-point and SIMD parameters have dedicated registers, which we won't delve into here.

You can see that `1` and `2` are passed to the `f` function via registers `edi` and `esi`, while `g` passes the address of a temporary variable to the `g` function. However, this is System V ABI. For Windows x64 ABI, **if the structure size is greater than 8 bytes, it must be passed by reference**. The same code compiled on Windows produces the following assembly:

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

You can see that the code generated for both function calls is identical. This means that for Windows x64 ABI, structures larger than 8 bytes generate the same code whether passed by value or by reference.

- **unique_ptr and raw_ptr are equally efficient**

I used to believe this firmly, thinking that `unique_ptr` is just a simple wrapper around raw pointers. However, after watching the thought-provoking talk [There are no zero-cost abstractions](https://www.bilibili.com/video/BV1qp421y75W/?spm_id_from=333.999.0.0) at CPPCON, I realized I was mistaken. Here, we won't discuss the additional overhead caused by exceptions (destructors requiring the compiler to generate additional stack frame cleanup code). Instead, we'll focus on whether a C++ object (less than 8 bytes) can be passed via registers. For a completely [trivial](https://en.cppreference.com/w/cpp/language/classes#Trivial_class) type, this is possible; it behaves almost exactly like a C structure. But what if it's not trivial?

For example, if a custom copy constructor is defined, can it still be passed via registers? Logically, it cannot. Why? We know that C++ allows taking the address of function parameters. If the parameter is an integer passed via a register, where does the address come from? Let's experiment:

```cpp
#include <cstdio>

extern void f(int&);

int g(int x) {
    f(x);
    return x;
}
```

The generated assembly is as follows:

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

You can see that the value in `edi` (used to pass the first integer parameter) is copied to the address `rsp+12`, which is on the stack. This address is then passed to `f`. This means that if a function parameter is passed via a register and its address is needed, the compiler copies the parameter to the stack. **However, users cannot observe these copy operations because their copy constructors are trivial. Any optimization that does not affect the final execution result complies with the as-if rule.**

If the object has a user-defined copy constructor, passing parameters via registers could lead to additional copy constructor calls, which users can observe. This is clearly unreasonable, so objects with custom copy constructors cannot be passed via registers. What about passing via the stack? Similar copy issues arise. Therefore, such objects must be passed by reference. **Note that explicitly marking the copy constructor as `delete` also counts as a custom copy constructor.**

Therefore, for `unique_ptr`, it must be passed by reference, whether you write the function signature as `void f(unique_ptr<int>)` or `void f(unique_ptr<int>&)`. The generated binary code for parameter passing is the same. However, raw pointers can be safely passed via registers. In conclusion, `unique_ptr` and raw pointers are not equally efficient.

> In reality, the situation is more complex for non-trivial C++ objects. Interested readers can refer to the relevant sections of the ABI documentation. Additionally, whether the rules for passing C++ objects belong to the operating system's ABI or the C++ compiler's ABI is not entirely clear.

## C++ Standard 

Finally, we've covered the operating system-level guarantees. Since this is low-level and involves a lot of assembly, readers unfamiliar with assembly might find it challenging. However, the following content is mostly assembly-free and can be read with ease.

We all know that the C++ standard does not explicitly specify ABI, but it does have some requirements for compiler implementations, such as:

- Structure member addresses increase in declaration order [incrementally](https://en.cppreference.com/w/c/language/struct#Explanation), ensuring that the compiler does not reorder structure members.
- Structures satisfying the [Standard Layout](https://en.cppreference.com/w/cpp/language/data_members#Standard-layout) constraints must be compatible with corresponding C structures.
- Structures satisfying the [Trivially Copyable](https://en.cppreference.com/w/cpp/types/is_trivially_copyable) constraints can be copied using `memmove` or `memcpy` to create an identical new object.
- `...`

Additionally, as C++ continues to release new versions, will the same code compiled with new and old standards produce the same result (ignoring the impact of macros controlling C++ version conditional compilation)? This depends on the C++ standard's guarantees for ABI compatibility. In fact, the C++ standard strives to ensure **backward compatibility**. This means that two pieces of code compiled with old and new standards should be identical.

However, there are a few exceptions, such as (I could only find these; feel free to comment with more):

- C++17 made `noexcept` part of the function type, affecting the function's mangling name.
- C++20 introduced `no_unique_address`, which MSVC still does not fully support due to ABI breakage.

More often, new C++ versions introduce new language features with new ABIs without affecting old code. For example, C++23 introduced two new features:

### Explicit Object Parameter 

Before C++23, there was no **legal** way to obtain the address of a member function. The only option was to obtain a member pointer (for more on member pointers, refer to this [article](https://www.ykiko.me/zh-cn/articles/659510753)):

```cpp
struct X {
    void f(int);
};

auto p = &X::f; 
// p is a pointer to member function of X
// type of p is void (X::*)(int)
```

To use a member function as a callback, you had to wrap it in a lambda expression:

```cpp
struct X {
    void f(int);
};

using Fn = void(*)(X*, int);
Fn p = [](A* self, int x) { self->f(x); };
```

This is cumbersome and unnecessary, and the wrapper could introduce additional function call overhead. This is somewhat a historical legacy issue. On 32-bit systems, member function calling conventions were special (the well-known `thiscall`), and C++ did not include calling convention details, leading to the creation of member function pointers. Old code cannot change for ABI compatibility, but new code can. C++23 introduced the explicit object parameter, allowing us to specify how `this` is passed, even by value:

```cpp
struct X {
    // Here, `this` is just a marker to distinguish from old syntax
    void f(this X self, int x); // pass by value
    void g(this X& self, int x); // pass by reference
};
```

Functions marked with explicit `this` can now have their addresses taken directly, just like ordinary functions:

```cpp
auto f = &X::f; // type of f is