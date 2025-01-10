---
title: 'Seeing Through the Fog: A True Understanding of C++ Templates'
date: 2023-09-12 23:46:11
updated: 2024-11-01 00:23:44
---

In C++, the concept of templates has existed for over two decades. As one of the most important language constructs in C++, discussions about templates are countless. Unfortunately, deep and valuable discussions are rare, especially those that view this feature from multiple perspectives. Many articles often intertwine templates with various syntactic details, making it easy to leave readers feeling lost in a fog. Similar examples occur in other topics, such as introducing coroutines while mixing them with various I/O discussions, or discussing reflection as if it were limited to Java or C#. While this approach is not without reason, it often makes it difficult to grasp the essence. After reading a lot of content, one may still fail to grasp the key points and instead end up confusing different concepts.

Personally, I prefer to discuss a problem from multiple levels and angles, rather than limiting myself to a specific aspect. This way, one can better understand the problem itself and avoid having too narrow a perspective. Therefore, this article will attempt to observe templates from four angles, starting from their inception, to clarify the development trajectory of this feature in C++. Note that this article is not a tutorial and will not delve into syntactic details. Instead, it will focus more on design philosophy and trade-offs. A basic understanding of templates is sufficient to follow along, so feel free to read on. Of course, this approach may lack some rigor, and any errors are welcome to be discussed in the comments.

**We will mainly discuss four themes:**

- Code Generation
- Type Constraints
- Compile-time Computing
- Type Manipulation

The first theme is generally considered to be the standard use of templates. The latter three are usually categorized under TMP, or Template Meta Programming. The original intent of templates was not to achieve these three functions, but they were eventually realized through some clever tricks, making the code more obscure and difficult to understand, hence the term "meta programming."

## Code Generation

### Generic

**Generic programming** involves writing the same code for different types to achieve code reuse. Before templates were introduced, we could only simulate generics using macros. Consider the following simple example:

```cpp
#define add(T) _ADD_IMPL_##T

#define ADD_IMPL(T)        \
    T add(T)(T a, T b) {   \
        return a + b;      \
    }

ADD_IMPL(int);
ADD_IMPL(float);

int main() {
    add(int)(1, 2);
    add(float)(1.0f, 2.0f);
}
```

The principle is simple: replace the type in a regular function with a macro parameter, and generate different names for different type parameters through macro concatenation. The `IMPL` macro is then used to generate definitions for specific functions, a process known as **instantiation**.

Of course, this is just a simple example, and it might seem fine. But imagine implementing a `vector` using macros—it would be quite daunting. Specifically, using macros for generics has several drawbacks:

- Poor code readability, as macro concatenation is coupled with code logic, making error messages hard to read.
- Difficult to debug, as breakpoints can only be set at the macro expansion point, not inside the macro definition.
- Requires explicit type parameters, which can become verbose with many parameters.
- Manual instantiation of function definitions is necessary, which can be cumbersome in larger codebases where a generic might have dozens of instantiations.

These issues are all resolved with templates:

```cpp
template <typename T>
T add(T a, T b) {
    return a + b;
}

template int add<>(int, int);  // explicit instantiation

int main() {
    add(1, 2);         // auto deduce T
    add(1.0f, 2.0f);   // implicit instantiation
    add<float>(1, 2);  // explicitly specify T
}
```

- Templates act as placeholders, eliminating the need for character concatenation, making the code look just like regular code, with only an additional template parameter declaration.
- Errors and debugging point accurately to the template definition location, not the instantiation point.
- Supports automatic template parameter deduction, eliminating the need for explicit type parameters, while also allowing explicit specification.
- Supports **implicit instantiation**, where the compiler automatically instantiates used functions, as well as **explicit instantiation**, where instantiations are done manually.

Additionally, features like **partial specialization**, **full specialization**, **variadic templates**, and **variable templates** are all impossible with macros. It is the advent of templates that made the implementation of generic libraries like STL possible.

### Table Generation

The generics discussed above can be seen as the most direct use of templates. Based on these, we can achieve more advanced code generation, such as generating a fixed table at compile time for runtime queries. The standard library's `std::visit` implementation uses this technique. Here's a simple simulation:

```cpp
template <typename T, typename Variant, typename Callback>
void wrapper(Variant& variant, Callback& callback) {
    callback(std::get<T>(variant));
}

template <typename... Ts, typename Callback>
void visit(std::variant<Ts...>& variant, Callback&& callback) {
    using Variant = std::variant<Ts...>;
    constexpr static std::array table = {&wrapper<Ts, Variant, Callback>...};
    table[variant.index()](variant, callback);
}

int main() {
    auto callback = [](auto& value) { std::cout << value << std::endl; };
    std::variant<int, float, std::string> variant = 42;
    visit(variant, callback);
    variant = 3.14f;
    visit(variant, callback);
    variant = "Hello, World!";
    visit(variant, callback);
    return 0;
}
```

Although the type of elements stored in the `variant` is determined at runtime, the set of possible types it can hold is known at compile time. Therefore, we instantiate a corresponding `wrapper` function for each possible type in the set using `callback` and store them in an array. At runtime, we simply use the `variant`'s `index` to access the corresponding member in the array to complete the call.

Of course, with C++17's **folding expressions**, we can do better:

```cpp
template <typename... Ts, typename Callback>
void visit(std::variant<Ts...>& variant, Callback&& callback) {
    auto foreach = []<typename T>(std::variant<Ts...>& variant, Callback& callback) {
        if(auto value = std::get_if<T>(&variant)) {
            callback(*value);
            return true;
        }
        return false;
    };
    (foreach.template operator()<Ts>(variant, callback) || ...);
}
```

By leveraging the short-circuiting behavior of logical operators, we can exit the evaluation of subsequent folding expressions early, and shorter functions are more conducive to inlining.

## Type Constraints

I agree with most points, but template error messages are definitely not easy to read. Compared to macros, isn't it a case of the pot calling the kettle black? Or even worse. Producing hundreds or thousands of lines of error messages is something only C++ templates can do.

This leads to the next question: why are C++ compilation error messages so long? And why are they sometimes so difficult to understand?

### Function Overloading

Consider this simple example with just a few lines:

```cpp
struct A {};

int main() {
    std::cout << A{} << std::endl;
    return 0;
}
```

On my GCC compiler, this produces a whopping 239 lines of error messages. The good news is that GCC highlights the key part, as shown below:

```cpp
no match for 'operator<<' (operand types are 'std::ostream' {aka 'std::basic_ostream<char>'} and 'A')
    9 |     std::cout << A{} << std::endl;
      |     ~~~~~~~~~ ^~ ~~~
      |          |       |
      |          |       A
      |          std::ostream {aka std::basic_ostream<char>}
```

So it's still somewhat understandable: it means no matching overloaded function was found, indicating that we need to overload `operator<<` for `A`. But what are the remaining 200 lines of errors doing? The key lies in **overload resolution**. Let's look at one of the messages:

```cpp
note:   template argument deduction/substitution failed:
note:   cannot convert 'A()' (type 'A') to type 'const char*'
    9 |     std::cout << A{} << std::endl;
```

This means the compiler tried to match the `A` type with the `const char*` overload (via implicit type conversion) and failed. The standard library has many such functions with numerous overloads. For example, `operator<<` is overloaded for `int`, `bool`, `long`, `double`, and many others—nearly dozens of functions. The error messages list all the reasons why each overload attempt failed, easily resulting in hundreds of lines. Combined with the cryptic naming in the standard library, it can look like gibberish.

### Instantiation Stack

Function overloading is part of the reason why error messages are hard to read, but not the whole story. As shown above, merely enumerating all possibilities results in a few hundred lines of errors. But we can produce thousands of lines—an order of magnitude difference that can't be easily explained by quantity alone. Moreover, this section is about type constraints, so what does it have to do with compiler errors? Consider this example:

```cpp
struct A {};

struct B {};

template <typename T>
void test(T a, T b) {
    std::cout << a << b << std::endl;
}

int main() {
    test(A{}, B{});  // #1: a few lines
    test(A{}, A{});  // #2: hundred lines
}
```

In this example, `#1` produces only a few lines of error messages, while `#2` produces hundreds. Why such a big difference? Recall the two advantages of templates over macros mentioned in the first part: automatic type deduction and implicit instantiation. Only when template parameter deduction succeeds does template instantiation occur, and only then are errors in the function body checked.

In `test(A{}, B{})`, template parameter deduction fails because the `test` function implies an important condition: the types of `a` and `b` must be the same. Thus, the error is that no matching function is found. In `test(A{}, A{})`, template parameter deduction succeeds, and instantiation proceeds, but an error occurs during instantiation. That is, `T` is deduced as `A`, and when substituting `A` into the function body, an error occurs. The compiler then lists all the reasons why the substitution failed.

This leads to a problem: when there are many layers of template nesting, the error might occur in the innermost template function, forcing the compiler to print the entire template instantiation stack.

So what's the use of type constraints? Consider this example:

```cpp
struct A {};

template <typename T>
void print1(T x) {
    std::cout << x << std::endl;
}

template <typename T>
// requires requires (T x) { std::cout << x; }
void print2(T x) {
    print1(x);
    std::cout << x << std::endl;
}

int main() {
    print2(A{});
    return 0;
}
```

This short code produces 700 lines of compilation errors on my GCC. Now, uncomment the commented line. In contrast, the error messages are much shorter:

```cpp
In substitution of 'template<class T>  requires requires(T x) {std::cout << x;} void print2(T) [with T = A]':
required from here
required by the constraints of 'template<class T>  requires requires(T x) {std::cout << x;} void print2(T)'
in requirements with 'T x' [with T = A]
note: the required expression '(std::cout << x)' is invalid
   15 | requires requires (T x) { std::cout << x; }
```

This means that an instance `x` of type `A` does not satisfy the `requires` clause `std::cout << x`. In fact, with this syntax, we can restrict errors to the type deduction phase, avoiding instantiation. Thus, the error messages become much more concise.

In other words, `requires` can prevent the propagation of compilation errors. Unfortunately, constraint-related syntax was only added in C++20. What about before that?

### Before C++20

Before C++20, we didn't have such convenient methods. We had to use a technique called [SFINAE](https://en.cppreference.com/w/cpp/language/sfinae) to achieve similar functionality for type constraints. For example, the above functionality could only be written like this before C++20:

```cpp
template <typename T, typename = decltype(std::cout << std::declval<T>())>
void print2(T x) {
    print1(x);
    std::cout << x << std::endl;
}
```

The specific rules won't be discussed here, but interested readers can search for related articles.

The result is that the line:

```cpp
typename = decltype(std::cout << std::declval<T>())
```

is completely unintuitive and hard to understand. Only by deeply understanding C++ template rules can one grasp what this is doing. For why `requires` wasn't added until C++20, you can read the [autobiography](https://github.com/Cpp-Club/Cxx_HOPL4_zh/blob/main/06.md) written by the father of C++ himself.

## Compile-time Computing

### Meaning

First, it's important to acknowledge that compile-time computing is definitely useful. The extent of its significance in specific scenarios cannot be generalized. Many people panic at the mention of compile-time computing, citing reasons like difficult-to-understand code, niche skills, or lack of value. This can easily mislead beginners. In fact, there is a real demand for such functionality. If a programming language lacks this feature but there is a need, programmers will find other ways to achieve it.

I will give two examples to illustrate:

- First, compiler optimizations for constant expressions are well-known. In extremely simple cases, like the expression `1+1+x`, the compiler will optimize it to `2+x`. In fact, modern compilers can perform many optimizations for similar cases, as seen in this [question](https://www.zhihu.com/question/619246858/answer/3184453259). The asker wondered if the C function `strlen` would optimize the function call directly to a constant when the parameter is a constant string. For example, would `strlen("hello")` be directly optimized to `5`? Based on experiments with mainstream compilers, the answer is yes. Similar cases are countless, and you are unknowingly using compile-time computing. It's just that it's categorized under compiler optimizations. However, the compiler's optimization capabilities are ultimately limited, and allowing users to define such optimization rules would be more flexible and free. For example, in C++, `strlen` is explicitly marked as `constexpr`, ensuring this optimization.
- Second, in the early days of programming language development, when compiler optimizations were not as advanced, external scripting languages were widely used to precompute data (or even generate code) to reduce runtime overhead. A typical example is precomputing trigonometric function tables, which are then used directly at runtime. For example, before compiling code, a script is run to generate some necessary code.

C++'s compile-time computing has clear semantic guarantees and is embedded within the language, allowing for good interaction with other parts. From this perspective, it effectively addresses the two issues mentioned above. Of course, many criticisms of it are not without merit. Compile-time computing via template meta-programming results in ugly and obscure code, involves many syntactic details, and significantly slows down compilation while increasing binary size. Undeniably, these issues exist. However, as C++ versions continue to evolve, compile-time computing has become much easier to understand, no longer requiring complex template meta-code, and even beginners can quickly learn it. This is because it now closely resembles runtime code. Next, we will clarify this through its historical development.

### History

Historically, TMP was an accidental discovery. During the standardization of C++, it was found that the template system was Turing complete, meaning it could, in principle, compute anything computable. The first concrete demonstration was a program written by Erwin Unruh that computed prime numbers, although it didn't actually compile: the list of primes was part of the error messages generated by the compiler while trying to compile the code. For a specific example, refer [here](https://en.wikibooks.org/wiki/C%2B%2B_Programming/Templates/Template_Meta-Programming#History_of_TMP).

As an introductory programming example, here's a method to compute factorials at compile time:

```cpp
template <int N>
struct factorial {
    enum { value = N * factorial<N - 1>::value };
};

template <>
struct factorial<0> {
    enum { value = 1 };
};

constexpr auto value = factorial<5>::value;  // => 120
```

This code can compile even before C++11. After C++11, many new features were introduced to simplify compile-time computing. The most important is the `constexpr` keyword. Before C++11, there was no suitable way to represent compile-time constants, so `enum` was used. After C++11, we can write:

```cpp
template <int N>
struct factorial {
    constexpr static int value = N * factorial<N - 1>::value;
};

template <>
struct factorial<0> {
    constexpr static int value = 1;
};
```

Although this simplifies things, we are still using templates for compile-time computing. This makes the code hard to read, mainly for two reasons:

- Template parameters can only be compile-time constants; there is no concept of compile-time variables, whether global or local.
- Only recursion can be used for programming, not loops.

Imagine writing code without variables or loops—it would be quite painful.

Are there programming languages that satisfy these two characteristics? In fact, programming languages that satisfy these two points are generally called pure functional programming languages. Haskell is a typical example. However, Haskell has powerful pattern matching, and once familiar with Haskell's mindset, one can write concise and elegant code (and Haskell itself can use the `do` syntax to simulate local variables, as using local variables is equivalent to passing them down as function parameters). C++ lacks these features, inheriting the drawbacks without the benefits. Fortunately, these issues are resolved with `constexpr` functions.

```cpp
constexpr std::size_t factorial(std::size_t N) {
    std::size_t result = 1;
    for(std::size_t i = 1; i <= N;