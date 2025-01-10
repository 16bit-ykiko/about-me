---
title: 'A 7-Year Relay Race: Obtaining the Number of Fields in a C++ Struct'
date: 2023-12-26 04:45:30
updated: 2024-11-30 18:24:28
---

## Introduction

In `C++17`, a feature called **structured binding** was introduced, also known as `Struct Bind`. This feature is similar to pattern matching in other languages, allowing us to conveniently access the members of a structure.

```cpp
struct Point { int x; int y; };

Point p = {1, 2};
auto [x, y] = p;
// x = 1, y = 2
```

Using this, we can implement some interesting functionalities, including *limited* reflection capabilities for structures, such as implementing a `for_each` function.

```cpp
void for_each(auto&& object, auto&& func)
{
    using T = std::remove_cvref_t<decltype(object)>;
    if constexpr (std::is_aggregate_v<T>)
    {
        auto&& [x, y] = object;
        for_each(x, func);
        for_each(y, func);
    }
    else
    {
        func(object);
    }
}
```

This way, for any aggregate type with two members, we can traverse it.

```cpp
struct Point { int x; int y; };
struct Line { Point start; Point end; };

Line line = {{ 1, 2 }, { 3, 4 }};
for_each(line, [](auto&& object)
{
    std::cout << object << std::endl;
    // 1 2 3 4
});
```

However, there is a problem: this only recursively supports structures with exactly `2` fields. If you try to use a structure with `3` fields, the compiler will throw a `hard error`. That is, the number of structured bindings is incorrect, and it cannot be handled by `SFINAE` or `requires`, causing the compilation to abort directly.

```cpp
struct Vec3 { float x; float y; float z; };

// Inside is a lambda
constexpr auto value = requires{ [](){ auto [x, y] = Vec3{ 1, 2, 3 }; }; };
// hard error
```

We can solve this problem by manually dispatching.

```cpp
if constexpr(N == 1)
{
    auto&& [x] = object;
    // ...
}
else if constexpr(N == 2)
{
    auto&& [x, y] = object;
    // ...
}
else if constexpr(N == 3)
{
    auto&& [x, y, z] = object;
    // ...
}
// ...
```

You can freely enumerate up to the number of fields you want to support. Here, `N` is the number of fields in the structure. You may need to pass it explicitly as a template parameter or specialize a template for each type, storing its number of fields. However, this is still cumbersome. Is there a way to let the compiler automatically calculate the number of fields in a structure?

## First Leg: Antony Polukhin

A preliminary solution was provided in [boost/pfr](https://www.boost.org/doc/libs/1_75_0/doc/html/boost_pfr.html). Its author, Antony Polukhin, gave detailed introductions at [CppCon2016](https://www.youtube.com/watch?v=abdeAew3gmQ) and [CppCon2018](https://www.youtube.com/watch?v=UlNUNxLtBI0). However, the author used `C++14/17`, and the code was quite obscure. After rewriting it in `C++20`, the readability improved significantly.

First, in `C++`, we can write an `Any` type that supports conversion to any type. Essentially, we just need to template the [type conversion function](https://en.cppreference.com/w/cpp/language/cast_operator).

```cpp
struct Any
{
    constexpr Any(int){}; // Supports construction from int

    template<typename T>
    constexpr operator T() const;
};

static_assert(std::is_convertible_v<Any, int>); // true
static_assert(std::is_convertible_v<Any, std::string>); // true
```

Then, we can utilize the feature of aggregate initialization: for expressions that exceed the maximum number of aggregate initializations, the `requires` statement will return `false`.

```cpp
struct Point { int x; int y; };

template<typename T, std::size_t N>
constexpr auto test()
{
    // Use make_index_sequence to construct N parameters
    return []<std::size_t... I>(std::index_sequence<I...>)
    {
        return requires{ T{ Any(I)... }; }; 
    }(std::make_index_sequence<N>{});
}

static_assert(test<Point, 0>()); // true
static_assert(test<Point, 1>()); // true
static_assert(test<Point, 2>()); // true
static_assert(!test<Point, 3>()); // false
```

Notice that `Point` only has two members. When we pass three parameters to the initialization list, `requires` will return `false`. Using this feature, we can turn the above trial process into a recursive one, linearly searching the sequence until we find `false`.

```cpp
template<typename T, int N = 0>
constexpr auto member_count()
{
    if constexpr(!test<T, N>())
    {
        return N - 1;
    }
    else
    {
        return member_count<T, N + 1>();
    }
}
```

If `test<T, N>` is true, it means `N` parameters can successfully construct `T`. Then we recursively try `N + 1` parameters until `test<T, N>` is false, and `N - 1` is the number of members in `T`. This way, we can get the number of members in `T` through `member_count<T>()`. Let's test it.

```cpp
struct A{ std::string a; };
static_assert(member_count<A>() == 1);

struct B{ std::string a; int b; };
static_assert(member_count<B>() == 2);
```

Great, it's a success! Is this the end of the story?

## Second Leg: João Baptista

Consider the following three examples:

- Lvalue reference

```cpp
struct A{ int& x; };
static_assert(member_count<A>() == 1); // error
```

- Default constructor deleted

```cpp
struct X { X() = delete; } // Default constructor deleted
struct B{ X x; X y; };
static_assert(member_count<B>() == 2); // error
```

- Arrays

```cpp
struct C { int x[2]; };
static_assert(member_count<C>() == 1); // error
```

**In these three cases, the original method completely fails. Why is that?**

This section mainly references two blogs by João Baptista:

- [Counting the number of fields in an aggregate in C++20](https://towardsdev.com/counting-the-number-of-fields-in-an-aggregate-in-c-20-c81aecfd725c) 
- [Counting the number of fields in an aggregate in C++20 — part 2](https://towardsdev.com/counting-the-number-of-fields-in-an-aggregate-in-c-20-part-2-d3103dec734f)

He summarized the issues in `boost/pfr` and proposed solutions to the three problems mentioned above.

### The Lvalue Reference Problem

The first problem is relatively easy to understand. It's mainly because the conversion produced by `T()` type generates pure rvalues, and lvalue references cannot bind to pure rvalues. If it were an rvalue reference, it would work.

```cpp
static_assert(!std::is_constructible_v<int&, Any>); // false
static_assert(std::is_constructible_v<int&&, Any>); // true
```

How to solve it? There's a clever way to handle this:

```cpp
struct Any
{
    constexpr Any(int) {}; // Supports construction from int

    template<typename T>
    constexpr operator T&() const;

    template<typename T>
    constexpr operator T&&() const;
};
```

One converts to an lvalue reference, and the other to an rvalue reference. If only one of them matches, that one will be chosen. If both can match, the lvalue reference conversion has higher priority and will be chosen first, avoiding overload resolution issues.

```cpp
static_assert(std::is_constructible_v<int, Any>); // true
static_assert(std::is_constructible_v<int&, Any>); // true
static_assert(std::is_constructible_v<int&&, Any>); // true
static_assert(std::is_constructible_v<const int&, Any>); // true
```

Great, the first problem is solved!

### The Default Constructor Problem

Why does deleting the default constructor cause issues? Remember our initial `Point` type?

```cpp
struct Point{ int x; int y; };
```

Our test results show that `0`, `1`, and `2` work, but `3` doesn't. If the number of parameters in `{ }` exceeds the number of members in `Point`, causing failure, I can understand. But why does it succeed when there are fewer parameters than the actual number of members? The reason is simple: members that are not explicitly initialized will be value-initialized. Thus, the number of parameters in `{ }` can be less than the actual number of fields. However, if a field prohibits default construction, value initialization is not possible, leading to a compilation error.

```cpp
struct X { X() = delete; } // Default constructor deleted
struct B
{  
    X x; 
    X y; 
    int z; 
};
```

For this type, if we try with `Any`, it should be that `0` and `1` don't work, but `2` and `3` do, and `4`, `5`, etc., don't work. That is, at least all members that cannot be default-initialized must be initialized. If a type supports default initialization, the valid search interval is `[0, N]`, where `N` is its maximum number of fields. If it doesn't support default initialization, the search interval becomes `[M, N]`, where `M` is the minimum number of parameters required to initialize all members that cannot be default-initialized.

Our previous search strategy started from `0`. If the current one is `true`, we try the next one until we find `false`. Clearly, this search strategy is not suitable for the current situation because in the interval `[0, M)`, it also fits the case where the search fails. Now, we need to change it so that if the current one is `true` and the next one is `false`, we stop the search, which will find the upper bound of the interval.

```cpp
template<typename T, int N = 0>
constexpr auto member_count()
{
    if constexpr(test<T, N>() && !test<T, N + 1>())
    {
        return N;
    }
    else
    {
        return member_count<T, N + 1>();
    }
}
```

Let's test it.

```cpp
struct A{ int& x; };
static_assert(member_count<A>() == 1); 

struct X { X() = delete; }; // Default constructor deleted
struct B{ X x; X y; };
static_assert(member_count<B>() == 2);
```

`OK`, the second problem is solved. That's awesome!

### The Array Problem

If there are arrays in the structure's members, the final result will count each element of the array as a separate field. This is because aggregate initialization of standard arrays has a backdoor.

```cpp
struct Array { int x[2]; };
Array{ 1, 2 }; // OK
```

Notice that there's only one field but two values can be filled. However, this backdoor for arrays leads to a dilemma: if a structure contains arrays, the final count will be incorrect. Is there any way to solve this problem?

*Note: The following part might be a bit hard to understand.*

Consider the following example:

```cpp
struct D
{
    int x;
    int y[2];
    int z[2];
}
```

Let's look at its initialization:

```cpp
D{ 1, 2, 3, 4, 5 } // OK

// Position 0
D{ {1}, 2, 3, 4, 5 } // OK, position 0 can hold at most 1 element
D{ {1, 2}, 3, 4, 5 } // Error 

// Position 1
D{ 1, {2}, 3, 4, 5 } // Error
D{ 1, {2, 3}, 4, 5 } // OK, position 1 can hold at most 2 elements
D{ 1, {2, 3, 4}, 5 } // Error

// Position 3
D{ 1, 2, 3, {4}, 5} // Error
D{ 1, 2, 3, {4, 5} } // OK, position 3 can hold at most 2 elements
```

Yes, we can use nested initialization to solve this problem! First, we use the original method to find the maximum possible number of fields in the structure (including array expansion, which is 5 here). Then, we try to fit the original sequence into this nested initialization at each position. By continuously trying, we can find the maximum number of elements that can be placed at this position. If the maximum number exceeds `1`, it means this position is an array. This maximum number is the number of elements in the array, and we subtract the extra numbers from the final result.

**It sounds simple, but the implementation is a bit complicated.**

First, write a helper function to assist. By filling in different `N1`, `N2`, `N3`, we can correspond to the above different situations. Note that `Any` in `I2` is nested initialization, with an extra layer of parentheses.

```cpp
template<typename T, std::size_t N1, std::size_t N2, std::size_t N3>
constexpr bool test_three_parts()
{
    return []<std::size_t... I1, std::size_t... I2, std::size_t... I3>
    (std::index_sequence<I1...>, std::index_sequence<I2...>, std::index_sequence<I3...>)
    {
        return requires{ T{ Any(I1)..., { Any(I2)... }, Any(I3)... }; };
    }(std::make_index_sequence<N1>{}, std::make_index_sequence<N2>{}, std::make_index_sequence<N3>{});
}
```

Next, we need to write a function to test whether placing `N` elements at a specified position with double `{ }` is feasible.

```cpp
template <typename T, std::size_t position, std::size_t N>
constexpr bool try_place_n_in_pos()
{
    constexpr auto Total = member_count<T>(); // Maximum possible number of fields
    if constexpr (N == 0) // Placing 0 elements is the same as the original effect, definitely feasible
    {
        return true;
    }
    else if constexpr (position + N <= Total) // The sum of elements cannot exceed the total
    {
        return test_three_parts<T, position, N, Total - position - N>();
    }
    else 
    {
        return false;
    }
}
```

Since there's a lot of content, it might be hard to understand. Here, we'll first show the test results of this function to help understand. If you don't understand the function implementation, it's okay. Let's take the previous structure `D` as an example.

```cpp
try_place_n_in_pos<D, 0, 1>(); 
// This is testing D{ {1}, 2, 3, 4, 5 }
// Placing 1 element at position 0

try_place_n_in_pos<D, 1, 2>();
// This is testing D{ 1, {2, 3}, 4, 5 }
// Placing 2 elements at position 1
```

Okay, just understand what this function is doing: trying at a certain position continuously, and then finding the maximum number of elements that can be placed at this position.

```cpp
template<typename T, std::size_t pos, std::size_t N = 0>
constexpr auto search_max_in_pos()
{
    constexpr auto Total = member_count<T>();
    std::size_t result = 0;
    [&]<std::size_t... Is>(std::index_sequence<Is...>)
    { ((try_place_n_in_pos<T, pos, Is>() ? result = Is : 0), ...); }(std::make_index_sequence<Total + 1>());
    return result;
}
```

Here, we search for the maximum number of elements that can be placed at this position.

```cpp
static_assert(search_max_in_pos<D, 0>() == 1); // 1, position 0 can hold at most 1 element
static_assert(search_max_in_pos<D, 1>() == 2); // 2, position 1 can hold at most 2 elements
static_assert(search_max_in_pos<D, 3>() == 2); // 2, position 3 can hold at most 2 elements
```

This matches our initial manual test results. Next, we traverse all positions, find all extra array elements, and subtract these extras from the initial maximum number.

```cpp
template <typename T, std::size_t N = 0>
constexpr auto search_all_extra_index(auto&& array)
{
    constexpr auto total = member_count<T>();
    constexpr auto num = search_max_in_pos<T, N>();
    constexpr auto value = num > 1 ? num : 1;
    array[N] = value;
    if constexpr (N + value < total)
    {
        search_all_extra_index<T, N + value>(array);
    }
}
```

Here, we recursively search, and the results are stored in the array. Note that `N + value`: if we find two elements here, we can directly skip two positions. For example, if position `1` can hold `2` elements, then we can directly go to position `3` without checking position `2`.

Next, we store the results in the array and subtract the extras.

```cpp
template<typename T>
constexpr auto true_member_count