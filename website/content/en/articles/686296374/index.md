---
title: Where exactly does C++ code bloat occur?
date: "2024-03-11 01:33:37"
updated: "2024-12-24 04:17:12"
zhihu_article_id: "686296374"
zhihu_url: https://zhuanlan.zhihu.com/p/686296374
zhihu_column_id: c_1656510843973046272
zhihu_column_title: 魅力C++
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

Readers probably often hear people say that C++ code suffers from severe binary bloat, but usually few people point out the specific reasons. After a search online, I found that there aren't many articles that delve deeply into this issue. The above statement is more like part of a cliché, passed down by word of mouth, but few can explain why. Today, your editor ykiko will take everyone on a journey to explore the ins and outs of C++ code bloat (^ω^)

First, let's discuss, what is code bloat? If a function is heavily inlined, the final executable file will be larger compared to not being inlined, right? Does that count as bloat? I don't think so; this is within our expectations, acceptable, and normal behavior. Conversely, code bloat that is outside our expectations, theoretically eliminable but not eliminated due to existing implementations, I call "true code bloat". All discussions of bloat in the following text refer to this meaning.

## Does marking a function with `inline` cause bloat?

First, it's important to clarify that `inline` here refers to C++'s `inline`, whose semantic meaning as defined by the standard is to **allow a function to be defined in multiple source files**. Functions marked with `inline` can be defined directly in header files, and even if `#include`d by multiple source files, they will not cause linking errors, thus conveniently supporting header-only libraries.

### Case of multiple instances

Since it can be defined in multiple source files, does that mean each source file will have a separate code instance, potentially leading to code bloat?

Consider the following example, where the comments at the beginning indicate the filename:

```cpp
// src1.cpp
inline int add(int a, int b) {
    return a + b;
}

int g1(int a, int b) {
    return add(a, b);
}

// src2.cpp
inline int add(int a, int b) {
    return a + b;
}

int g2(int a, int b){
    return add(a, b);
}

// main.cpp
#include <cstdio>
extern int g1(int, int);
extern int g2(int, int);

int main() {
    return g1(1, 2) + g2(3, 4);
}
```

Let's first try compiling the first two files **without optimization** to see if they each retain an instance of the `add` function.

```bash
$ g++ -c src1.cpp -o src1.o
$ g++ -c src2.cpp -o src2.o
```

Let's examine the symbol tables in these two files separately.

```bash
$ objdump -d src1.o | c++filt
$ objdump -d src2.o | c++filt
```

Local verification is done by directly viewing the symbol table using the above commands. However, for convenience of demonstration, I will include the corresponding Godbolt link and screenshot, which omits many non-critical symbols that affect readability, making it clearer.

![](https://pic4.zhimg.com/v2-0f8338487557d14a675e82276a73b9a3_r.jpg)

As you can see, these two [source files](https://godbolt.org/z/xoW8TTvP7) each retain an instance of the `add` function. Then we link them into an executable file.

```bash
$ g++ main.o src1.o src2.o -o main.exe
$ objdump -d main.exe | c++filt
```

The result is shown below.

![](https://pic1.zhimg.com/v2-90853d7ae94867f68e8130b835c8f832_r.jpg)

We find that the linker only keeps one of the two `add` instances, so there is no **additional code bloat**. Furthermore, the C++ standard requires that the definitions of inline functions in different translation units must be identical, so it makes no difference which copy of the code is kept. But if you ask: what if the definitions are different? That would lead to an ODR violation, which is strictly speaking undefined behavior. Which one is kept might depend on the specific implementation, and even on the linking order. I might write a separate article about ODR violations soon, so I won't go into too much detail here. **Just know that the C++ standard guarantees that inline functions have identical definitions across different translation units**.

### Case of complete inlining

Earlier, I specifically emphasized compiling without optimization. What happens if optimization is enabled? Using the same code as above, let's try enabling `O2` optimization. The final [result](https://godbolt.org/z/jfx2jrnzf) is shown below.

![](https://pic1.zhimg.com/v2-ef6dc326331416c2a20e98a632a87150_r.jpg)

It might be a bit surprising, but after enabling `-O2` optimization, the `add` call is completely inlined. The compiler doesn't even generate a symbol for `add` in the end, so naturally, there's no `add` during linking. According to our previous definition, this kind of function inlining is not considered code bloat, so there is no **additional** binary bloat overhead.

To digress slightly, since neither of these files generates the `add` symbol, wouldn't linking fail if another file referenced the `add` symbol?

Consider the following code:

```cpp
// src1.cpp
inline int add(int a, int b) {
    return a + b;
}

int g1(int a, int b) {
    return add(a, b);
}

// main.cpp
inline int add(int a, int b);

int main() {
    return g1(1, 2) + add(3, 4);
}
```

Let's try compiling and linking the above code. We find that linking succeeds without optimization. With optimization enabled, linking will fail. The linker will tell you `undefined reference to add(int, int)`. **This is the behavior of all three major compilers**. The specific reason has been explained above: after optimization is enabled, the compiler simply doesn't generate the `add` symbol, so it cannot be found during linking.

But what we want to know is, does this comply with the C++ standard?

Since all three major compilers behave this way, it seems there's no reason for it to be non-compliant. However, it's not explicitly stated in the `inline` section, but the [One Definition Rule](https://en.cppreference.com/w/cpp/language/definition#One_Definition_Rule) states the following two sentences:

- For an inline function or inline variable(since C++17), a definition is required in every translation unit where it is odr-used.
- a function is odr-used if a function call to it is made or its address is taken

What do these two sentences mean? It means that if an inline function is [odr-used](https://en.cppreference.com/w/cpp/language/definition#ODR-use) in a certain translation unit, then that translation unit must have the definition of that function. What constitutes odr-use? The next sentence explains that if a **function is called** or its **address is taken**, it is considered odr-used.

So, looking at our previous code, an inline function is called in `main.cpp` but not defined there, which actually violates the C++ standard's agreement. At this point, it's a relief. Although it's a bit counter-intuitive, it is indeed the case, and all three major compilers are correct!

### Other cases

In this subsection, we mainly discussed two situations:

- In the first case, the `inline` function has instances in multiple translation units (generating symbols). In this scenario, most mainstream linkers will only choose to keep one copy, so there will be no additional code bloat.
- The second case is when the `inline` function is completely inlined and no symbol is generated. In this situation, just like a regular function being inlined, it does not constitute "additional overhead".

Some might feel that C++ optimization has too many rules. But in reality, there's only one core rule: the `as-if` rule, which means the compiler can perform any optimization as long as the final generated code behaves the same as if it were not optimized. Compilers mostly optimize according to this principle, with only a few exceptions where this principle might not be met. The optimization of inline functions mentioned above also adheres to this principle; if the address of an inline function is not explicitly taken, there's indeed no need to retain its symbol.

Additionally, although `inline` no longer carries a mandatory inlining semantic at the standard level, it actually provides hints to the compiler, making the function more likely to be inlined. How does this hint work? As mentioned earlier, the standard wording indicates that inline functions may not generate symbols. In contrast, functions without any specifiers are implicitly marked as `extern` and must generate symbols. **Compilers are certainly more inclined to inline functions that do not need to generate symbols**. From this perspective, you might guess that `static` would also have a similar hint effect, and indeed it does. Of course, these are just one aspect; in reality, the calculation to determine whether a function is inlined is much more complex.

> Note: This subsection only discussed functions marked solely with `inline`. There are also combinations like `inline static` and `inline extern`. Interested readers can consult official documentation or experiment themselves to see their effects.

## The true reason for code bloat caused by templates?

If someone gives a reason for C++ binary bloat, their answer will almost certainly be templates. Is that really the case? How exactly do templates cause binary bloat? Under what circumstances does it occur? Does using them automatically lead to it?

### Implicit instantiation is like `inline` marking

We know that template instantiation happens in the current translation unit, and each instantiation generates a copy of the code. Consider the following example:

```cpp
// src1.cpp
template <typename T>
int add(T a, T b) { return a + b; }

float g1() {
    return add(1, 2) + add(3.0, 4.0);
}

// src2.cpp
template <typename T>
int add(T a, T b) { return a + b; }

float g2() {
    return add(1, 2) + add(3.0, 4.0);
}

// main.cpp
extern float g1();
extern float g2();

int main() {
    return g1() + g2();
}
```

Still without optimization, let's try compiling. The [compilation result](https://godbolt.org/z/aTxMsnK5n) is as follows:

![](https://pic4.zhimg.com/v2-5de99e270f381ff7f77f012ed72836bb_r.jpg)

As you can see, just like functions marked with `inline`, both translation units instantiate `add<int, int>` and `add<double, double>`, each having a copy of the code. Then, during final linking, the linker only keeps one copy of the code for each template instantiation. Now let's try enabling `-O2` and see what happens. The [result](https://godbolt.org/z/edEd8Tvo4) is as follows:

![](https://picx.zhimg.com/v2-5e915f5cb7b7fc25e00a5f6c8ae2fa95_r.jpg)

Similar to the effect of `inline` marking, the compiler directly inlines the function and discards the symbols of the instantiated functions. In this case, either the function is inlined and no symbol is generated, or a symbol is generated and the functions are eventually merged. Like `inline`, this situation doesn't seem to have additional bloat. So, where exactly is the often-mentioned template bloat?

### Explicit instantiation and extern templates

Before introducing the true reasons for bloat, let's first discuss explicit instantiation.

Although the linker can eventually merge multiple identical template instantiations. However, parsing template definitions, template instantiation, generating the final binary code, and the linker removing duplicate code all take compilation time. Sometimes, we know that we only use instantiations with a few fixed template parameters, for example, standard library `basic_string` almost exclusively uses a few fixed types as template parameters. If every file that uses them has to perform template instantiation, it can significantly increase compilation time.

Can we, like non-template functions, put the implementation in one source file and have other files reference functions from that source file? From the discussion in the previous subsection, since symbols are generated, there should be a way to link to them. But it's not guaranteed that symbols will always be generated. Is there a way to ensure symbol generation?

The answer is — explicit instantiation!

What is explicit instantiation? Simply put, if you use a template directly. Without explicitly declaring the specific type beforehand, and the compiler generates the declaration for you, that's implicit instantiation. Conversely, that's called explicit instantiation. Taking a function template as an example:

```cpp
template <typename T>
void f(T a, T b) { return a + b; }

template void f<int>(int, int); // Explicitly instantiate f<int> definition

void g()
{
    f(1, 2); // Call the previously explicitly instantiated f<int>
    f(1.0, 2.0); // Implicitly instantiate f<double>
}
```

I believe it's still easy to understand, and with **explicit instantiation definition**, the compiler will definitely retain the symbol for you. Next, how to link to this explicitly instantiated function from outside? There are two ways:

One way is to explicitly instantiate a function declaration directly:

```cpp
template <typename T>
void f(T a, T b);

template void f<int>(int, int); // Explicitly instantiate f<int> declaration only
```

Another way is to directly use the `extern` keyword to instantiate a definition:

```cpp
template <typename T>
void f(T a, T b){ return a + b; }

extern template void f<int>(int, int); // Explicitly instantiate f<int> declaration
// Note that without extern, it would explicitly instantiate a definition.
```

Both of these methods can correctly reference the function `f` above, allowing you to call template instantiations from other files!

### The true overhead of template bloat

Now for the most important part: we will introduce the true reasons for template bloat. Due to some historical legacy issues, the three types `char`, `unsigned char`, and `signed char` are always distinct in C++.

```cpp
static_assert(!std::is_same_v<char, unsigned char>);
static_assert(!std::is_same_v<char, signed char>);
static_assert(!std::is_same_v<unsigned char, signed char>);
```

However, when it comes to the compiler's final implementation, `char` is either `signed` or `unsigned`. Suppose we write a template function:

```cpp
template <typename T>
void f(T a, T b){ return a + b; }

void g()
{
    f<char>('a', 'a');
    f<unsigned char>('a', 'a');
    f<signed char>('a', 'a');
}
```

Instantiating function templates for these three types means that two of the instantiations will inevitably have identical code. Will the compiler merge two functions that have different function types but generate identical binary code? Let's try it. The [result](https://godbolt.org/z/KncEh3z5n) is as follows:

![](https://pica.zhimg.com/v2-5c57236015036328a7e0f321aadf513a_r.jpg)

As you can see, two identical functions are generated here, but they are not merged. Of course, if we enable `-O2` optimization, such short functions will be inlined and no final symbols will be generated. As discussed in the first subsection, there would be no "template bloat overhead". In actual code writing, there are many such short template functions, such as `end`, `begin`, `operator[]` for containers like `vector`. They are highly likely to be completely inlined, thus incurring no "additional bloat" overhead.

Now the question is, what if the function is not inlined? Suppose the template function is more complex and has a larger body. For demonstration purposes, we will temporarily use GCC's `[[gnu::noinline]]` attribute to achieve this effect, then enable O2, and compile the [code](https://godbolt.org/z/Exff5cnfj) again:

![](https://pic1.zhimg.com/v2-37da15bf141999c1bc8d6f7b07575f36_r.jpg)

As you can see, even though optimization left only one instruction, the compiler still generated three copies of the function. In reality, functions that are truly not inlined by the compiler might have a larger body, and the situation could be much worse than this "disguised large function". Thus, this is where the so-called "template bloat" arises. **Code that could have been merged was not, and this is where the true overhead of template bloat lies**.

What if we really want the compiler/linker to merge these identical binary codes? Unfortunately, mainstream toolchains like `ld`, `lld`, and `ms linker` do not perform such merging. Currently, the only linker that supports this feature is [gold](https://www.gnu.org/software/binutils/), but it can only be used to link ELF-formatted executables, so it cannot be used on Windows. Below, I will demonstrate how to use it to merge identical binary code:

```cpp
// main.cpp
#include <cstdio>
#include <utility>

template <std::size_t I>
struct X {
    std::size_t x;

    [[gnu::noinline]] void f() {
        printf("X<%zu>::f() called\n", x);
    }
};

template <std::size_t... Is>
void call_f(std::index_sequence<Is...>) {
    ((X<Is>{Is}).f(), ...);
}

int main(int argc, char *argv[]) {
    call_f(std::make_index_sequence<100>{});
    return 0;
}
```

Here, I generated `100` different types using templates, but in reality, their underlying type is `size_t`, so the final compiled binary code generated is completely identical. Try compiling it with the following commands:

```bash
$ g++ -O2 -ffunction-sections -fuse-ld=gold -Wl,--icf=all main.cpp -o main.o
$ objdump -d main.o | c++filt
```

Use `-fuse-ld=gold` to specify the linker, and `-Wl,--icf=all` to specify linker options. `icf` stands for `identical code folding`. Since the linker only operates at the section level, GCC needs to be used with `-ffunction-sections` enabled. The compiler above can also be replaced with `clang`.

```bash
0000000000000740 <X<99ul>::f() [clone .isra.0]>:
 740:   48 89 fa                mov    %rdi,%rdx
 743:   48 8d 35 1a 04 00 00    lea    0x41a(%rip),%rsi
 74a:   bf 01 00 00 00          mov    $0x1,%edi
 74f:   31 c0                   xor    %eax,%eax
 751:   e9 ca fe ff ff          jmp    620 <_init+0x68>
 756:   66 2e 0f 1f 84 00 00    cs nopw 0x0(%rax,%rax,1)
 75d:   00 00 00

0000000000000760 <void call_f<0..99>(std::integer_sequence<unsigned long, 0..99>) [clone .isra.0]>:
 760:   48 83 ec 08             sub    $0x8,%rsp
 764:   31 ff                   xor    %edi,%edi
 766:   e8 d5 ff ff ff          call   740 <X<99ul>::f() [clone .isra.0]>
 ... # repeated 98 times
 b48:   e9 f3 fb ff ff          jmp    740 <X<99ul>::f() [clone .isra.0]>
 b4d:   0f 1f 00                nopl   (%rax)
```

After some filtering of the output, it can be seen that gold merged 100 identical template functions into one, and the so-called "template bloat" disappeared. In contrast, the linkers that do not perform such merging naturally incur additional overhead.

However, gold is not a panacea; it cannot handle some situations well. Suppose that for these 100 functions, the first `90%` of the code is identical, but the last `10%` is different; then it would be powerless. It simply compares the final generated binaries and merges functions that are completely identical. Are there other solutions? **If there's no automatic, we still have manual. We C++ programmers aren't good at much else, but we're good at driving manual.**

### Manually optimizing template bloat

Below, taking the most commonly used `vector` as an example, I will demonstrate the main idea for solving template bloat. As mentioned earlier, short functions like iterator interfaces don't need our attention. We mainly deal with functions with more complex logic. For `vector`, the primary candidate is the growth function.

Suppose we have the following `vector` code:

```cpp
template <typename T>
struct vector {
    T* m_Begin;
    T* m_End;
    T* m_Capacity;

    void grow(std::size_t n);
};
```

Consider a naive implementation of `vector` growth, temporarily without considering exception safety:

```cpp
template <typename T>
void vector<T>::grow(std::size_t n) {
    T* new_date = static_cast<T*>(::operator new(n * sizeof(T)));
    if constexpr (std::is_move_constructible_v<T>) {
        std::uninitialized_move(m_Begin, m_End, new_date);
    } else {
        std::uninitialized_copy(m_Begin, m_End, new_date);
    }
    std::destroy(m_Begin, m_End);
    ::operator delete(m_Begin);
}
```

The logic seems quite simple. But undoubtedly, it's a relatively complex function, especially if the object's constructor is inlined, the amount of code can be quite large. So, how to merge it? Note that the prerequisite for merging templates is to find common parts among different template instantiations. If a function generates completely different code for different types, it cannot be merged.

For `vector`, if the element types in `T` are different, can the growth logic still be the same? Considering constructor calls, it seems there's no way. Here's the key point: we need to introduce the concept of `trivially_relocatable`. For a detailed discussion, you can refer to: [A brand new constructor, the relocate constructor in C++](https://www.ykiko.me/en/articles/679782886).

Here, we'll just state the result: if a type is `trivially_relocatable`, then `memcpy` can be used to move it from old memory to new memory, without needing to call constructors.

Consider writing the following growth function:

```cpp
void trivially_grow(char*& begin, char*& end, char*& capacity, std::size_t n, std::size_t size) {
    char* new_data = static_cast<char*>(::operator new(n * size));
    std::memcpy(new_data, begin, (end - begin) * size);
    ::operator delete(begin);
    begin = new_data;
    end = new_data + (end - begin);
    capacity = new_data + n;
}
```

Then, forward the original `grow` implementation to this function:

```cpp
template <typename T>
void vector<T>::grow(std::size_t n) {
    if constexpr (is_trivially_relocatable_v<T>) {
        trivially_grow(reinterpret_cast<char*&>(m_Begin), reinterpret_cast<char*&>(m_End),
                reinterpret_cast<char*&>(m_Capacity), n, sizeof(T));
    } else {
        // Original implementation
    }
}
```

This completes the extraction of common logic. Thus, all `T`s that satisfy `trivially_relocatable` can share a single copy of this code. And almost all types that do not contain self-references meet this condition, so `99%` of types use the same growth logic! The optimization effect is very significant! In fact, many LLVM container source codes, such as `SmallVector`, `StringMap`, etc., use this technique. Additionally, if you feel that the `reinterpret_cast` above violates strict aliasing and makes you a bit uneasy, you can achieve the same effect through inheritance (using `void*` for base class members). The specific code will not be shown here.

## Code bloat caused by exceptions!

Why does LLVM source code disable exceptions? Many people might subconsciously think the reason is that exceptions are slow and inefficient. But in fact, according to the [LLVM Coding Standard](https://llvm.org/docs/CodingStandards.html#do-not-use-rtti-or-exceptions), the main purpose of disabling exceptions and `RTTI` is to reduce binary size. It is said that enabling exceptions and `RTTI` can cause LLVM's compiled output to bloat by `10%-15%`. So, what is the actual situation?

Currently, there are two main exception implementations: the Itanium ABI implementation and the MS ABI implementation. Simply put, the MS ABI uses a runtime lookup approach, which incurs additional runtime overhead even for exceptions in the happy path, but its advantage is that the final generated binary code is relatively smaller. The Itanium ABI, on the other hand, is our focus today. It claims zero-cost exceptions, meaning no additional runtime overhead in the happy path. But Gul'dan, what is the cost? The cost is very severe binary bloat. Why does bloat occur? Simply put, if you don't want to wait until runtime for lookup, you have to pre-generate tables. Due to the implicit propagation nature of exceptions, these tables can occupy a large amount of space. The specific implementation details are very complex and not the topic of this article. Here's an image to give you a general idea:

![](https://pic4.zhimg.com/v2-35106aada3a2e1e089d6aa685a2ad145_r.jpg)

So, what are we mainly discussing? There's no doubt that exceptions cause binary bloat. We will mainly look at how to reduce binary bloat caused by exceptions, using the Itanium ABI as an example.

Let's first look at the following example code:

```cpp
#include <vector>

void foo(); // Externally linked function, might throw an exception

void bar() {
    std::vector<int> v(12); // Has a non-trivial destructor
    foo();
}
```

Note that `foo` here is an externally linked function that might throw an exception. Also, the `vector`'s destructor call is after `foo`. If `foo` throws an exception, and the control flow jumps to an unknown location, the `vector`'s destructor might be skipped. If the compiler doesn't handle this specially, it will lead to a memory leak. Let's first enable only `-O2` and see the program's compilation result:

```bash
bar():
        ...
        call    operator new(unsigned long)
        ...
        call    foo()
        ...
        jmp     operator delete(void*, unsigned long)
        mov     rbp, rax
        jmp     .L2
bar() [clone .cold]:
.L2:
        mov     rdi, rbx
        mov     esi, 48
        call    operator delete(void*, unsigned long)
        mov     rdi, rbp
        call    _Unwind_Resume
```

Omitting the unimportant parts, it's roughly the same as what we just guessed. So what is this `.L2` for? This `.L2` is actually where the program jumps after an exception is handled by `catch` to complete any unfinished work (here, destructing objects that haven't been destructed yet), and then `Resume`s back to the previous location.

Let's slightly adjust the code, moving the `foo` call before the `vector` construction, keeping everything else the same:

```bash
bar():
        sub     rsp, 8
        call    foo()
        mov     edi, 48
        call    operator new(unsigned long)
        ...
        jmp     operator delete(void*, unsigned long)
```

We can see that no stack cleanup code is generated, which is reasonable. The reason is simple: if `foo` throws an exception, control flow jumps away directly, and `vector` hasn't even been constructed, so naturally, it doesn't need to be destructed. Simply adjusting the call order reduces binary size! However, dependency relationships are only obvious in such particularly simple cases. If there are many functions that actually throw exceptions, it becomes difficult to analyze.

### noexcept

Let's first discuss `noexcept`, introduced in C++11. Note that even with `noexcept`, this function might still throw an exception. If it does, the program will `terminate` directly. So you might ask, what's the use of this thing? If I throw an exception and don't catch it, doesn't it also `terminate`?

Actually, this is somewhat similar to `const`. If you want to modify a `const` variable, although it's undefined behavior, you can freely modify it at runtime with few restrictions. So you might ask, what's the point of `const`? One important meaning is to provide optimization hints to the compiler. The compiler can use this for _constant folding_ and _common subexpression elimination_.

`noexcept` is similar; it allows the compiler to assume that the function will not throw exceptions, thereby enabling some additional optimizations. Taking the code from the first example again, the only change is declaring the `foo` function as `noexcept`, and then compiling again:

```bash
bar():
        push    rbx
        mov     edi, 48
        call    operator new(unsigned long)
        ...
        call    foo()
        ...
        jmp     operator delete(void*, unsigned long)
```

As you can see, the code path for exception handling is also gone. This is thanks to `noexcept`.

### fno-exceptions

Finally, we come to the main event: `-fno-exceptions`. Note that this option is non-standard. However, all three major compilers provide it, though the specific implementation effects may vary slightly. There doesn't seem to be very detailed documentation. Based on my experience with GCC, this option prohibits the use of keywords like `try`, `catch`, `throw` in user code, leading to a compilation error if used. However, it specifically allows the use of the standard library. If an exception is thrown, just like with `noexcept`, the program will `terminate` directly. Therefore, if this option is enabled, GCC will by default assume that all functions do not throw exceptions.

Using the same example as above, let's try enabling `-fno-exceptions` and then compiling again:

```bash
bar():
        push    rbx
        mov     edi, 48
        call    operator new(unsigned long)
        ...
        call    foo()
        ...
        jmp     operator delete(void*, unsigned long)
```

As you can see, the effect is similar to that produced by `noexcept`: both make the compiler assume that a certain function will not throw exceptions, thus eliminating the need to generate additional stack cleanup code and achieving a reduction in program binary size.

---

This article covers a wide range of topics, so errors in some places are inevitable. Discussions and exchanges in the comments section are welcome.
