---
title: '跨越 7 年的接力赛：获取 C++ 结构体字段数量'
date: 2023-12-25 20:45:30
updated: 2024-01-01 23:13:15
---

## 引子 

在`C++17`中引入了叫做「**结构化绑定**」的特性也就是`Struct Bind`，这一特性类似于别的语言中的模式匹配，可以让我们方便的对结构体的成员进行访问

```cpp
struct Point { int x; int y; };

Point p = {1, 2};
auto [x, y] = p;
// x = 1, y = 2
```

利用它我们能实现一些有趣的功能，包括*有限的* 对结构体的反射功能，比如实现一个`for_each`函数

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

这样的话对于任意的含有两个成员的聚合类型，我们都可以对其进行遍历

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

但是这样有一个问题那就是，只能递归的支持结构体字段数量为`2`的情况，如果你尝试填入一个字段数量为`3`的结构体，那么编译器就会抛出一个`hard error`。即结构化绑定数量错误，它不能被`SFINAE`或者`requires`处理，会直接导致编译中止

```cpp
struct Vec3 { float x; float y; float z; };

// 里面是个 lambda
constexpr auto value = requires{ [](){ auto [x, y] = Vec3{ 1, 2, 3 }; }; };
// hard error
```

我们可以通过手动分发的方式来解决这个问题

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

你可以自由枚举到你想要支持的数量，这里面的`N`就是结构体字段数量了，你可能需要把它作为模板参数显式传入，或者给每个类型都特化一个模板，里面存上它的字段数量。但是这仍然很麻烦，那么有没有一种方法可以让编译器自动的帮我们计算出结构体的字段数量呢？

## 第一棒 Antony Polukhin 

初步解决方案在 [boost/pfr](https://www.boost.org/doc/libs/1_75_0/doc/html/boost_pfr.html) 中就已经给出了，其作者 Antony Polukhin 在 [CppCon2016](https://www.youtube.com/watch?v=abdeAew3gmQ) 和 [CppCon2018](https://www.youtube.com/watch?v=UlNUNxLtBI0) 中对此做了详细的介绍，不过作者采用的版本是`C++14/17`，其中的代码较为晦涩难懂，在我使用`C++20`进行重写之后可读性提高了不少。

首先在`C++`中我们可以写一个`Any`类型，它支持向任意类型进行转换，其实就是把它的 [类型转换函数](https://en.cppreference.com/w/cpp/language/cast_operator) 写成模板函数就行了

```cpp
struct Any
{
    constexpr Any(int){}; // 支持从 int 构造

    template<typename T>
    constexpr operator T() const;
};

static_assert(std::is_convertible_v<Any, int>); // true
static_assert(std::is_convertible_v<Any, std::string>); // true
```

之后我们可以利用聚合初始化的特性，那就是对于超出聚合初始化最大数量的表达式，`requires`语句会返回`false` 

```cpp
struct Point { int x; int y; };

template<typename T, std::size_t N>
constexpr auto test()
{
    // 利用 make_index_sequence 构造 N 个参数
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

注意到这里`Point`只有两个成员，当我们传入了三个参数给初始化列表的时候，`requires`就会返回`false`。利用这个特性，我们可以把上面的尝试过程改成递归的，也就是线性查找这个序列直到找到`false`为止。

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

如果`test<T, N>`为真说明`N`个参数可以成功构造`T`，那么我们就递归的尝试`N + 1`个参数，直到`test<T, N>`为假，那么`N - 1`就是`T`的成员数量了。这样我们就可以通过`member_count<T>()`来获取`T`的成员数量了。测试一下效果

```cpp
struct A{ std::string a; };
static_assert(member_count<A>() == 1);

struct B{ std::string a; int b; };
static_assert(member_count<B>() == 2);
```

很好啊，大获成功！事情到这里就结束了吗？

## 第二棒 João Baptista 

考虑下面这三个例子 

- 左值引用


```cpp
struct A{ int& x; };
static_assert(member_count<A>() == 1); // error
```

- 默认构造函数被删除


```cpp
struct X { X() = delete; } // 默认构造函数被删除
struct B{ X x; X y; };
static_assert(member_count<B>() == 2); // error
```

- 数组


```cpp
struct C { int x[2]; };
static_assert(member_count<C>() == 1); // error
```

**遇到这三种情况，原来的方法完全失效了，为什么会这样？**

这一小节的主要内容参考自 João Baptista 的两篇博客

- [Counting the number of fields in an aggregate in C++20](https://towardsdev.com/counting-the-number-of-fields-in-an-aggregate-in-c-20-c81aecfd725c) 
- [Counting the number of fields in an aggregate in C++20 — part 2](https://towardsdev.com/counting-the-number-of-fields-in-an-aggregate-in-c-20-part-2-d3103dec734f)


他总结了`boost/pfr`中的问题，并提出了解决方案，解决了上述提到的三个问题

### 左值引用的问题 

第一个问题相对比较好理解，主要就是因为`T()`类型产生的转换产生的都是纯右值，左值引用没法绑定到纯右值，如果是右值引用就可以了

```cpp
static_assert(!std::is_constructible_v<int&, Any>); // false
static_assert(std::is_constructible_v<int&&, Any>); // true
```

怎么办呢？其实有一种很巧妙的写法，可以解决这个问题

```cpp
struct Any
{
    constexpr Any(int) {}; // 支持从 int 构造

    template<typename T>
    constexpr operator T&() const;

    template<typename T>
    constexpr operator T&&() const;
};
```

一个转换成左值引用，一个转换成右值引用。如果它们俩只有一个能匹配，那就会选择那一个能匹配的。如果两个都能匹配，左值引用转换的优先级比右值引用高，会被优先选择，不会有重载决议的问题。

```cpp
static_assert(std::is_constructible_v<int, Any>); // true
static_assert(std::is_constructible_v<int&, Any>); // true
static_assert(std::is_constructible_v<int&&, Any>); // true
static_assert(std::is_constructible_v<const int&, Any>); // true
```

很好，这样的话第一个问题，解决！

### 默认构造函数的问题 

为什么把默认构造函数删了就不行了呢？还记得我们最开始的那个`Point`类型吗？

```cpp
struct Point{ int x; int y; };
```

我们尝试的结果是`0`,`1`,`2`都可以，`3`不行。可是，如果说，`{ }`里面的数量多于`Point`的成员数量导致失败我能理解，为啥少于里面的成员数量可以成功呢？其实原因很简单，那就是你没有**显式初始化的成员**会被**值初始化**。于是`{ }`里面的参数，可以少于实际的字段数量。但是如果字段禁止了默认构造函数，就没法进行值初始化，就会编译错误

```cpp
struct X { X() = delete; } // 默认构造函数被删除
struct B
{  
    X x; 
    X y; 
    int z; 
};
```

对于下面这个类型，我们如果用`Any`尝试的话，应该是`0`,`1`不行,`2`,`3`可以,`4`,`5`,`...`以及往后的都不行。也就是说至少要让所有**不能默认初始化**的成员都初始化之后才行。 如果一个类型支持默认初始化，那么搜索它的有效区间是`[0, N]`其中`N`就是它的**最大字段数量**。如果不支持默认初始化，那其实搜索区间就变成了`[M, N]`，`M`是保证其不能默认初始化的成员全都初始化的最小数量。

我们之前的搜索策略是从`0`开始搜索，如果当前这个是`true`，那就求下一个，直到`false`停止。显然这种搜索策略不适合现在这种情况了，因为在`[0, M)`之间，也符合之前的搜索策略搜索失败的情况。我们现在要改成，如果当前这个是`ture`并且下一个是`false`才停止搜索，这样刚好能搜到这个**区间的上界**。

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

测试一下

```cpp
struct A{ int& x; };
static_assert(member_count<A>() == 1); 

struct X { X() = delete; }; // 默认构造函数被删除
struct B{ X x; X y; };
static_assert(member_count<B>() == 2);
```

`OK`，第二个问题也解决了，实在是太酷了！

### 数组的问题 

如果在结构体的成员里面有数组，那么计算的时候最终得到的结果就是把数组的每一个成员都当成一个字段来计算，其实就是因为对标准数组的聚合初始化开了后门

```cpp
struct Array { int x[2]; };
Array{ 1, 2 }; // OK
```

注意到没有，只有一个字段却可以填两个值。但是对数组开洞就导致了这样的困境，如果结构体里面含有数组就会最终得到错误的计数。那有没有什么办法能解决这个问题？

*注意：下面这部分可能有点难以理解* 

考虑下面这个例子

```cpp
struct D
{
    int x;
    int y[2];
    int z[2];
}
```

举例子，来看一下它初始化的情况：

```cpp
D{ 1, 2, 3, 4, 5 } // OK

// 第 0 个位置
D{ {1}, 2, 3, 4, 5 } // OK, 0号位置最多放置 1 个元素
D{ {1, 2}, 3, 4, 5 } // Error 

// 第 1 个位置
D{ 1, {2}, 3, 4, 5 } // Error
D{ 1, {2, 3}, 4, 5 } // OK, 1号位置最多放置 2 个元素
D{ 1, {2, 3, 4}, 5 } // Error

// 第 3 个位置
D{ 1, 2, 3, {4}, 5} // Error
D{ 1, 2, 3, {4, 5} } // OK, 3号位置最多放置 2 个元素
```

没错，我们可以利用嵌套初始化，来解决这个问题！我们先用原本的方法求出最大的可能的结构体字段数量（包含数组展开的，这里就是5个），然后再在每个位置尝试把原本的序列塞到这个嵌套初始化里面去，通过不停尝试就能找到这个位置所能放置的元素的最大数量，如果最大数量超过`1`的话，说明这个位置是个数组。这个最大数量就是数组的元素数量，我们在最后的结果中，把多余数量减掉就行了。

**听起来简单，实现起来还是有点复杂的哦。**

先写一个函数用来辅助，通过填不同的`N1`,`N2`,`N3`就能对应到上面不同情况了，注意`I2`那里的`Any`那里是嵌套初始化，多了一层括号

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

接下来我们要写一个函数，用来测试在指定位置用二层`{ }` 放置`N`个元素是不是可行的

```cpp
template <typename T, std::size_t position, std::size_t N>
constexpr bool try_place_n_in_pos()
{
    constexpr auto Total = member_count<T>(); // 可能的最大字段数量
    if constexpr (N == 0) // 放置 0 个和原本的效果是一样的肯定可行
    {
        return true;
    }
    else if constexpr (position + N <= Total) // 元素数量之和的肯定不能超过总共的
    {
        return test_three_parts<T, position, N, Total - position - N>();
    }
    else 
    {
        return false;
    }
}
```

由于内容有点多，可能有点难以理解，我们这里先展示一下这个函数的测试结果，方便理解，这样如果你看不懂函数实现也没问题。 还是以之前那个结构体`D`为例子

```cpp
try_place_n_in_pos<D, 0, 1>(); 
// 这其实就是在测试 D{ {1}, 2, 3, 4, 5 } 这种情况
// 在 0 号位置放置 1个元素

try_place_n_in_pos<D, 1, 2>();
// 这其实就是在测试 D{ 1, {2, 3}, 4, 5 } 这种情况
// 在 1 号位置放置 2 个元素
```

好了，看懂这个函数是在做什么事情就行了，在某一个位置不停地尝试就行了，然后就能找到这个位置能放置的最大的元素数量了。

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

这里就是在这个位置搜索能放置的元素最大数量

```cpp
static_assert(search_max_in_pos<D, 0>() == 1); // 1, 0号位置最多放置 1 个元素
static_assert(search_max_in_pos<D, 1>() == 2); // 2, 1号位置最多放置 2 个元素
static_assert(search_max_in_pos<D, 3>() == 2); // 2, 3号位置最多放置 2 个元素
```

这与我们最开始的手动测试结果一致，接下来就是遍历所有位置，找出所有的额外的数组元素数量，然后从一开始的那个最大数量里面减掉这些多余的就行了。

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

这里就是递归的找，结果储存在数组里面。注意这里`N + value`，如果这里找到两个元素了，我们可以直接往后挑两个位置。例如`1`号位置可以放置`2`个元素，那我直接找`3`号位置就行了，不用找`2`号位置了。

接下来就是把结果都存到数组里面然后，把多余的减掉就行了。

```cpp
template<typename T>
constexpr auto true_member_count()
{
    constexpr auto Total = member_count<T>();
    if constexpr (Total == 0)
    {
        return 0;
    }
    else
    {
        std::array<std::size_t, Total> indices = { 1 };
        search_all_extra_index<T>(indices);
        std::size_t result = Total;
        std::size_t index = 0;
        while (index < Total)
        {
            auto n = indices[index];
            result -= n - 1;
            index += n;
        }
        return result;
    }
}
```

测试一下结果

```cpp
struct D
{
    int x;
    int y[2];
    int z[2];
};
static_assert(true_member_count<D>() == 3);

struct E
{
    int& x;
    int y[2][2];
    int z[2];
    int&& w;
};
static_assert(true_member_count<E>() == 4);
```

拿这里的`E`类型最后生成的数组举一下例子吧，可以都`print`出来看看

```cpp
index: 0 num: 1  // 0 号位置对应 x， 数量是 1 合理
index: 1 num: 4  // 1 号位置对应 y， 数量是 4 合理
index: 5 num: 2  // 5 号位置对应 z， 数量是 2 合理
index: 7 num: 1  // 7 号位置对应 w， 数量是 1 合理
```

完美谢幕！我很佩服这个作者的想法，真的是太巧妙了，让人叹为观止。然而，在文章的末尾他却说道，

>  As it could be seen, I ran into some inconsistencies between gcc and clang (and for some reason I haven’t managed to make it work on MSVC at all, but that is another story). 

他说，他遇到了`clang`和`gcc`的行为不一致的情况，而且完全没法让这种方法在`msvc`上工作。

**看来事情远远没有结束！**

## 第三棒 YKIKO 

我花了一些时间读懂了刚才这位作者的文章，说实话他的模板写的我很难读懂，他不喜欢用`if constexpr`来做分支选择，用了很多特化来做选择，给可读性造成了很大影响。所以刚才那些代码并不完全是原作者中的代码，是我用我认为的，更好阅读的形式进行转译的。

哪些情况会`break`第二位作者的代码呢？ 

- 移动构造被删除


```cpp
struct X { X(X&&) = delete; };
struct F{ X x; };
static_assert(true_member_count<F>() == 1); // error
```

- 结构体中含有其它结构体成员


```cpp
struct Y{ int x; int y; };
struct G{ Y x; int y; };
static_assert(true_member_count<G>() == 2); // error
```

- `MSVC`的`bug`和`GCC`的`bug`


### 移动构造被删除的问题 

这一切都源于`C++17`加入的一条新规则，是关于 [copy elision](https://en.cppreference.com/w/cpp/language/copy_elision) 的。

>  Since C++17, a prvalue is not materialized until needed, and then it is constructed directly into the storage of its final destination. This sometimes means that even when the language syntax visually suggests a copy/move (e.g. copy initialization), no copy/move is performed — which means the type need not have an accessible copy/move constructor at all.  

什么意思呢，举例子说明最清晰

```cpp
struct M
{
    M() = default;
    M(M&&) = delete;
};

M m1 = M(); // ok in C++17, error in C++14
M m2 = std::move(M()); // error
```

啊？为什么会这样，第一个可以编译通过，第二个不行，难道我写`std::move`还多余了吗？

其实第二个编译不通过的原因是很好理解的，因为移动构造函数被删除了，所以没法调用移动构造函数了，于是就编译失败了。注意到第一种情况在`C++14`和`C++17`中的行为是不一样的，`C++14`是先产生临时对象，然后调用移动构造函数，初始化`m1`，但是这样的行为其实是多余的，所以编译器可能会优化掉这步多余的步骤。但是这里还是有调用移动构造函数的可能性，所以删除构造函数了就`GG`了，编译失败。**到了C++17这个优化直接变成语言强制性的要求了**，所以完全没有**移动构造**这一步了，自然也不需要可访问的构造函数了，所以在`C++17`可以编译通过。

**这也就意味着，右值之间亦有差距**。`prvalue`即纯右值可以直接复制消除构造对象（比如这里的**非引用类型**的函数返回值就是纯右值），但是`xvalue`也即亡值必须得有可调用的移动构造函数才行，也不行进行复制消除（**右值引用类型**的函数返回值就是亡值）。所以这里`std::move`反倒起了负面效果。

回到我们的问题，注意到`Any`有一个转化成右值引用类型的转换函数，所以如果遇到了这种情况就没办法了。但是再次通过巧妙地修改，又能解决这个问题：

```cpp
struct Any
{
    constexpr Any(int) {}

    template<typename T>
    requires std::is_copy_constructible_v<T>
    operator T&();

    template<typename T>
    requires std::is_move_constructible_v<T>
    operator T&&();

    template<typename T>
    requires(!std::is_copy_constructible_v<T> && !std::is_move_constructible_v<T>)
    operator T();
};
```

注意到我们这里对类型做了约束，如果是不可移动的类型（移动构造被删除），那就对应到了最后一个类型转换函数。直接产生`prvalue`构造对象，这样就巧妙地解决了这个问题了。写拷贝构造的约束是为了防止重载决议歧义（同时在最后可以顺便修复`MSVC`的`bug`）。

### 结构体中含有其它结构体成员 

事实上作者原本的思路很好，但是忽略了一个问题，那就是**不只有数组类型在可以使用二重**`{{ }}`初始化，结构体也是可以的

```cpp
struct A{ int x; int y; };
struct B{ A x; int y; };
B{ {1, 2}, 3 }; // ok
```

所以如果这个位置有是结构体成员的话，就会导致错误的计数。所以我们需要先判断一个下这个位置是不是结构体，如果是的话，就不用对这个位置尝试求最大放置数量了，直接去求下一个位置就行了

那怎么判断当前位置成员是不是结构体呢？考虑下面这个例子

```cpp
struct A{ int x; int y; };
struct B
{ 
    A x; 
    int y[2]; 
};
```

手动枚举一下测试情况

```cpp
Any any(1);
B{ any, any, any }; // ok
B{ {any}, any, any }; // ok
B{ {any, any}, any, any }; // ok

B{ any, {any}, any }; // error
B{ any, {any, any}, any }; // error
```

`OK`其实答案很显然了，那就是如果当前位置是结构体的话，可以往这个位置额外添加元素。注意到原本的`Total`即最大可能的元素数量是`3`，但是如果当前位置是结构体的话，放`4`个元素也是可以，但是如果是数组就不行了。我们利用这个特性来判断当前位置的是不是结构体，如果是的话，就跳去下一个位置，如果不是就在这个位置搜索最大能放置的元素。

其实就是在这个位置递归尝试放置元素，但是这里有一个问题是，当前位置的结构体成员中仍然可能含有不能默认初始化的成员。所以究竟放几个才能确定这个位置能被初始化呢？这还是不确定的，我这里设置的最大上线是`10`个，如果子结构体中不能默认初始化的成员位置在`10`之后的话这个方法就失败了。

```cpp
template <typename T, std::size_t pos, std::size_t N = 0, std::size_t Max = 10>
constexpr bool has_extra_elements()
{
    constexpr auto Total = member_count<T>();
    if constexpr (test_three_parts<T, pos, N, Total - pos - 1>())
    {
        return false;
    }
    else if constexpr (N + 1 <= Max)
    {
        return has_extra_elements<T, pos, N + 1>();
    }
    else
    {
        return true;
    }
}
```

有了这个函数之后在把原来那个`serach`函数逻辑稍微改一下就行了

```cpp
template<typename T, std::size_t pos, std::size_t N = 0>
constexpr auto search_max_in_pos()
{
    constexpr auto Total = member_count<T>();
    if constexpr (!has_extra_elements<T, pos>())
    {
        return 1;
    }
    else
    {
        // ... 原本的代码不变
    }
}
```

就是加一个分支判断，如果当前位置没有额外的元素就直接返回`1`，如果有的就去搜索（数组的）最大边界。这样的话就解决了原作者的代码中中的问题了

仍然测试一下

```cpp
struct Y{ int x; int y; };
struct G{ Y x; int y; };
static_assert(true_member_count<G>() == 2); // OK
```

`Nice`！！！太好了。

### MSVC 的 bug 和 GCC 的 bug 

作者在原文中提到的`GCC`和`MSVC`的问题我也一并找出来了，`MSVC`目前有一个[缺陷](https://developercommunity.visualstudio.com/t/MSVC-accepts-invalid-initialization-of-a/10541811)：

```cpp
struct Any
{
    template<typename T> // requires std::is_copy_constructible_v<T>
    operator T&() const;
};

int main()
{
    struct A { int x[2]; };
    A a{ Any{} }; // 这里 Any 转化成 int(&)[2]类型了，即数组的引用
}
```

上述的代码可以正常编译，这意味着`MSVC`允许直接从数组的引用聚合初始化数组成员。但是这是`C++`标准所不允许的，这个`Bug`会导致在`MSVC`上对成员计数错误，解决办法其实很简单，前面我们已经顺便解决过这个问题了，只要把注释的那行加上就行了。因为数组是不可拷贝构造的类型，所以约束会把这个重载函数排除掉，这样就不会出现这个问题了。

`GCC 13`也有一个严重的 [缺陷](https://gcc.gnu.org/bugzilla/show_bug.cgi?id=113141)，直接会导致`ice`，这个`bug`用下面几行代码就能复现出来：

```cpp
struct Number
{
    int x;
    operator int&(){ return x; }
};

struct X { int& x; };

template<typename T>
concept F = requires{ T{ { Number{} } }; };

int main()
{
    static_assert(!F<X>); // internal compiler error
}
```

这个显然是不应该导致`ice`的，而且只在`GCC 13`才有这个`bug`实在是很奇怪。测试代码在 [godbolt](https://godbolt.org/z/jW4YWYf1P) 。`clang`没任何问题，但是`GCC 13`就直接内部编译器错误了。而`GCC 12`和`clang`的编译结果不一样`...`但是其实`clang`是对的。这也就是原作者文章里面说的`clang`和`gcc`不一致的地方。*注：后经评论区提醒，clang 15也会遇到类似的内部编译器错误。 * 

## 后记 

后来又和评论区的各位讨论了一番，上面的处理仍然有些欠缺考虑。一个典型的例子是，当成员变量的构造函数是模板函数的时候就会出错，例如`std::any`，原因是不知道调用类型转换函数和模板构造函数中的哪一个（重载决议失败）

```cpp
std::any any = Any(0); // conversion from 'Any' to 'std::any' is ambiguous
// candidate: 'Any::operator T&() [with T = std::any]'
// candidate: 'std::any::any(_Tp&&)
```

但是目前还没有一个完美的解决办法能解决这个问题，不能直接检测`T`能不能由`Any`构造来解决这个问题，这会涉及到递归的约束，最后导致无法求解，从而编译错误。这里用了一个比较取巧的办法

```cpp
struct Any
{
    constexpr Any(int) {}

    template <typename T>
    requires(std::is_copy_constructible_v<T>)
    operator T&();

    template <typename T>
    requires(std::is_move_constructible_v<T> && !std::is_copy_constructible_v<T>)
    operator T&&();

    struct Empty{};

    template <typename T>
    requires(!std::is_copy_constructible_v<T> && !std::is_move_constructible_v<T> && !std::is_constructible_v<T, Empty>)
    operator T();
}; 
```

就是声明了一个空类，然后尝试用这个空类能不能转换成类型`T`，如果不行就能说明`T`的构造函数应该不是模板函数，于是类型转换可以生效。如果可以，则说明`T`的构造函数是模板函数，要排除这个类型转换函数。当然了，如果`T`的构造函数有一些奇怪的约束，比如直接把`Empty`排掉，但是接受`Any`。这样话还是会导致错误，但是这属于刻意为之了，正常情况下基本是不会遇到这个问题的，这个问题可以算是解决了 

除此之外还有一个和引用相关的问题，如果结构体中含有不可拷贝/复制类型的引用成员，那么也会失败，下面就拿左值引用举例子吧

```cpp
struct CanNotCopy
{
    CanNotCopy(const CanNotCopy&) = delete;
};

struct X { CanNotCopy& x; };

X x{ Any(0) }; // error
```

这里`T`就会实例化成`CanNotCopy`类型。显然因为它不可拷贝，导致重载决议选到了`operator T()`上，然后实际产生的是右值没法绑定到左值引用，就编译错误了。那这个问题可能解决吗？非常困难。事实上，我们无法让下面两个表达式同时成立

```cpp
struct X { CanNotCopy& x; };
struct Y { CanNotCopy x; };

X x{ Any(0) };
Y y{ Any(0) }; 
```

在这两个聚合初始化里面，类型转换函数实例化的`T`都是`CanNotCopy`类型，但是如果想让`x`，`y`都良构，那么就意味对于同一个`T`要选择两个不同的重载函数，第一个选`operator T&()`，第二个选`operator T()`，但是这两个函数之间并没有哪个更优先，`C++`也没法对返回值进行重载，所以这是做不到的。一个可能的解决方案是写三种`Any`,分别转化成`T&`，`T&&`，`T`然后在每个位置使用这三种进行尝试，这样的话倒是可以解决这个问题，**但是可能会导致模板实例化个数以3 ^ N次方的速度增长**。这种实现比之前的遍历方式加起来开销都要大，所以这里我就不做展示了，理论可行，实践上会累跨编译器

## 结语 

本文的全部代码都在 [Compiler Explorer - C++](https://godbolt.org/z/scPP6WxbT) 上，三大编译器均通过（gcc版本是12），有很多测试代码，如果你找到其它的`concer case`欢迎留言讨论 

好了，这篇文章到这里就结束了。如果你耐心看完了全文，相比你也是和我一样，喜欢这些好玩的东西。这种东西最有趣的地方就在于，利用`C++`暴露的一点点接口，去一步步扩展它，最后实现非常漂亮的接口出来。当然对于作者来说其实并不漂亮`OvO`。总之这种东西就像是游戏一样，是日常的消遣，没事给`C++`编译器找找`bug`，钻研这些犄角旮旯的特性，也是一份乐趣。如果非要谈实际价值，**其实这种东西几乎不可能在实际的代码生产环境中使用**。首先通过实例化大量模板来寻找结构体的字段数量，会大大拖慢编译速度，而且即使花费如此大的功夫，也只是实现了对聚合类型的遍历，还不支持其的非聚合类型。不仅副作用强，而且主要功能也不强。权衡一下考虑也是非常不值当了，对于这种需要类似反射的需求的时候，在`C++`加入静态反射之前（真正用上也许还得过十年！？），目前真正可行的自动化方案是采用代码生成来做这个事情。

我也有相关的文章详细介绍了相关的原理，不依赖于这些奇淫巧技，真正可用于实际项目中的方案： 

{{< article link="zh-cn/articles/669358870" >}}

**当然如果用这些功能仅仅是为了log，debug或者study的话**，而不是用于任何核心的代码部分，又不想引入很重的依赖，那这些东西用一用也未尝不可。我专门写了一个`C++20`的库，把这些有用的奇淫巧技都合并起来了，方便进行`log`，`debug`之类的。目前还在更新中，欢迎`star`和报告问题呐

{{< article link="https://github.com/16bit-ykiko/magic-cpp" >}}

