---
title: 'C++ 禁忌黑魔法：STMP （上）'
date: 2023-07-29 10:20:50
updated: 2024-07-20 14:19:41
---

众所周知，传统的 C++ 的常量表达式求值既不依赖也不改变程序全局的状态。对于任意相同的输入，它的输出结果总是相同的，被认为是**纯函数式 (purely functional)** 的。**模板元编程 (Template Meta Programming)** 作为常量求值的一个子集，也应该遵守这个规则。 

![](https://pic3.zhimg.com/v2-310046d2ded45ca99cb74d992a94a51e_r.jpg)

 但事实真的如此吗？在不违背 C++ 标准的情况下，下面的代码可能通过编译吗？

```cpp
constexpr auto a = value();
constexpr auto b = value();
static_assert(a != b);
```

下面这样的编译期计数器可能实现吗？

```cpp
constexpr auto a = next();
constexpr auto b = next();
constexpr auto c = next();
static_assert(a == 0 && b == 1 && c == 2);
```

每次常量求值得到的结果不同，说明求值改变了全局的状态。这种有状态的元编程，就叫做状态元编程。如果再与模板联系起来，就叫做 **Stateful Template Meta Programming(STMP)**。

其实借助一些编译器内置的宏，我们是可以实现这样的效果的，比如

```cpp
constexpr auto a = __COUNTER__;
constexpr auto b = __COUNTER__;
constexpr auto c = __COUNTER__;
static_assert(a == 0 && b == 1 && c == 2);
```

编译器在预处理的时候，会对`__COUNTER__`宏的替换结果进行递增。如果你对源文件执行预处理，会发现源文件变成了这样

```cpp
constexpr auto a = 0;
constexpr auto b = 1;
constexpr auto c = 2;
static_assert(a == 0 && b == 1 && c == 2);
```

这与我们想要实现的效果还是有很大区别的，毕竟预处理并不涉及到 C++ 程序的语义部分。而且这样的计数器是全局唯一的，我们并不能创建很多个计数器，那还有别的办法吗？

答案是肯定的。不管多么难以置信，相关的 [讨论](https://b.atch.se/posts/non-constant-constant-expressions/) 其实早在 2015 年的时候就有了，知乎上也有相关的 [文章](https://zhuanlan.zhihu.com/p/24835482)。但这篇文章是 2017 年发布的，使用的 C++ 版本还是 14，时过境迁，文章里面已经有很多的内容不适用了。更何况现在 C++26 的相关标准都开始制定了，有很多东西需要被重新讨论。我们将要选择的版本是 C++20。

如果你只对代码感兴趣，我已经将相关的代码放在 [Compiler Explorer](https://godbolt.org/z/T543Tvc3q) 上。三大编译器 C++20 均编译通过，你可以直接看到编译器的输出结果。为了防止链接失效，也放到 [GitHub](https://github.com/16bit-ykiko/blog/blob/main/code/compile-time-counter.cpp) 上。如果你想要了解它的原理，欢迎继续往下阅读。C++ 标准非常复杂，作者也没法保证文章内容完全正确，如果有任何错误，欢迎评论区讨论交流。

>  注意：本文仅仅是技术讨论，请不要将相关的代码运用于实际生产中。根据 [CWG 2118](https://cplusplus.github.io/CWG/issues/2118.html)，相关的代码似乎被认为是非良构的 (ill formed)。并且 STMP 较为容易造成 ODR 违背，需要十分谨慎。 

# observable state 

在改变之前，我们首先得能在编译期观测到全局状态的变化。由于 C++ 支持**向前声明 (forward declaration)**，而一个`struct`在看到 definition 之前被认为是**不完整类型 (incomplete type)**，即类的完整性在不同的上下文中是不同的。

而 C++ 标准规定`sizeof`只能对完整类型使用（毕竟不完整类型没有定义无法计算`size`）。如果对不完整类型使用会导致编译错误，并且这个错误不是一个**硬错误 (hard error)**，所以可以利用`SFINAE`或`requires`来捕获到这个错误。于是我们就能通过如下的方式检测类的完整性

```cpp
template <typename T>
constexpr inline bool is_complete_v = requires { sizeof(T); };
```

> 可能有读者会问，都 C++20 了为什么不使用 concept 呢？这里用 concept 会有一些奇怪的效果，是标准中有关原子约束 (atomic constraint) 的措辞导致的。就不深究了，感兴趣的读者可以自行尝试。 

尝试使用它来观测类型完整性

```cpp
struct X;

static_assert(!is_complete_v<X>);

struct X {};

static_assert(is_complete_v<X>);
```

实际上，上面的代码会编译错误，第二个静态断言失败了。太奇怪了，怎么回事呢？分开试一下

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

分开试发现都行，但是放一起就不行了，究竟为什么会这样呢？还记得文章开头说的那段话吗？

> 传统的 C++ 的常量表达式求值既不依赖也不改变程序全局的状态。对于任意相同的输入，它的输出结果总是相同的。 

不仅 C++ 标准这么认为，编译器也这么认为。为了提高编译速度，编译器会把模板实例化的结果缓存起来，也就是会把在第一个位置实例化的结果记录下来，之后再遇到相同的模板会直接复用这个结果。所以在上面的代码中，第二个`is_complete_v<X>`仍然使用第一次实例化的模板，导致求值为`false`，于是静态断言失败了。

如何解决呢？答案是加一个模板参数作为种子，每次求值的时候填入不同的参数，从而让编译器实例化新的模板

```cpp
template <typename T, int seed = 0>
constexpr inline bool is_complete_v = requires { sizeof(T); };

struct X;

static_assert(!is_complete_v<X, 0>);

struct X {};

static_assert(is_complete_v<X, 1>);
```

每次都手动填入一个不同的参数是很麻烦的，有没有什么办法能自动填入呢？

注意到如果用 lambda 表达式作为 **Non Type Template Parameter(NTTP)** 默认模板参数，则该模板每次实例化的时候都是不同的类型

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

这个特性很好的满足了我们的需求，它可以每次自动填入一个不同的种子。于是最终的`is_complete_v`实现如下

```cpp
template <typename T, auto seed = [] {}>
constexpr inline bool is_complete_v = requires { sizeof(T); };
```

再次尝试使用它来观测类型完整性

```cpp
struct X;

static_assert(!is_complete_v<X>);

struct X {};

static_assert(is_complete_v<X>);
```

编译通过！至此，我们成功观察到了编译期全局状态的变化。

# modifiable state 

再可以观测到状态变化之后，下面我们要考虑能否通过代码来主动进行状态更改。很可惜，对于绝大多数 declaration 来说，你唯一能改变它们的状态的办法就是通过修改源代码来添加 definition，没有其它的手段实现这个效果。

唯一的例外是友元函数。但在考虑友元函数如何发挥作用之前，先让我们考虑一下如何观测到一个函数有没有被定义。对于绝大多数的函数是无法观测的，考虑到函数可能定义在其它编译单元，调用一个函数并不要求其定义可见。

例外就是返回值类型为`auto`的函数，如果看不到它的函数定义，则无法推导出返回值类型，进而无法进行函数调用。下面的代码就可以检测`foo`函数是否有定义

```cpp
template <auto seed = [] {}>
constexpr inline bool is_complete_v = requires { foo(seed); };

auto foo(auto);

static_assert(!is_complete_v<>);

auto foo(auto value) { return sizeof(value); }

static_assert(is_complete_v<>);
```

接下来让我们谈谈如何通过友元函数来改变全局的状态。

友元函数与普通函数最大的不同就在于不要求函数定义与函数声明在同一 scope 中，考虑如下示例

```cpp
struct X {
    friend auto foo(X);
};

struct Y {
    friend auto foo(X) { return 42; }
};

int x = foo(X{});
```

上面的代码三大编译器都可以编译通过，并且完全符合 C++ 标准。这就给了我们操作的空间，我们可以在实例化类模板同时实例化其内部定义的友元函数，从而给其它位置的函数声明添加定义。这种技术也被叫做**友元注入 (friend injection)**。

```cpp
auto foo(auto);

template <typename T>
struct X {
    friend auto foo(auto value) { return sizeof(value); }
};

static_assert(!is_complete_v<>); // #1

X<void> x; // #2

static_assert(is_complete_v<>); // #2
```

注意到 #1 处模板`X`没有任何的实例化，故此时`foo`函数还未有定义，于是`is_complete_v`返回`false`。而在 #2 处，我们实例化了一个`X<void>`，进而导致`X`内的`foo`函数被实例化，给`foo`添加了一个定义，于是`is_complete_v`返回`true`。当然了，函数定义最多只能有一个，如果你再尝试实例化一个`X<int>`，这时候编译器就会报`foo`被重定义的错误了。

# constant switch 

结合上面提到的技巧，我们可以轻松实例化一个编译时的开关了

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

它的原理很简单。第一次的时候，`setter`尚未有任何实例化，所以`flag`函数也没有定义，于是`exist`求值为`false`，走到了`if constexpr`里面那个分支，实例化了一个`setter<false>`，并且返回`false`。第二次的时候，`setter`有了一个实例化，`flag`函数也有了定义，于是`exist`求值为`true`，直接返回`true`。

> 注意，这里的 N 的类型必须写成 auto，而不能使用 std::size_t。只有这样`flag(N)`才是 [dependent name](https://en.cppreference.com/w/cpp/language/dependent_name)，才能被 requires 检测表达式合法性。由于模板的 [two phase lookup](https://en.cppreference.com/w/cpp/language/two-phase_lookup)，如果写成`flag(0)`，会在第一阶段就进行查找，发现调用失败，产生一个 hard error，导致编译失败。 

# compile time counter 

更进一步，我们可以直接实现一个编译期的计数器

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

它的逻辑是，从`N`为 0 开始，检测`flag(reader<N>{})`是否有定义，如果没有定义就实例化一个`setter<N>`，并返回`N`，否则递归调用`next<N + 1>()`。所以这个计算器记录的实际上是`setter`的实例化次数。

# easter egg: access private 

首先要明确一个观点：类的访问权限说明符`private`, `public`, `protected`仅仅只作用于编译期的检查。如果能通过某种手段绕过这个编译期检查，那完全就可以合法的访问类的任意成员。

那么存在这样的方法吗？有的：**模板显示实例化的时候会忽略类作用域的访问权限：**

>  The C++11/14 standards state the following in note 14.7.2/12 [temp.explicit]: The usual access checking rules do not apply to names used to specify explicit instantiations. [ Note: In particular, the template arguments and names used in the function declarator (including parameter types, return types and exception speciﬁcations) may be private types or objects which would normally not be accessible and the template may be a member template or member function which would not normally be accessible. — end note ]  

也就是说在模板**显示实例化 (explicit instantiate)** 的时候，我们可以直接访问类的私有成员。

```cpp
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

其中 #2 处的语法就是模板显式实例化了，我们可以直接访问到`Bank`的私有成员`money`。通过`&Bank::money`从而取得该成员对应的成员指针。于此同时，该模板显式实例化还通过友元函数，给 #1 处的`steal`函数添加了一个定义，从而可以直接在 #3 处调用该函数并获取到`money`的引用。最后成功输出 100。