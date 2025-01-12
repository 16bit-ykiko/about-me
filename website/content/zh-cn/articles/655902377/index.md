---
title: '雾里看花：真正意义上的理解 C++ 模板'
date: 2023-09-12 23:46:11
updated: 2024-11-01 00:23:44
---

在 C++ 中，模板（Template）这个概念已经存在二十多年了。作为 C++ 最重要的一个语言构成之一，相关的讨论数不胜数。很可惜的是，深入有价值的讨论很少，尤其是以多个视角来看待这个特性。很多文章在谈论模板的时候往往会把它和各种语法细节缠绕在一起，容易给人一种云里雾里的感觉。类似的例子还发生在其它话题上面，比如介绍协程就和各种 IO 混在一起谈，谈到反射似乎就限定了 Java，C# 中的反射。这样做并不无道理，但是往往让人感觉抓不到本质。看了很多内容，但却不得其要领，反倒容易把不同的概念混淆在一起。

就我个人而言，讨论一个问题喜欢多层次，多角度的去讨论，而不仅限于某一特定的方面。这样一来，既能更好的理解问题本身，也不至于让自己的视野太狭隘。故本文将尝试从模板诞生之初开始，以四个角度来观察，理清模板这一特性在 C++ 中的发展脉络。注意，本文并不是教学文章，不会深入语法细节。更多的谈论设计哲学和 trade-off 。掌握一些模板的基础知识就能看懂，请放心阅读。当然，这样可能严谨性有所缺失，如有错误欢迎评论区讨论。

**我们主要讨论四个主题：**

- 代码生成 (Code Generation)
- 类型约束 (Type Constraint)
- 编译时计算 (Compile-time Computing)
- 操纵类型 (Type Manipulation)


其中第一个主题一般认为就是普通的 Template。而后三者一般被规划到 TMP 中去。TMP 即 Template meta programming 也就是模板元编程。因为模板设计之初的意图并不是实现后面这三个功能，但是最后却通过一些奇怪的 trick 实现了这些功能，代码写起来也比较晦涩难懂，所以一般叫做元编程。

## Code Generation 

### Generic 

**泛型 (Generic)** 编程，也就是为不同的类型编写相同的代码，实现代码复用。在加入模板之前，我们只能通过宏来模拟泛型。考虑下面这个简单的示例：

```cpp
#define add(T) _ADD_IMPL_##T

#define ADD_IMPL(T)        \
    T add(T)(T a, T b) {   \
        return a + b;      \
    }

ADD_IMPL(int);
ADD_IMPL(float);

int main() {
    add(int)(1, 2);
    add(float)(1.0f, 2.0f);
}
```

它的原理很简单，就是把普通函数中的类型替换成宏参数，通过宏符号拼接来为不同的类型参数生成不同的名字。再通过`IMPL`宏来为特定的函数生成定义，这个过程可以叫做**实例化 (instantiate)**。

当然，这只是一个最简单的例子，也许你觉得看上去还不错。但如果要用宏来实现一个`vector`呢？想想就有点可怕。具体来说，用宏来实现泛型主要有如下几个缺点

- 代码可读性差，宏的拼接和代码逻辑耦合，报错信息不好阅读
- 很难调试，打断点只能打到宏展开的位置，而不是宏定义内部
- 需要显式写出类型参数，参数一多起来就会显得十分冗长
- 必须手动实例化函数定义，在较大的代码库中，往往一个泛型可能有几十个实例化，全部手动写出过于繁琐


这些问题，在模板中都被解决了：

```cpp
template <typename T>
T add(T a, T b) {
    return a + b;
}

template int add<>(int, int);  // explicit instantiation

int main() {
    add(1, 2);         // auto deduce T
    add(1.0f, 2.0f);   // implicit instantiation
    add<float>(1, 2);  // explicitly specify T
}
```

- 模板就是占位符，不需要字符拼接，和普通的代码别无二致，仅仅多了一项模板参数声明
- 报错和调试都能准确的指向模板定义的位置，而不是模板实例化的位置
- 支持模板参数自动推导，不需要显式写出类型参数，同时也支持显式指定类型参数
- 支持**隐式实例化 (implicit instantiation)**，即由编译器自动实例化使用到的函数。也支持**显式实例化 (explicit instantiation)**，即手动实例化。


除此之外，还有诸如**偏特化 (partial specialization)**，**全特化 (full specialization)**，**可变模板参数 (variadic template)**，**变量模板 (variable template)** 等等一系列特性，这些仅凭宏都是做不到的。正是由于模板的出现，才使用 STL 这样的泛型库的实现成为可能。

### Table Gen 

上面提到的泛型，可以看成模板最直接的用法。基于它们我们可以有一些更加高级的代码生成，例如在编译期生成一个确定的表以供运行期查询。标准库中`std::visit`的实现就利用了这种技巧，下面是它的一个简单模拟

```cpp
template <typename T, typename Variant, typename Callback>
void wrapper(Variant& variant, Callback& callback) {
    callback(std::get<T>(variant));
}

template <typename... Ts, typename Callback>
void visit(std::variant<Ts...>& variant, Callback&& callback) {
    using Variant = std::variant<Ts...>;
    constexpr static std::array table = {&wrapper<Ts, Variant, Callback>...};
    table[variant.index()](variant, callback);
}

int main() {
    auto callback = [](auto& value) { std::cout << value << std::endl; };
    std::variant<int, float, std::string> variant = 42;
    visit(variant, callback);
    variant = 3.14f;
    visit(variant, callback);
    variant = "Hello, World!";
    visit(variant, callback);
    return 0;
}
```

尽管`variant`中储存的元素类型是在运行时才能确定的，但是它可能取值的类型集合在编译期就可以确定，所以我们用`callback`给集合中每一个可能的类型都实例化一个对应的`wrapper`函数，并且存到一个数组里面。在运行时直接用`variant`的`index`访问数组里面对应的成员即可完成调用了。

当然，利用 C++17 加入的**折叠表达式 (folding expression)** 我们其实有更好的做法

```cpp
template <typename... Ts, typename Callback>
void visit(std::variant<Ts...>& variant, Callback&& callback) {
    auto foreach = []<typename T>(std::variant<Ts...>& variant, Callback& callback) {
        if(auto value = std::get_if<T>(&variant)) {
            callback(*value);
            return true;
        }
        return false;
    };
    (foreach.template operator()<Ts>(variant, callback) || ...);
}
```

利用逻辑运算符的短路特性，我们可以提前退出后续折叠表达式的求值，短的函数也更加有利于内联。

## Type Constraint 

别的我都同意，但是模版的报错信息明明一点都不好读啊。和宏比起来，难道不是五十步笑百步吗？甚至有过之而无不及。轻松产生几百，几千行的报错，我想只有 C++ 的模板能做到吧。

这就是接下来要讨论的问题，为什么 C++ 的编译错误信息这么长？而且有时候非常难读懂。

### Function Overload 

考虑下面这个只有几行的简单示例

```cpp
struct A {};

int main() {
    std::cout << A{} << std::endl;
    return 0;
}
```

在我的 GCC 编译器上，足足产生了 239 行报错信息。不过好消息是 GCC 把关键部分标记出来了，如下所示：

```cpp
no match for 'operator<<' (operand types are 'std::ostream' {aka 'std::basic_ostream<char>'} and 'A')
    9 |     std::cout << A{} << std::endl;
      |     ~~~~~~~~~ ^~ ~~~
      |          |       |
      |          |       A
      |          std::ostream {aka std::basic_ostream<char>}
```

那大概还是能读懂的的，意思就是没有找到匹配的重载函数，也就是说我们需要为`A`重载`operator<<`。但我们好奇的是，剩下的两百行报错在干嘛呢？其实关键就在于**重载决议 (Overload Resolution)**。让我们来看其中一段信息

```cpp
note:   template argument deduction/substitution failed:
note:   cannot convert 'A()' (type 'A') to type 'const char*'
    9 |     std::cout << A{} << std::endl;
```

意思就是尝试用`A`类型匹配`const char*`这个重载（通过隐式类型转换），结果失败了。标准库类似中这样的函数，都有非常多的重载，比如这个`operator<<`就重载了`int`,`bool`,`long`,`double` 等等，将近几十个函数。结果报错信息就是把所有重载函数尝试失败的原因都列出来，于是轻松就有几百行了，再加上标准库诡异的命名，看起来就像天书一样。

### Instantiation Stack 

函数重载是导致报错信息难以读懂的一部分原因，但不是全部。实际上如上所示，仅仅是把所有可能性枚举出来，不过几百行报错。要知道我们还能产出上千行呢，量级上的差距可不是能用数量轻松弥补的。况且本小节要说的是类型约束，和编译器报错有什么关系呢。 考虑下面这个示例：

```cpp
struct A {};

struct B {};

template <typename T>
void test(T a, T b) {
    std::cout << a << b << std::endl;
}

int main() {
    test(A{}, B{});  // #1: a few lines
    test(A{}, A{});  // #2: hundred lines
}
```

在上面的实例中，`#1`处仅有短短的几行报错信息，而`#2`处却有上百行。为什么会出现如此大的差距呢？还记得我们在第一部分里面说到的模板相比于宏的两个优点吗？一个是自动类型推导，一个是隐式实例化。只有模板参数推导成功了，才会触发模板实例化，才会去检查函数体中出现的错误。

`test(A{}, B{})`这里模板参数推导失败了。因为`test`函数隐含了一个重要的条件，那就是 a 和 b 的类型是一样的，于是实际上它报的错误是找不到匹配的函数。而第二个函数`test(A{}, A{})`则是模板参数推导成功了，进入到实例化的阶段了，但是在实例化的阶段出错了。也就是说`T`已经被推断为`A`了，尝试把`A`代入函数体的时候，出错了。于是就只能把函数体中替换失败的原因列出来了。

这会导致一个问题，当出现很多层模板嵌套的时候，可能是最内层的模板函数出错，而编译器不得不把整个模板实例化栈都打印出来。

那对类型做约束有什么用呢？看下面这个例子

```cpp
struct A {};

template <typename T>
void print1(T x) {
    std::cout << x << std::endl;
}

template <typename T>
// requires requires (T x) { std::cout << x; }
void print2(T x) {
    print1(x);
    std::cout << x << std::endl;
}

int main() {
    print2(A{});
    return 0;
}
```

短短几行，在我的 GCC 上产生了 700 行的编译错误。稍微改动一下，把注释掉的那行代码加上。相比之下这种情况的代码报错只有短短几行：

```cpp
In substitution of 'template<class T>  requires requires(T x) {std::cout << x;} void print2(T) [with T = A]':
required from here
required by the constraints of 'template<class T>  requires requires(T x) {std::cout << x;} void print2(T)'
in requirements with 'T x' [with T = A]
note: the required expression '(std::cout << x)' is invalid
   15 | requires requires (T x) { std::cout << x; }
```

意思就是`A`类型的实例`x`不满足`requires`语句`std::cout << x`。事实上通过这样的语法，我们就可以把错误限制在类型推断的阶段，而不去进行实例化。于是相对的报错就会简洁很多了。

也就是说通过`requires`我们能阻止编译错误的传播。 但是可惜的是，约束相关的语法是在 C++20 才加入的。那在这之前呢？

### Before C++20 

在 C++20 之前，我们并没有这么好用的方法。只能通过一种叫做 [SFINAE](https://en.cppreference.com/w/cpp/language/sfinae) 的技术来实现类似的功能，对类型实现约束。比如上面那个功能，在 C++20 之前只能这么写：

```cpp
template <typename T, typename = decltype(std::cout << std::declval<T>())>
void print2(T x) {
    print1(x);
    std::cout << x << std::endl;
}
```

具体的规则在这里就不介绍了，感兴趣的可以去搜搜相关的文章看看。

结果就是

```cpp
typename = decltype(std::cout << std::declval<T>())
```

这行代码，让人捉不着头脑，完全不知道是在表达什么含义。只有深入了解 C++ 模板相关的规则之后才能看懂这究竟是在干嘛。关于为什么`requires`直到 C++20 才被加入，可以阅读 C++ 之父本人写的 [自述](https://github.com/Cpp-Club/Cxx_HOPL4_zh/blob/main/06.md)。

## Compile-time Computing 

### Meaning 

首先要肯定的一点是，编译期计算肯定是有用的。具体到特定场景，意义有多大，这肯定就不能一概而论了。有很多人谈编译期计算色变，什么代码难懂，屠龙技，没有价值云云。这样的确很容易误导初学者。事实上相关的需求的确存在。如果编程语言没有这个功能，但是确有需求，程序员也会想方设法的通过其它的办法来实现。

我将举两个例子来说明：

- 首先是编译器对常量表达式的优化，相信这个大家都并不陌生。极其简单的情况，像`1+1+x`这样的表达式，编译器会把它优化成`2+x`。事实上现代编译器对于类似的情况能做的优化非常多，比如这个 [问题](https://www.zhihu.com/question/619246858/answer/3184453259)。提问者问 C 语言的`strlen`函数在参数是常量字符串的时候，会不会把函数调用直接优化成一个常量。比如`strlen("hello")`会不会直接优化成`5`。从主流编译器的实验结果来看，答案是肯定的。类似的情况数不胜数，不知不觉中你就在使用编译期计算。只是它被归到编译器优化的一部分去了。而编译器的优化能力总归是有上限的，允许使用者自己定义这种优化规则，会更加灵活和自由。比如在 C++ 里面明确了`strlen`是`constexpr`的，这种优化必然会发生。 
- 其而是在程序语言发展早期，编译器优化能力还没那么强的时候。就已经开始广泛的使用外部脚本语言提前算好数据（甚至生成好代码）用来减少运行时开销了。典型的例子是算好三角函数表这种常量表，然后运行期直接用就行了。例如在编译代码之前，运行一段脚本用来生成一些需要的代码。


C++ 的编译期计算有明确的语义保证，并且内嵌于语言之中，能和其它部分良好的交互。从这个角度来说，很好的解决了上面两点问题。当然很多人对它的讨伐并不无道理，通过模板元编程进行的编译期计算。代码丑陋且晦涩难懂，牵扯到的语法细节多，并且大大拖慢编译时间，增加二进制文件大小。无可否认的是，这些问题的确存在。但是随着 C++ 版本的不断更新，编译期计算现在已经非常容易理解了，不再需要去写那些复杂的模板元代码，新手也能很快学会。因为和运行期代码几乎一样了。接下来伴随着它的发展史，我们将逐步阐明。

### History 

从历史上看，TMP 是一个偶然事件。在标准化 C++ 语言的过程中发现它的模板系统恰好是图灵完备的，即原则上能够计算任何可计算的东西。第一个具体演示是 Erwin Unruh 编写的一个程序，该程序计算素数，尽管它实际上并未完成编译：素数列表是编译器在尝试编译代码时生成的错误消息的一部分。具体的示例，请参考 [这里](https://en.wikibooks.org/wiki/C%2B%2B_Programming/Templates/Template_Meta-Programming#History_of_TMP)。

作为入门级别的编程案例，可以展示一个编译期计算阶乘的方法：

```cpp
template <int N>
struct factorial {
    enum { value = N * factorial<N - 1>::value };
};

template <>
struct factorial<0> {
    enum { value = 1 };
};

constexpr auto value = factorial<5>::value;  // => 120
```

这段代码即使在 C++11 之前也能通过编译，在那之后 C++ 引入了很多新的东西用于简化编译期计算。最重要的就是`constexpr`关键字了。可以发现在 C++11 之前，我们并没有合适的办法表示编译期常量这一概念，只能借用`enum`来表达。而 C++11 之后，我们可以这么写：

```cpp
template <int N>
struct factorial {
    constexpr static int value = N * factorial<N - 1>::value;
};

template <>
struct factorial<0> {
    constexpr static int value = 1;
};
```

尽管进行了一些简化，但实际上我们仍然是借助模板来进行编译期计算。这样写出的代码是难以读懂的，主要原因有以下两点： 

- 模板参数只能是编译期常量，并没有编译期变量的概念，无论是全局还是局部都没有 
- 只能通过递归而不能通过循环来进行编程


想象一下，如果平常写代码，把变量和循环给你禁了，那写起来是有多难受啊。

那有没有满足上面两个特征的编程语言呢？其实满足上面两点的编程语言，一般称为 pure functional 也即纯函数式的编程语言。Haskell 就是一个典型的例子。 但是 Haskell 它有强大的模式匹配，在熟悉了 Haskell 的思维之后，也能写出短小优美的代码（而且 Haskell 本身也能用 do 语法模拟出局部变量，因为使用局部变量，其实就相当于把它作为函数参数一级级传递下去）。而 C++ 这些都没有，属于是把别人缺点都继承来了，优点一个没有。幸运的是，上面这些问题都在`cosntexpr function`中都被解决了。

```cpp
constexpr std::size_t factorial(std::size_t N) {
    std::size_t result = 1;
    for(std::size_t i = 1; i <= N; ++i) {
        result *= i;
    }
    return result;
}

int main() {
    constexpr auto a = factorial(5);  // compile-time
    std::size_t& n = *new std::size_t(6);
    auto b = factorial(n);  // run-time
}
```

C++ 允许在一个函数前面直接加上`constexpr`关键字修饰。表示这个函数既可以在运行期调用，也可以在编译期调用，而函数本身的内容几乎不需要任何改变。这样一来，我们可以直接把运行期的代码复用到编译期。也允许使用循环和局部变量进行编程，可以说和平常写的代码没有任何区别。很令人震惊对吧，所以编译期计算在 C++ 里面早已经是一件司空见惯的事情了，用户压根就不需要去写复杂的模板元。在 C++20 之后几乎所有的标准库函数也都是`constexpr`的了，我们可以轻松的调用它们，比如编译期排序。

```cpp
constexpr auto sort(auto&& range) {
    std::sort(std::begin(range), std::end(range));
    return range;
}

int main() {
    constexpr auto arr = sort(std::array{1, 3, 4, 2, 3});
    for(auto i: arr) {
        std::cout << i;
    }
}
```

真正意义上的代码复用！如果你想要这个函数只在编译期执行，你也可以用`consteval`标记它。同时，在 C++20 中还允许了编译期动态内存分配，可以在`constexpr function`中使用`new`来进行内存分配，但是编译期分配的内存必须要在编译期释放。你也可以直接在编译期使用`vector`和`string`这样的容器。而且请注意，相比于利用模板进行编译期计算，`constexpr`函数的编译速度会快很多 。如果你好奇编译期是如何实现这一强大的特性的，可以认为，`C++`编译器内部内嵌了一个小的解释器，这样遇到`constexpr`函数的时候用这个解释器解释一下，再把计算结果返回就行了。 

相信你已经充分见识到 C++ 在编译期计算方面所做的努力，编译期计算早就和模板元脱离关系了，在 C++ 中已经成为一种非常自然的特性，不需要特殊的语法，却能发挥强大的威力。所以以后千万不要一谈到 C++ 的编译期计算就十分恐慌，以为是什么屠龙之技。现在它早已经变得十分温柔美丽。

尽管编译期计算已经脱离了模板元的魔爪，但是 C++ 并没有。还有两种情况，我们不得不编写蹩脚的模板元代码。

## Type Manipulation 

### Match Type 

如何判断两个类型相等呢，或者说判断两个变量的类型相等。可能有人会想，这不是多此一举吗，变量的类型都是编译期已知的，还需要判断吗？其实这个问题可以说是伴随着泛型编程而出现的，考虑下面的示例：

```cpp
template <typename T>
void test() {
    if(T == int) {
        /* ... */
    }
}
```

这样的代码是符合我们直觉的，可惜 C++ 并不允许你这么写。不过在 Python / Java 等语言中确实有这种写法，但是它们的判断大多都是在运行时的。C++ 的确允许我们在编译期对类型进行操作，但是可惜的是类型并不能作为一等公民，作为普通的值，只能作为模板参数。我们只能写出如下的代码：

```cpp
template <typename T>
void test() {
    if constexpr(std::is_same_v<T, int>) {
        /* ... */
    }
}
```

类型只能存在于模板参数里面，这直接导致上一小节的`constexpr`编译计算提到的优势全都消失了。我们又回到了刀耕火种的时代，没有变量和循环。

下面是判断两个`type_list`满足不满足子序列关系的代码:

```cpp
template <typename... Ts>
struct type_list {};

template <typename SubFirst, typename... SubRest, typename SuperFirst, typename... SuperRest>
constexpr auto is_subsequence_of_impl(type_list<SubFirst, SubRest...>, type_list<SuperFirst, SuperRest...>) {
    if constexpr(std::is_same_v<SubFirst, SuperFirst>)
        if constexpr(sizeof...(SubRest) == 0)
            return true;
        else
            return is_subsequence_of(type_list<SubRest...>{}, type_list<SuperRest...>{});
    else if constexpr(sizeof...(SuperRest) == 0)
        return false;
    else
        return is_subsequence_of(type_list<SubFirst, SubRest...>{}, type_list<SuperRest...>{});
}

template <typename... Sub, typename... Super>
constexpr auto is_subsequence_of(type_list<Sub...>, type_list<Super...>) {
    if constexpr(sizeof...(Sub) == 0)
        return true;
    else if constexpr(sizeof...(Super) == 0)
        return false;
    else
        return is_subsequence_of_impl(type_list<Sub...>{}, type_list<Super...>{});
}

int main() {
    static_assert(is_subsequence_of(type_list<int, double>{}, type_list<int, double, float>{}));
    static_assert(!is_subsequence_of(type_list<int, double>{}, type_list<double, long, char, double>{}));
    static_assert(is_subsequence_of(type_list<>{}, type_list<>{}));
}
```

写起来非常难受，我把相同的代码逻辑用`constexpr`函数写一遍，把类型参数换成`std::size_t` 

```cpp
constexpr bool is_subsequence_of(auto&& sub, auto&& super) {
    std::size_t index = 0;
    for(std::size_t i = index; index < sub.size() && i < super.size(); i++) {
        if(super[i] == sub[index]) {
            index++;
        }
    }
    return index == sub.size();
}

static_assert(is_subsequence_of(std::array{1, 2}, std::array{1, 2, 3}));
static_assert(!is_subsequence_of(std::array{1, 2, 4}, std::array{1, 2, 3}));
```

瞬间清爽一万倍，仅仅是因为在 C++ 中类型不是一等公民，只能作为模板参数，在涉及到类型相关的计算的时候，我们就不得不编写繁琐的模板元代码。事实上对类型做计算的需求一直都存在，典型的例子是`std::variant`。在编写`operator=`的时候，我们需要从一个类型列表里面（`variant`的模板参数列表）里面查找某个类型并返回一个索引，其实就是从一个数组里面查找一个满足特定条件的元素。相关的实现这里就不展示了。其实可怕的并不是使用模板元编程本身，而是就 C++ 自身而言，把类型当作值这样的改动是完全不可接受 unacceptable 的。也就是说这样的状况会一直持续下去，以后都不会有什么本质上的改变，这一事实才是最让人悲伤的。不过仍然要清楚的一个事实是，支持对类型做计算的语言并不多，像 Rust 对于这方面的支持几乎没有。C++ 的代码虽然写起来蹩脚，但是至少能写。

但是还好这里有还有另外一条路可以走。就是通过一些手段把类型映射到值。例如把类型映射到字符串，匹配类型可以类似于匹配字符串，只要对字符串进行计算就好了，也能实现一定程度上的`type as value`。C++23之前 并没有标准化的手段进行这种映射，通过一些特殊的编译器扩展能做到，可以参考 [C++ 中如何优雅进行 enum 到 string 的转换](https://www.ykiko.me/zh-cn/articles/680412313)

```cpp
template <typename... Ts>
struct type_list {};

template <typename T, typename... Ts>
constexpr std::size_t find(type_list<Ts...>) {
    // type_name returns the name of the type
    std::array arr = {type_name<Ts>()...};
    for(auto i = 0; i < arr.size(); i++) {
        if(arr[i] == type_name<T>()) {
            return i;
        }
    }
}
```

在 C++23 之后也可以直接用`typeid`实现映射，而不使用字符串映射。但是类型映射到值简单，把值映射到类型回去可一点都不简单，除非你利用 [STMP](https://www.ykiko.me/zh-cn/articles/646752343) 这种黑魔法，才能方便的把值映射回类型。但是，如果静态反射将来被引入，那么这种从类型和值的双向映射会非常简单。这样的话虽然不能直接支持把类型当成值来进行操作，但是也基本差不多了。不过还有很长一段路要走，具体什么时候能加入标准，还是个未知数。如果对静态反射感兴趣，可以阅读 [C++26 静态反射提案解析](https://www.ykiko.me/zh-cn/articles/661692275)。

### Comptime Variable 

除了上面说的对类型做计算不得不用到模板元编程之外，如果需要在编译期计算的同时实例化模板，也不得不用模板元编程。

```cpp
consteval auto test(std::size_t length) {
    return std::array<std::size_t, length>{};
    // error length is not constant expression
}
```

报错的意思就是`length`不是编译期常量，一般认为它属于编译期变量。这样就很让人讨厌了，考虑如下需求：我们要实现一个完全类型安全的`format`。也就是说根据第一个常量字符串的内容，来约束后面函数参数的个数。比如是`"{}"` 的话，后面`format`的函数参数个数就是`1`个

```cpp
consteval auto count(std::string_view fmt) {
    std::size_t num = 0;
    for(auto i = 0; i < fmt.length(); i++) {
        if(fmt[i] == '{' && i + 1 < fmt.length()) {
            if(fmt[i + 1] == '}') {
                num += 1;
            }
        }
    }
    return num;
}

template <typename... Args>
constexpr auto format(std::string_view fmt, Args&&... args)
    requires (sizeof...(Args) == count(fmt))
{
    /* ... */
}
```

事实上我们并没有办法保证一个函数参数是编译期常量，所以上面的代码是没法编译通过的。想要编译期常量，只能把这部分内容填到模板参数里面去，比如上面的函数可能会最后修改成`format<"{}">(1)`这样的形式。虽然只是形式上的差别，但这无疑给使用者带来了困难。这样来看，也就不难理解为什么`std::make_index_sequence`这样的东西大行其道了。想要真正意义上可以做模板参数的编译期变量，也可以通过 [STMP](https://www.ykiko.me/zh-cn/articles/646752343) 这种黑魔法做到，但是如前文所述，难以在日常的编程中真正使用它。

### Type is Value 

非常值得一提的是，有一个比较新的语言叫 Zig。它解决了上述提到的问题，不仅支持编译期变量，还支持把把类型作为一等公民来进行操作。得益于 Zig 独特的`comptime`机制，被它标记的变量或代码块都是在编译期执行的。这样一来，我们就可以写出如下的代码：

```rust
const std = @import("std");

fn is_subsequence_of(comptime sub: anytype, comptime super: anytype) bool {
    comptime {
        var subIndex = 0;
        var superIndex = 0;
        while(superIndex < super.len and subIndex < sub.len) : (superIndex += 1) {
            if(sub[subIndex] == super[superIndex]) {
                subIndex += 1;
            }
        }
        return subIndex == sub.len;
    }
}

pub fn main() !void {
    comptime var sub = [_] type { i32, f32, i64 };
    comptime var super = [_] type { i32, f32, i64, i32, f32, i64 };
    std.debug.print("{}\n", .{comptime is_subsequence_of(sub, super)});

    comptime var sub2 = [_] type { i32, f32, bool, i64 };
    comptime var super2 = [_] type { i32, f32, i64, i32, f32 };
    std.debug.print("{}\n", .{comptime is_subsequence_of(sub2, super2)});
}
```

写出了我们梦寐以求的代码，啊，实在是太优雅了！在对类型计算这方面 Zig 可以说是完胜目前的 C++，感兴趣的读者可以自己去 Zig 官网了解一下，不过在类型计算以外的其它方面，比如泛型和代码生成，Zig 其实做的并不好，这并不是本文的重点，所以就不讨论了。

## Conclusion 

可以发现，在一开始模板承担了太多角色，而且根本不是当初设计它的时候所期望的用法，是通过一些 trick 来弥补语言表达能力的不足。随着 C++ 的不断发展，这些额外的角色渐渐地被更简单，更直接，更易懂的语法所取代。类型约束由`concept`和`requires`来完成，编译期计算由`constexpr`来完成，操作类型则由未来的`static reflection`来完成。模板逐渐回到了它最初的模样，负责代码生成。那些晦涩难懂的 workaround 也逐渐被淘汰，这是一个好的信号，虽然我们往往还是不得不和老代码打交道。但是至少我们知道，未来会更好！