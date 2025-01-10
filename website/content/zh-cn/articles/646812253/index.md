---
title: 'C++ 禁忌黑魔法：STMP （下）'
date: 2023-07-30 09:29:27
updated: 2024-12-18 11:33:47
series: ['STMP']
series_order: 2
---

上一篇 [文章](https://www.ykiko.me/zh-cn/articles/646752343) 我们初步了解了 STMP 的原理，并且利用它实现了简单的一个编译期的计数器。然而，它的威力远不止如此，这篇文章就来讨论一些基于 STMP 的高级应用。

## type <=> value 

在 C++ 中，对类型做计算的需求却一直存在，例如

- `std::variant`要求其模板参数不能重复，那我们就需要对类型列表进行查重
- 需要对`variant`类型列表进行排序，排序后相同的类型，例如`std::variant<int, double>`和`std::variant<double, int>`可以共用一份代码，减少二进制膨胀
- 根据给定索引获取一个类型列表中的类型
- 变序对函数参数进行映射


等等等，这里就不一一列举了。但在 C++ 中，类型并不是一等公民，只能作为模板参数传递。为了对类型进行计算，我们往往不得不进行晦涩难懂的模板元编程。如果类型能像值一样传递给 cosntexpr 函数进行计算就好了，这样对类型的计算就会变得很简单了。直接传递肯定是不可能了，考虑建立类型和值之间的一一映射，在计算之前将类型映射到值，计算完之后再将值映射回类型，这样也能实现我们的需求。

### type -> value 

首先考虑将类型映射到值

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

利用不同模板实例化的静态变量地址也不同的特性，我们可以轻松的把类型映射到唯一的值（地址）。

### value -> type 

反过来如何把值映射回类型呢？考虑使用朴素的模板特化

```cpp
template <meta_value value>
struct type_of;

template <>
struct type_of<value_of<int>()> {
    using type = int;
};

// ...
```

的确可以，但是这要求我们提前特化好所有要使用到的类型，对于绝大多数程序来说这是不现实的。有没有什么办法能在求值的时候添加这个特化呢？答案就是我们上一篇文章提到的 friend inject 了。

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

然后我们只需在实例化`value_of`的同时实例化一个`setter`即可完成注册

```cpp
template <typename T>
consteval meta_value value_of() {
    constexpr auto value = &storage<T>::value;
    setter<value, T> setter;
    return value;
}
```

最后直接通过`reader`读取注册的结果即可实现`type_of`

```cpp
template <meta_value value>
using type_of = typename decltype(to_type(reader<value>{}))::type;
```

### sort types! 

话不多说，我们赶紧来试一下用`std::sort`一下对`type_list`进行排序

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

`type_list`是一个简单的类型容器，`array_to_list`用于将`std::array`中的类型映射回`type_list`，`sort_list`就是排序的具体实现，过程就是先把类型都映射到一个`std::array`中，然后用`std::ranges::sort`对这个数组排序，最后再将排序后的`std::array`映射回`type_list`。

实验一下

```cpp
using list = type_list<int, char, int, double, char, char, double>;
using sorted = typename sort_list<list>::result;
using expected = type_list<char, char, char, int, int, double, double>;
static_assert(std::is_same_v<sorted, expected>);
```

三大编译器 C++20 均编译通过！代码放在 [Compiler Explorer](https://godbolt.org/z/4qW7MhfWP) 上了，为了防止链接失效。在 [Github](https://github.com/16bit-ykiko/about-me/blob/main/code/type-list-sort.cpp) 上也放了一份。

> 非常值得一提的是，这种类型和值的双向映射在 Reflection for C++26 中已经成为语言内置的功能。我们不再需要去利用 friend injection 这种奇淫巧技，直接使用`^`和`[: :]`运算符即可完成映射。更多内容详见 [C++26 静态反射提案解析](https://www.ykiko.me/zh-cn/articles/661692275)。  

## the true any 

`std::any`常常用于类型擦除，可以把完全不同的类型擦除，并放在同一个容器里面。但是擦除容易，还原难，尤其是有些时候想把`any`里面存的对象打印出来看看，还得一个个类型去`cast`。有没有一种可能，能编写出一个真正的`any`类型呢？不需要我们去手动`cast`，直接就可以调用它里面的类型对应的成员函数呢？

对于单个编译单元来说，这是完全可能的，因为单个编译单元内的构造为`any`的类型集合是编译时确定的，只需要记录下所有实例化的类型，然后使用模板元编程自动的对每个类型进行尝试即可。

### type register 

先考虑如何注册类型

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

仍然使用`setter`来注册类型。`lookup`用于查找某个类型在类型集合中的索引，原理就是遍历这个集合，然后一个个`is_same_v`比较，找到了就返回对应的索引。如果到最后都没有找到，就注册一个新的类型。`count`用于计算类型集合的大小。

### any type 

接下来我们定义一个简单的`any`类型，并定义一个`make_any`函数，用于构造`any`对象

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

>  为什么要额外写一个 make_any，而不是直接写一个模板构造函数呢？这是因为再我实际尝试之后，发现三大编译器对于模板构造函数实例化的位置都不一样，并且有些奇怪，导致求值结果不同。但对于普通的模板函数，实例化位置都是一样的，所以写成了一个单独的函数。 

### visit it! 

重头戏来了，我们可以实现一个类似`std::visit`的函数，用于访问`any`对象。它接受一个回调函数，然后遍历`any`对象的类型集合，如果找到了对应的类型，把`any`转换成对应的类型，然后调用回调函数。

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

然后让我们尝试一下

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

三大编译器都按照我们的预期输出了结果！代码同样放在 [Compiler Explorer](https://godbolt.org/z/aP3zs7479) 和 [Github](https://github.com/16bit-ykiko/about-me/blob/main/code/the-true-any.cpp) 上了。

## conclusion 

这两篇关于 STMP 的文章，算是了却了我一直以来的心愿。在这之前，我一直在思考，如何像上面的代码这样，实现一个真的`any`类型，无需使用者提前注册。我尝试了很多方法，最后都未能如愿。但是 STMP 的出现，让我看到了希望。再意识到它所能到达的高度之后，我立马通宵写完了文章和案例。

当然了，不推荐以任何形式在实际的项目中使用这种技术。由于这种代码十分依赖于模板实例化的位置，非常容易造成 ODR 违背，并且多次重复实例化会大大增长编译时间。对于这种需要有状态的代码需求，我们往往可以将其改成无状态的代码，当然，纯手写工作量可能十分巨大，更推荐使用代码生成器进行额外的代码生成来完成这项需求。比如我们可以用 libclang 收集所有编译单元中 any 的实例化信息，然后打一个对应的表就行了。

最后，感谢大家的阅读，希望这两篇文章能让你对 C++ 的模板有更深刻的理解。