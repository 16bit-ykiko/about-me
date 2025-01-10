---
title: 'C++ Forbidden Dark Magic: STMP (Part 2)'
date: 2023-07-30 09:29:27
updated: 2024-12-18 11:33:47
series: ['STMP']
series_order: 2
---

In the previous [article](https://www.ykiko.me/zh-cn/articles/646752343), we gained a preliminary understanding of the principles of STMP and used it to implement a simple compile-time counter. However, its power extends far beyond that. This article will discuss some advanced applications based on STMP.

## type <=> value 

In C++, the need to perform calculations on types has always existed, such as:

- `std::variant` requires that its template parameters must not be duplicated, so we need to deduplicate the type list.
- Sorting the type list of `variant` so that identical types, such as `std::variant<int, double>` and `std::variant<double, int>`, can share the same code, reducing binary bloat.
- Retrieving a type from a type list based on a given index.
- Mapping function parameters with variable order.

And so on, the list goes on. However, in C++, types are not first-class citizens and can only be passed as template parameters. To perform calculations on types, we often have to resort to obscure template metaprogramming. If types could be passed to constexpr functions like values for computation, calculations on types would become much simpler. Directly passing types is impossible, so consider establishing a one-to-one mapping between types and values. Before computation, map types to values, and after computation, map values back to types, thus achieving our goal.

### type -> value 

First, consider mapping types to values.

```cpp
struct identity {
    int size;
};

using meta_value = const identity*;

template <typename T>
struct storage {
    constexpr inline static identity value = {sizeof(T)};
};

template <typename T>
consteval meta_value value_of() {
    return &storage<T>::value;
}
```

By leveraging the fact that the addresses of static variables in different template instantiations are also different, we can easily map types to unique values (addresses).

### value -> type 

How do we map values back to types? Consider using straightforward template specialization.

```cpp
template <meta_value value>
struct type_of;

template <>
struct type_of<value_of<int>()> {
    using type = int;
};

// ...
```

This works, but it requires us to specialize all the types we want to use in advance, which is impractical for most programs. Is there a way to add this specialization during evaluation? The answer is the friend injection technique we discussed in the previous article.

```cpp
template <typename T>
struct self {
    using type = T;
};

template <meta_value value>
struct reader {
    friend consteval auto to_type(reader);
};

template <meta_value value, typename T>
struct setter {
    friend consteval auto to_type(reader<value>) {
        return self<T>{};
    }
};
```

Then, we just need to instantiate a `setter` while instantiating `value_of` to complete the registration.

```cpp
template <typename T>
consteval meta_value value_of() {
    constexpr auto value = &storage<T>::value;
    setter<value, T> setter;
    return value;
}
```

Finally, we can directly read the registration result through `reader` to implement `type_of`.

```cpp
template <meta_value value>
using type_of = typename decltype(to_type(reader<value>{}))::type;
```

### sort types! 

Without further ado, let's try using `std::sort` to sort a `type_list`.

```cpp
#include <array>
#include <algorithm>

template <typename... Ts>
struct type_list {};

template <std::array types, typename = std::make_index_sequence<types.size()>>
struct array_to_list;

template <std::array types, std::size_t... Is>
struct array_to_list<types, std::index_sequence<Is...>> {
    using result = type_list<type_of<types[Is]>...>;
};

template <typename List>
struct sort_list;

template <typename... Ts>
struct sort_list<type_list<Ts...>> {
    constexpr inline static std::array sorted_types = [] {
        std::array types{value_of<Ts>()...};
        std::ranges::sort(types, [](auto lhs, auto rhs) { return lhs->size < rhs->size; });
        return types;
    }();

    using result = typename array_to_list<sorted_types>::result;
};
```

`type_list` is a simple type container, `array_to_list` is used to map the types in `std::array` back to `type_list`, and `sort_list` is the specific implementation of sorting. The process involves first mapping all types to a `std::array`, then sorting this array with `std::ranges::sort`, and finally mapping the sorted `std::array` back to `type_list`.

Let's test it.

```cpp
using list = type_list<int, char, int, double, char, char, double>;
using sorted = typename sort_list<list>::result;
using expected = type_list<char, char, char, int, int, double, double>;
static_assert(std::is_same_v<sorted, expected>);
```

All three major compilers pass with C++20! The code is available on [Compiler Explorer](https://godbolt.org/z/4qW7MhfWP), and to prevent link failure, it's also on [Github](https://github.com/16bit-ykiko/about-me/blob/main/code/type-list-sort.cpp).

> It's worth mentioning that this bidirectional mapping between types and values has become a built-in feature in Reflection for C++26. We no longer need to rely on friend injection tricks; we can directly use the `^` and `[: :]` operators to complete the mapping. For more details, see [C++26 Static Reflection Proposal Analysis](https://www.ykiko.me/zh-cn/articles/661692275).  

## the true any 

`std::any` is often used for type erasure, allowing completely different types to be erased and placed in the same container. However, erasure is easy, but restoration is difficult, especially when you want to print the object stored in `any` to see what it is, you have to `cast` it one by one. Is it possible to write a true `any` type that doesn't require manual `cast` and can directly call the member functions of the type it contains?

For a single translation unit, this is entirely possible because the set of types constructed as `any` within a single translation unit is determined at compile time. We just need to record all instantiated types and use template metaprogramming to automatically try each type.

### type register 

First, consider how to register types.

```cpp
template <typename T>
struct self {
    using type = T;
};

template <int N>
struct reader {
    friend consteval auto at(reader);
};

template <int N, typename T>
struct setter {
    friend consteval auto at(reader<N>) {
        return self<T>{};
    }
};

template <typename T, int N = 0>
consteval int lookup() {
    constexpr bool exist = requires { at(reader<N>{}); };
    if constexpr(exist) {
        using type = decltype(at(reader<N>{}))::type;
        if constexpr(std::is_same_v<T, type>) {
            return N;
        } else {
            return lookup<T, N + 1>();
        }
    } else {
        setter<N, T> setter{};
        return N;
    }
}

template <int N = 0, auto seed = [] {}>
consteval int count() {
    constexpr bool exist = requires { at(reader<N>{}); };
    if constexpr(exist) {
        return count<N + 1, seed>();
    } else {
        return N;
    }
}
```

We still use `setter` to register types. `lookup` is used to find the index of a type in the type set. The principle is to traverse the set and compare each one with `is_same_v`. If found, return the corresponding index. If not found by the end, register a new type. `count` is used to calculate the size of the type set.

### any type 

Next, we define a simple `any` type and a `make_any` function to construct `any` objects.

```cpp
struct any {
    void* data;
    void (*destructor)(void*);
    std::size_t index;

    constexpr any(void* data, void (*destructor)(void*), std::size_t index) noexcept :
        data(data), destructor(destructor), index(index) {}

    constexpr any(any&& other) noexcept : data(other.data), destructor(other.destructor), index(other.index) {
        other.data = nullptr;
        other.destructor = nullptr;
    }

    constexpr ~any() {
        if(data && destructor) {
            destructor(data);
        }
    }
};

template <typename T, typename Decay = std::decay_t<T>>
auto make_any(T&& value) {
    constexpr int index = lookup<Decay>();
    auto data = new Decay(std::forward<T>(value));
    auto destructor = [](void* data) { delete static_cast<Decay*>(data); };
    return any{data, destructor, index};
}
```

> Why write a separate `make_any` instead of a template constructor? Because in my actual attempts, I found that the three major compilers have different and somewhat strange instantiation locations for template constructors, leading to different evaluation results. However, for ordinary template functions, the instantiation locations are the same, so I wrote it as a separate function. 

### visit it! 

The highlight is here. We can implement a function similar to `std::visit` to access `any` objects. It accepts a callback function, then traverses the type set of the `any` object. If it finds the corresponding type, it converts `any` to that type and calls the callback function.

```cpp
template <typename Callback, auto seed = [] {}>
constexpr void visit(any& any, Callback&& callback) {
    constexpr std::size_t n = count<0, seed>();
    [&]<std::size_t... Is>(std::index_sequence<Is...>) {
        auto for_each = [&]<std::size_t I>() {
            if(any.index == I) {
                callback(*static_cast<type_at<I>*>(any.data));
                return true;
            }
            return false;
        };
        return (for_each.template operator()<Is>() || ...);
    }(std::make_index_sequence<n>{});
}
```

Then let's try it out.

```cpp
struct String {
    std::string value;

    friend std::ostream& operator<< (std::ostream& os, const String& string) {
        return os << string.value;
    }
};

int main() {
    std::vector<any> vec;
    vec.push_back(make_any(42));
    vec.push_back(make_any(std::string{"Hello world"}));
    vec.push_back(make_any(3.14));
    for(auto& any: vec) {
        visit(any, [](auto& value) { std::cout << value << ' '; });
        // => 42 Hello world 3.14
    }
    std::cout << "\n-----------------------------------------------------\n";
    vec.push_back(make_any(String{"\nPowerful Stateful Template Metaprogramming!!!"}));
    for(auto& any: vec) {
        visit(any, [](auto& value) { std::cout << value << ' '; });
        // => 42 Hello world 3.14
        // => Powerful Stateful Template Metaprogramming!!!
    }
    return 0;
}
```

All three major compilers output the results as expected! The code is also available on [Compiler Explorer](https://godbolt.org/z/aP3zs7479) and [Github](https://github.com/16bit-ykiko/about-me/blob/main/code/the-true-any.cpp).

## conclusion 

These two articles on STMP fulfill a long-standing wish of mine. Before this, I had been pondering how to implement a true `any` type like the code above, without requiring users to register in advance. I tried many methods but never succeeded. However, the emergence of STMP gave me hope. After realizing the heights it could reach, I immediately stayed up all night to write the article and examples.

Of course, I do not recommend using this technique in any form in actual projects. Since this code heavily relies on the location of template instantiation, it is very prone to ODR violations, and repeated instantiation can significantly increase compilation time. For such stateful code requirements, we can often refactor them into stateless code. However, manually writing this can be very labor-intensive, so it's more recommended to use code generators for additional code generation to meet this requirement. For example, we can use libclang to collect all instantiation information of `any` in the translation unit and then create a corresponding table.

Finally, thank you for reading. I hope these two articles have given you a deeper understanding of C++ templates.