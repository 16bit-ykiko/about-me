---
title: 'C++ Forbidden Dark Arts: STMP (Part 1)'
date: 2023-07-29 18:20:50
updated: 2025-01-01 13:53:54
series: ['STMP']
series_order: 1
---

As is well known, traditional C++ constant expression evaluation neither depends on nor alters the global state of the program. For any identical input, its output is always the same, making it considered **purely functional**. **Template Meta Programming (TMP)**, as a subset of constant evaluation, should also adhere to this rule.

![](https://pica.zhimg.com/v2-310046d2ded45ca99cb74d992a94a51e_r.jpg)

But is this really the case? Without violating the C++ standard, could the following code possibly compile?

```cpp
constexpr auto a = value();
constexpr auto b = value();
static_assert(a != b);
```

Is it possible to implement a compile-time counter like this?

```cpp
constexpr auto a = next();
constexpr auto b = next();
constexpr auto c = next();
static_assert(a == 0 && b == 1 && c == 2);
```

If the results of constant evaluations differ each time, it implies that the evaluation alters the global state. This form of stateful meta-programming is known as Stateful Template Meta Programming (STMP).

In fact, with the help of some compiler built-in macros, we can achieve such effects, for example:

```cpp
constexpr auto a = __COUNTER__;
constexpr auto b = __COUNTER__;
constexpr auto c = __COUNTER__;
static_assert(a == 0 && b == 1 && c == 2);
```

During preprocessing, the compiler increments the replacement result of the `__COUNTER__` macro. If you preprocess the source file, you will find it transformed into:

```cpp
constexpr auto a = 0;
constexpr auto b = 1;
constexpr auto c = 2;
static_assert(a == 0 && b == 1 && c == 2);
```

This still differs significantly from the effect we aim to achieve, as preprocessing does not involve the semantic part of the C++ program. Moreover, such a counter is globally unique, and we cannot create multiple counters. Is there another way?

The answer is yes. As unbelievable as it may seem, related [discussions](https://b.atch.se/posts/non-constant-constant-expressions/) date back to 2015, and there are also related [articles](https://zhuanlan.zhihu.com/p/24835482) on Zhihu. However, this article was published in 2017, using C++14, and much of its content is no longer applicable. With the C++26 standard now being developed, many things need to be revisited. We will focus on C++20.

If you are only interested in the code, I have placed the relevant code on [Compiler Explorer](https://godbolt.org/z/T543Tvc3q). It compiles successfully with the three major compilers under C++20, and you can directly see the compiler's output. To prevent link failure, it is also available on [GitHub](https://github.com/16bit-ykiko/blog/blob/main/code/compile-time-counter.cpp). If you want to understand its principles, please continue reading. The C++ standard is very complex, and the author cannot guarantee the complete accuracy of the article. If there are any errors, please discuss them in the comments.

> Note: This article is for technical discussion only. Please do not use the related code in actual production. According to [CWG 2118](https://cplusplus.github.io/CWG/issues/2118.html), the related code seems to be considered ill-formed. Moreover, STMP is prone to ODR violations and requires great caution.

## Observable State

Before changing, we must first be able to observe changes in the global state at compile time. Since C++ supports **forward declaration**, a `struct` is considered an **incomplete type** before its definition is seen, meaning the completeness of the class varies in different contexts.

The C++ standard stipulates that `sizeof` can only be used on complete types (after all, incomplete types cannot calculate `size`). Using it on an incomplete type causes a compilation error, and this error is not a **hard error**, so we can use `SFINAE` or `requires` to capture this error. Thus, we can detect class completeness as follows:

```cpp
template <typename T>
constexpr inline bool is_complete_v = requires { sizeof(T); };
```

> Some readers might ask, why not use concept in C++20? Using concept here would have some strange effects due to the wording in the standard regarding atomic constraints. We won't delve into this; interested readers can try it themselves.

Try using it to observe type completeness:

```cpp
struct X;

static_assert(!is_complete_v<X>);

struct X {};

static_assert(is_complete_v<X>);
```

Actually, the above code will fail to compile, with the second static assertion failing. How strange, what's going on? Let's try it separately:

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

Separately, it works, but together it doesn't. Why is this? It's because the compiler caches the result of the first template instantiation, and subsequent encounters with the same template directly use the first instantiation result. In the initial example, the second `is_complete_v<X>` still uses the first template instantiation result, so it evaluates to `false`, causing the compilation to fail.

Is it reasonable for the compiler to do this? Yes, because templates may ultimately produce externally linked symbols. If the results of two instantiations differ, which one should be chosen during linking? But this does affect our ability to observe compile-time state. How to solve it? The answer is to add a template parameter as a seed, filling in different parameters each time to force the compiler to instantiate a new template:

```cpp
template <typename T, int seed = 0>
constexpr inline bool is_complete_v = requires { sizeof(T); };

struct X;

static_assert(!is_complete_v<X, 0>);

struct X {};

static_assert(is_complete_v<X, 1>);
```

Manually filling in a different parameter each time is cumbersome. Is there a way to automate this?

Note that if a lambda expression is used as a **Non Type Template Parameter (NTTP)** default template parameter, each instantiation of the template will be of a different type:

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

This feature perfectly meets our needs, as it automatically fills in a different seed each time. Thus, the final implementation of `is_complete_v` is as follows:

```cpp
template <typename T, auto seed = [] {}>
constexpr inline bool is_complete_v = requires { sizeof(T); };
```

Try using it again to observe type completeness:

```cpp
struct X;

static_assert(!is_complete_v<X>);

struct X {};

static_assert(is_complete_v<X>);
```

Compilation succeeds! We have successfully observed changes in the compile-time global state.

## Modifiable State

After being able to observe state changes, the next consideration is whether we can actively change the state through code. Unfortunately, for most declarations, the only way to change their state is by modifying the source code to add definitions; there are no other means to achieve this.

The only exception is friend functions. But before considering how friend functions can play a role, let's first consider how to observe whether a function has been defined. For most functions, this is unobservable, as a function may be defined in another compilation unit, and calling a function does not require its definition to be visible.

The exception is functions with a return type of `auto`. If the function definition is not visible, the return type cannot be deduced, making the function call impossible. The following code can detect whether the `foo` function is defined:

```cpp
template <auto seed = [] {}>
constexpr inline bool is_complete_v = requires { foo(seed); };

auto foo(auto);

static_assert(!is_complete_v<>);

auto foo(auto value) { return sizeof(value); }

static_assert(is_complete_v<>);
```

Next, let's discuss how to change the global state through friend functions.

The biggest difference between friend functions and ordinary functions is that the function definition and declaration do not need to be in the same scope. Consider the following example:

```cpp
struct X {
    friend auto foo(X);
};

struct Y {
    friend auto foo(X) { return 42; }
};

int x = foo(X{});
```

The above code compiles successfully with the three major compilers and fully complies with the C++ standard. This gives us room to operate. We can instantiate a class template while also instantiating the friend functions defined within it, thereby adding definitions to function declarations in other locations. This technique is also known as **friend injection**.

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

Note that at #1, the template `X` has not been instantiated, so the `foo` function has not yet been defined, causing `is_complete_v` to return `false`. At #2, we instantiate an `X<void>`, causing the `foo` function within `X` to be instantiated, adding a definition to `foo`, so at #3, `is_complete_v` returns `true`. Of course, a function can only have one definition. If you try to instantiate an `X<int>`, the compiler will report a redefinition error for `foo`.

## Constant Switch

Combining the above techniques, we can easily instantiate a compile-time switch:

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

Its principle is simple. The first time, `setter` has not been instantiated, so the `flag` function has not been defined, causing `exist` to evaluate to `false`, entering the `if constexpr` branch, instantiating a `setter<false>`, and returning `false`. The second time, `setter` has been instantiated, and the `flag` function has been defined, so `exist` evaluates to `true`, directly returning `true`.

> Note: The type of N here must be written as auto, not std::size_t. Only then is `flag(N)` a [dependent name](https://en.cppreference.com/w/cpp/language/dependent_name), allowing the requires to detect the legality of the expression. Due to the [two-phase lookup](https://en.cppreference.com/w/cpp/language/two-phase_lookup) of templates, if written as `flag(0)`, it would be looked up in the first phase, find the call fails, and produce a hard error, causing compilation to fail.

## Constant Counter

Going further, we can directly implement a compile-time counter:

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

Its logic is, starting from `N` as 0, detect whether `flag(reader<N>)` is defined. If not defined, instantiate a `setter<N>`, adding a definition to `flag(reader<N>)`, and return `N`. Otherwise, recursively call `next<N + 1>()`, detecting the situation for `N+1`. Thus, this counter actually records the number of `setter` instantiations.

## §: Access Private

First, it's important to clarify a point: the class access specifiers `private`, `public`, `protected` only act during compile-time checks. If there is a way to bypass this compile-time check, it is entirely possible to legally access any member of the class.

Is there such a method? Yes: **Template explicit instantiation ignores class scope access permissions:**

> The C++11/14 standards state the following in note 14.7.2/12 [temp.explicit]: The usual access checking rules do not apply to names used to specify explicit instantiations. [ Note: In particular, the template arguments and names used in the function declarator (including parameter types, return types and exception speciﬁcations) may be private types or objects which would normally not be accessible and the template may be a member template or member function which would not normally be accessible. — end note ]

This means that during template **explicit instantiation**, we can directly access private members of a class.

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

The syntax at #2 is template explicit instantiation, allowing us to directly access the private member `money` of `Bank`. By using `&Bank::money`, we obtain the corresponding member pointer. Simultaneously, through template explicit instantiation, a definition is added to the `steal` function at #1, allowing direct invocation of this function at #3 to obtain a reference to `money`. Finally, 100 is successfully output.