---
title: "Seeing Through the Fog: A True Understanding of C++ Templates"
date: "2023-09-12 15:46:11"
updated: "2025-12-24 05:14:54"
zhihu_article_id: "655902377"
zhihu_url: https://zhuanlan.zhihu.com/p/655902377
zhihu_column_id: c_1656510843973046272
zhihu_column_title: 魅力C++
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

在 C++ 中，模板（Template）这个概念已经存在二十多年了。作为 C++ 最重要的一个语言构成之一，相关的讨论数不胜数。很可惜的是，深入有价值的讨论很少，尤其是以多个视角来看待这个特性。很多文章在谈论模板的时候往往会把它和各种语法细节缠绕在一起，容易给人一种云里雾里的感觉。类似的例子还发生在其它话题上面，比如介绍协程就和各种 IO 混在一起谈，谈到反射似乎就限定了 Java，C# 中的反射。这样做并不无道理，但是往往让人感觉抓不到本质。看了很多内容，但却不得其要领，反倒容易把不同的概念混淆在一起。

就我个人而言，讨论一个问题喜欢多层次，多角度的去讨论，而不仅限于某一特定的方面。这样一来，既能更好的理解问题本身，也不至于让自己的视野太狭隘。故本文将尝试从模板诞生之初开始，以四个角度来观察，理清模板这一特性在 C++ 中的发展脉络。注意，本文并不是教学文章，不会深入语法细节。更多的谈论设计哲学和 trade-off 。掌握一些模板的基础知识就能看懂，请放心阅读。当然，这样可能严谨性有所缺失，如有错误欢迎评论区讨论。

**我们主要讨论四个主题：**

- 代码生成 (Code Generation)
- 类型约束 (Type Constraint)
- 编译时计算 (Compile-time Computing)
- 操纵类型 (Type Manipulation)

其中第一个主题一般认为就是普通的 Template。而后三者一般被规划到 TMP 中去。TMP 即 Template meta programming 也就是模板元编程。因为模板设计之初的意图并不是实现后面这三个功能，但是最后却通过一些奇怪的 trick 实现了这些功能，代码写起来也比较晦涩难懂，所以一般叫做元编程。

## Code Generation

### Generic

**Generic** programming, which means writing the same code for different types to achieve code reuse. Before templates were introduced, we could only simulate generics using macros. Consider the simple example below:

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

Its principle is very simple: it replaces the type in a regular function with a macro parameter and uses macro symbol concatenation to generate different names for different type parameters. Then, the `IMPL` macro is used to generate definitions for specific functions. This process can be called **instantiation**.

Of course, this is just the simplest example, and perhaps it looks fine to you. But what if you wanted to implement a `vector` using macros? Just thinking about it is a bit scary. Specifically, using macros to implement generics has the following disadvantages:

- Poor code readability: Macro concatenation and code logic are coupled, making error messages difficult to read.
- Difficult to debug: Breakpoints can only be set at the macro expansion location, not inside the macro definition.
- Requires explicit writing of type parameters: If there are many parameters, it becomes very verbose.
- Requires manual instantiation of function definitions: In larger codebases, a generic might have dozens of instantiations, and writing them all manually is too cumbersome.

These problems are all solved in templates:

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

- Templates are placeholders; they don't require character concatenation and are indistinguishable from ordinary code, except for the template parameter declaration.
- Errors and debugging can accurately point to the template definition location, not the template instantiation location.
- Supports automatic template parameter deduction, eliminating the need to explicitly write type parameters, while also supporting explicit specification of type parameters.
- Supports **implicit instantiation**, where the compiler automatically instantiates used functions. It also supports **explicit instantiation**, which is manual instantiation.

In addition, there are a series of features such as **partial specialization**, **full specialization**, **variadic templates**, and **variable templates**, none of which can be achieved with macros alone. It is precisely because of the advent of templates that the implementation of generic libraries like STL became possible.

### Table Gen

The generics mentioned above can be seen as the most direct use of templates. Based on them, we can have more advanced code generation, for example, generating a fixed table at compile time for runtime lookup. The implementation of `std::visit` in the standard library uses this technique; below is a simple simulation of it:

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

Although the type of elements stored in `variant` can only be determined at runtime, the set of possible types it can take can be determined at compile time. So, we use `callback` to instantiate a corresponding `wrapper` function for each possible type in the set and store them in an array. At runtime, we can directly use `variant`'s `index` to access the corresponding member in the array to complete the call.

Of course, using the **folding expression** introduced in C++17, we actually have a better approach:

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

By utilizing the short-circuiting property of logical operators, we can exit the evaluation of subsequent folding expressions early, and shorter functions are more conducive to inlining.

## Type Constraint

I agree with everything else, but template error messages are clearly not easy to read! Compared to macros, isn't it just a case of "fifty paces behind a hundred paces"? Perhaps even worse. Easily producing hundreds or thousands of lines of errors, I think only C++ templates can do that.

This is the next problem to discuss: why are C++ compilation error messages so long? And sometimes very difficult to understand.

### Function Overload

Consider this simple example with only a few lines:

```cpp
struct A {};

int main() {
    std::cout << A{} << std::endl;
    return 0;
}
```

On my GCC compiler, it produced a whopping 239 lines of error messages. The good news is that GCC highlighted the critical part, as shown below:

```cpp
no match for 'operator<<' (operand types are 'std::ostream' {aka 'std::basic_ostream<char>'} and 'A')
    9 |     std::cout << A{} << std::endl;
      |     ~~~~~~~~~ ^~ ~~~
      |          |       |
      |          |       A
      |          std::ostream {aka std::basic_ostream<char>}
```

That's probably understandable; it means no matching overloaded function was found, so we need to overload `operator<<` for `A`. But what we're curious about is, what are the remaining two hundred lines of errors doing? The key lies in **Overload Resolution**. Let's look at one piece of information:

```cpp
note:   template argument deduction/substitution failed:
note:   cannot convert 'A()' (type 'A') to type 'const char*'
    9 |     std::cout << A{} << std::endl;
```

This means that an attempt was made to match type `A` with the `const char*` overload (via implicit type conversion), and it failed. Standard library functions like this have many overloads, for example, `operator<<` is overloaded for `int`, `bool`, `long`, `double`, etc., nearly dozens of functions. The error message then lists the reasons why all these overloaded functions failed, easily reaching hundreds of lines. Coupled with the cryptic naming in the standard library, it looks like gibberish.

### Instantiation Stack

Function overloading is one reason why error messages are difficult to read, but not the only one. In fact, as shown above, merely enumerating all possibilities only results in a few hundred lines of errors. Keep in mind that we can still produce thousands of lines; the difference in magnitude cannot be easily compensated by quantity. Moreover, this subsection is about type constraints, so what does it have to do with compiler errors? Consider the following example:

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

In the example above, `#1` only has a few lines of error messages, while `#2` has hundreds of lines. Why is there such a large difference? Do you remember the two advantages of templates over macros that we discussed in the first part? One is automatic type deduction, and the other is implicit instantiation. Only when template parameter deduction succeeds will template instantiation be triggered, and only then will errors in the function body be checked.

In `test(A{}, B{})`, template parameter deduction failed. This is because the `test` function implies an important condition: that the types of `a` and `b` are the same. So, it actually reports an error that no matching function was found. For the second function, `test(A{}, A{})`, template parameter deduction succeeded, and it entered the instantiation phase, but an error occurred during instantiation. This means that `T` has been deduced as `A`, and an error occurred when trying to substitute `A` into the function body. Therefore, the compiler has to list the reasons for the substitution failure within the function body.

This leads to a problem: when there are many layers of nested templates, an error might occur in the innermost template function, but the compiler has to print out the entire template instantiation stack.

So what's the use of constraining types? Look at the example below:

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

Just a few lines, but on my GCC, it produced 700 lines of compilation errors. If we make a slight change and uncomment the commented line of code, the error message in this situation is only a few lines:

```cpp
In substitution of 'template<class T>  requires requires(T x) {std::cout << x;} void print2(T) [with T = A]':
required from here
required by the constraints of 'template<class T>  requires requires(T x) {std::cout << x;} void print2(T)'
in requirements with 'T x' [with T = A]
note: the required expression '(std::cout << x)' is invalid
   15 | requires requires (T x) { std::cout << x; }
```

This means that an instance `x` of type `A` does not satisfy the `requires` clause `std::cout << x`. In fact, with such syntax, we can limit errors to the type deduction phase, without proceeding to instantiation. This results in much more concise error messages.

In other words, `requires` allows us to prevent the propagation of compilation errors. However, unfortunately, constraint-related syntax was only added in C++20. What about before that?

### Before C++20

Before C++20, we didn't have such a convenient method. We could only achieve similar functionality, constraining types, through a technique called [SFINAE](https://en.cppreference.com/w/cpp/language/sfinae). For example, the functionality above could only be written like this before C++20:

```cpp
template <typename T, typename = decltype(std::cout << std::declval<T>())>
void print2(T x) {
    print1(x);
    std::cout << x << std::endl;
}
```

I won't go into the specific rules here; if you're interested, you can search for related articles.

The result is:

```cpp
typename = decltype(std::cout << std::declval<T>())
```

This line of code is baffling; it's completely unclear what it's trying to express. Only after a deep understanding of C++ template rules can one comprehend what it's doing. For why `requires` was only added in C++20, you can read the [autobiography](https://github.com/Cpp-Club/Cxx_HOPL4_zh/blob/main/06.md) written by the creator of C++ himself.

## Compile-time Computing

### Meaning

First, it must be affirmed that compile-time computation is definitely useful. As for how significant it is in specific scenarios, that certainly cannot be generalized. Many people dread compile-time computation, calling it hard to understand, a "dragon-slaying skill," or worthless. This can easily mislead beginners. In fact, such demands do exist. If a programming language lacks this feature but there is a need for it, programmers will find ways to implement it through other means.

I will give two examples to illustrate:

- First, the compiler's optimization of constant expressions, which I believe everyone is familiar with. In extremely simple cases, like `1+1+x`, the compiler will optimize it to `2+x`. In fact, modern compilers can perform many optimizations for similar situations, such as this [question](https://www.zhihu.com/question/619246858/answer/3184453259). The questioner asked whether the C language's `strlen` function, when its parameter is a constant string, would directly optimize the function call into a constant. For example, would `strlen("hello")` be directly optimized to `5`? From the experimental results of mainstream compilers, the answer is yes. Similar situations are countless; you are using compile-time computation without even realizing it. It's just categorized as part of compiler optimization. However, the compiler's optimization capabilities always have limits, and allowing users to define such optimization rules themselves would be more flexible and free. For example, in C++, if `strlen` is explicitly `constexpr`, this optimization will necessarily occur.
- Second, in the early days of programming language development, when compiler optimization capabilities were not as strong, external scripting languages were already widely used to pre-calculate data (or even generate code) to reduce runtime overhead. A typical example is calculating constant tables like trigonometric function tables, which can then be used directly at runtime. For instance, running a script to generate some necessary code before compiling the main code.

C++'s compile-time computation has clear semantic guarantees and is embedded within the language, allowing good interaction with other parts. From this perspective, it effectively solves the two problems mentioned above. Of course, many people's criticisms of it are not without reason: compile-time computation performed through template metaprogramming results in ugly and obscure code, involves many syntactic details, and significantly slows down compilation time and increases binary file size. Undeniably, these problems do exist. However, with continuous updates to C++ versions, compile-time computation is now very easy to understand, no longer requiring complex template metaprogramming, and even beginners can quickly learn it because it is almost identical to runtime code. We will gradually clarify this as we trace its development history.

### History

Historically, TMP was an accident. In the process of standardizing the C++ language, it was discovered that its template system was Turing-complete, meaning it could, in principle, compute anything computable. The first concrete demonstration was a program written by Erwin Unruh that computed prime numbers, although it didn't actually compile: the list of prime numbers was part of the error message generated by the compiler when trying to compile the code. For a specific example, please refer to [here](https://en.wikibooks.org/wiki/C%2B%2B_Programming/Templates/Template_Meta-Programming#History_of_TMP).

As an introductory programming example, here's a method for compile-time factorial calculation:

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

This code could compile even before C++11. After that, C++ introduced many new features to simplify compile-time computation. The most important one is the `constexpr` keyword. It can be seen that before C++11, we didn't have a suitable way to represent the concept of a compile-time constant, only borrowing `enum` to express it. After C++11, we can write it like this:

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

Despite some simplification, we are still relying on templates for compile-time computation. Code written this way is difficult to read, mainly due to two points:

- Template parameters can only be compile-time constants; there is no concept of compile-time variables, neither global nor local.
- Programming can only be done through recursion, not loops.

Imagine if, in your everyday coding, variables and loops were forbidden; how uncomfortable would that be to write?

Are there programming languages that satisfy these two characteristics? In fact, programming languages that satisfy these two points are generally called pure functional programming languages. Haskell is a typical example. However, Haskell has powerful pattern matching, and once familiar with Haskell's way of thinking, one can write concise and elegant code (and Haskell itself can simulate local variables using `do` syntax, because using local variables is essentially passing them down as function parameters level by level). C++ has none of these; it inherits all the disadvantages of others and none of the advantages. Fortunately, all these problems have been solved in `constexpr function`.

```cpp
constexpr std::size_t factorial(std::size_t N) {
    std::size_t result = 1;
    for(std::size_t i = 1; i <= N; ++i) {
        result *= i;
    }
    return result;
}

int main() {
    constexpr auto a = factorial(5);  // compile-time
    std::size_t& n = *new std::size_t(6);
    auto b = factorial(n);  // run-time
}
```

C++ allows a function to be directly modified with the `constexpr` keyword. This indicates that the function can be called both at runtime and compile-time, with almost no changes to the function's content itself. This way, we can directly reuse runtime code at compile-time. It also allows programming with loops and local variables, meaning it's indistinguishable from ordinary code. Quite astonishing, isn't it? So, compile-time computation has long been commonplace in C++, and users don't need to write complex template metaprogramming. After C++20, almost all standard library functions are also `constexpr`, allowing us to easily call them, such as compile-time sorting.

```cpp
constexpr auto sort(auto&& range) {
    std::sort(std::begin(range), std::end(range));
    return range;
}

int main() {
    constexpr auto arr = sort(std::array{1, 3, 4, 2, 3});
    for(auto i: arr) {
        std::cout << i;
    }
}
```

True code reuse! If you want this function to execute only at compile time, you can mark it with `consteval`. Additionally, in C++20, compile-time dynamic memory allocation is allowed; you can use `new` in a `constexpr function` for memory allocation, but memory allocated at compile time must also be deallocated at compile time. You can also directly use containers like `vector` and `string` at compile time. And please note, `constexpr` functions compile much faster compared to compile-time computation using templates. If you're curious how the compiler implements this powerful feature, you can imagine that the C++ compiler internally embeds a small interpreter. When it encounters a `constexpr` function, it interprets it with this interpreter and then returns the calculated result.

I believe you have fully witnessed C++'s efforts in compile-time computation. Compile-time computation has long been decoupled from template metaprogramming and has become a very natural feature in C++, requiring no special syntax yet wielding powerful capabilities. So, from now on, don't panic when C++ compile-time computation is mentioned, thinking it's some "dragon-slaying skill." It has already become very gentle and beautiful.

Although compile-time computation has escaped the clutches of template metaprogramming, C++ has not. There are still two situations where we are forced to write awkward template metaprogramming code.

## Type Manipulation

### Match Type

How do you determine if two types are equal, or rather, if the types of two variables are equal? Some might think this is redundant, as variable types are known at compile time, so why would we need to check? This question actually arose with generic programming. Consider the following example:

```cpp
template <typename T>
void test() {
    if(T == int) {
        /* ... */
    }
}
```

Such code aligns with our intuition, but unfortunately, C++ doesn't allow you to write it this way. However, in languages like Python/Java, such syntax does exist, but their checks are mostly performed at runtime. C++ does allow us to operate on types at compile time, but unfortunately, types cannot be first-class citizens, treated as ordinary values; they can only be template parameters. We can only write code like this:

```cpp
template <typename T>
void test() {
    if constexpr(std::is_same_v<T, int>) {
        /* ... */
    }
}
```

Types can only exist within template parameters, which directly nullifies all the advantages of `constexpr` compile-time computation mentioned in the previous section. We are back to the Stone Age, without variables or loops.

Below is code to check if two `type_list`s satisfy a subsequence relationship:

```cpp
template <typename... Ts>
struct type_list {};

template <typename SubFirst, typename... SubRest, typename SuperFirst, typename... SuperRest>
constexpr auto is_subsequence_of_impl(type_list<SubFirst, SubRest...>, type_list<SuperFirst, SuperRest...>) {
    if constexpr(std::is_same_v<SubFirst, SuperFirst>)
        if constexpr(sizeof...(SubRest) == 0)
            return true;
        else
            return is_subsequence_of(type_list<SubRest...>{}, type_list<SuperRest...>{});
    else if constexpr(sizeof...(SuperRest) == 0)
        return false;
    else
        return is_subsequence_of(type_list<SubFirst, SubRest...>{}, type_list<SuperRest...>{});
}

template <typename... Sub, typename... Super>
constexpr auto is_subsequence_of(type_list<Sub...>, type_list<Super...>) {
    if constexpr(sizeof...(Sub) == 0)
        return true;
    else if constexpr(sizeof...(Super) == 0)
        return false;
    else
        return is_subsequence_of_impl(type_list<Sub...>{}, type_list<Super...>{});
}

int main() {
    static_assert(is_subsequence_of(type_list<int, double>{}, type_list<int, double, float>{}));
    static_assert(!is_subsequence_of(type_list<int, double>{}, type_list<double, long, char, double>{}));
    static_assert(is_subsequence_of(type_list<>{}, type_list<>{}));
}
```

It's very uncomfortable to write. If I write the same code logic using a `constexpr` function, replacing type parameters with `std::size_t`:

```cpp
constexpr bool is_subsequence_of(auto&& sub, auto&& super) {
    std::size_t index = 0;
    for(std::size_t i = index; index < sub.size() && i < super.size(); i++) {
        if(super[i] == sub[index]) {
            index++;
        }
    }
    return index == sub.size();
}

static_assert(is_subsequence_of(std::array{1, 2}, std::array{1, 2, 3}));
static_assert(!is_subsequence_of(std::array{1, 2, 4}, std::array{1, 2, 3}));
```

It instantly becomes a million times cleaner, simply because types are not first-class citizens in C++ and can only be template parameters. When it comes to type-related computations, we are forced to write cumbersome template metaprogramming code. In fact, the need to compute with types has always existed; a typical example is `std::variant`. When writing `operator=`, we need to find a certain type from a type list (the `variant`'s template parameter list) and return an index, which is essentially finding an element that satisfies a specific condition from an array. The related implementation will not be shown here. The truly terrible thing is not using template metaprogramming itself, but rather that for C++ itself, such a change as treating types as values is completely unacceptable. This means that this situation will continue indefinitely, and there will be no fundamental change in the future, and this fact is the most disheartening. However, it is still important to realize that not many languages support computing with types; Rust, for example, has almost no support in this area. Although C++ code is awkward to write, at least it can be written.

But thankfully, there's another path we can take: mapping types to values through certain means. For example, mapping types to strings, where matching types can be similar to matching strings; we just need to compute with strings, which can achieve a certain degree of `type as value`. Before C++23, there was no standardized way to perform this mapping. It could be done through some special compiler extensions; you can refer to [How to elegantly convert enum to string in C++](https://www.ykiko.me/en/articles/680412313).

```cpp
template <typename... Ts>
struct type_list {};

template <typename T, typename... Ts>
constexpr std::size_t find(type_list<Ts...>) {
    // type_name returns the name of the type
    std::array arr = {type_name<Ts>()...};
    for(auto i = 0; i < arr.size(); i++) {
        if(arr[i] == type_name<T>()) {
            return i;
        }
    }
}
```

After C++23, `typeid` can also be used directly for mapping, instead of string mapping. However, mapping types to values is simple, but mapping values back to types is not simple at all, unless you use black magic like [STMP](https://www.ykiko.me/en/articles/646752343) to conveniently map values back to types. But, if static reflection is introduced in the future, this bidirectional mapping between types and values will be very simple. In that case, although it won't directly support treating types as values, it will be pretty close. However, there's still a long way to go, and when it will be added to the standard is still unknown. If you're interested in static reflection, you can read [Analysis of the C++26 Static Reflection Proposal](https://www.ykiko.me/en/articles/661692275).

### Comptime Variable

Besides the necessity of using template metaprogramming for type computations as mentioned above, if you need to instantiate templates while performing compile-time computations, you also have to use template metaprogramming.

```cpp
consteval auto test(std::size_t length) {
    return std::array<std::size_t, length>{};
    // error length is not constant expression
}
```

The error means that `length` is not a compile-time constant; it's generally considered a compile-time variable. This is quite annoying. Consider the following requirement: we want to implement a completely type-safe `format` function. That is, based on the content of the first constant string, constrain the number of subsequent function parameters. For example, if it's `"{}"`, the `format` function should have `1` parameter.

```cpp
consteval auto count(std::string_view fmt) {
    std::size_t num = 0;
    for(auto i = 0; i < fmt.length(); i++) {
        if(fmt[i] == '{' && i + 1 < fmt.length()) {
            if(fmt[i + 1] == '}') {
                num += 1;
            }
        }
    }
    return num;
}

template <typename... Args>
constexpr auto format(std::string_view fmt, Args&&... args)
    requires (sizeof...(Args) == count(fmt))
{
    /* ... */
}
```

In fact, we have no way to guarantee that a function parameter is a compile-time constant, so the code above cannot compile. To have a compile-time constant, this content must be put into template parameters, for example, the above function might eventually be modified to `format<"{}">(1)`. Although it's only a formal difference, this undoubtedly creates difficulties for the user. From this perspective, it's not hard to understand why things like `std::make_index_sequence` are so prevalent. To truly have compile-time variables that can be template parameters, it can also be achieved through black magic like [STMP](https://www.ykiko.me/en/articles/646752343), but as mentioned earlier, it's difficult to actually use it in everyday programming.

### Type is Value

It's worth mentioning that there's a relatively new language called Zig. It solves the problems mentioned above, supporting not only compile-time variables but also treating types as first-class citizens. Thanks to Zig's unique `comptime` mechanism, variables or code blocks marked with it are executed at compile time. This allows us to write code like this:

```rust
const std = @import("std");

fn is_subsequence_of(comptime sub: anytype, comptime super: anytype) bool {
    comptime {
        var subIndex = 0;
        var superIndex = 0;
        while(superIndex < super.len and subIndex < sub.len) : (superIndex += 1) {
            if(sub[subIndex] == super[superIndex]) {
                subIndex += 1;
            }
        }
        return subIndex == sub.len;
    }
}

pub fn main() !void {
    comptime var sub = [_] type { i32, f32, i64 };
    comptime var super = [_] type { i32, f32, i64, i32, f32, i64 };
    std.debug.print("{}\n", .{comptime is_subsequence_of(sub, super)});

    comptime var sub2 = [_] type { i32, f32, bool, i64 };
    comptime var super2 = [_] type { i32, f32, i64, i32, f32 };
    std.debug.print("{}\n", .{comptime is_subsequence_of(sub2, super2)});
}
```

This is the code we've dreamed of writing; it's truly elegant! In terms of type computation, Zig completely outperforms current C++. Interested readers can check out the Zig official website, but in other areas besides type computation, such as generics and code generation, Zig actually doesn't do as well. This is not the focus of this article, so I won't discuss it.

## Conclusion

It can be seen that templates initially took on too many roles, and their usage was not what was originally intended during their design; they were used as tricks to compensate for the language's lack of expressive power. With the continuous development of C++, these additional roles have gradually been replaced by simpler, more direct, and easier-to-understand syntax. Type constraints are handled by `concept` and `requires`, compile-time computation by `constexpr`, and type manipulation by future `static reflection`. Templates are gradually returning to their original form, responsible for code generation. Those obscure and difficult-to-understand workarounds are also gradually being phased out, which is a good sign, although we often still have to deal with legacy code. But at least we know that the future will be better!
