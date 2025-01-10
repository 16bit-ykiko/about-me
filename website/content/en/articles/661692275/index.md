---
title: 'Analysis of the C++26 Static Reflection Proposal'
date: 2023-10-17 02:38:26
updated: 2024-11-30 17:59:18
series: ['Reflection']
series_order: 6
---

I recently planned to write a series of articles discussing the concept of reflection in detail. Coincidentally, C++26 has introduced a new reflection proposal, and I noticed that there are no related articles on Zhihu, even though this topic is frequently discussed. Therefore, I decided to take this opportunity to talk about static reflection in C++, serving as a warm-up for the series.

## What is Static Reflection?

First, what is reflection? Like many other terms in computer science, it doesn't have a detailed and precise definition. I won't delve into this question in this article, as I will explain it in detail in subsequent articles. The focus of this article is on C++'s static reflection. Why emphasize "static"? Mainly because when we talk about reflection, we almost always refer to reflection in languages like Java, C#, and Python, where the implementation involves type erasure and runtime information querying. This approach inevitably incurs runtime overhead, which clearly violates C++'s principle of zero-cost abstraction. To distinguish it from their reflection, we add "static" as a qualifier, indicating that C++'s reflection is done at compile time. Of course, this statement still lacks some rigor. A detailed discussion will be provided in subsequent articles. For now, you just need to know that C++'s static reflection is different from Java, C#, and Python's reflection and is primarily done at compile time.

## What Can Static Reflection Do?

### Type as Value

We all know that as C++ versions continue to update, the capabilities of compile-time computation are constantly improving. Through `constexpr/consteval` functions, we can largely reuse runtime code directly, making compile-time computation more convenient. This completely replaces the old method of using template metaprogramming for compile-time computation. Not only is it easier to write, but it also compiles faster.

Observe the following code snippets for computing factorials at compile time:

In C++03/98, we could only achieve this through template recursive instantiation, and we couldn't reuse the code at runtime.

```cpp
template<int N>
struct factorial
{
    enum { value = N * factorial<N - 1>::value };
};

template<>
struct factorial<0>
{
    enum { value = 1 };
};
```

C++11 introduced the concept of `constexpr` functions for the first time, allowing us to write code that can be reused at both compile time and runtime. However, there were many restrictions, such as no variables or loops, so we had to write code in a purely functional style.

```cpp
constexpr int factorial(int n) 
{ 
    return n == 0 ? 1 : n * factorial(n - 1); 
}

int main()
{
    constexpr std::size_t a = factorial(5); // Compile-time computation
    std::size_t& n = *new std::size_t(6);
    std::size_t b = factorial(n); // Runtime computation
    std::cout << a << std::endl;
    std::cout << b << std::endl;
}
```

With the advent of C++14/17, the restrictions in `constexpr` functions were further relaxed. Now, we can use local variables and loops in constexpr functions, as shown below.

```cpp
constexpr std::size_t factorial(std::size_t N)
{
    std::size_t result = 1;
    for (std::size_t i = 1; i <= N; ++i)
    {
        result *= i;
    }
    return result;
}
```

After C++20, we can even use `new/delete` at compile time, and we can use `vector` in compile-time code. Much of the runtime code can be directly reused at compile time without any changes, just by adding a constexpr marker to the function. We no longer need to use obscure template metaprogramming for compile-time computation. However, the above examples only apply to values. In C++, besides values, there are types and higher-kinded types.

```cpp
template<typename ...Ts>
struct type_list;

template<typename T, typename U, typename ...Ts>
struct find_first_of
{
    constexpr static auto value = find_first_of<T, Ts...>::value + 1;
};

template<typename T, typename ...Ts>
struct find_first_of<T, T, Ts...>
{
    constexpr static std::size_t value = 0;
};

static_assert(find_first_of<int, double, char, int, char>::value == 2);
```

Since types and higher-kinded types can only be template arguments, we still have to process them through **template recursive matching**. It would be great if we could manipulate them like values, so that constexpr functions could handle them too. But C++ is not a language like Zig, where "type is value." What can we do? No problem, we can map types to values to achieve the effect of "type as value." Before static reflection was introduced, we could achieve this effect through some tricks. We could map types to type names at compile time, and then perform computations on the type names. For how to perform such mapping, refer to [How to Elegantly Convert enum to string in C++](https://www.ykiko.me/zh-cn/articles/680412313).

```cpp
template<typename ...Ts>
struct type_list{};

template<typename T, typename ...Ts>
constexpr std::size_t find(type_list<Ts...>)
{
    // type_name is used to get compile-time type names
    std::array arr{ type_name<Ts>()... };
    for(auto i = 0; i < arr.size(); i++)
    {
        if(arr[i] == type_name<T>())
        {
            return i;
        }
    }
}
```

The code is very intuitive, but if we want to map the value back to the type, it becomes more difficult. However, in the upcoming **static reflection**, this bidirectional mapping between types and values has become a language feature, and we no longer need to handle it manually.

Use the `^` operator to map types to values.

```cpp
constexpr std::meta::info value = ^int;
```

Use `[: ... :]` to map it back. Note that this is a symbol-level mapping.

```cpp
using Int = typename[:value:]; // In this context, typename can be omitted
typename[:value:] a = 3; // Equivalent to int a = 3;
```

Now we can write code like this.

```cpp
template<typename ...Ts>
struct type_list
{
    constexpr static std::array types = {^Ts...};

    template<std::size_t N>
    using at = typename[:types[N]:]; 
};

using Second = typename type_list<int, double, char>::at<1>;
static_assert(std::is_same_v<Second, double>);
```

No more recursive matching! We can compute types like values. As long as you understand this mapping relationship, writing code becomes very simple. Template metaprogramming for type computation can now retire!

In fact, the `^` operator can map more than just types. It has the following functionalities:

- `^::` —— Represents the global namespace
- `^namespace-name` —— Namespace name
- `^type-id` —— Type
- `^cast-expression` —— Special expressions, currently including:
  - Primary expressions representing functions or member functions
  - Primary expressions representing variables, static member variables, and structured bindings
  - Primary expressions representing non-static members
  - Primary expressions representing templates
  - Constant expressions

Similarly, `[: ... :]` can also restore the corresponding entities. Note that it restores to the corresponding symbol, so this operator is called the "splicer."

- `[: r :]` —— Restores to the corresponding entity or expression
- `typename[: r :]` —— Restores to the corresponding type
- `template[: r :]` —— Restores to template parameters
- `namespace[: r :]` —— Restores to the namespace
- `[:r:]::` —— Restores to the corresponding namespace, class, or enum nested specifier

See the usage example below.

```cpp
int x = 0;
void g() {
    [:^x:] = 42;     // Okay. Same as: x = 42;
}
```

If the restored entity does not match the originally stored one, a compilation error will occur.

```cpp
typename[: ^:: :] x = 0;  // Error
```

### Meta Info

The above feature alone is enough to be exciting. However, there's much more. The ability to obtain meta-information about entities like `class` has also been introduced.

The most basic is obtaining type names (variable names, field names can also use this function).

```cpp
namespace std::meta 
{
    consteval auto name_of(info r) -> string_view;
    consteval auto display_name_of(info r) -> string_view;
}
```

For example:

```cpp
display_name_of(^std::vector<int>) //  => std::vector<int>
name_of(^std::vector<int>) // => std::vector<int, std::allocator<int>>
```

Determine if a template is a specialization of another higher-order template and extract parameters from the higher-order template.

```cpp
namespace std::meta 
{
    consteval auto template_of(info r) -> info;
    consteval auto template_arguments_of(info r) -> vector<info>;
}

std::vector<int> v = {1, 2, 3};
static_assert(template_of(type_of(^v)) == ^std::vector);
static_assert(template_arguments_of(type_of(^v))[0] == ^int);
```

Fill template parameters into higher-order templates.

```cpp
namespace std::meta 
{
    consteval auto substitute(info templ, span<info const> args) -> info; 
}

constexpr auto r = substitute(^std::vector, std::vector{^int});
using T = [:r:]; // Ok, T is std::vector<int>
```

Obtain member information of `struct`, `class`, `union`, and `enum`.

```cpp
namespace std::meta
{
    template<typename ...Fs>
    consteval auto members_of(info class_type, Fs ...filters) -> vector<info>;

    template<typename ...Fs>
    consteval auto nonstatic_data_members_of(info class_type, Fs ...filters) -> vector<info>
    {
        return members_of(class_type, is_nonstatic_data_member, filters...);
    }

    template<typename ...Fs>
    consteval auto bases_of(info class_type, Fs ...filters) -> vector<info>
    {
        return members_of(class_type, is_base, filters...);
    }

    template<typename ...Fs>
    consteval auto enumerators_of(info class_type, Fs ...filters) -> vector<info>;

    template<typename ...Fs>
    consteval auto subobjects_of(info class_type, Fs ...filters) -> vector<info>;
}
```

Later, we can use this to implement features like traversing structures and enums. Further, we can implement advanced features like serialization and deserialization. Some examples will be provided later. In addition, there are other compile-time functions, and only a part of the content is shown above. For more APIs, refer to the proposal. Since functions for directly obtaining parameters from higher-order templates are provided, we no longer need to use templates for type extraction! Template metaprogramming for type extraction can also retire.

## Better Compile Facilities

The main part of reflection has been introduced. Now let's talk about other things. Although this part is from other proposals, they can make writing code easier and give code stronger expressiveness.

### Template For

In C++, generating a large number of code segments is a very difficult problem to solve. Thanks to C++'s unique (or rather, bizarre) mechanisms, current code segment generation is almost entirely based on lambda expressions + variadic parameter pack expansion. See the example below.

```cpp
constexpr auto dynamic_tuple_get(std::size_t N, auto& tuple)
{
    constexpr auto size = std::tuple_size_v<std::decay_t<decltype(tuple)>>;
    [&]<std::size_t ...Is>(std::index_sequence<Is...>)
    {
        auto f = [&]<std::size_t Index>
        {
            if(Index == N)
            {
                std::cout << std::get<Index>(tuple) << std::endl;
            }
        };
        (f.template operator()<Is>(), ...);
    }(std::make_index_sequence<size>{});
}

int main()
{
    std::tuple tuple = {1, "Hello", 3.14, 42};
    auto n1 = 0;
    dynamic_tuple_get(n1, tuple); // 1
    auto n2 = 3;
    dynamic_tuple_get(n2, tuple); // 42
}
```

A classic example, the principle is to distribute runtime variables to compile-time constants through multiple branch judgments. Implement accessing elements in `tuple` based on runtime `index`. **Note: A more efficient method here is to generate a function pointer array at compile time and then jump directly based on the index, but this is just for demonstration, so don't worry too much.**

The above code expands to the equivalent of:

```cpp
constexpr auto dynamic_tuple_get(std::size_t N, auto& tuple)
{
    if(N == 0)
    {
        std::cout << std::get<0>(tuple) << std::endl;
    }
    // ...
    if(N == 3)
    {
        std::cout << std::get<3>(tuple) << std::endl;
    }
}
```

As you can see, we used extremely awkward syntax just to achieve a very simple effect. Moreover, since lambda is actually a function, it cannot directly return to the upper-level function, causing us to do many redundant `if` judgments.

Using `template for` makes the code much cleaner.

```cpp
constexpr void dynamic_tuple_get(std::size_t N, auto& tuple)
{
    constexpr auto size = std::tuple_size_v<std::decay_t<decltype(tuple)>>;
    template for(constexpr auto num : std::views::iota(0, size))
    {
        if(num == N)
        {
            std::cout << std::get<num>(tuple) << std::endl;
            return;
        }
    }
}
```

You can think of `template for` as a syntax sugar-enhanced version of lambda expansion. It's very useful. If this is added, using template metaprogramming to generate functions (code) can retire.

### Non-Transient Constexpr Allocation

This proposal mainly discusses two issues together.

- C++ can reserve space in the data segment by controlling template instantiation of static members, which can be seen as compile-time memory allocation.

```cpp
template<auto... items>
struct make_array
{
    using type = std::common_type_t<decltype(items)...>;
    static inline type value[sizeof ...(items)] = {items...};
};

template<auto... items>
constexpr auto make_array_v = make_array<items...>::value;

int main()
{
    constexpr auto arr = make_array_v<1, 2, 3, 4, 5>;
    std::cout << arr[0] << std::endl;
    std::cout << arr[1] << std::endl; // Successfully reserves space in the data segment, storing 1 2 3 4 5
}
```

- C++20 allows `new` in `constexpr`, but memory allocated at compile time must be `delete`d at compile time.

```cpp
constexpr auto size(auto... Is)
{
    std::vector<int> v = {Is...};
    return v.size();
}
```

So, can't we `new` at compile time and not `delete`, with the actual data placed in the data segment? This is the problem this proposal aims to solve. It hopes we can use:

```cpp
constexpr std::vector<int> v = {1, 2, 3, 4, 5}; // Global
```

The main difficulty is that memory allocated in the data segment, unlike memory on the heap, has no ownership and doesn't need to be `delete`d. Once this problem is solved, we can use compile-time `std::map`, `std::vector` and retain them until runtime. The author's approach is to mark them. The specific details won't be discussed here. If this is added, using template metaprogramming to create constant tables can also retire.

## Some Examples

Alright, after all that, let's see what we can do with reflection.

### Print Any Type

```cpp
template<typename T>
constexpr auto print(const T& t)
{
    template for(constexpr auto member : nonstatic_data_members_of(type_of(^t)))
    {
        if constexpr (is_class(type_of(member))) 
        {
            // If it's a class, recursively traverse its members
            println("{}= ", name_of(member));
            print(t.[:member:]);
        }
        else
        {
            // Non-class types can be printed directly
            std::println("{}= {}", name_of(member), t.[:member:]); 
        }
    }
}
```

### Enum to String

```cpp
template <typename E> requires std::is_enum_v<E>
constexpr std::string enum_to_string(E value) 
{
    template for (constexpr auto e : std::meta::members_of(^E)) 
    {
        if (value == [:e:]) 
        {
            return std::string(std::meta::name_of(e));
        }
    }
    return "<unnamed>";
}
```

## Conclusion

I spent a long time introducing C++'s static reflection. Actually, I really like C++'s compile-time computation and am very interested in its development history. C++'s compile-time computation has been developed step by step, with many wise masters proposing their unique ideas, turning the impossible into reality. From the perverse template metaprogramming of C++03, to `constexpr` variables in C++11, to the gradual relaxation of restrictions in `constexpr` functions from C++14 to C++23, moving more and more operations to compile time. To today's static reflection, C++ is gradually breaking free from the clutches of template metaprogramming. All those old template metaprogramming techniques can now be retired!!! If you haven't written old-style template metaprogramming code, you probably can't appreciate how terrifying it is.

To get static reflection into the standard sooner, the author team specifically selected a core subset of the original proposal. Hopefully, as the author wishes, static reflection will enter the standard in C++26! Of course, the core part enters first, and more useful features will be added later, so this is by no means the entirety of reflection