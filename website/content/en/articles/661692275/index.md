---
series:
  - Reflection
series_order: 6
title: C++26 Static Reflection Proposal Analysis
date: "2023-10-16 18:38:26"
updated: "2025-06-22 03:33:38"
zhihu_article_id: "661692275"
zhihu_url: https://zhuanlan.zhihu.com/p/661692275
zhihu_column_id: c_1656510843973046272
zhihu_column_title: 魅力C++
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

Recently, I've been planning to write a series of articles discussing the concept of reflection in detail. Coincidentally, C++26 has a new reflection proposal, and I noticed there aren't many related articles on Zhihu, despite this topic being frequently discussed. So, I'm taking this opportunity to talk about static reflection in C++, as a warm-up for the series.

> This article is outdated. Static reflection has officially entered C++26. Please refer to [Reflection for C++26!!!](https://www.ykiko.me/en/articles/1919923607997518115)

## What is Static Reflection?

First, what exactly is reflection? This term, like many other idioms in computer science, doesn't have a detailed and precise definition. I won't discuss this question in this article; I'll explain it in detail in subsequent articles. The focus of this article is C++'s static reflection. Why emphasize "static"? Mainly because when we usually talk about reflection, we almost always refer to reflection in languages like Java, C#, and Python, and their implementations invariably involve type erasure and querying information at runtime. This approach, of course, has unavoidable runtime overhead, which clearly violates C++'s zero-cost abstraction principle. To distinguish it from their reflection, the qualifier "static" is added, also indicating that C++'s reflection is completed at compile time. Of course, this statement still lacks some rigor. A detailed discussion will be provided in subsequent articles; you just need to know that C++'s static reflection is different from Java, C#, and Python's reflection, and it is primarily completed at compile time.

## What can static reflection do?

### Type as Value

As we all know, with the continuous updates of C++ versions, the capabilities of compile-time computation have been constantly enhanced. Through `constexpr/consteval` functions, we can largely reuse runtime code directly, making compile-time computation convenient. This has completely replaced the method of using template metaprogramming for compile-time computation from a long time ago. It's not only easier to write but also compiles faster.

Observe the following snippets of code for compile-time factorial calculation:

In C++03/98, we could only achieve this through recursive template instantiation, and the code could not be reused at runtime.

```cpp
template<int N>
struct factorial {
    enum { value = N * factorial<N - 1>::value };
};

template<>
struct factorial<0> {
    enum { value = 1 };
};
```

C++11 first introduced the concept of `constexpr` functions, allowing us to write code that can be reused at both compile time and runtime. However, there were many restrictions; without variables and loops, we could only write code in a purely functional style.

```cpp
constexpr int factorial(int n) {
    return n == 0 ? 1 : n * factorial(n - 1);
}

int main() {
    constexpr std::size_t a = factorial(5); // Compile-time calculation
    std::size_t& n = *new std::size_t(6);
    std::size_t b = factorial(n); // Runtime calculation
    std::cout << a << std::endl;
    std::cout << b << std::endl;
}
```

With the arrival of C++14/17, the restrictions in `constexpr` functions were further relaxed. Now, local variables and loops can be used in `constexpr` functions, as shown below:

```cpp
constexpr std::size_t factorial(std::size_t N) {
    std::size_t result = 1;
    for (std::size_t i = 1; i <= N; ++i) {
        result *= i;
    }
    return result;
}
```

After C++20, we can also use `new/delete` at compile time, allowing us to use `vector` in compile-time code. Many runtime codes can be directly reused at compile time without any changes, simply by adding a `constexpr` marker before the function. There's no longer a need to use obscure template metaprogramming for compile-time calculations. However, the examples above only apply to values. In C++, besides values, there are also types and higher-kind types.

```cpp
template<typename ...Ts>
struct type_list;

template<typename T, typename U, typename ...Ts>
struct find_first_of {
    constexpr static auto value = find_first_of<T, Ts...>::value + 1;
};

template<typename T, typename ...Ts>
struct find_first_of<T, T, Ts...> {
    constexpr static std::size_t value = 0;
};

static_assert(find_first_of<int, double, char, int, char>::value == 2);
```

Since types and higher-kind types can only be template arguments, they still have to be processed through **recursive template matching**. It would be great if we could manipulate them like values, so `constexpr` functions could also handle them. But C++ is not a language like Zig, where type is value. What to do? No problem, we can just map types to values, right? To achieve the effect of type as value. Before static reflection was added, we could achieve this effect through some tricks. We could map types to type names at compile time, and then just compute on the type names. For how to perform this mapping, you can refer to [How to elegantly convert enum to string in C++](https://www.ykiko.me/en/articles/680412313).

```cpp
template<typename ...Ts>
struct type_list{};

template<typename T, typename ...Ts>
constexpr std::size_t find(type_list<Ts...>) {
    // type_name is used to get the compile-time type name
    std::array arr{ type_name<Ts>()... };
    for(auto i = 0; i < arr.size(); i++) {
        if(arr[i] == type_name<T>()) {
            return i;
        }
    }
}
```

This code is very intuitive, but it's more difficult if we want to map values back to types. However, it doesn't matter, in the upcoming **static reflection**, this bidirectional mapping between types and values has become a language feature, and we no longer need to handle it manually.

Use the `^` operator to map a type to a value.

```cpp
constexpr std::meta::info value = ^int;
```

Use `[: ... :]` to map it back. Note that this is a symbol-level mapping.

```cpp
using Int = typename[:value:]; // In this context, typename can be omitted
typename[:value:] a = 3; // Equivalent to int a = 3;
```

Now we can write code like this:

```cpp
template<typename ...Ts>
struct type_list {
    constexpr static std::array types = {^Ts...};

    template<std::size_t N>
    using at = typename[:types[N]:];
};

using Second = typename type_list<int, double, char>::at<1>;
static_assert(std::is_same_v<Second, double>);
```

No more recursive matching; we can compute types like values. Once you understand this mapping relationship, writing code becomes very simple. Template metaprogramming for type computation can now retire!

In fact, `^` can not only map types, but also has the following main functions:

- `^::` —— Represents the global namespace
- `^namespace-name` —— Namespace name
- `^type-id` —— Type
- `^cast-expression` —— Special expressions, currently including:
  - Primary expression representing a function or member function
  - Primary expression representing a variable, static member variable, or structured binding
  - Primary expression representing a non-static member
  - Primary expression representing a template
  - Constant expression

Similarly, `[: ... :]` can restore to the corresponding entities. Note that it restores to the corresponding symbols, so this operator is called a Splicer.

- `[: r :]` —— Restores to the corresponding entity or expression
- `typename[: r :]` —— Restores to the corresponding type
- `template[: r :]` —— Restores to template arguments
- `namespace[: r :]` —— Restores to a namespace
- `[:r:]::` —— Restores to the corresponding namespace, class, or enum nested specifier

See the following example:

```cpp
int x = 0;
void g() {
    [:^x:] = 42;     // Okay.  Same as: x = 42;
}
```

If the restored entity is different from what was originally stored, it will result in a compilation error.

```cpp
typename[: ^:: :] x = 0;  // Error
```

### metainfo

Just the feature above is enough to be exciting. However, there's much more; the ability to obtain metadata for entities like `class` is also available.

Most basically, getting the type name (variable name, field name can all use this function):

```cpp
namespace std::meta {
    consteval auto name_of(info r) -> string_view;
    consteval auto display_name_of(info r) -> string_view;
}
```

For example:

```cpp
display_name_of(^std::vector<int>) //  => std::vector<int>
name_of(^std::vector<int>) // => std::vector<int, std::allocator<int>>
```

Determine if a template is a specialization of another higher-order template and extract the parameters from the higher-order template:

```cpp
namespace std::meta {
    consteval auto template_of(info r) -> info;
    consteval auto template_arguments_of(info r) -> vector<info>;
}

std::vector<int> v = {1, 2, 3};
static_assert(template_of(type_of(^v)) == ^std::vector);
static_assert(template_arguments_of(type_of(^v))[0] == ^int);
```

Fill template parameters into a higher-order template:

```cpp
namespace std::meta {
    consteval auto substitute(info templ, span<info const> args) -> info;
}

constexpr auto r = substitute(^std::vector, std::vector{^int});
using T = [:r:]; // Ok, T is std::vector<int>
```

Get member information for `struct`, `class`, `union`, `enum`:

```cpp
namespace std::meta{
    template<typename ...Fs>
    consteval auto members_of(info class_type, Fs ...filters) -> vector<info>;

    template<typename ...Fs>
    consteval auto nonstatic_data_members_of(info class_type, Fs ...filters) -> vector<info> {
        return members_of(class_type, is_nonstatic_data_member, filters...);
    }

    template<typename ...Fs>
    consteval auto bases_of(info class_type, Fs ...filters) -> vector<info> {
        return members_of(class_type, is_base, filters...);
    }

    template<typename ...Fs>
    consteval auto enumerators_of(info class_type, Fs ...filters) -> vector<info>;

    template<typename ...Fs>
    consteval auto subobjects_of(info class_type, Fs ...filters) -> vector<info>;
}
```

With this, we can implement features like iterating through structs and enums. Further, we can implement advanced features like serialization and deserialization. Some examples will be given later. In addition, there are other compile-time functions for various features; only a part of the content is shown above. More APIs can be found in the proposal. Since functions are provided to directly get parameters from higher-order templates, there is no longer a need to use templates for type extraction! Template metaprogramming for type extraction can also retire.

## Better compile facilities

The main part of reflection has been introduced; now let's talk about other things. Although these are contents of other proposals, they can make code easier to write and give it stronger expressive power.

### template for

How to generate a large number of code snippets in C++ is a very difficult problem to solve. Thanks to C++'s unique (and amazing) mechanism, current code snippet generation is almost entirely based on lambda expressions + variadic pack expansion. Look at the example below:

```cpp
constexpr auto dynamic_tuple_get(std::size_t N, auto& tuple) {
    constexpr auto size = std::tuple_size_v<std::decay_t<decltype(tuple)>>;
    [&]<std::size_t ...Is>(std::index_sequence<Is...>) {
        auto f = [&]<std::size_t Index> {
            if(Index == N) {
                std::cout << std::get<Index>(tuple) << std::endl;
            }
        };
        (f.template operator()<Is>(), ...);
    }(std::make_index_sequence<size>{});
}

int main() {
    std::tuple tuple = {1, "Hello", 3.14, 42};
    auto n1 = 0;
    dynamic_tuple_get(n1, tuple); // 1
    auto n2 = 3;
    dynamic_tuple_get(n2, tuple); // 42
}
```

A classic example, the principle is to distribute runtime variables to compile-time constants through multiple branch judgments. This achieves accessing elements in a `tuple` based on a runtime `index`. **Note: A more efficient way here would be to generate an array of function pointers at compile time and then jump directly based on the index, but this is just for demonstration, don't dwell on it too much.**

The expanded code above is equivalent to:

```cpp
constexpr auto dynamic_tuple_get(std::size_t N, auto& tuple) {
    if(N == 0) {
        std::cout << std::get<0>(tuple) << std::endl;
    }
    // ...
    if(N == 3) {
        std::cout << std::get<3>(tuple) << std::endl;
    }
}
```

It can be seen that we used an extremely awkward way to achieve an extremely simple effect. Moreover, since a lambda is essentially a function, it cannot directly return to the parent function from within the lambda. This leads to us doing a lot of redundant `if` checks.

With `template for`, the code looks much cleaner:

```cpp
constexpr void dynamic_tuple_get(std::size_t N, auto& tuple) {
    constexpr auto size = std::tuple_size_v<std::decay_t<decltype(tuple)>>;
    template for(constexpr auto num : std::views::iota(0, size)) {
        if(num == N) {
            std::cout << std::get<num>(tuple) << std::endl;
            return;
        }
    }
}
```

`template for` can be considered an enhanced syntactic sugar for lambda expansion, and it's very useful. If this is added, using template metaprogramming to generate functions (code) can retire.

### non-transient constexpr allocation

This proposal mainly discusses two issues together.

- C++ can reserve space in the data segment at compile time by controlling template instantiation of static members, which can be seen as compile-time memory allocation.

```cpp
template<auto... items>
struct make_array {
    using type = std::common_type_t<decltype(items)...>;
    static inline type value[sizeof ...(items)] = {items...};
};

template<auto... items>
constexpr auto make_array_v = make_array<items...>::value;

int main() {
    constexpr auto arr = make_array_v<1, 2, 3, 4, 5>;
    std::cout << arr[0] << std::endl;
    std::cout << arr[1] << std::endl; // Successfully reserves space in the data segment, storing 1 2 3 4 5
}
```

- C++20 allows `new` in `constexpr`, but memory `new`ed at compile time must be `delete`d at compile time.

```cpp
constexpr auto size(auto... Is) {
    std::vector<int> v = {Is...};
    return v.size();
}
```

So, can't we `new` at compile time and not `delete` it? And store the actual data in the data segment? This is the problem this proposal aims to solve. It hopes we can use:

```cpp
constexpr std::vector<int> v = {1, 2, 3, 4, 5}; // Global
```

The main difficulty is that memory allocated in the data segment does not have ownership like memory on the heap, and does not require `delete`. As long as this problem is solved, we can use compile-time `std::map` and `std::vector` and retain them at runtime. The author's approach is to use tagging. The specific details will not be discussed here. If this is added, using template metaprogramming to create constant tables can also retire.

## Some examples

Alright, after all that, let's see what we can do with reflection.

### print any type

```cpp
template<typename T>
constexpr auto print(const T& t) {
    template for(constexpr auto member : nonstatic_data_members_of(type_of(^t))) {
        if constexpr (is_class(type_of(member)))  {
            // If it's a class, recursively iterate through members
            println("{}= ", name_of(member));
            print(t.[:member:]);
        } else {
            // Non-class types can be printed directly
            std::println("{}= {}", name_of(member), t.[:member:]);
        }
    }
}
```

### enum to string

```cpp
template <typename E> requires std::is_enum_v<E>
constexpr std::string enum_to_string(E value) {
    template for (constexpr auto e : std::meta::members_of(^E)) {
        if (value == [:e:]) {
            return std::string(std::meta::name_of(e));
        }
    }
    return "<unnamed>";
}
```

## conclusion

I've spent a long time introducing C++'s static reflection. In fact, I'm very fond of C++'s compile-time computation, and I'm also very interested in its history. C++'s compile-time computation has been explored step by step, with many wise masters proposing their unique ideas, making the impossible a reality. From the abnormal template metaprogramming of C++03, to `constexpr` variables in C++11, to the gradual relaxation of restrictions in `constexpr` functions from C++14 to C++23, moving more and more operations to compile time. And now, with static reflection, C++ is gradually breaking free from the clutches of template metaprogramming. All those old-fashioned template metaprogramming styles can be eliminated! If you haven't written old-style template metaprogramming code before, you probably can't appreciate how terrible it was.

To get static reflection into the standard sooner, the author team specifically selected a core subset of the original proposal. I hope, as the author wishes, that static reflection can enter the standard in C++26! Of course, the core part will enter first, and then more useful features will be added, so this is by no means the entirety of reflection.

Experimental compiler:

- Try online: [https://godbolt.org/z/13anqE1Pa](https://godbolt.org/z/13anqE1Pa)
- Build locally: [clang-p2996](https://github.com/bloomberg/clang-p2996.git)

Reflection series articles: [Reflection Tutorial for C++ Programmers](https://www.ykiko.me/en/articles/669358870)
