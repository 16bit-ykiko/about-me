---
series:
  - Constexpr
series_order: 1
title: The History of constexpr in C++! (Part One)
date: "2024-02-10 15:15:47"
updated: "2024-12-18 03:21:51"
zhihu_article_id: "682031684"
zhihu_url: https://zhuanlan.zhihu.com/p/682031684
zhihu_column_id: c_1656510843973046272
zhihu_column_title: 魅力C++
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

A few months ago, I wrote an article introducing C++ templates: [Looking at Flowers in a Fog: A True Understanding of C++ Templates](https://www.ykiko.me/en/articles/655902377).

It clarified the position of templates in modern C++. Among the changes, using constexpr functions to replace templates for compile-time computation is arguably one of the most important improvements in modern C++. `constexpr` itself is not difficult to understand; it's very intuitive. However, because it has been improved in almost every version of C++, the features available in different C++ versions vary greatly, which can sometimes give a feeling of `inconsistency`.

Coincidentally, I recently came across this article: [Design and evolution of constexpr in C++](https://pvs-studio.com/en/blog/posts/cpp/0909/), which provides a comprehensive history of the development of `constexpr` in C++. It's very well-written. So, I decided to translate it for the Chinese-speaking community.

But interestingly, this article is also a translation. The original author is Russian, and the article was first published on a Russian forum. Here is the author's email: `izaronplatz@gmail.com`. I have already contacted him, and he replied:

> It's always good to spread knowledge in more languages.

This means translation is permitted. However, I don't understand Russian, so I mainly followed the structure of the original article, but the main body is mostly my own re-narration.

The original content is quite long, so it is divided into two parts. This is the first part.

## Is it magical?

`constexpr` is one of the most magical keywords in modern C++. It allows certain code to be executed at compile time.

Over time, the capabilities of `constexpr` have become increasingly powerful. Now, almost all features of the standard library can be used in compile-time computations.

The history of `constexpr` can be traced back to the early versions of C++. By studying standard proposals and compiler source code, we can understand how this language feature was built step by step, why it exists in its current form, how `constexpr` expressions are actually computed, what future features might be possible, and which features could have existed but were not included in the standard.

This article is suitable for everyone, whether you are familiar with `constexpr` or not!

## C++98/03: I'm more const than you

In C++, some places require integer constants (like the length of a built-in array type), and these values must be determined at compile time. The C++ standard allows constants to be constructed through simple expressions, for example:

```cpp
enum EPlants{
    APRICOT = 1 << 0,
    LIME = 1 << 1,
    PAPAYA = 1 << 2,
    TOMATO = 1 << 3,
    PEPPER = 1 << 4,
    FRUIT = APRICOT | LIME | PAPAYA,
    VEGETABLE = TOMATO | PEPPER,
};

template <int V>
int foo(int v = 0){
    switch(v){
        case 1 + 4 + 7:
        case 1 << (5 | sizeof(int)):
        case (12 & 15) + PEPPER: return v;
    }
}

int f1 = foo<1 + 2 + 3>();
int f2 = foo<((1 < 2) ? 10 * 11 : VEGETABLE)>();
```

These expressions are defined in the `[expr.const]` section and are called _constant expressions_. They can only contain:

- Literals: `1`, `'A'`, `true`, `...`
- Enum values
- Template parameters of integer or enum type (e.g., `v` in `template<int v>`)
- `sizeof` expressions
- `const` variables initialized by a constant expression

The first few items are easy to understand, but the last one is a bit more complex. If a variable has [static storage duration](https://en.cppreference.com/w/cpp/language/storage_duration), its memory is normally filled with `0` and then changed when the program starts executing. But for the variables mentioned above, this is too late; their values need to be computed before compilation ends.

In C++98/03, there were two types of [static initialization](https://en.cppreference.com/w/cpp/language/initialization#Static_initialization):

- [Zero initialization](https://en.cppreference.com/w/cpp/language/zero_initialization): memory is filled with `0` and then changed during program execution.
- [Constant initialization](https://en.cppreference.com/w/cpp/language/constant_initialization): initialized with a constant expression, and the memory (if needed) is immediately filled with the computed value.

> All other initializations are called [dynamic initialization](https://en.cppreference.com/w/cpp/language/initialization#Dynamic_initialization), which we will not consider here.

Let's look at an example that includes both types of static initialization:

```cpp
int foo() { return 13; }

const int v1 = 1 + 2 + 3 + 4;              // const initialization
const int v2 = 15 * v1 + 8;                // const initialization
const int v3 = foo() + 5;                  // zero initialization
const int v4 = (1 < 2) ? 10 * v3 : 12345;  // zero initialization
const int v5 = (1 > 2) ? 10 * v3 : 12345;  // const initialization
```

The variables `v1`, `v2`, and `v5` can be used as constant expressions, serving as template arguments, `switch` `case` labels, `enum` values, etc. `v3` and `v4` cannot. Even though we can clearly see that the value of `foo() + 5` is `18`, there was no suitable semantics to express this at the time.

Since constant expressions are defined recursively, if any part of an expression is not a constant expression, the entire expression is not a constant expression. In this evaluation process, only the actually computed expressions are considered, which is why `v5` is a constant expression, but `v4` is not.

If the address of a constantly initialized variable is not taken, the compiler may not allocate memory for it. So we can force the compiler to reserve memory for a constantly initialized variable by taking its address (in fact, even ordinary local variables might be optimized away if their address is not explicitly taken; any optimization that does not violate the [as-if](https://en.cppreference.com/w/cpp/language/as_if) rule is allowed. You can consider using the `[[gnu::used]]` attribute to prevent a variable from being optimized away).

```cpp
int main() {
    std::cout << v1 << &v1 << std::endl;
    std::cout << v2 << &v2 << std::endl;
    std::cout << v3 << &v3 << std::endl;
    std::cout << v4 << &v4 << std::endl;
    std::cout << v5 << &v5 << std::endl;
}
```

Compile the above code and check the symbol table (environment is Windows x86-64):

```bash
$ g++ --std=c++98  -c main.cpp
$ objdump -t -C main.o

(sec  6)(fl 0x00)(ty    0)(scl   3) (nx 0) 0x0000000000000000 v1
(sec  6)(fl 0x00)(ty    0)(scl   3) (nx 0) 0x0000000000000004 v2
(sec  3)(fl 0x00)(ty    0)(scl   3) (nx 0) 0x0000000000000000 v3
(sec  3)(fl 0x00)(ty    0)(scl   3) (nx 0) 0x0000000000000004 v4
(sec  6)(fl 0x00)(ty    0)(scl   3) (nx 0) 0x0000000000000008 v5

----------------------------------------------------------------

(sec  3)(fl 0x00)(ty    0)(scl   3) (nx 1) 0x0000000000000000 .bss
(sec  4)(fl 0x00)(ty    0)(scl   3) (nx 1) 0x0000000000000000 .xdata
(sec  5)(fl 0x00)(ty    0)(scl   3) (nx 1) 0x0000000000000000 .pdata
(sec  6)(fl 0x00)(ty    0)(scl   3) (nx 1) 0x0000000000000000 .rdata
```

You can see that on my GCC 14, the zero-initialized variables `v3` and `v4` are placed in the `.bss` section, while the constant-initialized variables `v1`, `v2`, and `v5` are placed in the `.rdata` section. The operating system protects the `.rdata` section, making it read-only; attempting to write to it will cause a segmentation fault.

From the differences above, it's clear that some `const` variables are more `const` than others. But at the time, we had no way to detect this difference (later, C++20 introduced [constinit](https://en.cppreference.com/w/cpp/language/constinit) to ensure a variable undergoes constant initialization).

## 0-∞: The Constant Evaluator in the Compiler

To understand how constant expressions are evaluated, we need a brief overview of compiler construction. The process is roughly the same across different compilers; we will use Clang/LLVM as an example.

In general, a compiler can be seen as consisting of three parts:

- **Front-end**: Converts source code like C/C++/Rust into LLVM IR (a special intermediate representation). Clang is the compiler front-end for the C language family.
- **Middle-end**: Optimizes the LLVM IR based on relevant settings.
- **Back-end**: Converts the LLVM IR into machine code for a specific platform: x86/Arm/PowerPC, etc.

For a simple programming language, you can implement a compiler in `1000` lines by calling LLVM. You only need to be responsible for implementing the language front-end; the back-end is handled by LLVM. You can even consider using existing parser generators like lex/yacc for the front-end.

Specifically, the work of a compiler front-end, like Clang here, can be divided into three stages:

- **Lexical analysis**: Converts the source file into a Token Stream. For example, `[]() { return 13 + 37; }` is converted to `[`, `]`, `(`, `)`, `{`, `return`, `13`, `+`, `37`, `;`, `}`.
- **Syntax analysis**: Produces an Abstract Syntax Tree (AST), which converts the Token Stream from the previous step into a recursive tree-like structure like the one below.

```bash
lambda-expr
└── body
    └── return-expr
        └── plus-expr
            ├── number 13
            └── number 37
```

- **Code generation**: Generates LLVM IR from the given AST.

Therefore, the computation of constant expressions (and related matters, like template instantiation) happens strictly in the front-end of the C++ compiler, and LLVM is not involved in such work. The tool that handles this processing of constant expressions (from the simple expressions of C++98 to the complex ones of C++23) is called a **constant evaluator**.

Over the years, the restrictions on constant expressions have been continuously relaxed, and Clang's constant evaluator has correspondingly become more and more complex, to the point of managing a memory model. There is an old [document](https://clang.llvm.org/docs/InternalsManual.html#constant-folding-in-the-clang-ast) that describes constant evaluation in C++98/03. Since constant expressions were very simple back then, they were handled by analyzing the syntax tree for _constant folding_. Because all arithmetic expressions in the syntax tree have already been parsed into the form of subtrees, computing constants was simply a matter of traversing the subtrees.

The source code for the constant evaluator is located in [lib/AST/ExprConstant.cpp](https://clang.llvm.org/doxygen/ExprConstant_8cpp_source.html), which has grown to nearly 17,000 lines at the time of this writing. Over time, it has learned to interpret many things, such as loops (`EvaluateLoopBody`), all of which are done on the syntax tree.

Constant expressions have an important difference from runtime code: they must not cause undefined behavior. If the constant evaluator encounters undefined behavior, the compilation will fail.

```cpp
error: constexpr variable 'foo' must be initialized by a constant expression
    2 | constexpr int foo = 13 + 2147483647;
      |               ^     ~~~~~~~~~~~~~~~
note: value 2147483660 is outside the range of representable values of type 'int'
    2 | constexpr int foo = 13 + 2147483647;
```

Therefore, they can sometimes be used to detect potential errors in a program.

## 2003: Can we really be macro-free?

**Changes to the standard are made through proposals.**

> Where can proposals be found? What are they composed of?<br><br>All proposals related to the C++ standard can be found on [open-std.org](https://open-std.org/JTC1/SC22/WG21/). Most of them have detailed descriptions and are easy to read. They usually consist of the following parts: <br><br>- The problem currently being faced <br>- Links to relevant wording in the standard <br>- A solution to the aforementioned problem <br>- Suggested changes to the standard's wording <br>- Links to related proposals (a proposal may have multiple versions or need to be compared with other proposals) <br>- In advanced proposals, links to experimental implementations are often included<br><br>You can use these proposals to understand how each part of C++ has evolved. Not all proposals in the archive are ultimately accepted, but they all have a significant impact on the development of C++.<br><br>Anyone can participate in the evolution of C++ by submitting new proposals.

The `2003` proposal [N1521 Generalized Constant Expressions](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2003/n1521.pdf) pointed out a problem. If a part of an expression contains a function call, the entire expression cannot be a constant expression, even if the function could ultimately be constant-folded. This forced people to use macros when dealing with complex constant expressions, and to some extent, led to the abuse of macros.

```cpp
inline int square(int x) { return x * x; }
#define SQUARE(x) ((x) * (x))

square(9)
std::numeric_limits<int>::max()
// Theoretically usable in constant expressions, but actually not

SQUARE(9)
INT_MAX
// Forced to use macros instead
```

Therefore, it was proposed to introduce the concept of **constant-valued** functions, allowing these functions to be used in constant expressions. For a function to be a constant-valued function, it must satisfy:

- `inline`, non-recursive, and its return type is not `void`
- Consists only of a single `return expr` statement, and after replacing the function parameters in `expr` with constant expressions, the result is still a constant expression.

If such a function is called with constant expression arguments, the function call expression is also a constant expression.

```cpp
int square(int x) { return x * x; }         // constant-valued
long long_max(int x) { return 2147483647; } // constant-valued
int abs(int x) { return x < 0 ? -x : x; }   // constant-valued
int next(int x) { return ++x; }             // non constant-valued
```

With this, without modifying any code, `v3` and `v4` from the initial example could also be used as constant expressions, because `foo` would be considered a constant-valued function.

The proposal suggested that further support for the following situation could be considered:

```cpp
struct cayley{
    const int value;
    cayley(int a, int b) : value(square(a) + square(b)) {}
    operator int() const { return value; }
};

std::bitset<cayley(98, -23)> s; // same as bitset<10133>
```

Because the member `value` is `totally constant`, initialized in the constructor by two calls to constant-valued functions. In other words, according to the general logic of the proposal, this code could be roughly transformed into the following form (moving variables and functions outside the struct):

```cpp
// Simulate the constructor call and operator int() of cayley::cayley(98, -23)
const int cayley_98_m23_value = square(98) + square(-23);

int cayley_98_m23_operator_int() { return cayley_98_m23_value; }

// Create bitset
std::bitset<cayley_98_m23_operator_int()> s; // same as bitset<10133>
```

But just like with variables, programmers cannot be certain whether a function is a constant-valued function; only the compiler knows.

> Proposals usually do not delve into the details of how compilers should implement them. The above proposal stated that implementing it should not present any difficulties, only requiring a slight change to the constant folding that exists in most compilers. However, proposals are closely related to compiler implementation. If a proposal cannot be implemented in a reasonable amount of time, it is unlikely to be adopted. From a later perspective, many large proposals were eventually broken down into several smaller proposals and implemented gradually.

## 2006-2007: When Everything Comes to the Surface

Fortunately, three years later, a subsequent revision of this proposal, [N2235](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2007/n2235.pdf), recognized that too many implicit features are bad, and programmers should have a way to ensure that a variable can be used as a constant, with a compilation error resulting if the corresponding conditions are not met.

```cpp
struct S{
    static const int size;
};

const int limit = 2 * S::size;                 // dynamic initialization
const int S::size = 256;                       // const initialization
const int z = std::numeric_limits<int>::max(); // dynamic initialization
```

According to the programmer's intention, `limit` should be constantly initialized, but this is not the case because `S::size` is defined after `limit`, which is too late. This can be verified with [constinit](https://en.cppreference.com/w/cpp/language/constinit), which was added in C++20. `constinit` guarantees that a variable undergoes constant initialization, and if it cannot, a compilation error will occur.

In the new proposal, constant-valued functions were **renamed** to _constexpr functions_, and the requirements for them remained the same. But now, to be able to use them in constant expressions, they **must** be declared with the `constexpr` keyword. Furthermore, if the function body does not meet the relevant requirements, compilation will fail. It was also suggested that some standard library functions (like those in `std::numeric_limits`) be marked as `constexpr`, as they meet the relevant requirements. **Variables** or class members can also be declared as `constexpr`, in which case, if the variable is not initialized with a constant expression, compilation will fail.

`constexpr` constructors for user-defined `class`es were also legalized. Such a constructor must have an empty function body and initialize members with constant expressions. Implicitly generated constructors will be marked as `constexpr` whenever possible. For `constexpr` objects, the destructor must be trivial, because non-trivial destructors usually make changes in the context of a running program, and no such context exists in `constexpr` computation.

Here is an example class containing `constexpr`:

```cpp
struct complex {
    constexpr complex(double r, double i) : re(r), im(i) { }

    constexpr double real() { return re; }
    constexpr double imag() { return im; }

private:
    double re;
    double im;
};

constexpr complex I(0, 1); // OK
```

In the proposal, objects like `I` were called user-defined literals. "Literals" are fundamental entities in C++. Just as "simple" literals (numbers, characters, etc.) are immediately embedded into assembly instructions, and string literals are stored in sections like `.rodata`, user-defined literals also have their place there.

Now `constexpr` variables can be not only numbers and enums, but also of a [literal type](https://en.cppreference.com/w/cpp/named_req/LiteralType), which was introduced in this proposal (reference types were not yet supported). A literal type is a type that can be passed to a `constexpr` function, and these types are simple enough for the compiler to support them in constant computation.

The `constexpr` keyword eventually became a _specifier_, similar to _override_, used only as a marker. After discussion, it was decided not to create a new [storage duration type](https://en.cppreference.com/w/cpp/language/storage_duration) or a new type qualifier, and it was also decided not to allow its use on function parameters, to avoid making the function [overload resolution](https://en.cppreference.com/w/cpp/language/overload_resolution) rules overly complex.

## 2007: Trying to make the standard library more constexpr?

In this year, proposal [N2349 Constant Expressions in the Standard Library](https://open-std.org/JTC1/SC22/WG21/docs/papers/2007/n2349.pdf) was put forward, which marked some functions and constants as `constexpr`, as well as some container functions, for example:

```cpp
template<size_t N>
class bitset{
    // ...
    constexpr bitset();
    constexpr bitset(unsigned long);
    // ...
    constexpr size_t size();
    // ...
    constexpr bool operator[](size_t) const;
};
```

The constructors initialize the class members via constant-expressions, and the other functions contain a single `return` statement, conforming to the current rules.

Of all the proposals about `constexpr`, more than half suggest marking certain functions in the standard library as `constexpr`. In terms of content, they are not very interesting because they do not lead to changes in the core language rules.

## 2008: Halting... problem? I don't care!

```cpp
constexpr unsigned int factorial(unsigned int n){
    return n == 0 ? 1 : n * factorial(n - 1);
}
```

Initially, the proposal authors wanted to allow recursive calls in `constexpr` functions, but this was forbidden out of caution. However, during the review process, due to a change in wording, this practice was accidentally allowed. The CWG believed that recursion has enough use cases that it should be allowed. If mutual recursion between functions is allowed, then _forward declarations_ of `constexpr` functions must also be allowed. When an undefined `constexpr` function is called in a context that requires constant evaluation, a diagnostic should be issued. This was clarified in [N2826](https://open-std.org/JTC1/SC22/WG21/docs/papers/2009/n2826.html).

Since there is recursion, infinite recursion is possible. Will a function actually recurse infinitely? In some simple cases, static analysis tools can determine if infinite recursion will occur. But in the general case, this is actually the [halting problem](https://en.wikipedia.org/wiki/Halting_problem), which is unsolvable.

Generally, compilers set a default recursion depth. If the recursion depth exceeds this default, compilation will fail.

```cpp
constexpr int foo(){ return f() + 1; }
constexpr int x = foo();
```

The above code results in a compilation error:

```bash
error: 'constexpr' evaluation depth exceeds maximum of 512
    (use '-fconstexpr-depth=' to increase the maximum)
   24 |     constexpr int x = foo();
```

In Clang, the default depth is 512, which can be changed with `-fconstexpr-depth`. In fact, template instantiation has a similar depth limit. In effect, this limit can be seen as analogous to the stack size for runtime function calls; exceeding this size results in a "stack overflow," which is quite reasonable.

## 2010: References or Pointers?

At the time, many functions could not be marked as `constexpr` because their parameters contained references.

```cpp
template <class T>
constexpr const T& max(const T& a, const T& b); // error

constexpr pair();               // ok
pair(const T1& x, const T2& y); // error
```

Proposal [N3039 Constexpr functions with const reference parameters](https://open-std.org/JTC1/SC22/WG21/docs/papers/2010/n3039.pdf) aimed to allow constant references as function parameters and return values.

In fact, this was a huge change. Before this, constant evaluation only involved **values**, not references (or pointers). It was enough to simply operate on values. The introduction of references forced the constant evaluator to build a memory model. To support `const T&`, the compiler needs to create a temporary object at compile time and then bind the reference to it. Any illegal access to this object should result in a compilation error.

```cpp
template <typename T>
constexpr T self(const T& a) { return *(&a); }

template <typename T>
constexpr const T* self_ptr(const T& a) { return &a; }

template <typename T>
constexpr const T& self_ref(const T& a) { return *(&a); }

template <typename T>
constexpr const T& near_ref(const T& a) { return *(&a + 1); }

constexpr auto test1 = self(123); // OK
constexpr auto test2 = self_ptr(123); // Fails, a pointer to a temporary object is not a constant expression

constexpr auto test3 = self_ref(123); // OK
constexpr auto tets4 = near_ref(123); // Fails, out-of-bounds pointer access
```

## 2011: Why no declarations?

As mentioned earlier, a `constexpr` function could only consist of a single `return` statement. This meant that even declarations that did not affect the evaluation were not allowed. But at least three types of declarations would be helpful for writing such functions: static assertions, type aliases, and local variables initialized by constant expressions.

```cpp
constexpr int f(int x){
    constexpr int magic = 42;
    return x + magic; // should be ok
}
```

Proposal [N3268 static_assert and list-initialization in constexpr functions](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2011/n3268.htm) aimed to support these static declarations in `constexpr` functions.

## 2012: I need branches!

There are many simple functions that one would want to compute at compile time, such as calculating `a` to the power of `n`:

```cpp
int pow(int a, int n){
    if (n < 0)
        throw std::range_error("negative exponent for integer power");

    if (n == 0)
        return 1;

    int sqrt = pow(a, n / 2);
    int result = sqrt * sqrt;

    if (n % 2)
        return result * a;

    return result;
}
```

However, at that time (C++11), to make it `constexpr`, programmers had to write a completely new version in a pure functional style (no local variables or loops):

```cpp
constexpr int pow_helper(int a, int n, int sqrt) {
    return sqrt * sqrt * ((n % 2) ? a : 1);
}

constexpr int pow(int a, int n){
    return (n < 0)
               ? throw std::range_error("negative exponent for integer power")
               : (n == 0)
                     ? 1
                     : pow_helper(a, n, pow(a, n / 2));
}
```

Proposal [N3444 Relaxing syntactic constraints on constexpr functions](https://open-std.org/JTC1/SC22/WG21/docs/papers/2012/n3444.html) aimed to further relax the constraints on `constexpr` functions to allow writing more arbitrary code.

- Allow declaration of local variables of [literal type](https://en.cppreference.com/w/cpp/named_req/LiteralType). If they are initialized via a constructor, that constructor must also be marked as `constexpr`. This allows the constant evaluator to cache these variables, avoiding re-evaluation of the same expressions and improving the efficiency of the constant evaluator. However, modifying these variables is not allowed.
- Allow local type declarations.
- Allow the use of `if` and multiple `return` statements, requiring each branch to have at least one `return` statement.
- Allow expression statements (statements consisting only of an expression).
- Allow the address or reference of a static variable as a constant expression.

```cpp
constexpr mutex& get_mutex(bool which){
    static mutex m1, m2;
    if (which)
        return m1;
    else
        return m2;
}

constexpr mutex& m = get_mutex(true); // OK
```

However, `for/while` loops, `goto`, `switch`, and `try` were not allowed, as these could create complex control flow and even infinite loops.

## 2013: Only kids make choices, I want loops too!

However, the CWG believed that supporting loops (at least `for`) in `constexpr` functions was essential. In `2013`, a revised version of the proposal, [Relaxing constraints on constexpr functions](https://open-std.org/JTC1/SC22/WG21/docs/papers/2013/n3597.html), was published.

Four options were considered for implementing `constexpr for`.

- Add a completely new loop syntax that interacts well with the functional programming style required by `constexpr`. While this solves the lack of loops, it does not eliminate programmers' dissatisfaction with the existing language (having to rewrite existing code to support `constexpr`).
- Only support traditional C-style `for` loops. For this, at least, changes to variables within `constexpr` functions would need to be supported.
- Only support the [range-based for loop](https://en.cppreference.com/w/cpp/language/range-for). Such loops cannot be used with user-defined iterator types unless language rules are further relaxed.
- Allow a consistent and broad subset of C++ to be used in `constexpr` functions, potentially including all of C++.

The last option was chosen, which greatly influenced the subsequent development of `constexpr` in C++.

To support this option, we had to introduce mutability for variables in `constexpr` functions, i.e., support modifying the value of variables. According to the proposal, objects created during constant evaluation can now be changed until the end of the evaluation process or the object's [lifetime](https://en.cppreference.com/w/cpp/language/lifetime). These evaluation processes will take place in a sandbox-like virtual machine and will not affect external code. Therefore, in theory, the same `constexpr` arguments will produce the same result.

```cpp
constexpr int f(int a){
    int n = a;
    ++n; // ++n is not a constant expression
    return n * a;
}

int k = f(4);
// OK, this is a constant expression
// n in f can be modified because its lifetime
// begins during the evaluation of the expression

constexpr int k2 = ++k;
// Error, not a constant expression, cannot modify k
// because its lifetime did not begin within this expression

struct X{
    constexpr X() : n(5){
        n *= 2; // not a constant expression
    }
    int n;
};

constexpr int g(){
    X x; // initialization of x is a constant expression
    return x.n;
}

constexpr int k3 = g();
//  OK, this is a constant expression
//  x.n can be modified because
//  the lifetime of x begins during the evaluation of g()
```

Additionally, I want to point out that code like this can now also compile:

```cpp
constexpr void add(X& x) { x.n++; }

constexpr int g(){
    X x;
    add(x);
    return x.n;
}
```

Local side effects are also allowed in constant evaluation!

## 2013: constexpr is not a subset of const!

Currently, `constexpr` functions of a class are automatically marked as `const`.

The proposal [constexpr member functions and implicit const](https://open-std.org/JTC1/SC22/WG21/docs/papers/2013/n3598.html) points out that if a member function is `constexpr`, it does not necessarily have to be `const`. As mutability in `constexpr` computations becomes more important, this point becomes more prominent. But even before this, it hindered the use of the same function in both `constexpr` and non-`constexpr` code:

```cpp
struct B{
    A a;
    constexpr B() : a() {}
    constexpr const A& getA() const /*implicit*/ { return a; }
    A& getA() { return a; } // code duplication
};
```

Interestingly, the proposal provided three options, and the second one was chosen:

- Maintain the status quo -> leads to code duplication.
- A function marked `constexpr` is not implicitly `const` -> breaks ABI, as the `const` signature of a member function is part of the function's type.
- Use `mutable` for marking: `constexpr A &getA() mutable { return a; };` -> even more inconsistent.

Ultimately, option `2` was accepted. Now, if a member function is marked `constexpr`, it does not mean it is an implicitly `const` member function.

---

The next part is here: [The History of constexpr in C++ (Part 2)](https://www.ykiko.me/en/articles/683463723).
