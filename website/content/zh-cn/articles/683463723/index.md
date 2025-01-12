---
title: 'The History of constexpr in C++! (Part Two)'
date: 2024-02-22 22:15:32
updated: 2024-11-30 18:28:59
series: ['Constexpr']
series_order: 2
---

前情提要：[The History of constexpr in C++! (Part One)](https://www.ykiko.me/zh-cn/articles/682031684)

## 2015-2016：模板的语法糖 

在 C++ 中支持 [全特化 (full specialization)](https://en.cppreference.com/w/cpp/language/template_specialization) 的模板很多，但是支持 [偏特化 (partial specialization)](https://en.cppreference.com/w/cpp/language/partial_specialization) 的模板并不多，事实上其实只有类模板 (class template) 和变量模板 (variable template) 两种支持，而变量模板其实可以看做类模板的语法糖，四舍五入一下其实只有类模板支持偏特化。不支持偏特化会导致有些代码十分难写

假设我们想实现一个`destroy_at`函数，效果就是调用对象的析构函数。特别的，如果析构函数是 trivial 的，那我们就省去这次无意义的析构函数调用。

直觉上我们能写出下面这样的代码

```cpp
template<typename T, bool value = std::is_trivially_destructible_v<T>>
void destroy_at(T* p) { p->~T(); }

template<typename T>
void destroy_at<T, true>(T* p) {}
```

很可惜，clangd 已经可以智慧的提醒你：**Function template partial specialization is not allowed**。函数模板不能偏特化，那咋办呢？当然了，可以包一层类模板解决，但是每次遇到这种情况都额外包一层实在是让人难以接受。

旧时代的做法是利用 SFINAE 来解决这个问题

```cpp
template<typename T, std::enable_if_t<(!std::is_trivially_destructible_v<T>)>* = nullptr>
void destroy_at(T* p) { p->~T(); }

template<typename T, std::enable_if_t<std::is_trivially_destructible_v<T>>* = nullptr>
void destroy_at(T* p) {}
```

具体的原理这里就不叙述了，虽然少了一层包装，但是仍然有很多与代码逻辑无关的东西出现。这里的`std::enable_if_t`就是典型例子，严重影响了代码的可读性。

提案 [N4461](https://open-std.org/JTC1/SC22/WG21/docs/papers/2015/n4461.html) 希望引入`static_if`（借鉴自 D 语言）可以用来编译期控制代码生成，只会把实际用到的分支编译进最终的二进制代码。这样就可以写出下面这样的代码，其中`static_if`的条件必须是常量表达式

```cpp
template<typename T>
void destroy_at(T* p){
    static_if(!std::is_trivially_destructible_v<T>){
        p->~T();
    }
}
```

可以发现逻辑非常清晰，但是委员会一般对于加新的关键字比较谨慎。后来`static_if`被重命名为`constexpr_if`，再后来变成了我们今天熟悉的这种形式并且进入 [C++17](https://en.cppreference.com/w/cpp/language/if#Constexpr_if)

```cpp
if constexpr (...){...}
else if constexpr (...){...}
else {...}
```

巧妙地避免了加新的关键字，C++ 委员会还真是喜欢关键字复用呢。

## 2015：constexpr lambda 

提案 [N4487](https://open-std.org/JTC1/SC22/WG21/docs/papers/2015/n4487.pdf) 讨论了支持 constexpr lambda 可能性，尤其希望能在 constexpr 计算中能够使用 lambda 表达式，并附带了一个实验性实现。

其实支持 constexpr 的 lambda 表达式并不困难，我们都知道 lambda 在 C++ 里面是很透明的，基本上完全就是一个匿名的函数对象。函数对象都能是 constexpr 的，那么支持 constexpr 的 lambda 也就是理所当然的事情了。

唯一需要注意的就是，lambda 是可以进行捕获的，捕获 constexpr 的变量会怎么样呢？

```cpp
void foo() {
    constexpr int x = 3;
    constexpr auto foo = [=]() { return x + 1; };
    static_assert(sizeof(foo) == 1);
}
```

从直觉上来说，由于`x`是常量表达式，没有必要给它分配空间来储存。那么`f`其实里面没有任何成员，在 C++ 中空类的 size 至少是`1`。上面的代码挺合理的，但是在文章的上篇也说到了，constexpr 变量其实也是可以占用内存的，我们可以显式取它的地址

```cpp
void foo() {
    constexpr int x = 3;
    constexpr auto foo = [=]() { return &x + 1; };
    static_assert(sizeof(foo) == 4);
}
```

可以发现这种情况下，编译器不得不给`x`分配内存。实际上的判断规则更复杂一些，感兴趣的可以自行参考 [lambda capture](https://en.cppreference.com/w/cpp/language/lambda#Lambda_capture)。最终这个提案被接受，进入了 [C++17](https://en.cppreference.com/w/cpp/language/lambda#Lambda_capture:~:text=This%20function%20is%20constexpr%20if%20the%20function%20call%20operator%20(or%20specialization%2C%20for%20generic%20lambdas)%20is%20constexpr.)。

## 2017-2019：编译期和运行期...不同? 

通过不断放宽 constexpr 的限制，越来越多的函数可以在编译期执行。但是具有外部链接（也就是被`extern`的函数）无论如何是无法在编译期执行的。绝大部分从 C 继承过来的函数都是这样的，例如`memcpy`, `memmove`等等。

假设我写了一个 constexpr 的`memcpy`

```cpp
template <typename T>
constexpr T* memcpy(T* dest, const T* src, std::size_t count) {
    for(std::size_t i = 0; i < count; ++i) {
        dest[i] = src[i];
    }
    return dest;
}
```

虽然能在编译期用了，编译期执行效率倒是无所谓，但是运行期效率肯定不如标准库的实现。如果能在编译期使用我的实现，运行期使用外部链接的标准库函数就好了。

提案 [P0595](https://open-std.org/JTC1/SC22/WG21/docs/papers/2017/p0595r0.html) 希望加入一个新的 magic function 也就是 `constexpr()` 用来判断当前的函数是否在编译期执行，后来被更名为`is_constant_evaluated`并且进入 C++20。使用起来就像下面这样

```cpp
constexpr int foo(int x) {
    if(std::is_constant_evaluated()) {
        return x;
    } else {
        return x + 1;
    }
}
```

这样的话编译期和运行期就可以采用不同的逻辑实现了，我们可以对外部链接的函数进行一层封装，使得它们在内部暴露为 constexpr 的函数接口，既可以代码复用又可以保证运行期效率，两全其美。

唯一的问题是，假设上面的`foo`在运行期运行，你会发现第一个分支仍然被编译了，虽然可能编译器最终应该会把`if(false)`这个分支优化掉。但是这个分支里面仍然会进行语法检查之类的工作，如果里面用到了模板，那么模板实例化仍然会被触发（甚至产生预料外的实例化导致编译错误），显然这不是我们想要的结果。尝试使用`if constexpr`改写上面的代码呢？

```cpp
constexpr int foo(int x) {
    if constexpr(std::is_constant_evaluated()) {
        // ...
    }
}
```

这种写法被认为是 **obviously incorrect**，因为`if constexpr`的条件只能在编译期执行，所以这里`is_constant_evaluated`永远会返回`true`，这与我们最开始的目的相悖了。 所以提案 [P1938R3](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2021/p1938r3.html) 提议加入新的语法来解决这个问题

```cpp
if consteval /* !consteval */ {
    // ...
} else {
    // ...
}
```

代码看上去是一目了然的，两个分支一个编译期一个运行期。这个升级过后的版本最终被接受并加入 C++23。

## 2017-2019： 高效的调试 

C++ 模板一个最被人诟病的问题就是报错信息非常糟糕，而且难以调试。内层模板实例化失败之后，会把整个实例化栈打印出来，能轻松产生成百上千行报错。但是事情在 constexpr 函数这里其实也并没有变好，如果 constexpr 函数常量求值失败，也会把整个函数调用堆栈打印出来

```cpp
constexpr int foo(){ return 13 + 2147483647; }
constexpr int bar() { return oo(); }
constexpr auto x = bar();
```

报错

```cpp
in 'constexpr' expansion of 'bar()'
in 'constexpr' expansion of 'foo()'
error: overflow in constant expression [-fpermissive]
  233 | constexpr auto x = bar();
```

如果函数嵌套多了，报错信息也非常糟糕。不同于模板的地方在于，constexpr 函数也可以在运行期运行。所以我们可以在运行期调试代码，最后在编译期执行就好了。但是如果考虑到上一小节加的`is_constant_evaluated`，就会发现这种做法并不完全可行，因为编译期和运行期的代码逻辑可能不同。提案 [P0596](https://open-std.org/JTC1/SC22/WG21/docs/papers/2017/p0596r0.html) 希望引入`constexpr_trace`和`constexpr_assert`来方便编译期调试代码，虽然投票一致赞成，但是暂时未进入 C++ 标准。

## 2017： 编译期可变容器 

尽管在先前的提案中，允许了 constexpr 函数使用和修改变量，但是动态内存分配还是不允许的。如果有未知长度的数据需要处理，一般就是在栈上开一个大数组，这没什么问题。但是从实践上来说，有特别多的函数依赖于动态内存分配，支持 constexpr 函数中使用`vector`势在必得。

在当时，直接允许在 constexpr 函数中使用`new`/`delete`似乎过于让人惊讶了，所以提案 [P0597](https://open-std.org/JTC1/SC22/WG21/docs/papers/2017/p0597r0.html) 想了一个折中的办法，先提供一个 magic container 叫做`std::constexpr_vector`，它由编译器实现，并且支持在 constexpr 函数中使用和修改。

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

这并不彻底解决问题，用户仍然需要重写它的代码以支持常量求值。从在 constexpr 函数支持循环的那一节来看，这种加重语言不一致性的东西，很难被加入标准。最终有更好的提案取代了它，后面会提到。

## 2018：真正的编译期多态？ 

提案 [P1064R0](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2018/p1064r0.html) 希望在常量求值中支持虚函数调用。哎，还不支持动态内存分配呢，咋就要支持虚函数调用了？其实不依赖动态内存分配也可以弄出来多态指针嘛，指向栈上的对象或者静态储存就可以了。

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

似乎没有任何理由拒绝上面这段代码编译通过。由于是在编译期执行，编译器当然能知道`p`指向的是`Derived`，然后调用`Derived::f`，实践上没有任何难度。的确如此，之后又有一个新的提案 [P1327R1](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2018/p1327r1.html) 进一步希望`dynamic_cast`和`typeid`也能在常量求值中使用，最终它们都被接受并且加入了 [C++20](https://en.cppreference.com/w/cpp/language/constexpr#:~:text=it%20must%20not%20be%20virtual)，现在可以自由的在编译期使用这些特性了。

## 2017-2019： 真正的动态内存分配！ 

在 [constexpr everything](https://www.youtube.com/watch?v=HMB9oXFobJc) 的这个演示视频中，展示了一个能在编译期处理`JSON`对象的例子

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

希望能直接通过解析常量字符串起到配置文件的作用（字符串文本可以由`#include`引入）。作者们因为不能使用 STL 的容器受到了严重影响，并且自己编写了替代品。通过`std::array`来实现`std::vector`和`std::map`这样的容器，由于没有动态内存分配，只能预先计算出需要的大小（可能导致多次遍历）或者在栈上开块大内存。

提案 [P0784R7](https://open-std.org/JTC1/SC22/WG21/docs/papers/2019/p0784r7.html) 重新讨论了在常量求值中支持标准库容器的可能性

主要有以下三个难点： 

- 析构函数不能被声明为 constexpr（对于 constexpr 对象，它们必须是 trivial 的） 
- 无法进行动态内存分配/释放 
- 无法在常量求值中使用 [placement new](https://en.cppreference.com/w/cpp/language/new#Placement_new) 来调用对象的构造函数


针对第一个问题，作者们与 MSVC，GCC，Clang，EDG 等前端开发人员快速讨论并解决了这个问题。C++20 起，可以符合 [literal type](https://en.cppreference.com/w/cpp/named_req/LiteralType) 要求的类型具有 constexpr 修饰的析构函数，而不是严格要求平凡的析构函数。

针对第二个问题，处理起来并不简单。C++ 有很多未定义行为都是由于错误的内存处理导致的，相比之下，不能直接操作内存的脚本语言则安全的多。但是为了复用代码，C++ 编译器中的常量求值器不得不直接操作内存，不过由于所有信息都是编译期已知的，理论上可以保证常量求值中不会出现内存错误 (out of range, double free, memory leak, ...)，如果出现应该中止编译并报告错误。

常量求值器需要跟踪许多对象的的元信息，并找出这些错误 

- 记录`union`哪个 field 是 active 的，访问 unactive 的成员导致未定义行为，这由 [P1330](https://open-std.org/JTC1/SC22/WG21/docs/papers/2018/p1330r0.pdf) 阐明 
- 正确记录对象的 [lifetime](https://en.cppreference.com/w/cpp/language/lifetime)，访问未初始化的内存和已经析构的对象都是不允许的


当时还不允许在常量求值中把`void*`转换成`T*`，所以理所当然的

```cpp
void* operator new(std::size_t);
```

不支持在常量求值中使用，取而代之的是

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

对于第三个问题，则是添加了一个 magic function 即 [std::construct_at](https://en.cppreference.com/w/cpp/memory/construct_at)，它的作用是在指定的内存位置上调用对象的构造函数，用来在常量求值中取代`placement new`。这样的话我们就可以先通过`std::allocator`分配内存，再通过`std::construct_at`来构造对象了。该提案最终被接受，进入了 [C++20](https://en.cppreference.com/w/cpp/memory/construct_at)，同时使得`std::vector`，`std::string`在常量求值中可用（其它的容器理论上也行，但是目前的实现还没支持，如果非常想要只能自己搓一个了）。

虽然支持了动态内存分配，但并不是毫无限制。**在一次常量求值中分配的内存必须要在这次常量求值结束之前释放完全，不能有内存泄漏，否则会导致编译错误**。这种类型的内存分配被叫做 *transient constexpr allocations（瞬态内存分配）* 。该提案也讨论了 *non-transient allocation（非瞬态内存分配）* ，在编译期未被释放的内存，将被转为静态储存（其实就是存在数据区，就像全局变量那样）。但是，委员会认为这种可能性 "too brittle"，出于多种原因，目前尚未采纳。

## 2018：更多的 constexpr 

提案 [P1002](https://open-std.org/JTC1/SC22/WG21/docs/papers/2018/p1002r1.pdf) 希望在 constexpr 函数中支持`try-catch`块。但是不能`throw`，这样是为了能把更多的标准库容器的成员函数标记为`constexpr`。

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

有些时候我们想保证一个函数在编译期执行

```cpp
extern int foo(int x);

constexpr int bar(int x){ return x; }

foo(bar(1)); // evaluate at compile time ?
```

事实上`g`无论是在编译期还是运行期执行，理论上都可以。为了保证它在编译期执行，我们需要多写一些代码

```cpp
constexpr auto x = bar(1);
foo(x);
```

这样就保证了`g`在编译期执行，同样，这种没意义的局部变量实在是多余。提案 [P1073](https://open-std.org/JTC1/SC22/WG21/docs/papers/2018/p1073r0.html) 希望增加一个标记 `constexpr!`来确保一个函数在编译期执行，如果不满足则导致编译错误。最终该标记被更名为 [consteval](https://en.cppreference.com/w/cpp/language/consteval) 并进入了 C++20。

```cpp
extern int foo(int x);

consteval int bar(int x){ return x; }

foo(bar(1)); // ensure evaluation at compile time
```

`consteval`函数不能在常量求值上下文外获取指针或引用，编译器后端既不需要，也不应该知道这些函数的存在。事实上该提案也为未来打算加入标准的 static reflection 做了铺垫，它将会添加非常多的只能在编译期执行的函数。

## 2018：默认 constexpr ？ 

在当时，有很多提案的内容仅仅是把标准库的某个部分标记为`constexpr`，在本文中没有讨论它们，因为它们具有相同的模式。

提案 [P1235](https://open-std.org/JTC1/SC22/WG21/docs/papers/2018/p1235r0.pdf) 希望把所有函数都标记为 implicit constexpr 的

- non：如果可能，将方法标记为 constexpr。
- constexpr：与当前行为相同
- constexpr(false)：不能在编译时调用
- constexpr(true)：只能在编译时调用


该提案最终没有被接受。

## 2020：更强的动态内存分配？ 

正如之前提到的，在 constexpr 函数中支持内存分配已经被允许了，也可以在 constexpr 函数中使用`std::vector`这样的容器，但是由于是瞬态内存分配，无法创建全局的`std::vector`

```cpp
constexpr std::vector<int> v{1, 2, 3};  // error
```

所以如果一个 constexpr 函数返回一个`std::vector`，只能额外包装一层把这个`std::vector`转成`std::array`然后作为全局变量

```cpp
constexpr auto f() { return std::vector<int>{1, 2, 3}; }

constexpr auto arr = [](){
    constexpr auto len = f().size();
    std::array<int, len> result{};
    auto temp = f();
    for(std::size_t i = 0; i < len; ++i){
        result[i] = temp[i];
    }
    return result;
};
```

提案 [P1974](https://open-std.org/JTC1/SC22/WG21/docs/papers/2020/p1974r0.pdf) 提议使用`propconst`来支持非瞬态内存分配，这样上述的额外的包装代码就不需要了。

非瞬态内存分配的原理很简单

```cpp
constexpr std::vector vec = {1, 2, 3};
```

编译器会将上述代码编译为类似下面这样

```cpp
constexpr int data[3] = {1, 2, 3};
constexpr std::vector vec{
    .begin = data, 
    .end = data + 3, 
    .capacity = data + 3
};
```

其实就是把本来应该指向动态分配的内存的指针改为指向静态内存。原理并不复杂，真正的难点是如何保证程序的正确性。**显然上述的vec即使在程序结束的时候也不应该调用析构函数，否则会导致段错误**。这个问题要解决很简单，我们可以约定，**任何constexpr标记的变量都不会调用析构函数**。

但是考虑如下情况：

```cpp
constexpr unique_ptr<unique_ptr<int>> ppi { 
    new unique_ptr<int> { new int { 42 } } 
};

int main(){
    ppi.reset(new int { 43 }); // error, ppi is const
    auto& pi = *ppi;
    pi.reset(new int { 43 }); // ok
}
```

由于`pp1`是`constexpr`的，那么它的析构函数不应该调用。对`ppi`尝试调用`reset`是不允许的，因为`constexpr`标记的变量隐含`const`，而`reset`并不是一个`const`方法。但是对`pi`调用`reset`是允许的，因为外层`const`不影响内层指针。

如果允许`pi`调用`reset`，显然这是一次运行期调用，会在运行期动态内存分配，而由于`ppi`不会调用析构函数，里面的`pi`当然也不会调用析构函数，于是内存就泄露了，显然这种做法不应该被允许。

解决办法自然是想办法禁止`pi`调用`reset`，提案提出了`propconst`关键字，它可以把外层的`constexpr`传递给内层，这样`pi`也是`const`的了，也就不能调用`reset`了，就不会出现代码逻辑问题了。

可惜的的是暂时还未被标准接受，在那之后还有一些新的的提案希望能够支持这个特性比如 [P2670R1](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2023/p2670r1.html)，相关的讨论还在继续。

## 2021：constexpr 类 

C++ 标准库中的很多类型，比如`vector`, `string`, `unique_ptr`中的所有方法都被标记为 constexpr，并且真正可以在编译期执行。很自然的，我们希望能直接标记整个类为 constexpr，这样可以省去哪些重复的说明符编写。

提案 [P2350](https://open-std.org/JTC1/SC22/WG21/docs/papers/2021/p2350r1.pdf) 希望支持这个特性，constexpr 标记的`class`中的所有方法都被隐式标记为 constexpr

```cpp
// before
class struct {
    constexpr bool empty() const { /* */ }

    constexpr auto size() const { /* */ }

    constexpr void clear() { /* */ }
};

// after
constexpr struct SomeType {
    bool empty() const { /* */ }

    auto size() const { /* */ }

    void clear() { /* */ }
};
```

有一个有趣的故事与这个提案有关 - 在不知道它的存在之前，我（文章原作者）在 [stdcpp.ru](https://stdcpp.ru/) 提出了同样的想法。

在标准制定过程中，很多几乎相同的提案几乎可以同时出现。这证明了 [多重发现理论的正确性](https://en.wikipedia.org/wiki/Multiple_discovery)：某些思想或概念会在不同的人群中独立地出现，就像它们在空气中漂浮一样，并且谁先发现的并不重要。如果社区的规模足够大，这些思想或概念自然会发生演变。

## 2023：编译期类型擦除！ 

在常量求值中，一直不允许把`void*`转换成`T*`，这样导致诸如`std::any`，`std::function`等类型擦除实现的容器无法在常量求值中使用。原因呢，是因为我们可以通过`void*`来绕过类型系统，把一个类型转换为不相干的类型

```cpp
int* p = new int(42);
double* p1 = static_cast<float*>(static_cast<void*>(p));
```

如果对`p1`解引用实际上是未定义的行为，所以禁止了这种转换（**注意 reinterpret_cast 一直在常量求值中禁用**）。但是显然这种做法已经误伤了正确的写法了，因为像`std::any`这种实现，显然不会把一个从`void*`转换成无关的类型，而是会把它转换回原来的类型，完全不允许这种转换是不合理的。提案 [P2738R0](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2023/p2738r0.pdf) 希望在常量求值中支持这种转换，编译器理论上能在编译期记录一个`void*`指针原本的类型，如果转换的不是原本的类型，就报错。

最终该提案被接受，并且加入 C++26，现在可以进行 `T*` -> `void*` -> `T*` 的转换了

```cpp
constexpr void f(){
    int x = 42;
    void* p = &x;
    int* p1 = static_cast<int*>(p); // ok
    float* p2 = static_cast<float*>(p); // error
}
```

## 2023：支持 placement new？ 

前面我们提到，为了支持`vector`在常量求值中使用，加入了`construct_at`用于在常量求值中调用构造函数。它具有如下形式

```cpp
template<typename T, typename... Args>
constexpr T* construct_at(T* p, Args&&... args);
```

虽然一定程度上解决了问题，但是它并不能完全提供`placement new`的功能

- value initialization


```cpp
new (p) T(args...) // placement new version
construct_at(p, args...) // construct_at version
```

- default initialization


```cpp
new (p) T // placement new version
std::default_construct_at(p) // P2283R1
```

- list initialization


```cpp
new (p) T{args...} // placement new version
// construct_at version doesn't exist
```

- designated initialization


```cpp
new (p) T{.x = 1, .y = 2} // placement new version
// construct_at version cannot exist
```

提案 [P2747R1](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2023/p2747r1.html) 希望在常量求值中直接支持`placement new`。暂时还未被加入标准。

## 2024-∞：未来无极限！ 

截止目前，C++ 的常量求值已经支持了非常丰富的功能，支持条件，变量，循环，虚函数调用，动态内存分配等等一系列特性。但是受限于日常开发使用的 C++ 版本，有很多功能可能暂时没法使用，可以在 [这里](https://en.cppreference.com/w/cpp/feature_test#:~:text=P2564R3-,__cpp_constexpr,-constexpr) 方便的查看哪个版本支持了什么特性。

未来的 constexpr 中仍然有很多可能性，比如像`memcpy`这样的函数或许也能在常量求值中使用？又或者目前的`small_vector`的**某些实现不能在不改动任何代码的前提**下变成 constexpr 的，因为它们使用`char`数组为栈上的对象提供储存（为了避免默认构造）

```cpp
constexpr void foo(){
    std::byte buf[100];
    std::construct_at(reinterpret_cast<int*>(buf), 42); // no matter what
}
```

但是目前在常量求值中无法直接在`char`数组上构造对象。更进一步，在 C++20 加入的 [implicit lifetime](https://en.cppreference.com/w/cpp/named_req/ImplicitLifetimeType) 是否可能在常量求值中表现出来呢？这些理论上都是可能实现的，只是要求编译器记录更多的元信息。而在未来，一切皆有可能！最终我们或许真的能 constexpr everything！