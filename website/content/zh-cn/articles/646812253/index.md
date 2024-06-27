---
title: 'C++ 禁忌黑魔法: STMP 多态'
date: 2023-07-30 01:29:27
updated: 2024-05-26 15:07:56
---

## 前情提要： 

{{< article link="/zh-cn/articles/646752343" >}}

## 什么是 STMP 多态 

```cpp
struct Any{
    void* data;
    std::size_t index;
};

int main() {
    Set<>();

    std::vector<Any> vec = make_any(1, std::string("hello"), 3.14);

    for(auto&& any: vec) {
        visit([](auto&& v) { std::cout << v << std::endl; }, any);
    }

    vec.push_back(make_any(std::string_view("world")));
    vec.push_back(make_any(A{}));

    std::cout << "-----------------------" << std::endl;
    for(auto&& any: vec) {
        visit([](auto&& v) { std::cout << v << std::endl; }, any);
    }
}
```

`STMP`多态把所有类型都擦成了`Any`类型，但是与`std::any`不同的是，`std::any`需要显示进行类型转换，非常麻烦，但是我们的`Any`可以方便的使用`visit`进行访问，不需要任何显示类型转换。这是因为我们利用了`STMP`，实现了类型的自动注册。

相关的代码仍然放 [Compiler Explorer](https://godbolt.org/z/7W7c7P8n1) 上。为了防止链接失效，同样放在 [Github](https://github.com/16bit-ykiko/blog/blob/main/code/stmp-polymorphic.cpp)。 

## 书接上文 

上一篇文章我们实现了一个简单编译期计数器。可以返回一个递增的序列。但是这还不够。我们这篇文章来实现编译器类型容器，可以在编译期动态的添加和删除类型。

## type_list 工具箱 

由于我们要实现对类型列表的操作，所以一套称手的工具箱是必要的。我们简单写一些，不求多，只求够用就行。看不懂也没关系，看测试用例明白怎么用就行了。原理我就不讲解了，是非常基础的元编程知识。

```cpp
// type_list
template <typename... Types>
struct type_list {
    using type = type_list<Types...>;
};

// push_back
template <typename List, typename T>
struct list_push_back;

template <typename... Types, typename T>
struct list_push_back<type_list<Types...>, T> {
    using type = type_list<Types..., T>;
};

template <typename List, typename T>
using list_push_back_t = typename list_push_back<List, T>::type;

// push_front
template <typename List, typename T>
struct list_push_front;

template <typename... Types, typename T>
struct list_push_front<type_list<Types...>, T> {
    using type = type_list<T, Types...>;
};

template <typename List, typename T>
using list_push_front_t = typename list_push_front<List, T>::type;

// pop_back
template <typename List>
struct list_pop_back;

template <typename T, typename... Types>
struct list_pop_back<type_list<T, Types...>> {
    using type = list_push_front_t<typename list_pop_back<type_list<Types...>>::type, T>;
};

template <typename T>
struct list_pop_back<type_list<T>> {
    using type = type_list<>;
};

template <typename List>
using list_pop_back_t = typename list_pop_back<List>::type;
```

测试用例如下

```cpp
using list0 = type_list<int, double, char>;

using list1 = list_push_back_t<list0, bool>;
static_assert(std::is_same_v<list1, type_list<int, double, char, bool>>);

using list2 = list_push_front_t<list1, float>;
static_assert(std::is_same_v<list2, type_list<float, int, double, char, bool>>);

using list3 = list_pop_back_t<list2>;
static_assert(std::is_same_v<list3, type_list<float, int, double, char>>);
```

## 返回不同的类型 

先来看一个简单案例

```cpp
template <std::size_t N>
struct reader {
    friend auto counted_flag(reader<N>);
};

template <std::size_t N, typename T>
struct setter {
    friend auto counted_flag(reader<N>) { return T{}; }
};

int main() {
    setter<0, int> setter0;  // set
    auto a = counted_flag(reader<0>{});  // read
    static_assert(std::is_same_v<decltype(a), int>);

    setter<1, double> setter1;  // set
    auto b = counted_flag(reader<1>{});  // read
    static_assert(std::is_same_v<decltype(b), double>);

    setter<2, std::string> setter2;  // set
    auto c = counted_flag(reader<2>{});  // read
    static_assert(std::is_same_v<decltype(c), std::string>);
}
```

发现没有，可以在某一个位置注册信息。然后仅仅通过这个位置的序号就可以读取到对应的类型。就像一个数组一样，是不是非常神奇。原理就是很好理解，利用了类型推导以及友元函数的 ADL 查找。

## 编译期类型容器 

让我们结合把这个特性和程序计数器结合起来，神奇的事情就发生了。

```cpp
// counter
template <std::size_t N>
struct reader {
    friend auto counted_flag(reader<N>);
};

template <std::size_t N, typename T>
struct setter {
    friend auto counted_flag(reader<N>) { return T{}; }
};

template <auto tag = [] {},
          auto N = 0,
          bool condition = requires(reader<N> red) { counted_flag(red); }>
consteval auto count() {
    if constexpr(!condition) {
        return N - 1;
    } else {
        return count<tag, N + 1>();
    }
}

template <typename... Ts>
consteval void Set() {
    setter<0, type_list<Ts...>> s [[maybe_unused]]{};
}

template <auto tag = [] {}>
using value = decltype(counted_flag(reader<count<tag>()>{}));

template <typename T, auto tag = [] {}>
consteval void push() {
    constexpr auto len = count<tag>();
    setter<len + 1, list_push_back_t<value<tag>, T>> s [[maybe_unused]]{};
}

template <auto tag = [] {}>
consteval void pop() {
    constexpr auto len = count<tag>();
    using last = value<tag>;
    setter<len + 1, list_pop_back_t<value<tag>>> s [[maybe_unused]]{};
}

int main() {
    Set<int>();
    static_assert(std::is_same_v<value<>, type_list<int>>);

    push<double>();
    static_assert(std::is_same_v<value<>, type_list<int, double>>);

    push<char>();
    static_assert(std::is_same_v<value<>, type_list<int, double, char>>);

    pop();
    static_assert(std::is_same_v<value<>, type_list<int, double>>);
}
```

这里我们实现了一个`count`函数，它的原理是前面的`next`类似，不同的是，`next`每次会进行递增，而`count`仅仅是返回实例化的目标模板数量。

剩下的逻辑就很简单了：

- `Set`函数用来初始化一个`setter`，这个`setter`里面包含了一个类型列表，这个列表表示初始值。
- `value`用`count`取出最后一个状态。
- `push`用`count`取出最后一个状态的`index`，取出对应的`type_list`，然后对这个`type_list`进行操作。通过实例化一个新的模板，添加一个新的状态，把新得到的`type_list`存进去。
- `pop`与`push`类似，只不过对`type_list`的操作变成了删除。


按照这个原理，可以轻松的扩展很多类似的操作，其实只要对`type_list`进行操作就行了。

## 挑战C++的极限 

好了时候到了最终实现的时候了，让我们看看C++的极限在哪里。

```cpp
// Any
struct Any {
    void* data;
    std::size_t index;
};

template <typename T, auto tag = [] {}>
constexpr auto make_any(T&& t) {
    auto ls = push<std::decay_t<T>, tag>();
    return Any{new auto(std::forward<T>(t)), count<tag>()};
}

template <typename... Ts>
    requires (sizeof...(Ts) > 1)
constexpr auto make_any(Ts&&... ts) {
    return std::vector{make_any(std::forward<Ts>(ts))...};
}

template <typename Fn, typename T, auto tag = [] {}>
constexpr auto wrap(Fn&& fn, void* ptr) {
    auto& value = *static_cast<T*>(ptr);
    using ret = decltype(fn(value));
    if constexpr(std::is_same_v<ret, void>) {
        fn(value);
        return Any{nullptr, 0};
    } else {
        push<ret, tag>();
        return Any{new auto(fn(value)), count<tag>()};
    }
}

template <typename Fn, auto tag = [] {}>
constexpr auto visit(Fn&& fn, Any any) {
    constexpr auto size = count<tag>();
    using Wrapper = Any (*)(Fn&&, void*);

    constexpr auto wrappers = []<typename... Ts>(type_list<Ts...>) {
        return std::array<Wrapper, size>{wrap<Fn, Ts>...};
    }(value<tag>());

    return wrappers[any.index](std::forward<Fn>(fn), any.data);
}
```

到这里实现了对`Any`的自动注册。每次当你调用`make_any`的时候，就会自动注册一个新的类型，到全局的状态表里。然后`visit`的时候，其实我们是生成了一些`Wrapper`函数，打了一个表，然后通过`index`去调用对应的函数。这样就实现了对`Any`的自动访问。这里的关键步骤就是，向全局的状态表里面自动注册信息。其余的步骤都和`std::visit`实现类似。感兴趣的可以去看看`std::visit`的实现。

## 结语 

事实上，这个系列算是了解了笔者一直以来的心愿。经常听到有人调侃，男人两大爱好是：拉良家妇女下水 劝风尘女子从良。程序员，也有两大爱好：让静态类型的语言变的更动态，为动态语言加上类型检查。事实上自从我学`C++`以来，一直有这样的心愿，想要实现类型的自动注册。很遗憾，网络上相关的讨论很少。在那之后，我尝试了各种方法，包括但不限于，使用宏元编程，采用`libclang`等库`parse`对`C++`的源码进行解析，但是效果都不如`STMP`好。当我了解`STMP`，并且意识到它所能达到的高度之后。我立马通宵写完了文章和案例，毕竟它是如此的令人着迷。在这里，我不想讨论什么可读性，可维护性。由于`STMP`尚未被标准认可，所以运用到实际项目的编程里，事实上是很困难的。再一次强调，用到实际项目里面并不现实（具体可以看一下评论区讨论）。但是就像当初模板元编程的意外发现一样，这再一次证明了，一门语言能够能多么疯狂的超过它所预期的能力。本文实现的`STMP`多态，在其它任何一门语言里面都是不可能出现的，这就是`C++`的魅力所在！