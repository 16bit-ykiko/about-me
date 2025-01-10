---
title: 'C++ 中 constexpr 的发展史！（上篇）'
date: 2024-02-10 23:15:47
updated: 2024-12-18 11:21:51
series: ['Constexpr']
series_order: 1
---

几个月前，我写了一篇介绍 C++ 模板的文章：[雾里看花：真正意义上的理解 C++ 模板](https://www.ykiko.me/zh-cn/articles/655902377)。

文章梳理了现代 C++ 中模板的地位。其中，使用 constexpr 函数替代模板进行编译期计算可以说是现代 C++ 最重要的改进之一。constexpr 本身其实并不难理解，非常直观。但由于几乎每个 C++ 版本都在改进它，不同 C++ 版本中可用的内容差异很大，有时可能会给人一种“不一致”的感觉。

最近我偶然读到了这篇文章：[Design and evolution of constexpr in C++](https://pvs-studio.com/en/blog/posts/cpp/0909/)，它全面介绍了 C++ 中 constexpr 的发展史，写得非常好。于是便想将其翻译到中文社区。

有趣的是，这篇文章其实也是翻译的。文章的原作者是一位俄罗斯人，最初发表在俄罗斯的论坛上。这是作者的邮箱：`izaronplatz@gmail.com`，我已经和他联系过了，他回复说：

>  It's always good to spread knowledge in more languages. 

也就是允许翻译了。不过我不懂俄文，所以主要参考了原文的结构，而主体部分基本都是我重新叙述的。

原文内容较长，故分为上下两篇，这是上篇。

## 很神奇吗？

constexpr 是当代 C++ 中最神奇的关键字之一。它使得某些代码可以在编译期执行。

随着时间的推移，constexpr 的功能越来越强大。现在几乎可以在编译时计算中使用标准库的所有功能。

constexpr 的发展历史可以追溯到早期版本的 C++。通过研究标准提案和编译器源代码，我们可以了解这一语言特性是如何一步步地构建起来的，为什么会以这样的形式存在，实际上 constexpr 表达式是如何计算的，未来有哪些可能的功能，以及哪些功能可能会存在但没有被纳入标准。

本文适合任何人，无论你是否了解 constexpr！

## C++98/03：我比你更 const

在 C++ 中，有些地方需要整数常量（比如内建数组类型的长度），这些值必须在编译期就确定。C++ 标准允许通过简单的表达式来构造常量，例如：

```cpp
enum EPlants{
    APRICOT = 1 << 0,
    LIME = 1 << 1,
    PAPAYA = 1 << 2,
    TOMATO = 1 << 3,
    PEPPER = 1 << 4,
    FRUIT = APRICOT | LIME | PAPAYA,
    VEGETABLE = TOMATO | PEPPER,
};

template <int V>
int foo(int v = 0){
    switch(v){
        case 1 + 4 + 7:
        case 1 << (5 | sizeof(int)):
        case (12 & 15) + PEPPER: return v;
    }
}

int f1 = foo<1 + 2 + 3>();
int f2 = foo<((1 < 2) ? 10 * 11 : VEGETABLE)>();
```

这些表达式在`[expr.const]`小节中被定义，并且被叫做*常量表达式（constant expression）*。它们只能包含：

- 字面量：`1`,`'A'`,`true`,`...`
- 枚举值
- 整数或枚举类型的模板参数（例如`template<int v>`中的`v`）
- `sizeof`表达式
- 由常量表达式初始化的`const`变量

前几项都很好理解，最后一项稍微有点复杂。如果一个变量具有[静态储存期](https://en.cppreference.com/w/cpp/language/storage_duration)，那么在常规情况下，它的内存会被填充为`0`，之后在程序开始执行的时候改变。但对于上述的变量来说，这太晚了，需要在编译结束之前就计算出它们的值。

在 C++98/03 当中有两种类型的[静态初始化](https://en.cppreference.com/w/cpp/language/initialization#Static_initialization)：

- [零初始化](https://en.cppreference.com/w/cpp/language/zero_initialization)：内存被填充为`0`，然后在程序执行期间改变
- [常量初始化](https://en.cppreference.com/w/cpp/language/constant_initialization)：使用常量表达式进行初始化，内存（如果需要的话）立即填充为计算出来的值

> 所有其它的初始化都被叫做[动态初始化](https://en.cppreference.com/w/cpp/language/initialization#Dynamic_initialization)，这里我们不考虑它们。

让我们看一个包含两种静态初始化的例子：

```cpp
int foo() { return 13; }

const int v1 = 1 + 2 + 3 + 4;              // 常量初始化
const int v2 = 15 * v1 + 8;                // 常量初始化
const int v3 = foo() + 5;                  // 零初始化
const int v4 = (1 < 2) ? 10 * v3 : 12345;  // 零初始化
const int v5 = (1 > 2) ? 10 * v3 : 12345;  // 常量初始化
```

变量`v1`, `v2`和`v5`都可以作为常量表达式，可以用作模板参数，`switch`的`case`，`enum`的值，等等。而`v3`和`v4`则不行。即使我们能明显看出`foo() + 5`的值是`18`，但在那时还没有合适的语义来表达这一点。

由于常量表达式是递归定义的，如果一个表达式的某一部分不是常量表达式，那么整个表达式就不是常量表达式。在这个判断过程中，只考虑实际计算的表达式，所以`v5`是常量表达式，但`v4`不是。

如果没有获取常量初始化的变量的地址，编译器就可以不为它分配内存。所以我们可以通过取地址的方式，来强制编译器给常量初始化的变量预留内存（其实如果没有显式取地址的话，普通的局部变量也可能被优化掉，任何不违背[as-if](https://en.cppreference.com/w/cpp/language/as_if)原则的优化都是允许的。可以考虑使用`[[gnu::used]]`这个 attribute 标记避免变量被优化掉）。

```cpp
int main() {
    std::cout << v1 << &v1 << std::endl;
    std::cout << v2 << &v2 << std::endl;
    std::cout << v3 << &v3 << std::endl;
    std::cout << v4 << &v4 << std::endl;
    std::cout << v5 << &v5 << std::endl;
}
```

编译上述代码并查看符号表（环境是 windows x86-64）：

```bash
$ g++ --std=c++98  -c main.cpp 
$ objdump -t -C main.o

(sec  6)(fl 0x00)(ty    0)(scl   3) (nx 0) 0x0000000000000000 v1
(sec  6)(fl 0x00)(ty    0)(scl   3) (nx 0) 0x0000000000000004 v2
(sec  3)(fl 0x00)(ty    0)(scl   3) (nx 0) 0x0000000000000000 v3
(sec  3)(fl 0x00)(ty    0)(scl   3) (nx 0) 0x0000000000000004 v4
(sec  6)(fl 0x00)(ty    0)(scl   3) (nx 0) 0x0000000000000008 v5

----------------------------------------------------------------

(sec  3)(fl 0x00)(ty    0)(scl   3) (nx 1) 0x0000000000000000 .bss
(sec  4)(fl 0x00)(ty    0)(scl   3) (nx 1) 0x0000000000000000 .xdata
(sec  5)(fl 0x00)(ty    0)(scl   3) (nx 1) 0x0000000000000000 .pdata
(sec  6)(fl 0x00)(ty    0)(scl   3) (nx 1) 0x0000000000000000 .rdata
```

可以发现在我的 GCC 14 上，零初始化的变量`v3`和`v4`被放在`.bss`段，而常量初始化的变量`v1`, `v2`,`v5`被放在`.rdata`段。操作系统会对`.rdata`段进行保护，使其处于只读模式，尝试写入会导致段错误。

从上述的差异可以看出，一些`const`变量比其它的更加`const`。但是在当时我们并没有办法检测出这种差异（后来的 C++20 引入了[constinit](https://en.cppreference.com/w/cpp/language/constinit)来确保一个变量进行常量初始化）。

## 0-∞：编译器中的常量求值器

为了理解常量表达式是如何求值的，我们需要简单了解编译器的构造。不同编译器的处理方法大致相同，接下来将以 Clang/LLVM 为例。

总的来说，编译器可以看做由以下三个部分组成：

- **前端（Front-end）**：将 C/C++/Rust 等源代码转换为 LLVM IR（一种特殊的中间表示）。Clang 是 C 语言家族的编译器前端。
- **中端（Middle-end）**：根据相关的设置对 LLVM IR 进行优化。
- **后端（Back-end）**：将 LLVM IR 转换为特定平台的机器码：x86/Arm/PowerPC 等等。

对于一个简单的编程语言，通过调用 LLVM，`1000`行就能实现一个编译器。你只需要负责实现语言前端就行了，后端交给 LLVM 即可。甚至前端也可以考虑使用 lex/yacc 这样的现成的语法解析器。

具体到编译器前端的工作，例如这里提到的 Clang，可以分为以下三个阶段：

- **词法分析**：将源文件转换为 Token Stream，例如 `[]() { return 13 + 37; }` 被转换为 `[`, `]`, `(`, `)`, `{`, `return`, `13`, `+`, `37`, `;`, `}`
- **语法分析**：产生 Abstract Syntax Tree（抽象语法树），就是将上一步中的 Token Stream 转换为类似于下面这样的递归的树状结构：

```bash
lambda-expr 
└── body 
    └── return-expr 
        └── plus-expr 
            ├── number 13
            └── number 37
```

- **代码生成**：根据给定的 AST 生成 LLVM IR

因此，常量表达式的计算（以及相关的事情，如模板实例化）严格发生在 C++ 编译器的前端，而 LLVM 不涉及此类工作。这种处理常量表达式（从 C++98 的简单表达式到 C++23 的复杂表达式）的工具被称为**常量求值器 (constant evaluator)**。

多年来，对常量表达式的限制一直在不断放宽，而 Clang 的常量求值器相应地变得越来越复杂，直到管理 memory model（内存模型）。有一份旧的[文档](https://clang.llvm.org/docs/InternalsManual.html#constant-folding-in-the-clang-ast)，描述 C++98/03 的常量求值。由于当时的常量表达式非常简单，它们是通过分析语法树进行 *constant folding* （常量折叠）来进行的。由于在语法树中，所有的算术表达式都已经被解析为子树的形式，因此计算常量就是简单地遍历子树。

常量计算器的源代码位于[lib/AST/ExprConstant.cpp](https://clang.llvm.org/doxygen/ExprConstant_8cpp_source.html)，在撰写本文时已经扩展到将近 17000 行。随着时间的推移，它学会了解释许多内容，例如循环（`EvaluateLoopBody`），所有这些都是在语法树上进行的。

常量表达式与运行时代码有一个重要的区别：它们必须不引发 undefined behavior（未定义行为）。如果常量计算器遇到未定义行为，编译将失败。

```cpp
error: constexpr variable 'foo' must be initialized by a constant expression
    2 | constexpr int foo = 13 + 2147483647;               
      |               ^     ~~~~~~~~~~~~~~~
note: value 2147483660 is outside the range of representable values of type 'int'
    2 | constexpr int foo = 13 + 2147483647;
```

因此在有些时候可以用它们来检测程序中的潜在错误。

## 2003：真的能 macro free 吗？

**标准的改变是通过 proposals（提案）进行的**

> 在哪里可以找到提案？它们是由什么组成的？<br><br>所有的有关 C++ 标准的提案都可以在[open-std.org](https://open-std.org/JTC1/SC22/WG21/)上找到。它们中的大多数都有详细的描述并且易于阅读。通常由如下部分组成：<br><br>-  当前遇到的问题<br>-  标准中相关措辞的的链接<br>-  上述问题的解决方案<br>-  建议对标准措辞进行的修改<br>-  相关提案的链接（提案可能有多个版本或者需要和其它提案进行对比）<br>-  在高级提案中，往往还会附带上实验性实现的链接<br><br>可以通过这些提案来了解 C++ 的每个部分是如何演变的。并非存档中的所有提案最终都被接受，但是它们都对 C++ 的发展有着重要的影响。<br><br>通过提交新提案，任何人都可以参与到 C++ 的演变过程中来。

`2003`年的提案[N1521 Generalized Constant Expressions](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2003/n1521.pdf)指出一个问题。如果一个表达式中的某个部分含有函数调用，那么整个表达式就不能是常量表达式，即使这个函数最终能够被常量折叠。这迫使人们在处理复杂常量表达式的时候使用宏，甚至一定程度上导致了宏的滥用：

```cpp
inline int square(int x) { return x * x; }
#define SQUARE(x) ((x) * (x))

square(9)
std::numeric_limits<int>::max() 
// 理论上可用于常量表达式, 但是实际上不能

SQUARE(9)
INT_MAX
// 被迫使用宏代替
```

因此，建议引入**常值 (constant-valued)**函数的概念，允许在常量表达式中使用这些函数。如果希望一个函数是常值函数，那么它必须满足：

- inline ，non-recursive，并且返回类型不是 void
- 仅由单一的 return expr 语句组成，并且在把 expr 里面的函数参数替换为常量表达式之后，得到的仍然是一个常量表达式

如果这样的函数被调用，并且参数是常量表达式，那么函数调用表达式也是常量表达式：

```cpp
int square(int x) { return x * x; }         // 常值函数
long long_max(int x) { return 2147483647; } // 常值函数
int abs(int x) { return x < 0 ? -x : x; }   // 常值函数
int next(int x) { return ++x; }             // 非常值函数
```

这样的话，不需要修改任何代码，最开始的例子中的`v3`和`v4`也可以被用作常量表达式了，因为`foo`被认为是常值函数。

该提案认为，可以考虑进一步支持下面这种情况：

```cpp
struct cayley{
    const int value;
    cayley(int a, int b) : value(square(a) + square(b)) {}
    operator int() const { return value; }
};

std::bitset<cayley(98, -23)> s; // same as bitset<10133>
```

因为成员`value`是`totally constant`的，在构造函数中通过两次调用常值函数进行初始化。换句话说，根据该提案的一般逻辑，此代码可以大致转换为以下形式（将变量和函数移到结构体之外）：

```cpp
// 模拟 cayley::cayley(98, -23)的构造函数调用和 operator int()
const int cayley_98_m23_value = square(98) + square(-23);

int cayley_98_m23_operator_int() { return cayley_98_m23_value; }

// 创建 bitset
std::bitset<cayley_98_m23_operator_int()> s; // same as bitset<10133>
```

但是和变量一样，程序员无法确定一个函数是否为常值函数，只有编译器知道。

> 提案通常不会深入到编译器实现它们的细节。上述提案表示，实现它不应该有任何困难，只需要稍微改变大多数编译器中存在的常量折叠即可。然而，提案与编译器实现密切相关。如果提案无法在合理时间内实现，很可能不会被采纳。从后来的视角来看，许多大的提案最后被分成了多个小的提案逐步实现。

## 2006-2007：当一切浮出水面

幸运的是，三年后，这个提案的后续修订版[N2235](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2007/n2235.pdf)认识到了过多的隐式特性是不好的，程序员应该有办法确保一个变量可以被用作常量，如果不满足相应的条件应该导致编译错误。

```cpp
struct S{
    static const int size;
};

const int limit = 2 * S::size;                 // 动态初始化
const int S::size = 256;                       // 常量初始化
const int z = std::numeric_limits<int>::max(); // 动态初始化
```

根据程序员的设想，`limit`应该被常量初始化，但事实并非如此，因为`S::size`被定义在`limit`之后，定义的太晚了。可以通过 C++20 加入的[constinit](https://en.cppreference.com/w/cpp/language/constinit)来验证这一点，`constinit`保证一个变量进行常量初始化，如果不能进行常量初始化，则会编译错误。

在新的提案中，常值函数被**重命名**为 *constexpr function*，对它们的要求保持不变。但现在，为了能够在常量表达式中使用它们，**必须**使用 constexpr 关键字进行声明。此外，如果函数体不符合相关的要求，将会编译失败。同时建议将一些标准库的函数（如`std::numeric_limits`中的函数）标记为 constexpr，因为它们符合相关的要求。**变量**或类成员也可以声明为 constexpr，这样的话，如果变量不是通过常量表达式进行初始化，将会编译失败。

用户自定义`class`的 constexpr 构造函数也合法化了。该构造函数必须具有空函数体，并用常量表达式初始化成员。隐式生成的构造函数将尽可能的被标记为 constexpr。对于 constexpr 的对象，析构函数必须是平凡的，因为非平凡的析构函数通常会在正在执行的程序上下文中做一些改变，而在 constexpr 计算中不存在这样的上下文。

以下是包含 constexpr 的示例类：

```