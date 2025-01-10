---
title: 'C++中constexpr的历史！（第二部分）'
date: 2024-02-22 22:15:32
updated: 2024-11-30 18:28:59
series: ['Constexpr']
series_order: 2
---

前情提要：[C++中constexpr的历史！（第一部分）](https://www.ykiko.me/zh-cn/articles/682031684)

## 2015-2016：模板的语法糖

在C++中，支持[全特化（full specialization）](https://en.cppreference.com/w/cpp/language/template_specialization)的模板很多，但支持[偏特化（partial specialization）](https://en.cppreference.com/w/cpp/language/partial_specialization)的模板并不多。事实上，只有类模板（class template）和变量模板（variable template）支持偏特化，而变量模板可以看作是类模板的语法糖，因此实际上只有类模板支持偏特化。不支持偏特化会导致某些代码难以编写。

假设我们想实现一个`destroy_at`函数，其作用是调用对象的析构函数。特别地，如果析构函数是trivial的，我们就省去这次无意义的析构函数调用。

直觉上，我们可以写出如下代码：

```cpp
template<typename T, bool value = std::is_trivially_destructible_v<T>>
void destroy_at(T* p) { p->~T(); }

template<typename T>
void destroy_at<T, true>(T* p) {}
```

遗憾的是，clangd已经可以智能地提醒你：**Function template partial specialization is not allowed**。函数模板不能偏特化，那怎么办呢？当然，可以通过包装一层类模板来解决，但每次遇到这种情况都额外包装一层实在是让人难以接受。

旧时代的做法是利用SFINAE来解决这个问题：

```cpp
template<typename T, std::enable_if_t<(!std::is_trivially_destructible_v<T>)>* = nullptr>
void destroy_at(T* p) { p->~T(); }

template<typename T, std::enable_if_t<std::is_trivially_destructible_v<T>>* = nullptr>
void destroy_at(T* p) {}
```

具体的原理这里就不赘述了，虽然少了一层包装，但仍然有很多与代码逻辑无关的东西出现。这里的`std::enable_if_t`就是典型例子，严重影响了代码的可读性。

提案[N4461](https://open-std.org/JTC1/SC22/WG21/docs/papers/2015/n4461.html)希望引入`static_if`（借鉴自D语言），用于在编译期控制代码生成，只会把实际用到的分支编译进最终的二进制代码。这样就可以写出如下代码，其中`static_if`的条件必须是常量表达式：

```cpp
template<typename T>
void destroy_at(T* p){
    static_if(!std::is_trivially_destructible_v<T>){
        p->~T();
    }
}
```

可以发现逻辑非常清晰，但委员会一般对新增关键字比较谨慎。后来`static_if`被重命名为`constexpr_if`，再后来变成了我们今天熟悉的这种形式，并进入了[C++17](https://en.cppreference.com/w/cpp/language/if#Constexpr_if)：

```cpp
if constexpr (...){...}
else if constexpr (...){...}
else {...}
```

巧妙地避免了新增关键字，C++委员会还真是喜欢关键字复用呢。

## 2015：constexpr lambda

提案[N4487](https://open-std.org/JTC1/SC22/WG21/docs/papers/2015/n4487.pdf)讨论了支持constexpr lambda的可能性，尤其希望在constexpr计算中能够使用lambda表达式，并附带了一个实验性实现。

其实支持constexpr的lambda表达式并不困难，我们都知道lambda在C++中是很透明的，基本上完全就是一个匿名的函数对象。函数对象都能是constexpr的，那么支持constexpr的lambda也就是理所当然的事情了。

唯一需要注意的是，lambda是可以进行捕获的，捕获constexpr的变量会怎么样呢？

```cpp
void foo() {
    constexpr int x = 3;
    constexpr auto foo = [=]() { return x + 1; };
    static_assert(sizeof(foo) == 1);
}
```

从直觉上来说，由于`x`是常量表达式，没有必要给它分配空间来储存。那么`f`其实里面没有任何成员，在C++中空类的size至少是`1`。上面的代码挺合理的，但在文章的上篇也说到了，constexpr变量其实也是可以占用内存的，我们可以显式取它的地址：

```cpp
void foo() {
    constexpr int x = 3;
    constexpr auto foo = [=]() { return &x + 1; };
    static_assert(sizeof(foo) == 4);
}
```

可以发现这种情况下，编译器不得不给`x`分配内存。实际上的判断规则更复杂一些，感兴趣的可以自行参考[lambda capture](https://en.cppreference.com/w/cpp/language/lambda#Lambda_capture)。最终这个提案被接受，进入了[C++17](https://en.cppreference.com/w/cpp/language/lambda#Lambda_capture:~:text=This%20function%20is%20constexpr%20if%20the%20function%20call%20operator%20(or%20specialization%2C%20for%20generic%20lambdas)%20is%20constexpr.)。

## 2017-2019：编译期和运行期...不同？

通过不断放宽constexpr的限制，越来越多的函数可以在编译期执行。但具有外部链接（也就是被`extern`的函数）无论如何是无法在编译期执行的。绝大部分从C继承过来的函数都是这样的，例如`memcpy`, `memmove`等等。

假设我写了一个constexpr的`memcpy`：

```cpp
template <typename T>
constexpr T* memcpy(T* dest, const T* src, std::size_t count) {
    for(std::size_t i = 0; i < count; ++i) {
        dest[i] = src[i];
    }
    return dest;
}
```

虽然能在编译期用了，编译期执行效率倒是无所谓，但运行期效率肯定不如标准库的实现。如果能在编译期使用我的实现，运行期使用外部链接的标准库函数就好了。

提案[P0595](https://open-std.org/JTC1/SC22/WG21/docs/papers/2017/p0595r0.html)希望加入一个新的magic function，也就是`constexpr()`，用于判断当前函数是否在编译期执行，后来被更名为`is_constant_evaluated`并进入C++20。使用起来就像下面这样：

```cpp
constexpr int foo(int x) {
    if(std::is_constant_evaluated()) {
        return x;
    } else {
        return x + 1;
    }
}
```

这样的话编译期和运行期就可以采用不同的逻辑实现了，我们可以对外部链接的函数进行一层封装，使得它们在内部暴露为constexpr的函数接口，既可以代码复用又可以保证运行期效率，两全其美。

唯一的问题是，假设上面的`foo`在运行期运行，你会发现第一个分支仍然被编译了，虽然可能编译器最终应该会把`if(false)`这个分支优化掉。但这个分支里面仍然会进行语法检查之类的工作，如果里面用到了模板，那么模板实例化仍然会被触发（甚至产生预料外的实例化导致编译错误），显然这不是我们想要的结果。尝试使用`if constexpr`改写上面的代码呢？

```cpp
constexpr int foo(int x) {
    if constexpr(std::is_constant_evaluated()) {
        // ...
    }
}
```

这种写法被认为是**obviously incorrect**，因为`if constexpr`的条件只能在编译期执行，所以这里`is_constant_evaluated`永远会返回`true`，这与我们最开始的目的相悖了。所以提案[P1938R3](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2021/p1938r3.html)提议加入新的语法来解决这个问题：

```cpp
if consteval /* !consteval */ {
    // ...
} else {
    // ...
}
```

代码看上去是一目了然的，两个分支一个编译期一个运行期。这个升级过后的版本最终被接受并加入C++23。

## 2017-2019：高效的调试

C++模板一个最被人诟病的问题就是报错信息非常糟糕，而且难以调试。内层模板实例化失败之后，会把整个实例化栈打印出来，能轻松产生成百上千行报错。但事情在constexpr函数这里其实也并没有变好，如果constexpr函数常量求值失败，也会把整个函数调用堆栈打印出来：

```cpp
constexpr int foo(){ return 13 + 2147483647; }
constexpr int bar() { return oo(); }
constexpr auto x = bar();
```

报错：

```cpp
in 'constexpr' expansion of 'bar()'
in 'constexpr' expansion of 'foo()'
error: overflow in constant expression [-fpermissive]
  233 | constexpr auto x = bar();
```

如果函数嵌套多了，报错信息也非常糟糕。不同于模板的地方在于，constexpr函数也可以在运行期运行。所以我们可以在运行期调试代码，最后在编译期执行就好了。但如果考虑到上一小节加的`is_constant_evaluated`，就会发现这种做法并不完全可行，因为编译期和运行期的代码逻辑可能不同。提案[P0596](https://open-std.org/JTC1/SC22/WG21/docs/papers/2017/p0596r0.html)希望引入`constexpr_trace`和`constexpr_assert`来方便编译期调试代码，虽然投票一致赞成，但暂时未进入C++标准。

## 2017：编译期可变容器

尽管在先前的提案中，允许了constexpr函数使用和修改变量，但动态内存分配还是不允许的。如果有未知长度的数据需要处理，一般就是在栈上开一个大数组，这没什么问题。但从实践上来说，有特别多的函数依赖于动态内存分配，支持constexpr函数中使用`vector`势在必得。

在当时，直接允许在constexpr函数中使用`new`/`delete`似乎过于让人惊讶了，所以提案[P0597](https://open-std.org/JTC1/SC22/WG21/docs/papers/2017/p0597r0.html)想了一个折中的办法，先提供一个magic container叫做`std::constexpr_vector`，它由编译器实现，并且支持在constexpr函数中使用和修改。

```cpp
constexpr constexpr_vector<int> x;  // ok
constexpr constexpr_vector<int> y{ 1, 2, 3 };  // ok

constexpr auto series(int n) {
    std::constexpr_vector<int> r{};
    for(int k; k < n; ++k) {
        r.push_back(k);
    }
    return r;
}
```

这并不彻底解决问题，用户仍然需要重写它的代码以支持常量求值。从在constexpr函数支持循环的那一节来看，这种加重语言不一致性的东西，很难被加入标准。最终有更好的提案取代了它，后面会提到。

## 2018：真正的编译期多态？

提案[P1064R0](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2018/p1064r0.html)希望在常量求值中支持虚函数调用。哎，还不支持动态内存分配呢，咋就要支持虚函数调用了？其实不依赖动态内存分配也可以弄出来多态指针嘛，指向栈上的对象或者静态储存就可以了。

```cpp
struct Base {
    virtual int foo() const { return 1; }
};

struct Derived : Base {
    int foo() const override { return 2; }
};

constexpr auto foo() {
    Base* p;
    Derived d;
    p = &d;
    return p->foo();
}
```

似乎没有任何理由拒绝上面这段代码编译通过。由于是在编译期执行，编译器当然能知道`p`指向的是`Derived`，然后调用`Derived::f`，实践上没有任何难度。的确如此，之后又有一个新的提案[P1327R1](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2018/p1327r1.html)进一步希望`dynamic_cast`和`typeid`也能在常量求值中使用，最终它们都被接受并且加入了[C++20](https://en.cppreference.com/w/cpp/language/constexpr#:~:text=it%20must%20not%20be%20virtual)，现在可以自由的在编译期使用这些特性了。

## 2017-2019：真正的动态内存分配！

在[constexpr everything](https://www.youtube.com/watch?v=HMB9oXFobJc)的这个演示视频中，展示了一个能在编译期处理`JSON`对象的例子：

```cpp
constexpr auto jsv= R"({
    "feature-x-enabled": true,
    "value-of-y": 1729,
    "z-options": {"a": null,
        "b": "220 and 284",
         "c": [6, 28, 496]}
 })"_json;

if constexpr (jsv["feature-x-enabled"]) {
    // feature x
} else {
    // feature y
}
```

希望能直接通过解析常量字符串起到配置文件的作用（字符串文本可以由`#include`引入）。作者们因为不能使用STL的容器受到了严重影响，并且自己编写了替代品。通过`std::array`来实现`std::vector`和`std::map`这样的容器，由于没有动态内存分配，只能预先计算出需要的大小（可能导致多次遍历）或者在栈上开块大内存。

提案[P0784R7](https://open-std.org/JTC1/SC22/WG21/docs/papers/2019/p0784r7.html)重新讨论了在常量求值中支持标准库容器的可能性。

主要有以下三个难点：

- 析构函数不能被声明为constexpr（对于constexpr对象，它们必须是trivial的）
- 无法进行动态内存分配/释放
- 无法在常量求值中使用[placement new](https://en.cppreference.com/w/cpp/language/new#Placement_new)来调用对象的构造函数

针对第一个问题，作者们与MSVC，GCC，Clang，EDG等前端开发人员快速讨论并解决了这个问题。C++20起，可以符合[literal type](https://en.cppreference.com/w/cpp/named_req/LiteralType)要求的类型具有constexpr修饰的析构函数，而不是严格要求平凡的析构函数。

针对第二个问题，处理起来并不简单。C++有很多未定义行为都是由于错误的内存处理导致的，相比之下，不能直接操作内存的脚本语言则安全的多。但是为了复用代码，C++编译器中的常量求值器不得不直接操作内存，不过由于所有信息都是编译期已知的，理论上可以保证常量求值中不会出现内存错误（out of range, double free, memory leak, ...），如果出现应该中止编译并报告错误。

常量求值器需要跟踪许多对象的元信息，并找出这些错误：

- 记录`union`哪个field是active的，访问unactive的成员导致未定义行为，这由[P1330](https://open-std.org/JTC1/SC22/WG21/docs/papers/2018/p1330r0.pdf)阐明
- 正确记录对象的[lifetime](https://en.cppreference.com/w/cpp/language/lifetime)，访问未初始化的内存和已经析构的对象都是不允许的

当时还不允许在常量求值中把`void*`转换成`T*`，所以理所当然的：

```cpp
void* operator new(std::size_t);
```

不支持在常量求值中使用，取而代之的是：

```cpp
// new => initialize when allocate
auto pa = new int(42);
delete pa;

// std::allocator => initialize after allocate
std::allocator<int> alloc;
auto pb = alloc.allocate(1);
alloc.deallocate(pb, 1);
```

它们返回的都是`T*`，并且由编译器实现，这对于支持标准库容器来说已经足够了。

对于第三个问题，则是添加了一个magic function即[std::construct_at](https://en.cppreference.com/w/cpp/memory/construct_at)，它的作用是在指定的内存位置上调用对象的构造函数，用来在常量求值中取代`placement new`。这样的话我们就可以先通过`std::allocator`分配内存，再通过`std::construct_at`来构造对象了。该提案最终被接受，进入了[C++20](https://en.cppreference.com/w/cpp/memory/construct_at)，同时使得`std::vector`，`std::string`在常量求值中可用（其它的容器理论上也行，但目前的实现还没支持，如果非常想要只能自己搓一个了）。

虽然支持了动态内存分配，但并不是毫无限制。**在一次常量求值中分配的内存必须要在这次常量求值结束之前释放完全，不能有内存泄漏，否则会导致编译错误**。这种类型的内存分配被叫做*transient constexpr allocations（瞬态内存分配）*。该提案也讨论了*non-transient allocation（非瞬态内存分配）*，在编译期未被释放的内存，将被转为静态储存（其实就是存在数据区，就像全局变量那样）。但是，委员会认为这种可能性"too brittle"，出于多种原因，目前尚未采纳。

## 2018：更多的constexpr

提案[P1002](https://open-std.org/JTC1/SC22/WG21/docs/papers/2018/p1002r1.pdf)希望在constexpr函数中支持`try-catch`块。但不能`throw`，这样是为了能把更多的标准库容器的成员函数标记为`constexpr`。

```cpp
constexpr int foo(){
    throw 1;
    return 1;
}

constexpr auto x = foo();  // error

// expression '<throw-expression>' is not a constant expression
//    233 |     throw 1;
```

如果在编译期`throw`会直接导致编译错误，由于`throw`不会发生，那自然也不会有异常被捕获。

## 2018：保证编译期执行！

有些时候我们想保证一个函数在编译期执行：

```cpp
extern int foo(int x);

constexpr int bar(int x){ return x; }

foo(bar(1)); // evaluate at compile time ?
```

事实上`g`无论是在编译期还是运行期执行，理论上都可以。为了保证它在编译期执行，我们需要多写一些代码：

```cpp
constexpr auto x = bar(1);
foo(x);
```

这样就保证了`g`在编译期执行，同样，这种没意义的局部变量实在是多余。提案[P1073](https://open-std.org/JTC1/SC22/WG21/docs/papers/2018/p1073r0.html)希望增加一个标记`constexpr!`来确保一个函数在编译期执行，如果不满足则导致编译错误。最终该标记被更名为[consteval](https://en.cppreference.com/w