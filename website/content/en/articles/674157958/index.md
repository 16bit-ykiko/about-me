---
title: "A 7-Year Relay Race: Getting the Number of Fields in a C++ Struct"
date: "2023-12-25 20:45:30"
updated: "2025-01-14 12:36:56"
zhihu_article_id: "674157958"
zhihu_url: https://zhuanlan.zhihu.com/p/674157958
zhihu_column_id: c_1656510843973046272
zhihu_column_title: 魅力C++
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

## Introduction

In `C++17`, a feature called "**structured binding**" was introduced. This feature is similar to pattern matching in other languages and allows us to conveniently access members of a struct.

```cpp
struct Point {
    int x;
    int y;
};

Point p = {1, 2};
auto [x, y] = p;
// x = 1, y = 2
```

Using it, we can implement some interesting functionalities, including _limited_ reflection capabilities for structs, such as implementing a `for_each` function.

```cpp
void for_each(auto&& object, auto&& func) {
    using T = std::remove_cvref_t<decltype(object)>;
    if constexpr(std::is_aggregate_v<T>) {
        auto&& [x, y] = object;
        for_each(x, func);
        for_each(y, func);
    } else {
        func(object);
    }
}
```

This way, for any aggregate type with two members, we can iterate over it.

```cpp
struct Line {
    Point start;
    Point end;
};

Line line = {
    {1, 2},
    {3, 4},
};

int main() {
    for_each(line, [](auto&& object) { std::cout << object << std::endl; });
    return 0;
}
```

However, there's a problem: it only recursively supports structs with 2 fields. If you try to use a struct with 3 fields, the compiler will throw a `hard error`. This means an incorrect number of structured bindings, which cannot be handled by `SFINAE` or `requires`, and will directly cause compilation to abort.

```cpp
struct Vec3 {
    float x;
    float y;
    float z;
};

template <typename T>
constexpr bool two = requires { []() { auto [x, y] = T{1, 2, 3}; }; };

static_assert(two<Vec3>); // !hard error
```

We can solve this problem through manual dispatch.

```cpp
if constexpr(N == 1) {
    auto&& [x] = object;
    // ...
} else if constexpr(N == 2) {
    auto&& [x, y] = object;
    // ...
} else if constexpr(N == 3) {
    auto&& [x, y, z] = object;
    // ...
} else {
    // ...
}
```

You can freely enumerate up to the number you want to support. Here, `N` is the number of struct fields. You might need to explicitly pass it as a template parameter, or specialize a template for each type to store its field count. But this is still cumbersome. So, is there a way for the compiler to automatically calculate the number of fields in a struct for us?

## Antony Polukhin

A preliminary solution has already been provided in [boost/pfr](https://www.boost.org/doc/libs/1_75_0/doc/html/boost_pfr.html). Its author, Antony Polukhin, gave a detailed introduction to this at [CppCon2016](https://www.youtube.com/watch?v=abdeAew3gmQ) and [CppCon2018](https://www.youtube.com/watch?v=UlNUNxLtBI0). However, the version used by the author was `C++14/17`, and the code was quite obscure and difficult to understand. After I rewrote it using `C++20`, readability improved significantly.

First, in `C++`, we can write an `Any` type, which supports conversion to any type. Essentially, you just need to write its [type conversion function](https://en.cppreference.com/w/cpp/language/cast_operator) as a template function.

```cpp
struct Any {
    constexpr Any(int) {};

    template <typename T>
    constexpr operator T () const;
};

static_assert(std::is_convertible_v<Any, int>);          // true
static_assert(std::is_convertible_v<Any, std::string>);  // true
```

Next, we can leverage the property of aggregate initialization, which is that for expressions exceeding the maximum number of aggregate initializers, the `requires` statement will return `false`.

```cpp
template <typename T, std::size_t N>
constexpr auto test() {
    return []<std::size_t... I>(std::index_sequence<I...>) {
        return requires { T{Any(I)...}; };
    }(std::make_index_sequence<N>{});
}

static_assert(test<Point, 0>());   // true
static_assert(test<Point, 1>());   // true
static_assert(test<Point, 2>());   // true
static_assert(!test<Point, 3>());  // false
```

Note that `Point` only has two members here. When we pass three arguments to the initializer list, `requires` will return `false`. Using this property, we can change the above trial process to be recursive, i.e., linearly search this sequence until `false` is found.

```cpp
template <typename T, int N = 0>
constexpr auto member_count() {
    if constexpr(!test<T, N>()) {
        return N - 1;
    } else {
        return member_count<T, N + 1>();
    }
}
```

If `test<T, N>` is true, it means `N` arguments can successfully construct `T`. Then we recursively try `N + 1` arguments until `test<T, N>` is false. Then `N - 1` is the number of members of `T`. This way, we can get the number of members of `T` using `member_count<T>()`. Let's test the effect.

```cpp
struct A {
    std::string a;
};

static_assert(member_count<A>() == 1);

struct B {
    std::string a;
    int b;
};

static_assert(member_count<B>() == 2);
```

Great, a big success! Does it end here?

## João Baptista

Consider the following three examples:

- LValue Reference

```cpp
struct A {
    int& x;
};

static_assert(member_count<A>() == 1);  /// error
```

- Default Constructor Deleted

```cpp
struct A {
    A() = delete;
};

struct B {
    A a1;
    A a2;
};

static_assert(member_count<B>() == 2);  // error
```

- Array

```cpp
struct C {
    int x[2];
};

static_assert(member_count<C>() == 1);  // error
```

**In these three cases, the original method completely fails. Why is that?**

The main content of this subsection is based on two blog posts by João Baptista:

- [Counting the number of fields in an aggregate in C++20](https://towardsdev.com/counting-the-number-of-fields-in-an-aggregate-in-c-20-c81aecfd725c)
- [Counting the number of fields in an aggregate in C++20 — part 2](https://towardsdev.com/counting-the-number-of-fields-in-an-aggregate-in-c-20-part-2-d3103dec734f)

He summarized the issues in `boost/pfr` and proposed solutions, addressing the three problems mentioned above.

### LValue Reference

The first problem is relatively easy to understand, mainly because conversions produced by `T()` types are all prvalues. Lvalue references cannot bind to prvalues, but rvalue references can.

```cpp
static_assert(!std::is_constructible_v<int&, Any>); // false
static_assert(std::is_constructible_v<int&&, Any>); // true
```

What to do? Actually, there's a clever way to solve this problem.

```cpp
struct Any {
    constexpr Any(int) {}

    template <typename T>
    constexpr operator T& () const;

    template <typename T>
    constexpr operator T&& () const;
};
```

One converts to an lvalue reference, the other to an rvalue reference. If only one of them can match, that one will be chosen. If both can match, the lvalue reference conversion has higher precedence than the rvalue reference conversion and will be preferred, avoiding overload resolution issues.

```cpp
static_assert(std::is_constructible_v<int, Any>);         // true
static_assert(std::is_constructible_v<int&, Any>);        // true
static_assert(std::is_constructible_v<int&&, Any>);       // true
static_assert(std::is_constructible_v<const int&, Any>);  // true
```

Great, first problem solved!

### Default Constructor

Why does it fail if the default constructor is deleted? Do you remember our initial `Point` type?

```cpp
struct Point {
    int x;
    int y;
};
```

Our test results show that `0`, `1`, `2` work, but `3` does not. I can understand why it fails if the number of elements in `{}` exceeds the number of `Point` members. But why does it succeed if the number of elements is less than the number of members? The reason is simple: members that are not **explicitly initialized** will be **value-initialized**. Therefore, the number of arguments in `{}` can be less than the actual number of fields. However, if a field's default constructor is forbidden, value initialization cannot occur, leading to a compilation error.

```cpp
struct A {
    A() = delete;
};

struct B {
    A a1;
    A a2;
    int x;
};
```

For the type below, if we try with `Any`, it should be that `0`, `1` don't work, `2`, `3` work, and `4`, `5`, ... and beyond don't work. This means that at least all members that **cannot be default-initialized** must be initialized. If a type supports default initialization, its valid search range is `[0, N]`, where `N` is its **maximum number of fields**. If it does not support default initialization, then the search range becomes `[M, N]`, where `M` is the minimum number of initializers required to initialize all non-default-initializable members.

Our previous search strategy started from `0`; if the current one was `true`, it would try the next, until `false` was encountered. Clearly, this search strategy is not suitable for the current situation, because in the range `[0, M)`, it would also match the previous search strategy's failure condition. We now need to change it so that it stops searching only if the current one is `true` AND the next one is `false`. This way, we can precisely find the **upper bound of this range**.

```cpp
template <typename T, int N = 0>
constexpr auto member_count() {
    if constexpr(test<T, N>() && !test<T, N + 1>()) {
        return N;
    } else {
        return member_count<T, N + 1>();
    }
}
```

Let's test it.

```cpp
struct A {
    int& x;
};

static_assert(member_count<A>() == 1);

struct B {
    A a1;
    A a2;
};

static_assert(member_count<B>() == 2);
```

`OK`, the second problem is also solved, that's really cool!

### Builtin Array

If there is an array among the struct's members, then the final result of the calculation will treat each member of the array as a separate field. This is essentially because aggregate initialization for standard arrays has a 'backdoor'.

```cpp
struct Array {
    int x[2];
};

Array array{1, 2};  // ok
```

Notice that there's only one field, yet two values can be filled. However, this 'hole' for arrays leads to a dilemma: if a struct contains an array, it will ultimately result in an incorrect count. Is there any way to solve this problem?

_Note: This part might be a bit difficult to understand_

Consider the following example:

```cpp
struct D
{
    int x;
    int y[2];
    int z[2];
}
```

For example, let's look at its initialization cases:

```cpp
D{ 1, 2, 3, 4, 5 } // ok

// Position 0
D{ {1}, 2, 3, 4, 5 } // ok, position 0 can hold at most 1 element
D{ {1, 2}, 3, 4, 5 } // error

// Position 1
D{ 1, {2}, 3, 4, 5 } // error
D{ 1, {2, 3}, 4, 5 } // ok, position 1 can hold at most 2 elements
D{ 1, {2, 3, 4}, 5 } // error

// Position 3
D{ 1, 2, 3, {4}, 5}  // error
D{ 1, 2, 3, {4, 5} } // ok, position 3 can hold at most 2 elements
```

That's right, we can use nested initialization to solve this problem! First, we use the original method to find the maximum possible number of struct fields (including array expansion, which is `5` here). Then, at each position, we try to insert the original sequence into this nested initialization. By continuously trying, we can find the maximum number of elements that can be placed at that position. If the maximum number exceeds `1`, it means this position is an array. This maximum number is the number of elements in the array. We just subtract the excess quantity from the final result.

**Sounds simple, but it's a bit complex to implement.**

First, let's write a helper function. By filling in different `N1`, `N2`, `N3`, we can correspond to the different cases above. Note that `Any` at `I2` is nested initialization, with an extra pair of braces.

```cpp
template <typename T, std::size_t N1, std::size_t N2, std::size_t N3>
constexpr bool test_three_parts() {
    return []<std::size_t... I1, std::size_t... I2, std::size_t... I3>(std::index_sequence<I1...>,
                                                                       std::index_sequence<I2...>,
                                                                       std::index_sequence<I3...>) {
        return requires { T{Any(I1)..., {Any(I2)...}, Any(I3)...}; };
    }(std::make_index_sequence<N1>{}, std::make_index_sequence<N2>{}, std::make_index_sequence<N3>{});
}
```

Next, we need to write a function to test if it's feasible to place `N` elements using two layers of `{}` at a specified position.

```cpp
template <typename T, std::size_t position, std::size_t N>
constexpr bool try_place_n_in_pos() {
    // Maximum possible number of fields
    constexpr auto Total = member_count<T>();
    if constexpr(N == 0) {
        // Placing 0 elements has the same effect as original, definitely feasible
        return true;
    } else if constexpr(position + N <= Total) {
        // The sum of elements definitely cannot exceed the total
        return test_three_parts<T, position, N, Total - position - N>();
    } else {
        return false;
    }
}
```

Since there's a lot of content, it might be a bit difficult to understand. Let's first show the test results of this function for easier understanding. This way, even if you don't understand the function implementation, it's fine. Let's use the previous struct `D` as an example again.

```cpp
try_place_n_in_pos<D, 0, 1>();
// This is testing the case D{ {1}, 2, 3, 4, 5 }
// placing 1 element at position 0

try_place_n_in_pos<D, 1, 2>();
// This is testing the case D{ 1, {2, 3}, 4, 5 }
// placing 2 elements at position 1
```

Alright, just understand what this function is doing. It keeps trying at a certain position, and then it can find the maximum number of elements that can be placed at that position.

```cpp
template <typename T, std::size_t pos, std::size_t N = 0>
constexpr auto search_max_in_pos() {
    constexpr auto Total = member_count<T>();
    std::size_t result = 0;
    [&]<std::size_t... Is>(std::index_sequence<Is...>) {
        ((try_place_n_in_pos<T, pos, Is>() ? result = Is : 0), ...);
    }(std::make_index_sequence<Total + 1>());
    return result;
}
```

This is where we search for the maximum number of elements that can be placed at this position.

```cpp
static_assert(search_max_in_pos<D, 0>() == 1);  // Position 0 can hold at most 1 element
static_assert(search_max_in_pos<D, 1>() == 2);  // Position 1 can hold at most 2 elements
static_assert(search_max_in_pos<D, 3>() == 2);  // Position 3 can hold at most 2 elements
```

This is consistent with our initial manual test results. Next, we iterate through all positions, find all additional array element counts, and then subtract these excess amounts from the initial maximum count.

```cpp
template <typename T, std::size_t N = 0>
constexpr auto search_all_extra_index(auto&& array) {
    constexpr auto total = member_count<T>();
    constexpr auto num = search_max_in_pos<T, N>();
    constexpr auto value = num > 1 ? num : 1;
    array[N] = value;
    if constexpr(N + value < total) {
        search_all_extra_index<T, N + value>(array);
    }
}
```

Here, it's a recursive search, with results stored in an array. Note `N + value` here. If two elements are found here, we can directly skip two positions forward. For example, if position `1` can hold `2` elements, I can directly look for position `3`, no need to check position `2`.

Next, we just store all results in an array and then subtract the excess.

```cpp
template <typename T>
constexpr auto true_member_count() {
    constexpr auto Total = member_count<T>();
    if constexpr(Total == 0) {
        return 0;
    } else {
        std::array<std::size_t, Total> indices = {1};
        search_all_extra_index<T>(indices);
        std::size_t result = Total;
        std::size_t index = 0;
        while(index < Total) {
            auto n = indices[index];
            result -= n - 1;
            index += n;
        }
        return result;
    }
}
```

Let's test the result.

```cpp
struct D {
    int x;
    int y[2];
    int z[2];
};

static_assert(true_member_count<D>() == 3);

struct E {
    int& x;
    int y[2][2];
    int z[2];
    int&& w;
};

static_assert(true_member_count<E>() == 4);
```

Let's take the array generated by type `E` as an example here; we can print them all out to see.

```cpp
index: 0 num: 1  // Position 0 corresponds to x, count is 1, reasonable
index: 1 num: 4  // Position 1 corresponds to y, count is 4, reasonable
index: 5 num: 2  // Position 5 corresponds to z, count is 2, reasonable
index: 7 num: 1  // Position 7 corresponds to w, count is 1, reasonable
```

A perfect curtain call! I really admire the author's idea; it's so ingenious and breathtaking. However, at the end of the article, he said,

> As it could be seen, I ran into some inconsistencies between gcc and clang (and for some reason I haven’t managed to make it work on MSVC at all, but that is another story).

He said he encountered inconsistencies in behavior between Clang and GCC, and couldn't get this method to work on MSVC at all.

**It seems things are far from over!**

## YKIKO

I spent some time understanding the previous author's article. To be honest, his template code was very difficult for me to read. He didn't like using `if constexpr` for branching, instead using many specializations for selection, which greatly impacted readability. Therefore, the code presented earlier is not entirely the original author's code, but rather my interpretation in a more readable form.

What situations would `break` the second author's code?

- Move constructor deleted

```cpp
struct X {
    X(X&&) = delete;
};

struct F {
    X x;
};

static_assert(true_member_count<F>() == 1);  // error
```

- Struct contains other struct members

```cpp
struct Y {
    int x;
    int y;
};

struct G {
    Y x;
    int y;
};

static_assert(true_member_count<G>() == 2);  // error
```

- MSVC and GCC bugs

### Move Constructor

All of this stems from a new rule introduced in `C++17` regarding [copy elision](https://en.cppreference.com/w/cpp/language/copy_elision).

> Since C++17, a prvalue is not materialized until needed, and then it is constructed directly into the storage of its final destination. This sometimes means that even when the language syntax visually suggests a copy/move (e.g. copy initialization), no copy/move is performed — which means the type need not have an accessible copy/move constructor at all.

What does this mean? An example will make it clearest.

```cpp
struct M {
    M() = default;
    M(M&&) = delete;
};

M m1 = M();             // ok in C++17, error in C++14
M m2 = std::move(M());  // error
```

Huh? Why is this happening? The first one compiles, but the second one doesn't. Did I write `std::move` unnecessarily?

The reason the second one fails to compile is quite understandable: because the move constructor was deleted, so it couldn't be called, leading to a compilation failure. Note that the behavior of the first case is different in `C++14` and `C++17`. In `C++14`, a temporary object is first created, then the move constructor is called to initialize `m1`. However, this behavior is actually redundant, so the compiler might optimize away this unnecessary step. But there was still a possibility of calling the move constructor, so if it was deleted, it would `GG` (game over) and fail to compile. **In C++17, this optimization became a language-mandated requirement**, so there is no **move construction** step at all, and naturally, no accessible constructor is needed, thus it compiles successfully in `C++17`.

**This also means there's a difference even among rvalues**. `prvalue`, i.e., pure rvalues, can directly construct objects via copy elision (for example, the return value of a **non-reference type** function here is a prvalue), but `xvalue`, i.e., expiring values, must have a callable move constructor and cannot undergo copy elision (the return value of an **rvalue reference type** function is an xvalue). Therefore, `std::move` actually had a negative effect here.

Back to our problem, note that `Any` has a conversion function that converts to an rvalue reference type, so if this situation is encountered, there's no way around it. But with another clever modification, this problem can be solved again:

```cpp
struct Any {
    constexpr Any(int) {}

    template <typename T>
        requires std::is_copy_constructible_v<T>
    operator T& ();

    template <typename T>
        requires std::is_move_constructible_v<T>
    operator T&& ();

    template <typename T>
        requires (!std::is_copy_constructible_v<T> && !std::is_move_constructible_v<T>)
    operator T ();
};
```

Note that we've added constraints to the types here. If it's a non-movable type (move constructor deleted), it corresponds to the last type conversion function, directly producing a prvalue to construct the object. This cleverly solves the problem. The constraint for copy construction is to prevent overload resolution ambiguity (and can also fix an MSVC bug at the end).

### Nested Struct

In fact, the author's original idea was good, but overlooked a problem, which is that **not only array types can be initialized with double braces** `{{}}`, structs can too.

```cpp
struct A {
    int x;
    int y;
};

struct B {
    A x;
    int y;
};

B{{1, 2}, 3};  // ok
```

Therefore, if this position is a struct member, it will lead to an incorrect count. So we need to first determine if this position is a struct. If it is, there's no need to try to find the maximum number of elements to place at this position; just move on to the next position.

So how do we determine if the member at the current position is a struct? Consider the following example:

```cpp
struct A {
    int x;
    int y;
};

struct B {
    A x;
    int y[2];
};
```

Manually enumerate the test cases:

```cpp
B{any, any, any};         // ok
B{{any}, any, any};       // ok
B{{any, any}, any, any};  // ok

B{any, {any}, any};       // error
B{any, {any, any}, any};  // error
```

`OK`, the answer is quite obvious: if the current position is a struct, extra elements can be added to it. Note that the original `Total`, i.e., the maximum possible number of elements, is `3`. But if the current position is a struct, placing `4` elements is also possible, but it's not possible if it's an array. We use this property to determine if the current position is a struct. If it is, we skip to the next position; if not, we search for the maximum number of elements that can be placed at this position.

Essentially, it's recursively trying to place elements at this position. But there's a problem here: the struct member at the current position might still contain members that cannot be default-initialized. So how many elements need to be placed to determine if this position can be initialized? This is still uncertain. I've set the maximum upper limit here to `10`. If the non-default-initializable members in the sub-struct are located after `10`, this method will fail.

```cpp
template <typename T, std::size_t pos, std::size_t N = 0, std::size_t Max = 10>
constexpr bool has_extra_elements() {
    constexpr auto Total = member_count<T>();
    if constexpr(test_three_parts<T, pos, N, Total - pos - 1>()) {
        return false;
    } else if constexpr(N + 1 <= Max) {
        return has_extra_elements<T, pos, N + 1>();
    } else {
        return true;
    }
}
```

With this function, we just need to slightly modify the logic of the original `search` function.

```cpp
template <typename T, std::size_t pos, std::size_t N = 0>
constexpr auto search_max_in_pos() {
    constexpr auto Total = member_count<T>();
    if constexpr(!has_extra_elements<T, pos>()) {
        return 1;
    } else {
        // ... unchanged
    }
}
```

It's just adding a branch condition: if there are no extra elements at the current position, it directly returns `1`; if there are, it searches for the maximum boundary (of the array). This way, the problem in the original author's code is solved.

Let's test it again.

```cpp
struct Y {
    int x;
    int y;
};

struct G {
    Y x;
    int y;
};

static_assert(true_member_count<G>() == 2);  // ok
```

Success!

### Compiler Bug

I also found the GCC and MSVC issues mentioned by the author in the original article. MSVC currently has a [defect](https://developercommunity.visualstudio.com/t/MSVC-accepts-invalid-initialization-of-a/10541811):

```cpp
struct Any {
    template <typename T>
    // requires std::is_copy_constructible_v<T>
    operator T& () const;
};

struct A {
    int x[2];
};

A a{Any{}};
```

The code above compiles successfully, which means MSVC allows aggregate initialization of array members directly from an array reference. However, this is not allowed by the C++ standard. This bug leads to incorrect member counting on MSVC. The solution is actually very simple: we've already incidentally solved this problem earlier; just uncomment that line. Because arrays are non-copy-constructible types, the constraint will exclude this overloaded function, thus preventing this issue.

GCC13 also has a serious [defect](https://gcc.gnu.org/bugzilla/show_bug.cgi?id=113141), which directly leads to an ICE (Internal Compiler Error). This bug can be reproduced with the following lines of code:

```cpp
struct Number {
    int x;

    operator int& () {
        return x;
    }
};

struct X {
    int& x;
};

template <typename T>
concept F = requires { T{{Number{}}}; };

int main() {
    static_assert(!F<X>);  // internal compiler error
}
```

This clearly shouldn't lead to an ICE, and it's very strange that this bug only exists in GCC13. The test code is on [godbolt](https://godbolt.org/z/jW4YWYf1P). Clang has no issues, but GCC directly throws an internal compiler error. And GCC12 and Clang have different compilation results, but `clang` is actually correct. This is where the original author's article mentioned inconsistencies between Clang and GCC.

> _Note: As reminded in the comments section, Clang15 also encounters similar internal compiler errors._

## Afterword

Later, after some discussion with people in the comments section, the above handling still had some shortcomings. A typical example is when a member variable's constructor is a template function, it will cause an error, for example, `std::any`. The reason is that it doesn't know whether to call the **type conversion function** or the **template constructor** (overload resolution failure).

```cpp
std::any any = Any(0); // conversion from 'Any' to 'std::any' is ambiguous
// candidate: 'Any::operator T&() [with T = std::any]'
// candidate: 'std::any::any(_Tp&&)
```

However, there is currently no perfect solution to this problem. Directly checking if `T` can be constructed from `Any` cannot solve this problem, as it would involve recursive constraints, ultimately leading to unsolvable problems and compilation errors. Here, a rather clever trick was used:

```cpp
struct Any {
    constexpr Any(int) {}

    template <typename T>
        requires (std::is_copy_constructible_v<T>)
    operator T& ();

    template <typename T>
        requires (std::is_move_constructible_v<T> && !std::is_copy_constructible_v<T>)
    operator T&& ();

    struct Empty {};

    template <typename T>
        requires (!std::is_copy_constructible_v<T> && !std::is_move_constructible_v<T> &&
                  !std::is_constructible_v<T, Empty>)
    operator T ();
};
```

It declares an empty class, and then tries to see if this empty class can be converted to type `T`. If not, it means `T`'s constructor should not be a template function, and thus the type conversion can take effect. If it can, it means `T`'s constructor is a template function, and this type conversion function should be excluded. Of course, if `T`'s constructor has some strange constraints, for example, explicitly excluding `Empty` but accepting `Any`, this would still lead to an error. But this would be intentional. Under normal circumstances, this problem is unlikely to be encountered, so this problem can be considered solved.

In addition, there's another issue related to references: if a struct contains a reference member of a non-copyable/non-movable type, it will also fail. Let's take an lvalue reference as an example below.

```cpp
struct CanNotCopy {
    CanNotCopy(const CanNotCopy&) = delete;
};

struct X {
    CanNotCopy& x;
};

X x{Any(0)};  // error
```

Here, `T` will be instantiated as `CanNotCopy` type. Clearly, because it's non-copyable, overload resolution selects `operator T()`, but the actual result is an rvalue that cannot bind to an lvalue reference, leading to a compilation error. Can this problem be solved? It's very difficult. In fact, we cannot make the following two expressions simultaneously valid:

```cpp
struct X {
    CanNotCopy& x;
};

struct Y {
    CanNotCopy x;
};

X x{Any(0)};
Y y{Any(0)};
```

In these two aggregate initializations, the `T` instantiated by the type conversion function is `CanNotCopy` type. But if we want both `x` and `y` to be well-formed, it means for the same `T`, two different overloaded functions must be chosen: the first choosing `operator T&()`, the second choosing `operator T()`. However, there is no precedence between these two functions, and C++ cannot overload based on return type, so this cannot be done. One possible solution is to write three `Any` types, converting to `T&`, `T&&`, and `T` respectively, and then try these three at each position. This way, the problem could indeed be solved, **but it could lead to an exponential increase in the number of template instantiations at a rate of 3^N**. This implementation would have a greater overhead than all previous iteration methods combined, so I won't demonstrate it here. Theoretically feasible, but practically it would exhaust compilers.

## Conclusion

All the code in this article is available on [Compiler Explorer](https://godbolt.org/z/EsWGnMqb5) and passes on all three major compilers (GCC version 12). There is a lot of test code. If you find other corner cases, feel free to leave a comment and discuss.

Alright, this article ends here. If you've patiently read through the entire article, you're probably like me, enjoying these interesting things. The most interesting aspect of this kind of thing is using the small interfaces exposed by `C++` to gradually extend it and finally achieve very elegant interfaces. Of course, for the author, it's not actually elegant `OvO`. In short, this kind of thing is like a game, a daily pastime. Finding `bugs` in `C++` compilers and delving into these obscure features is also a pleasure. If we must talk about practical value, **this kind of thing is almost impossible to use in a real-world production code environment**. Firstly, finding the number of struct fields by instantiating a large number of templates will significantly slow down compilation speed. Moreover, even with such a great effort, it only achieves iteration over aggregate types and does not support non-aggregate types. Not only are the side effects strong, but the main functionality is also not strong. Considering the trade-offs, it's very much not worth it. For such needs resembling reflection, before C++ adds static reflection, the currently truly feasible automated solution is to use code generation for this task.

I also have related articles that detail the principles, providing solutions that don't rely on these clever tricks and are truly usable in real-world projects: [A Reflection Tutorial for C++ Programmers](https://www.ykiko.me/en/articles/669358870).

Of course, if these functionalities are used merely for logging, debugging, or learning the principles of how templates work, and not for any core code parts, and you don't want to introduce heavy dependencies, then using these things might not be a bad idea.
