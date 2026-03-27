---
series:
  - STMP
series_order: 2
title: "C++ Forbidden Black Magic: STMP (Part 2)"
date: "2023-07-30 01:29:27"
updated: "2026-03-14 15:14:29"
zhihu_article_id: "646812253"
zhihu_url: https://zhuanlan.zhihu.com/p/646812253
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

In the previous [article](https://www.ykiko.me/en/articles/646752343), we gained a preliminary understanding of the principles of STMP and used it to implement a simple compile-time counter. However, its power extends far beyond that. This article will discuss some advanced applications based on STMP.

## type <=> value

In C++, the need for computations on types has always existed, for example:

- `std::variant` allows duplicate template parameters, but this requires constructing it with `in_place_index`, which is cumbersome. We can deduplicate the type list before using `variant` to solve this problem.
- It's necessary to sort `variant` type lists. After sorting, identical types, such as `std::variant<int, double>` and `std::variant<double, int>`, can share the same code, reducing binary bloat.
- Get a type from a type list based on a given index.
- Map function parameters in a reordered way, often used for automatic cross-language binding generation.

And so on, I won't list them all here. However, in C++, types are not first-class citizens and can only be passed as template parameters. To perform computations on types, we often have to resort to obscure template metaprogramming. It would be great if types could be passed to `constexpr` functions for computation just like values, making type computations much simpler. Direct passing is certainly impossible. Consider establishing a one-to-one mapping between types and values: map types to values before computation, and then map values back to types after computation. This can also fulfill our requirements.

### type -> value

First, consider mapping types to values:

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

By leveraging the characteristic that static variable addresses of different template instantiations are also different, we can easily map types to unique values (addresses).

### value -> type

How do we map values back to types? Consider using naive template specialization:

```cpp
template <meta_value value>
struct type_of;

template <>
struct type_of<value_of<int>()> {
    using type = int;
};

// ...
```

This certainly works, but it requires us to specialize all types we intend to use beforehand, which is impractical for most programs. Is there a way to add this specialization at evaluation time? The answer is the friend injection we mentioned in the previous article.

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

Then, we just need to instantiate a `setter` simultaneously with `value_of` to complete the registration:

```cpp
template <typename T>
consteval meta_value value_of() {
    constexpr auto value = &storage<T>::value;
    setter<value, T> setter;
    return value;
}
```

Finally, `type_of` can be implemented by directly reading the registered result through `reader`:

```cpp
template <meta_value value>
using type_of = typename decltype(to_type(reader<value>{}))::type;
```

### sort types!

Without further ado, let's try to sort a `type_list` using `std::sort`:

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

`type_list` is a simple type container. `array_to_list` is used to map types from `std::array` back to `type_list`. `sort_list` is the specific implementation of sorting. The process is to first map all types into a `std::array`, then sort this array using `std::ranges::sort`, and finally map the sorted `std::array` back to `type_list`.

Let's test it:

```cpp
using list = type_list<int, char, int, double, char, char, double>;
using sorted = typename sort_list<list>::result;
using expected = type_list<char, char, char, int, int, double, double>;
static_assert(std::is_same_v<sorted, expected>);
```

All three major compilers compile this successfully with C++20! The code is available on [Compiler Explorer](https://godbolt.org/z/4qW7MhfWP). To prevent link rot, a copy is also available on [Github](https://github.com/16bit-ykiko/about-me/blob/main/code/type-list-sort.cpp).

> It's worth noting that this bidirectional mapping between types and values has become a built-in language feature in Reflection for C++26. We no longer need to use clever tricks like friend injection; we can directly use the `^^` and `[: :]` operators to achieve the mapping. See [Reflection for C++26!!!](https://www.ykiko.me/en/articles/1919923607997518115) for details.

## the true any

`std::any` is often used for type erasure, allowing completely different types to be stored in the same container. However, erasure is easy, but restoration is difficult, especially when you want to print the object stored in `any`; you have to `cast` each type individually. Is there a possibility of writing a "true" `any` type? One that doesn't require us to manually `cast` and can directly call member functions corresponding to the type it holds?

For a single compilation unit, this is entirely possible, because the set of types constructed into `any` within a single compilation unit is determined at compile time. We only need to record all instantiated types and then automatically try each type using template metaprogramming.

### type register

First, let's consider how to register types:

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

We still use `setter` to register types. `lookup` is used to find the index of a type in the type set. The principle is to iterate through the set, compare each type with `is_same_v`, and return the corresponding index if found. If not found by the end, a new type is registered. `count` is used to calculate the size of the type set.

### any type

Next, we define a simple `any` type and a `make_any` function to construct `any` objects:

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

> Why write a separate `make_any` instead of directly writing a template constructor? This is because after my actual attempts, I found that the three major compilers instantiate template constructors in different and sometimes strange locations, leading to different evaluation results. However, for ordinary template functions, the instantiation locations are consistent, so I wrote it as a separate function.

### visit it!

Here comes the highlight: we can implement a function similar to `std::visit` to access `any` objects. It takes a callback function, then iterates through the `any` object's type set. If it finds the corresponding type, it converts `any` to that type and then calls the callback function.

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

Now let's try it:

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

All three major compilers output the results as we expected! The code is also available on [Compiler Explorer](https://godbolt.org/z/aP3zs7479) and [Github](https://github.com/16bit-ykiko/about-me/blob/main/code/the-true-any.cpp).

## conclusion

These two articles on STMP fulfill a long-standing wish of mine. Before this, I had been thinking about how to implement a "true" `any` type, like the code above, without requiring the user to register types beforehand. I tried many methods, but none succeeded. However, the emergence of STMP gave me hope. After realizing the heights it could reach, I immediately stayed up all night to write the articles and examples.

Of course, it's not recommended to use this technique in actual projects. Because this kind of code relies heavily on the instantiation location of templates, it can easily lead to ODR violations, and repeated instantiations will significantly increase compilation time. For such stateful code requirements, we can often transform them into stateless code, but pure manual implementation might be extremely laborious. It's more recommended to use code generators for additional code generation to fulfill this requirement. For example, we could use `libclang` to collect all `any` instantiation information across compilation units and then generate a corresponding table.
