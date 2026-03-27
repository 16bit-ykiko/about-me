---
series:
  - STMP
series_order: 1
title: "C++ Forbidden Black Magic: STMP (Part 1)"
date: "2023-07-29 10:20:50"
updated: "2026-03-14 15:05:50"
zhihu_article_id: "646752343"
zhihu_url: https://zhuanlan.zhihu.com/p/646752343
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

As is well known, traditional C++ constant expression evaluation neither depends on nor changes the global state of the program. For any identical input, its output is always the same, and it is considered **purely functional**. **Template Meta Programming**, as a subset of constant evaluation, should also adhere to this rule.

![](https://pica.zhimg.com/v2-310046d2ded45ca99cb74d992a94a51e_r.jpg)

But is this really the case? Without violating the C++ standard, could the following code compile?

```cpp
constexpr auto a = value();
constexpr auto b = value();
static_assert(a != b);
```

Could a compile-time counter like the following be implemented?

```cpp
constexpr auto a = next();
constexpr auto b = next();
constexpr auto c = next();
static_assert(a == 0 && b == 1 && c == 2);
```

Each time a constant expression is evaluated, a different result is obtained, indicating that the evaluation has changed the global state. This kind of stateful meta-programming is called state meta-programming. If it is further associated with templates, it is called **Stateful Template Meta Programming (STMP)**.

In fact, with the help of some compiler-built-in macros, we can achieve such an effect, for example:

```cpp
constexpr auto a = __COUNTER__;
constexpr auto b = __COUNTER__;
constexpr auto c = __COUNTER__;
static_assert(a == 0 && b == 1 && c == 2);
```

During preprocessing, the compiler increments the replacement result of the `__COUNTER__` macro. If you preprocess the source file, you will find that the source file becomes like this:

```cpp
constexpr auto a = 0;
constexpr auto b = 1;
constexpr auto c = 2;
static_assert(a == 0 && b == 1 && c == 2);
```

This is still quite different from the effect we want to achieve, as preprocessing does not involve the semantic part of a C++ program. Moreover, such a counter is globally unique, and we cannot create many counters. Is there another way?

The answer is yes. Unbelievable as it may seem, relevant [discussions](https://b.atch.se/posts/non-constant-constant-expressions/) actually existed as early as 2015, and there are also related [articles](https://zhuanlan.zhihu.com/p/24835482) on Zhihu. However, that article was published in 2017 and used C++14; much of its content is now outdated. Moreover, with C++26 standards now being drafted, many things need to be re-discussed. The version we will choose is C++20.

If you are only interested in the code, I have placed the relevant code on [Compiler Explorer](https://godbolt.org/z/T543Tvc3q). All three major compilers compile it successfully with C++20, and you can directly see the compiler's output. To prevent link rot, it's also available on [GitHub](https://github.com/16bit-ykiko/blog/blob/main/code/compile-time-counter.cpp). If you want to understand its principles, please continue reading. The C++ standard is very complex, and the author cannot guarantee that the content of this article is entirely correct. If there are any errors, feel free to discuss them in the comments section.

> According to [CWG 2118](https://cplusplus.github.io/CWG/issues/2118.html), the related code is considered ill-formed. However, the later introduction of C++26 static reflection, whose proposal itself provides similar counter examples, seems to affirm this approach. Overall, I believe this is an inherent flaw caused by C++ distinguishing declaration order. If, like many modern programming languages, it performed lazy parsing, didn't distinguish declaration order, and used a two-pass scan, perhaps this compile-time mutable state could truly be eliminated. If you intend to try this in your code, proceed with extreme caution, as STMP can easily lead to ODR violations.

## observable state

Before we can change it, we must first be able to observe changes in the global state at compile time. Because C++ supports **forward declaration**, a `struct` is considered an **incomplete type** before its definition is seen, meaning the completeness of a class differs in different contexts.

The C++ standard stipulates that `sizeof` can only be used on complete types (after all, an incomplete type has no definition and its `size` cannot be calculated). Using it on an incomplete type will result in a compilation error, and this error is not a **hard error**, so we can use `SFINAE` or `requires` to catch this error. Thus, we can detect the completeness of a class in the following way:

```cpp
template <typename T>
constexpr inline bool is_complete_v = requires { sizeof(T); };
```

> Some readers might ask, why not use concepts in C++20? Using concepts here would lead to some strange effects, caused by the wording in the standard regarding atomic constraints. We won't delve into it deeply, but interested readers can try it themselves.

Let's try using it to observe type completeness:

```cpp
struct X;

static_assert(!is_complete_v<X>);

struct X {};

static_assert(is_complete_v<X>);
```

In fact, the code above will result in a compilation error; the second static assertion fails. That's strange, what's going on? Let's try them separately:

```cpp
// first time
struct X;

static_assert(!is_complete_v<X>);

struct X {};

// second time
struct X;

struct X {};

static_assert(is_complete_v<X>);
```

Trying them separately works, but together it doesn't. Why is this? This is because the compiler caches the result of the first template instantiation, and subsequent encounters with the same template will directly use that cached result. In the initial example, the second `is_complete_v<X>` still used the result of the first template instantiation, so it still evaluated to `false`, causing compilation to fail. <br><br> Is the compiler's behavior reasonable? Yes, it is. Because templates can ultimately produce symbols with external linkage, if two instantiations yield different results, which one should be chosen during linking? However, this does affect our ability to observe compile-time state. How can we solve this? The answer is to add a template parameter as a seed, and provide a different parameter each time it's evaluated, forcing the compiler to instantiate a new template:

```cpp
template <typename T, int seed = 0>
constexpr inline bool is_complete_v = requires { sizeof(T); };

struct X;

static_assert(!is_complete_v<X, 0>);

struct X {};

static_assert(is_complete_v<X, 1>);
```

Manually entering a different parameter each time is cumbersome. Is there a way to automatically fill it in?

Note that if a lambda expression is used as a default **Non-Type Template Parameter (NTTP)**, the template will be a different type each time it is instantiated:

```cpp
#include <iostream>

template <auto seed = [] {}>
void test() {
    std::cout << typeid(seed).name() << std::endl;
}

int main() {
    test(); // class <lambda_1>
    test(); // class <lambda_2>
    test(); // class <lambda_3>
    return 0;
}
```

This feature perfectly meets our needs, as it can automatically fill in a different seed each time. Thus, the final `is_complete_v` implementation is as follows:

```cpp
template <typename T, auto seed = [] {}>
constexpr inline bool is_complete_v = requires { sizeof(T); };
```

Let's try using it again to observe type completeness:

```cpp
struct X;

static_assert(!is_complete_v<X>);

struct X {};

static_assert(is_complete_v<X>);
```

Compilation successful! At this point, we have successfully observed changes in the global state at compile time.

## modifiable state

After being able to observe state changes, we now need to consider whether we can actively change the state through code. Unfortunately, for most declarations, the only way to change their state is by modifying the source code to add a definition; there are no other means to achieve this effect.

The only exception is friend functions. But before considering how friend functions work, let's first consider how to observe whether a function has been defined. For most functions, this is not observable, given that a function might be defined in another compilation unit, and calling a function does not require its definition to be visible.

The exception is functions with an `auto` return type; if their function definition is not visible, the return type cannot be deduced, and thus the function cannot be called. The following code can detect whether the `foo` function is defined:

```cpp
template <auto seed = [] {}>
constexpr inline bool is_complete_v = requires { foo(seed); };

auto foo(auto);

static_assert(!is_complete_v<>);

auto foo(auto value) { return sizeof(value); }

static_assert(is_complete_v<>);
```

Next, let's discuss how to change the global state using friend functions.

The biggest difference between friend functions and ordinary functions is that the function definition and function declaration are not required to be in the same scope. Consider the following example:

```cpp
struct X {
    friend auto foo(X);
};

struct Y {
    friend auto foo(X) { return 42; }
};

int x = foo(X{});
```

The code above compiles successfully with all three major compilers and fully conforms to the C++ standard. This gives us room to maneuver: we can instantiate a class template and simultaneously instantiate its internally defined friend function, thereby adding a definition to a function declaration located elsewhere. This technique is also known as **friend injection**.

```cpp
auto foo(auto);

template <typename T>
struct X {
    friend auto foo(auto value) { return sizeof(value); }
};

static_assert(!is_complete_v<>); // #1

X<void> x; // #2

static_assert(is_complete_v<>); // #3
```

Note that at #1, template `X` has not been instantiated, so the `foo` function is not yet defined, and `is_complete_v` returns `false`. At #2, we instantiate an `X<void>`, which in turn causes the `foo` function within `X` to be instantiated, adding a definition for `foo`. Consequently, at #3, `is_complete_v` returns `true`. Of course, a function can have at most one definition; if you try to instantiate another `X<int>`, the compiler will report an error that `foo` is redefined.

## constant switch

Combining the techniques mentioned above, we can easily instantiate a compile-time switch:

```cpp
auto flag(auto);

template <auto value>
struct setter {
    friend auto flag(auto) {}
};

template <auto N = 0, auto seed = [] {}>
consteval auto value() {
    constexpr bool exist = requires { flag(N); };
    if constexpr(!exist) {
        setter<exist> setter;
    }
    return exist;
}

int main() {
    constexpr auto a = value();
    constexpr auto b = value();
    static_assert(a != b);
}
```

Its principle is simple. The first time, `setter` has not been instantiated, so the `flag` function is not defined. Thus, `exist` evaluates to `false`, entering the `if constexpr` branch, instantiating a `setter<false>`, and returning `false`. The second time, `setter` has been instantiated, and the `flag` function is defined. Thus, `exist` evaluates to `true`, and `true` is returned directly.

> Note that the type of N here must be `auto`, not `std::size_t`. Only then will `flag(N)` be a [dependent name](https://en.cppreference.com/w/cpp/language/dependent_name), allowing `requires` to check the validity of the expression. Due to [two-phase lookup](https://en.cppreference.com/w/cpp/language/two-phase_lookup) for templates, if written as `flag(0)`, it would be looked up in the first phase, fail to be called, and produce a hard error, leading to a compilation error.

## constant counter

Furthermore, we can directly implement a compile-time counter:

```cpp
template <int N>
struct reader {
    friend auto flag(reader);
};

template <int N>
struct setter {
    friend auto flag(reader<N>) {}
};

template <int N = 0, auto seed = [] {}>
consteval auto next() {
    constexpr bool exist = requires { flag(reader<N>{}); };
    if constexpr(!exist) {
        setter<N> setter;
        return N;
    } else {
        return next<N + 1>();
    }
}

int main() {
    constexpr auto a = next();
    constexpr auto b = next();
    constexpr auto c = next();
    static_assert(a == 0 && b == 1 && c == 2);
}
```

Its logic is as follows: starting with `N` at 0, it checks if `flag(reader<N>)` is defined. If it's not defined, it instantiates a `setter<N>`, which means adding a definition for `flag(reader<N>)`, and then returns `N`. Otherwise, it recursively calls `next<N + 1>()` to check the `N+1` case. Therefore, this counter actually records the number of `setter` instantiations.

## §: access private

First, it's important to clarify a point: class access specifiers `private`, `public`, `protected` only apply to compile-time checks. If there's a way to bypass this compile-time check, then any member of the class can be legally accessed.

So, does such a method exist? Yes: **template explicit instantiation ignores class scope access permissions:**

> The C++11/14 standards state the following in note 14.7.2/12 [temp.explicit]: The usual access checking rules do not apply to names used to specify explicit instantiations. [ Note: In particular, the template arguments and names used in the function declarator (including parameter types, return types and exception speciﬁcations) may be private types or objects which would normally not be accessible and the template may be a member template or member function which would not normally be accessible. — end note ]

This means that during **explicit instantiation** of a template, we can directly access private members of a class.

```cpp
#include <iostream>

class Bank {
    double money = 999'999'999'999;

public:
    void check() const { std::cout << money << std::endl; }
};

template <auto mp>
struct Thief {
    friend double& steal(Bank& bank) { return bank.*mp; }
};

double& steal(Bank& bank); // #1

template struct Thief<&Bank::money>; // #2

int main() {
    Bank bank;
    steal(bank) = 100; // #3
    bank.check(); // 100
    return 0;
}
```

The syntax at #2 is template explicit instantiation, allowing us to directly access the private member `money` of `Bank`. By using `&Bank::money`, we obtain the member pointer corresponding to that member. Concurrently, through explicit template instantiation, a definition is added to the `steal` function at #1, allowing us to directly call this function at #3 and obtain a reference to `money`. Finally, 100 is successfully output.
