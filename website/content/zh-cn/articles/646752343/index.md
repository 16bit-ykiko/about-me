---
title: 'C++ 禁忌黑魔法：STMP'
date: 2023-07-29 10:20:50
updated: 2024-06-27 05:23:30
---

STMP 全名 stateful template meta programming，又叫状态元编程。之所以这么称呼，是因为传统的 C++ 的常量表达式求值既不依赖，也不能改变全局的状态，对于任意确定的输入，它的输出结果总是不变的，是 purely functional 的。

![](https://pic1.zhimg.com/v2-17999d0f90003c348d733cd32c417a28_r.jpg)

但是事实真的如此吗？

- 在不触发未定义行为的情况下，下面的代码可能通过编译吗？


```cpp
constexpr auto a = f();
constexpr auto b = f();
static_assert(a != b);
```

- 再考虑下这样计数器的实现，这可能做到吗？


```cpp
constexpr auto a = f();
constexpr auto b = f();
constexpr auto c = f();
static_assert(a == 0 && b == 1 && c == 2);
```

事实上通过一些编译器内置的宏，我们是可以做到的。比如

```cpp
constexpr auto a = __COUNTER__;
constexpr auto b = __COUNTER__;
constexpr auto c = __COUNTER__;
static_assert(a == 0 && b == 1 && c == 2);
```

利用主流 C++ 编译器都内置的`__COUNTER__`宏可以实现上述的效果。但是即使三大编译器都有这个宏，它也不是标准的语法。并且这个计数器是全局唯一的，我们并不能创建很多个计数器。那还有别的办法吗？并且不依赖于编译器扩展？

答案是肯定的，不管多么难以置信。相关的讨论，早在2015年的时候就有了。知乎上也有相关讨论的 [文章](https://zhuanlan.zhihu.com/p/24835482)。但是时过境迁，这篇文章发布的时间是在 2017 年，使用的 C++ 版本还是14，文章里面已经有很多的内容不适用了。更何况现在 C++26 的相关标准都开始制定了，有很多东西需要被重新讨论。我们将要选择的版本是 C++20。

如果你只对代码感兴趣，我已经将相关的代码放在 [Compiler Explorer - C++](https://godbolt.org/z/MGPKeqPaj) 。三大编译器 C++20 均编译通过，你可以直接看到编译器的输出结果。防止链接失效，也放到 [GitHub](https://github.com/16bit-ykiko/blog/blob/main/code/compile-time-counter.cpp) 上。如果你想要了解它的原理，欢迎继续往下阅读。C++ 标准极其复杂，作者也没法保证文章内容百分百正确，如果有任何错误，欢迎评论区讨论。

> 注意：本文仅仅只是技术讨论，请不要将相关的代码运用于实际生产中。事实上，相关的代码似乎被认为是  ill formed。而且非常容易造成 ODR 违反。相关的提案在 [CWG](https://cplusplus.github.io/CWG/issues/2118.html) 2015 年就有了。但是似乎好像并没有进一步被解决，而且在 C++20 中标准库还主动加入了具有类似作用的库，那就是`std::source_location::line`。当`line`作为函数默认参数的时候，随着函数调用位置不同，实际上默认参数取值也是不同的。 

## 都是友元惹的祸 

我们都知道 C++ 的 friend 关键字，可以对一个函数进行标记，然后允许这个函数访问类的私有成员。让我们考虑下面这两种情况。

- 友元声明在全局空间


```cpp
class A;
void touch(A&);

class A {
    int member;
    friend void touch(A&);
};

void touch(A& ref) { ref.member = 123; }

int main() {
    A a;
    touch(a);
}
```

- 友元声明在类内部


```cpp
class A {
    int member = 0;

    friend void touch(A& ref) { ref.member = 123; }
};

int main() {
    A a;
    touch(a);  // OK
}
```

上面的两段代码都是 well defined 的，而且函数`touch`都能访问类`A`的私有成员。但是这两种实现方式之间，有微小的区别。在全局空间声明的友元函数，就和普通的函数一样，作用域也是一样的。都在全局命名空间，和全局普通的函数访问是一模一样的。而在类内部声明的友元函数，只能通过 C++ 的 [Argument-dependent lookup](https://en.cppreference.com/w/cpp/language/adl) 进行访问。

- 非 ADL 查找 


```cpp
class A;
void touch(A);

class A {
    int member;
    friend void touch(A);

public:
    A(int a) : member(a) {}
};

void touch(A ref) { std::cout << ref.member << std::endl; }

int main() {
    A a(10);
    touch(a);  // normal lookup
    touch(1);  // implicit conversion
}
```

- ADL 查找 


```cpp
class A {
    int member = 0;

public:
    friend void touch(A ref) { std::cout << ref.member << std::endl; }

    A(int a) : member(a) {}
};

int main() {
    A a(10);
    touch(a);
    touch(1);     // error
    A::touch(1);  // error
}
```

这里你就会发现了，第一次调用成功了，第二，三次调用失败了。这是因为，ADL会在函数参数对应的类型的命名空间中查找函数。在第一种情况下，`touch`函数的参数类型是`A`，发生了`ADL`查找。而`1`的类型是`int`，两者并不相关，所以 ADL 不会发生。

## 模板显式实例化 

考虑下面这种情况

```cpp
auto flag(auto);

template <bool val>
struct flag_setter {
    friend auto flag(auto) {}
};

int main() {
    flag(1);  // error
    flag_setter<true>{};
    flag(1);  // ok
}
```

首先直接调用`flag`会发生错误，因为它的返回值类型尚未确定。需要在函数定义里面推导。所以第一个调用就失败了。后面我们进行了一次类模板显式实例化，可以认为模板显式实例化的时候会在全局命名空间添加一个该类型模板的特化（通过友元函数），而这个特化版本实现了`flag()`。因为`flag`函数有了定义，返回值类型也就确定了，所以第二次调用就成功了。

## 一元常量表达式开关 

有了上面那些技巧，我们就可以来实现，本文开头所提到的常量开关了。

```cpp
auto flag(auto);

template <bool val>
struct flag_setter {
    bool value = false;

    friend auto flag(auto) {}
};

template <auto arg = 0, auto condition = requires { flag(arg); }>
consteval auto value() {
    if constexpr(!condition) {
        return flag_setter<condition>{}.value;
    }
    return condition;
}

int main() {
    constexpr auto a = value();
    constexpr auto b = value();
    static_assert(a != b);
}
```

它的原理很简单，首先 C++20 加入的`requires`语句可以用于检查表达式的合法性。最开始的时候，由于`flag_setter`还尚未实例化，所以`flag`函数还没有定义，所以`flag(arg)`是不合法的表达式的。所以`condition`的值就会是`false`。然后我们通过`if constexpr`来判断`condition`的值，如果是`false`，那么我们就实例化一个`flag_setter`，并且返回`false`的值。如果是`true`，那么我们就返回`condition`的值。这样就实现了一元常量表达式开关。相比于 C++14 的版本，这个版本更加的简洁也更好理解。

值得注意的一点是，可能有人会问为什么不能直接写`requries{ flag(0); }`呢？这是由于模板的 [two phase lookup](https://en.cppreference.com/w/cpp/language/two-phase_lookup)，如果直接写`requries{ flag(0); }`，会在第一阶段就进行查找，然后查找发现错误，并且这个错误是一个 hard error，会直接导致编译失败。如果让这个表达式依赖于模板变量，它就会变成 [dependent names](https://en.cppreference.com/w/cpp/language/dependent_name)，在第二阶段进行查找，并且可以被`requires`检测表达式是否合法。

## 编译期常量计数器 

基于上述的原理，更进一步，我们可以直接实现一个编译期的计数器！

```cpp
template <std::size_t N>
struct reader {
    friend auto counted_flag(reader<N>);
};

template <std::size_t N>
struct setter {
    friend auto counted_flag(reader<N>) {}

    std::size_t value = N;
};

template <auto N = 0,
          auto tag = [] {},
          bool condition = requires(reader<N> red) { counted_flag(red); }>
consteval auto next() {
    if constexpr(!condition) {
        constexpr setter<N> s;
        return s.value;
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

让我们来解释一下上面的代码。基本原理和一元开关情况类似。`reader`用来判断函数有没有被实现，`setter`用来生成实现的函数。然后在`next`里面，我们首先查看当前的`N`对应的函数，有没有被实现。如果被没有被实现，就实例化一个`setter<N>`的模板。如果实现了的话，就递归的查看`N+1`的情况。

为了防止有些读者想不通，这里直接从第一次调用开始举例子

第一次调用这个函数：

- `N = 0`时，检查发现`setter<0>`尚未实现，也就是`condition`是`false`。这样的话会走第一个分支，实例化一个`setter<0>`，并且返回`0`。


第二次调用这个函数： 

- `N = 0`时，检查发现`setter<0>`已经实现了，也就是`condition`是`true`。这样的话会走第二个分支，递归调用`next<1>()`。 
- `N = 1`时，检查发现`setter<1>`尚未实现，也就是`condition`是`false`。这样的话会走第一个分支，实例化一个`setter<1>`，并且返回`1`。


第三次调用这个函数： 

- `N = 0`时，检查发现`setter<0>`已经实现了，也就是`condition`是`true`。这样的话会走第二个分支，递归调用`next<1>()`。 
- `N = 1`时，检查发现`setter<1>`已经实现了，也就是`condition`是`true`。这样的话会走第二个分支，递归调用`next<2>()`。 
- `N = 2`时，检查发现`setter<2>`尚未实现，也就是`condition`是`false`。这样的话会走第一个分支，实例化一个`setter<2>`，并且返回`2`。


`......`，也就是说，我们每一次调用这个函数，就会实例化一个对应的模板函数，这个计数器，其实记录的就是已经实例化的模板函数的数量。

值得一提的是，上面有一个奇怪的写法。`auto tag = []{}`，你可能看的一脸懵逼。事实上，`[]{}`是一个简写的`lambda`表达式，其实就相当于`[](){}`。如果用不到函数参数的话，这个小括号可以省略。那为什么我们要在这里添加一个这个玩意呢，完全用不到啊。你可以尝试把它去掉，就会发现得到了错误的结果。变量的值并没有按照预期的结果进行递增。

这里的原因是，编译器会对常量表达式的求值结果进行缓存，也就是说编译器认为`next`函数是常量表达式，返回的值应该是不会变的。那既然不会变，我只要求一次不就行了。于是它就把所有`next`的返回值都记录成相同的了。但是这不是我们想要的结果，我们想要它每次调用的时候都能计算表达式的值。加上这个标签之后，每次调用的模板参数实际是不同的，于是编译器就会重新计算它的值了。

看下面这个例子

```cpp
template <auto arg = [] {}>
void test() {
    std::cout << typeid(arg).name() << std::endl;
}

int main() {
    test();  // class <lambda_1>
    test();  // class <lambda_2>
    test();  // class <lambda_3>
}
```

打印出来的结果不同，表面每一次调用的`test()`的模板参数其实是不同的，那么这三个`test()`其实是三个不同的函数。利用这个特性，我们在每次调用`next`的时候，其实就是不同的模板函数（因为`lambda`模板参数类型不同）。这样我们就阻止了编译器的缓存。代码就像我们预期的那样进行调用了。

## 彩蛋：合法访问类的私有成员 

我们首先要明确一个观点：类的访问权限说明符`private`, `public`, `protected`仅仅只作用于编译期的检查。如果能通过某种手段避免编译期检查，那完全就可以合法的访问，类的私有成员。

那么存在这样的方法吗？答案是存在。我们有**模板显示实例化的时候可以忽略类作用域的访问权限**

> The C++11/14 standards state the following in note 14.7.2/12 [temp.explicit]: The usual access checking rules do not apply to names used to specify explicit instantiations. [ Note: In particular, the template arguments and names used in the function declarator (including parameter types, return types and exception speciﬁcations) may be private types or objects which would normally not be accessible and the template may be a member template or member function which would not normally be accessible. — end note ] 

也就是说在显示实例化模板的时候，我们可以直接访问类的私有成员。

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

template struct Thief<&Bank::money>;
double& steal(Bank& bank);

int main() {
    Bank bank;
    steal(bank) = 100;
    bank.check();
    return 0;
}
```

续篇已出，欢迎阅读：

{{< linkcard url="https://www.ykiko.me/zh-cn/articles/646812253" title="YKIKO：C++ 禁忌黑魔法: STMP 多态" >}}

参考文章： 

- [Revisiting Stateful Metaprogramming in C++20](https://mc-deltat.github.io/articles/stateful-metaprogramming-cpp20)
- [b.atch: Non-constant constant-expressions in C++](https://b.atch.se/posts/non-constant-constant-expressions/)
- [How to Hack C++ with Templates and Friends](https://ledas.com/post/857-how-to-hack-c-with-templates-and-friends/)
