---
title: 'Where Exactly Does C++ Code Bloat Occur?'
date: 2024-03-11 09:33:37
updated: 2024-12-24 12:17:12
---

Readers often hear that C++ code suffers from severe binary bloat, but few can pinpoint the exact reasons. After some online research, it becomes clear that there are not many in-depth discussions on this topic. The statement seems more like a cliché, passed down through word of mouth, with few able to explain it thoroughly. Today, ykiko will take you on a journey to uncover the mysteries of C++ code bloat (^ω^)

First, let's discuss what code bloat actually means. If a function is heavily inlined, the resulting executable file will be larger compared to when it is not inlined. Does this count as bloat? I argue that it does not, as this is within our expectations and is considered normal behavior. Conversely, code bloat that is not within our expectations, theoretically avoidable but not eliminated due to current implementations, is what I call "true code bloat." The bloat discussed later in this article refers to this type.

## Does Marking Functions with `inline` Cause Bloat?

First, it's important to clarify that the `inline` keyword in C++ has a specific semantic meaning: **it allows a function to be defined in multiple source files**. Functions marked with `inline` can be defined directly in header files, and even if they are included by multiple source files, it won't cause linking errors. This facilitates the creation of header-only libraries.

### Multiple Instances

Since the function can be defined in multiple source files, does this mean each source file will have its own instance of the code, potentially leading to code bloat?

Consider the following example, where the comments indicate the file names:

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

First, let's compile the first two files **without optimization** to see if they each retain a copy of the `add` function.

```bash
$ g++ -c src1.cpp -o src1.o
$ g++ -c src2.cpp -o src2.o
```

Now, let's examine the symbol tables of these two files:

```bash
$ objdump -d src1.o | c++filt
$ objdump -d src2.o | c++filt
```

For convenience, I'll provide the corresponding links and screenshots from Godbolt, which omits many non-essential symbols for clarity.

![](https://pic4.zhimg.com/v2-0f8338487557d14a675e82276a73b9a3_r.jpg)

As you can see, both [source files](https://godbolt.org/z/xoW8TTvP7) retain their own instances of the `add` function. Now, let's link them into an executable:

```bash
$ g++ main.o src1.o src2.o -o main.exe
$ objdump -d main.exe | c++filt
```

The result is shown below:

![](https://pic1.zhimg.com/v2-90853d7ae94867f68e8130b835c8f832_r.jpg)

The linker retains only one instance of the `add` function, so there is **no additional code bloat**. The C++ standard requires that inline functions have identical definitions across different translation units, so it doesn't matter which instance is retained. But what if the definitions differ? This would violate the One Definition Rule (ODR), leading to undefined behavior. The specific instance retained may depend on the implementation or even the linking order. I might write a separate article on ODR violations in the future, so I won't delve too deep here. **Just know that the C++ standard guarantees that inline functions have identical definitions across translation units.**

### Full Inlining

Earlier, I specifically emphasized compiling without optimization. What happens if we enable optimization? Using the same code, let's try compiling with `-O2` optimization. The [result](https://godbolt.org/z/jfx8jrnzf) is shown below:

![](https://pic1.zhimg.com/v2-ef6dc326331416c2a20e98a632a87150_r.jpg)

Surprisingly, with `-O2` optimization, the `add` function is completely inlined. The compiler doesn't even generate a symbol for `add`, so there's nothing to link. According to our earlier definition, this type of function inlining doesn't count as code bloat, so there's **no additional binary bloat**.

As a side note, if neither file generates the `add` symbol, what happens if another file references `add`? Wouldn't that cause a linking error?

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

Compiling and linking this code without optimization works fine. However, with optimization enabled, the linker fails with `undefined reference to add(int, int)`. **All three major compilers behave this way**, and the reason is as explained earlier: with optimization, the compiler doesn't generate the `add` symbol, so it can't be found during linking.

But is this behavior compliant with the C++ standard?

Since all three major compilers behave this way, it seems compliant. However, the standard doesn't explicitly state this in the inline section. In the [One Definition Rule](https://en.cppreference.com/w/cpp/language/definition#One_Definition_Rule), there are two relevant points:

- For an inline function or inline variable (since C++17), a definition is required in every translation unit where it is odr-used.
- A function is odr-used if a function call to it is made or its address is taken.

What does this mean? It means that if an inline function is [odr-used](https://en.cppreference.com/w/cpp/language/definition#ODR-use) in a translation unit, that unit must have a definition of the function. What counts as odr-used? The second point explains that if **a function is called** or **its address is taken**, it is odr-used.

In our earlier code, `main.cpp` calls an inline function but doesn't define it, which violates the C++ standard. This is a bit counterintuitive, but it's the reality, and all three major compilers are correct!

### Other Cases

This section mainly discusses two scenarios:

- The first is when an `inline` function has instances (generates symbols) in multiple translation units. In this case, mainstream linkers will retain only one instance, avoiding additional code bloat.
- The second scenario is when an `inline` function is fully inlined and no symbol is generated. This is similar to regular function inlining and doesn't count as "additional overhead."

Some might think that C++ optimization rules are too complex. However, the core rule is the `as-if` principle: the compiler can perform any optimization as long as the resulting code behaves the same as the unoptimized version. Most compiler optimizations follow this principle, with only a few exceptions. The optimization of inline functions also adheres to this principle. If the address of an inline function isn't explicitly taken, there's no need to retain its symbol.

Additionally, while the `inline` keyword no longer enforces inlining at the standard level, it does provide a hint to the compiler that makes the function more likely to be inlined. How does this hint work? As mentioned earlier, the standard's wording allows inline functions to avoid generating symbols. In contrast, functions without any specifier are marked as `extern` by default and must generate symbols. **The compiler is more willing to inline functions that don't need to generate symbols.** From this perspective, you might guess that `static` has a similar hinting effect, and indeed it does. Of course, this is just one aspect; in reality, the decision to inline a function is much more complex.

Note: This section only discusses functions marked with `inline`. There are also combinations like `inline static` and `inline extern`, which interested readers can explore in the official documentation or by experimenting.

## What Really Causes Template Code Bloat?

If someone gives a reason for C++ binary bloat, it's almost always templates. Is this really the case? How exactly do templates cause binary bloat? Under what circumstances? Does using templates always cause bloat?

### Implicit Instantiation is Like `inline`

We know that template instantiation occurs in the current translation unit, and each instantiation generates a copy of the code. Consider the following example:

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

Compile without optimization and check the [compilation result](https://godbolt.org/z/aTxMsnK5n):

![](https://pic4.zhimg.com/v2-5de99e270f381ff7f77f012ed72836bb_r.jpg)

As with inline functions, both translation units instantiate `add<int, int>` and `add<double, double>`, each with its own copy. During linking, the linker retains only one instance of each template instantiation. Now, let's try compiling with `-O2` and see what happens. The [result](https://godbolt.org/z/edEd8Tvo4) is as follows:

![](https://picx.zhimg.com/v2-5e915f5cb7b7fc25e00a5f6c8ae2fa95_r.jpg)

Similar to inline functions, the compiler inlines the function and discards the symbols of the instantiated functions. In this case, either the function is inlined and no symbol is generated, or a symbol is generated and the function is merged during linking. Like inline functions, this doesn't seem to cause additional bloat. So, where does the often-mentioned template bloat come from?

### Explicit Instantiation and `extern` Templates

Before discussing the real cause of bloat, let's talk about explicit instantiation.

Although the linker can merge multiple identical template instantiations, parsing the template definition, instantiating the template, generating the final binary code, and removing duplicate code during linking all take time. Sometimes, we know that only a few fixed template parameter instantiations are needed, such as with the standard library's `basic_string`, which is almost always instantiated with a few fixed types. If every file that uses these types has to instantiate the template, it could significantly increase compilation time.

Can we place the implementation in a single source file and have other files reference it, like with non-template functions? From the previous discussion, since symbols are generated, there should be a way to link to them. But how can we ensure that symbols are generated?

The answer is — explicit instantiation!

What is explicit instantiation? Simply put, if you directly use a template without declaring specific types, and the compiler generates the declaration for you, it's called implicit instantiation. Conversely, if you declare specific types beforehand, it's called explicit instantiation. For function templates:

```cpp
template <typename T>
void f(T a, T b) { return a + b; }

template void f<int>(int, int); // Explicit instantiation of f<int> definition

void g()
{
    f(1, 2); // Calls the explicitly instantiated f<int>
    f(1.0, 2.0); // Implicitly instantiates f<double>
}
```

This is quite straightforward, and **explicit instantiation definitions** will always generate symbols. Now, how do other files link to this explicitly instantiated function? There are two ways:

One is to explicitly instantiate a function declaration:

```cpp
template <typename T>
void f(T a, T b);

template void f<int>(int, int); // Explicit instantiation of f<int> declaration
```

The other is to use the `extern` keyword to instantiate a definition:

```cpp
template <typename T>
void f(T a, T b){ return a + b; }

extern template void f<int>(int, int); // Explicit instantiation of f<int> declaration
// Note: Without extern, this would explicitly instantiate a definition
```

Both methods correctly reference the `f` function defined earlier, allowing calls to template instantiations in other files!

### The Real Cause of Template Bloat

Now, let's discuss the real cause of template bloat. Due to some historical reasons, in C++, `char`, `unsigned char`, and `signed char` are always distinct types:

```cpp
static_assert(!std::is_same_v<char, unsigned char>);
static_assert(!std::is_same_v<char, signed char>);
static_assert(!std::is_same_v<unsigned char, signed char>);
```

However, in the compiler's final implementation, `char` is either `signed` or `unsigned`. Suppose we write a template function:

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

Instantiating the template for these three types means that two of the instantiations will generate identical code. Will the compiler merge functions that have different types but generate identical binary code? Let's try it out. The [result](https://godbolt.org/z/KncEh3z5n) is as follows:

![](https://pica.zhimg.com/v2-5c57236015036328a7e0f321aadf513a_r.jpg)

As you can see, two identical functions are generated but not merged. Of course, if we enable `-O2` optimization, such short functions will be inlined, and no symbols will be generated. As mentioned earlier, this means there's no "additional template bloat." In practice, many small template functions, like `vector`'s `end`, `begin`, and `operator[]`, are likely to be fully inlined, avoiding "additional bloat."

Now, the question is: what if the function isn't inlined? Suppose the template function is complex and has a large body. For demonstration purposes, we'll use GCC's `[[gnu::noinline]]` attribute to simulate this effect, then compile the [code](https://godbolt.org/z/Exff5cnfj) with `-O2`:

![](https://pic1.zhimg.com/v2-37da15bf141999c1bc8d6f7b07575f36_r.jpg)

Even though the function is optimized down to a single instruction, the compiler still generates three copies. In reality, functions that aren't inlined by the compiler might be much larger, making the situation worse than this "pseudo-large function." This is where the so-called "template bloat" comes from. **Code that could be merged isn't merged, and this is the real cause of template bloat.**

If you really want the compiler/linker to merge identical binary code, what can you do? Unfortunately, mainstream toolchains like ld, lld, and MS linker don't perform this merging. The only linker that supports this feature is [gold](https://www.gnu.org/software/binutils/), but it only works with ELF format executables, so it can't be used on Windows. Here's how to use gold to merge identical binary code:

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

Here, I generate 100 different types using templates, but in reality, they are all based on `size_t`, so the final compiled binary code is identical. Compile it with the following command:

```bash
$ g++ -O2 -ffunction-sections -fuse-ld=gold -Wl,--icf=all main.cpp -o main.o
$ objdump -d main.o | c++filt
```

Using `-fuse-ld=gold` specifies the linker, and `-Wl,--icf=all` specifies the linker option. `icf` stands for "identical code folding," which merges identical code. Since the linker works at the section level, GCC needs to enable `-ffunction-sections`. You can also replace GCC with Clang:

```bash
0000000000000740 <X<99ul>::f() [clone .isra.0]>:
 740:   48 89 fa                mov    %rdi,%rdx
 743:   48 8d 35 1a 04 00 00    lea    0x41a(%rip),%rsi
 74a:   bf 01 00 00 00          mov    $0x1,%edi
 74f:   31 c0                   xor    %eax,%eax
 751:   e9 ca fe ff ff          jmp    620 <_init+0x68>
 756:   66 2e 0f 1f 84 00 00    cs nopw 0x0(%rax,%rax,1)
 75d:   00 00 00 

0000000000000760 <void call_f<0..99>(std::integer_sequence<unsigned long, 0..99>)