# Everything about constexpr in modern C++!


最近我读到一篇 [文章](https://pvs-studio.com/en/blog/posts/cpp/0909/)，从早期的 C++ 开始谈起，详细的介绍了 constexpr 这一概念在 C++ 中的发展。中文互联网确实缺少这样的资料，所以我决定把它翻译成中文。

*有趣的是，这篇文章的原作者其实是一位俄罗斯人，文章原文也是俄语。上面那篇文章（英文）也是翻译的（这也侧面反映出这篇文章确实写的很好）。我和文章原作者邮件联系过了，已经取得了翻译许可*

主要参照了原文的主题和结构，为了更加符合中文的表述习惯，其余部分由我补充。

# 
`constexpr` —— 这个在现代 C++ 中充满魔力的关键字。通过它，让一个函数在编译期执行。

# C++98 和 C++03 中的 const 变量
在 C++ 中，有些地方需要整数常量（比如内建数组类型的长度），这些值必须在编译期就确定。C++ 标准允许通过简单的表达式来构造常量，例如
```cpp
enum EPlants
{
    APRICOT = 1 << 0,
    LIME = 1 << 1,
    PAPAYA = 1 << 2,
    TOMATO = 1 << 3,
    PEPPER = 1 << 4,
    FRUIT = APRICOT | LIME | PAPAYA,
    VEGETABLE = TOMATO | PEPPER,
};

template <int V>
int foo(int v = 0)
{
    switch(v)
    {
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


前几项都很好理解的，对于最后一项稍微有点复杂。如果一个变量具有 [静态储存期](https://en.cppreference.com/w/cpp/language/storage_duration)，那么在常规情况下，它的内存会被填充为`0`。之后在程序开始执行的时候改变。但是对于上述的变量来说，这太晚了，需要在编译结束之前就计算出它们的值。

在 C++98/03 当中有两种类型的 [静态初始化](https://en.cppreference.com/w/cpp/language/initialization#Static_initialization)：
- [零初始化](https://en.cppreference.com/w/cpp/language/zero_initialization) 内存被填充为`0`，然后在程序执行期间改变
- [常量初始化](https://en.cppreference.com/w/cpp/language/constant_initialization)，使用常量表达式进行初始化，内存（如果需要的话）立即填充为计算出来的值

*注：所有其它的初始化都被叫做 [动态初始化](https://en.cppreference.com/w/cpp/language/initialization#Dynamic_initialization)，这里我们不考虑它们。*

让我们看一个包含两种静态初始化的例子
```cpp
int foo() { return 13; }

const int v1 = 1 + 2 + 3 + 4;              // 使用常量表达式初始化
const int v2 = 15 * v1 + 8;                // 使用常量表达式初始化
const int v3 = foo() + 5;                  // 零初始化
const int v4 = (1 < 2) ? 10 * v3 : 12345;  // 零初始化
const int v5 = (1 > 2) ? 10 * v3 : 12345;  // 使用常量表达式初始化
```
变量`v1`,`v2`和`v5`都是常量表达式，可以用作模板参数，`switch`的`case`，`enum`的值，等等。而`v3`和`v4`则不行。即使我们能明显看出`foo() + 5`的值是`18`，但在那时还没有合适的语义来表达这一点，最终只能选择相信编译器在用到`v3`的时候会自动进行常量折叠。

由于常量表达式是递归定义的，如果一个表达式的某一部分不是常量表达式，那么整个表达式就不是常量表达式。在这个判断过程中，只考虑实际计算的表达式，所以`v5`是常量表达式，但`v4`不是。

如果没有获取常量初始化的变量的地址，编译器就可以不为它分配内存。所以我们可以通过取地址的方式，来强制编译器给常量初始化的变量预留内存（其实如果没有显式取地址的话，普通的局部变量也可能被优化掉，任何不违背 [as-if](https://en.cppreference.com/w/cpp/language/as_if) 原则的优化都是允许的。可以考虑使用`[[gnu::used]]`这个 attribute 标记避免变量被优化掉）。

```cpp
int main() 
{
    std::cout << v1 << &v1 << std::endl;
    std::cout << v2 << &v2 << std::endl;
    std::cout << v3 << &v3 << std::endl;
    std::cout << v4 << &v4 << std::endl;
    std::cout << v5 << &v5 << std::endl;
}
```
编译上述代码并查看符号表（环境是 windows x86-64）
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
可以发现在我的`gcc 14`上，零初始化的变量`v3`和`v4`被放在`.bss`段，而常量初始化的变量`v1`,`v2`,`v5`被放在`.rdata`段。操作系统的加载器在启动程序之前会加载程序，使得`.rdata`段处于只读模式，该程序段在操作系统级别受到写保护，尝试写入会导致段错误。

从上述的差异可以看出，一些`const`变量比其它的更加`const`。但是在当时我们并没有办法检测出这种差异（后来的 C++20 引入了 [constinit](https://en.cppreference.com/w/cpp/language/constinit) 来确保一个变量进行常量初始化）。

# 0-∞ 编译器中的常量求值器

为了理解常量表达式是如何求值的，我们需要简单了解编译器的构造。不同编译器的处理方法大致相同，接下来将以 Clang/LLVM 为例


笼统的来说，编译器可以看做由以下三个部分组成：

- **前端（Front-end）**：将 C/C++/Rust 等源代码转换为 LLVM IR（一种特殊的中间表示）。Clang 是 C 语言家族的编译器前端
- **中端（Middle-end）**：根据相关的设置对 LLVM IR 进行优化
- **后端（Back-end）**：将 LLVM IR 转换为特定平台的机器码： x86/Arm/PowerPC 等等

对于一个简单的编程语言，通过调用 LLVM，`1000`行就能实现一个编译器。你只需要负责实现语言前端就行了，后端交给 LLVM 即可。甚至前端也可以考虑使用`lex/yacc`这样的现成的语法解析器。

具体到编译器前端的工作，例如这里提到的 Clang，可以分为以下三个部分：

- **词法分析**：将源文件转换为 Token Stream，例如 `[]() { return 13 + 37; }` 被转换为 `[`, `]`, `(`, `)`, `{`, `return`, `13`, `+`, `37`, `;`, `}`
- **语法分析**：产生 Abstract Syntax Tree（抽象语法树），就是将上一步中的 Token Stream 转换为类似于下面这样的递归的树状结构
```lisp
lambda-expr 
└── body 
    └── return-expr 
        └── plus-expr 
            ├── number 13
            └── number 37
```
- **代码生成**：根据给定的 AST 生成 LLVM IR

因此，常量表达式的计算（以及相关的事情，如模板实例化）严格发生在 C++ 编译器的前端，而 LLVM 不涉及此类工作。这种处理常量表达式（从 C++98 的简单表达式到 C++23 的复杂表达式）工具被称为 *常量求值器（constant evaluator）*。

如果按照标准，在某处的代码期望常量表达式；而该处的表达式确实满足了常量表达式的要求，则 Clang 应该`100％`的在编译期就能计算出它。多年来，对常量表达式的限制一直在不断放宽，而 Clang 的常量求值器相应地变得越来越复杂，直到管理 memory model（内存模型）。

有一份旧的 [文档](https://clang.llvm.org/docs/InternalsManual.html#constant-folding-in-the-clang-ast)，描述 C++98/03 的常量求值。由于当时的常量表达式非常简单，它们是通过分析语法树进行 *constant folding*（常量折叠）来进行的。由于在语法树中，所有的算术表达式都已经被解析为子树的形式，因此计算常量就是简单地遍历子树。

常量计算器的源代码位于 [lib/AST/ExprConstant.cpp](https://clang.llvm.org/doxygen/ExprConstant_8cpp_source.html)。在撰写本文时已经扩展到将近 17000 行。随着时间的推移，它学会了解释许多内容，例如循环（`EvaluateLoopBody`），所有这些都是在语法树上进行的。

常量表达式与运行时代码有一个重要的区别 - 它们必须不引发 undefined behavior（未定义行为）。如果常量计算器遇到未定义行为，编译将失败。

```cpp
error: constexpr variable 'foo' must be initialized by a constant expression
    2 | constexpr int foo = 13 + 2147483647;               
      |               ^     ~~~~~~~~~~~~~~~
note: value 2147483660 is outside the range of representable values of type 'int'
    2 | constexpr int foo = 13 + 2147483647;     
```
因此在有些时候可以用它们来检测程序中的潜在错误。

# 2003: No need for macros

**标准的改变是通过 proposals（提案）进行的**

> 在哪里可以找到提案？它们是由什么组成的？
> 
> 所有的有关 C++ 标准的提案都可以在 [open-std.org](https://open-std.org/JTC1/SC22/WG21/) 上找到。它们中的大多数都有详细的描述并且易于阅读。通常由如下部分组成：
> - 当前遇到的问题
> - 标准中相关措辞的的链接
> - 上述问题的解决方案
> - 建议对标准措辞进行的修改
> - 相关提案的链接（一个提案可能多个版本或者需要和其它提案进行对比）
> - 在高级提案中，往往还会附带上实验性实现的链接
>
>可以通过这些提案来了解 C++ 的每个部分是如何演变的。并非存档中的所有提案最终都被接受，但是它们都对 C++ 的发展有着重要的影响。
>
>通过提交新提案，任何人都可以参与到 C++ 的演变过程中来。


`2003`年的提案 [N1521 Generalized Constant Expressions](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2003/n1521.pdf) 指出一个问题。如果一个表达式中的某个部分含有函数调用，那么整个表达式就不能是常量表达式，即使这个函数能够被常量折叠。这迫使人们在处理复杂常量表达式的时候使用宏，甚至一定程度上导致了宏的滥用

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

因此，建议引入 *constant-valued（常值）* 函数的概念，允许在常量表达式中使用这些函数。如果希望一个函数是常值函数，那么它必须满足

- 是 inline 的
- 是 non-recursive 的
- 返回类型不是 void
- 仅由单一的 return 语句组成
  
如果这样的函数被调用，并且参数是常量表达式，那么函数调用表达式也是常量表达式。

```cpp
int square(int x) { return x * x; }         // 常值函数
long long_max(int x) { return 2147483647; } // 常值函数
int abs(int x) { return x < 0 ? -x : x; }   // 常值函数
int next(int x) { return ++x; }             // 非常值函数，尝试修改函数参数
```

这样的话，不需要修改任何代码，最开始的例子中的`v3`到`v4`也可以被用作常量表达式了，因为`foo`被认为是常值函数。

该提案认为，可以考虑进一步支持下面这种情况
```cpp
struct cayley
{
    const int value;
    cayley(int a, int b) : value(square(a) + square(b)) {}
    operator int() const { return value; }
};

std::bitset<cayley(98, -23)> s; // 等同于 bitset<10133>
```
因为成员`value`是`totally constant`的，在构造函数中通过两次调用常值函数进行初始化。换句话说，根据该提案的一般逻辑，此代码可以大致转换为以下形式（将变量和函数移到结构体之外）：
```cpp
// 模拟cayley::cayley(98, -23)的构造函数调用和operator int()
const int cayley_98_m23_value = square(98) + square(-23);

int cayley_98_m23_operator_int() { return cayley_98_m23_value; }

// 创建bitset
std::bitset<cayley_98_m23_operator_int()> s; // 等同于 bitset<10133>
```

**与变量一样，程序员无法确定函数是否为常值函数。**

*提案通常不会深入到编译器实现它们的细节。上述提案表示，实现它不应该有任何困难 - 只需要稍微改变大多数编译器中存在的常量折叠即可。然而，提案与编译器实现密切相关。如果提案无法在合理时间内实现，很可能不会被采纳。从后来的视角来看，许多大的提案最后被分成了多个小的提案逐步实现*


# 2006-2007：当一切浮出水面
幸运的是，三年后，这个提案的后续修订版 [N2235](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2007/n2235.pdf) 认识到了过多的隐含性是不好的。在问题列表中加入了对初始化控制的不可能性：

```cpp
struct S
{
    static const int size;
};

const int limit = 2 * S::size;                 // 动态初始化
const int S::size = 256;                       // 常量表达式初始化
const int z = std::numeric_limits<int>::max(); // 动态初始化
```

根据程序员的设想，`limit`应该被常量表达式初始化，但事实并非如此，因为`S::size`被定义在`limit`之后，定义的太晚了。可以通过 C++20 加入的 [constinit](https://en.cppreference.com/w/cpp/language/constinit) 来验证这一点，`constinit`保证一个变量进行常量初始化，如果不能进行常量初始化，则会编译错误。

函数也是如此。常值函数被重命名为常量表达式函数，对它们的要求保持不变。但现在，为了能够在常量表达式中使用它们，必须使用`constexpr`关键字进行声明。此外，如果函数体不是正确的`return expr`，编译将会失败。

同样，如果 constexpr 函数在任何参数下不能在常量表达式中使用，编译也会失败，并显示错误消息 constexpr function never produces a constant expression。这是为了确保程序员确切地知道该函数可能在常量表达式中使用。

建议将一些标准库的函数（如 std::numeric_limits 中的函数）标记为 constexpr，因为它们符合此标准。

变量或类成员也可以声明为 constexpr，这样如果变量不是通过常量表达式进行初始化，编译将失败。

当时决定保持新关键字与通过常量表达式隐式初始化的变量的兼容性，也就是说，此代码是有效的（预先介绍一下，使用 --std=c++11 编译时，此代码将无法通过编译，因此可能从未工作过）：

```cpp
const double mass = 9.8;
constexpr double energy = mass * square(56.6); // OK，即使 mass 没有被声明为 constexpr
extern const int side;
constexpr int area = square(side); // 错误：square(side) 不是常量表达式
```

用户自定义类的 constexpr 构造函数也合法化了。该构造函数必须具有空函数体，并用 constexpr 表达式初始化成员，如果用户创建了此类的 constexpr 对象。

尽可能将隐式构造函数标记为 constexpr。对于 constexpr 对象，析构函数必须是平凡的，因为非平凡的析构函数通常会在正在执行的程序上下文中做一些改变，而在 constexpr 计算中不存在这样的上下文。

以下是包含 constexpr 的示例类：

```cpp
struct complex 
{
    constexpr complex(double r, double i) : re(r), im(i) { }

    constexpr double real() { return re; }
    constexpr double imag() { return im; }

private:
    double re;
    double im;
};

constexpr complex I(0, 1); // OK -- 字面复数
```

在提案中，像 I 这样的对象被称为用户自定义字面值。"字面值" 是 C++ 中的基本实体。就像 "简单" 字面值（数字、字符等）立即被嵌入到汇编指令中一样，字符串字面值存储在类似 .rodata 的段中，用户定义的字面值也在其中占有一席之地。

现在 constexpr 变量不仅可以是数字和枚举，还可以是字面类型，在此提案中引入了字面类型（尚无引用类型）。字面类型是可以传递给 constexpr 函数的类型，并且/或者可以从中修改或返回。这些类型足够简单，以至于编译器可以在常量计算中支持它们。

constexpr 关键字成为了编译器需要的一个说明符，类似于类中的 override。在讨论提案后，决定不创建新的 [储存期类型](https://en.cppreference.com/w/cpp/language/storage_duration)（尽管合法），新的类型限定符，并且也决定不允许将其用于函数参数，以免使函数重载规则变得过于复杂。

# 2007 年：第一个用于数据结构的 constexpr
在这一年，提出了 [N2349 Constant Expressions in the Standard Library](https://open-std.org/JTC1/SC22/WG21/docs/papers/2007/n2349.pdf) 的提案，其中标记了一些函数和常量为constexpr，还有一些容器的函数，例如：

```cpp
template<size_t N>
class bitset
{
    // ...
    constexpr bitset();
    constexpr bitset(unsigned long);
    // ...
    constexpr size_t size();
    // ...
    constexpr bool operator[](size_t) const;
};
```

构造函数通过constant-expression初始化类的成员，其他函数内部有return expr;，适合当前的限制。

所有关于constexpr的提议中，超过一半是关于将标准库中的某些函数标记为constexpr。它们总是在constexpr的演化的下一个阶段立即出现，并且几乎总是不太有趣 - 我们将考虑语言本身的变化。

# 2008年：递归的constexpr函数
最初，提案者希望允许在 constexpr 函数中进行递归调用，但出于谨慎起见，这一做法被禁止了。然而，在审查过程中，由于措辞的变化，意外地允许了这种做法。CWG 认为递归具有足够的使用情景，因此应该允许它们。如果允许函数之间相互递归调用，还需要允许 constexpr 函数的前向声明。在 constexpr 函数中调用未定义的 constexpr 函数时，应该在需要常量表达式的上下文中进行诊断。这一点在 [N2826](https://open-std.org/JTC1/SC22/WG21/docs/papers/2009/n2826.html) 被澄清
```cpp
constexpr unsigned int factorial(unsigned int n)
{
    return n == 0 ? 1 : n * factorial(n - 1);
}
```

编译器在调用的嵌套层次上有一个限制（在clang中为512层），如果超出此限制，编译器将拒绝计算表达式。

类似的限制也存在于模板实例化中（如果我们通过模板进行编译时计算，而不是通过constexpr函数）。

# 2010年："const T&" 作为 constexpr 函数中的参数
当时，许多函数都无法被标记为 constexpr，因为它们的参数中含有引用。

```cpp
template <class T> 
constexpr const T& max(const T& a, const T& b); // 无法编译通过

constexpr pair();               // 可以使用 constexpr
pair(const T1& x, const T2& y); // 无法使用 constexpr
```
提案 [N3039 Constexpr functions with const reference parameters](https://open-std.org/JTC1/SC22/WG21/docs/papers/2010/n3039.pdf) 希望允许函数参数和返回值出现常量引用。

事实上，这是个非常巨大的改变。在此之前，常量求值中只有**值**，没有引用（指针）。只需要简单的对值进行运算就行了，引用的引入让常量求值器不得不建立一个内存模型。如果要支持`const T&`，编译器需要在编译期创建一个临时对象，然后将引用绑定到它上面。不能在编译期上下文之外访问这个临时对象，

```cpp
template <typename T>
constexpr T self(const T& a) { return *(&a); }

template <typename T>
constexpr const T* self_ptr(const T& a) { return &a; }

template <typename T>
constexpr const T& self_ref(const T& a) { return *(&a); }

template <typename T>
constexpr const T& near_ref(const T& a) { return *(&a + 1); }

constexpr auto test1 = self(123); // OK
constexpr auto test2 = self_ptr(123); // 失败，指向临时对象的指针不是常量表达式

constexpr auto test3 = self_ref(123); // OK
constexpr auto tets4 = near_ref(123); // 失败，指针越界访问
```

# 2011: static declaration in constexpr function
前文提到过，constexpr 函数只能由单个`return`语句构成。这就意味着，里面甚至不允许任何声明。但是至少有三种声明有助于编写此类函数：静态断言，类型别名声明和常量表达式初始化的局部变量
```cpp
constexpr int f(int x)
{
    const int magic = 42;
    return x + magic; // should be ok
}
```
提案 [N3268 static_assert and list-initialization in constexpr functions](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2011/n3268.htm) 希望在 constexpr 函数中支持这些静态声明。

> 大事记 C++11 发布


# (几乎) 在constexpr函数中使用任意代码

最初的 constexpr 的限制过强了，有许多简单的函数，希望能够在编译时计算，例如计算`a`的`n`次方：
```cpp
int pow(int a, int n)
{
    if (n < 0)
        throw std::range_error("negative exponent for integer power");

    if (n == 0)
        return 1;

    int sqrt = pow(a, n / 2);
    int result = sqrt * sqrt;

    if (n % 2)
        return result * a;
    
    return result;
}
```

然而，在当时（C++11），为了它能够变成 constexpr 的，程序员需要按照纯函数式风格（没有局部变量和循环）来一份新的代码

```cpp
constexpr int pow_helper(int a, int n, int sqrt) { return sqrt * sqrt * ((n % 2) ? a : 1); }

constexpr int pow(int a, int n)
{
    return (n < 0)
               ? throw std::range_error("negative exponent for integer power")
               : (n == 0)
                     ? 1
                     : pow_helper(a, n, pow(a, n / 2));
}
```

提案 [N3444 Relaxing syntactic constraints on constexpr functions](https://open-std.org/JTC1/SC22/WG21/docs/papers/2012/n3444.html) 希望进一步放宽 constexpr 函数的限制，以便能够编写任意的代码（但是仍然有一些限制）
- 允许声明具有 [literal type](https://en.cppreference.com/w/cpp/named_req/LiteralType) 类型的局部变量，并且如果它们是通过constexpr构造函数初始化的，则该构造函数必须是constexpr。这样，常量求值器可以在处理constexpr函数时，为每个具有确定参数的局部变量“后台”创建constexpr变量，并且随后使用它们来计算依赖于刚刚创建的变量的其他变量。
- 由于无法更改变量的值，因此无法使用循环（for/while/do/range-based for）。
- 禁止使用switch和goto，以防止常量求值器模拟复杂的控制流。
- 与旧的限制类似，函数必须在理论上存在一组参数，使其能够在常量表达式中使用。否则，认为该函数错误地标记为constexpr，编译将失败，并显示 `constexpr function never produces a constant expression`。

- 函数中可以声明静态变量。它们可以具有非字面类型（例如，以便从函数返回对它们的引用；这些引用本身是字面类型），但它们不能有动态初始化（即至少应该有零初始化）和非平凡析构函数。提案提供了一个示例，说明这可能很有用（在编译时获取对所需对象的引用）。

```cpp
constexpr mutex& get_mutex(bool which)
{
    static mutex m1, m2; // 非const，非字面，可以
    if (which)
        return m1;
    else
        return m2;
}
```

此外，还允许声明类型（class、enum等）并返回void。

# (Almost) Any Code in Constexpr Functions ver 2.0 Mutable Edition
然而，委员会决定，在constexpr函数中支持循环（至少for）是必不可少的。2013年，提案[N3597] Relaxing constraints on constexpr functions发布了修订版本。

实现“constexpr for”考虑了四种选项。

最远离“其余C ++”的选择是创建完全新的迭代构造，这将适用于当时当前constexpr代码的功能风格；但这实际上会创建一个新的子语言constexpr C ++功能风格。

最接近“其余C ++”的选项不是用数量取代质量，而是简单地尝试在constexpr计算中支持C ++的广泛子集（理想情况下是全部）。选择了这个选项。这对constexpr的进一步历史产生了重大影响。

因此，constexpr计算中的对象可变性成为必需。根据提案，在constexpr表达式计算中创建的对象现在可以在计算过程中进行修改，只要计算过程或对象的生存期尚未结束。

这些计算仍然在其“沙箱”中进行，外部任何内容都不会受到影响，因此理论上，使用相同参数评估constexpr表达式将产生相同的结果（不包括浮点和双精度计算中的误差）。

```cpp
constexpr int f(int a)
{
    int n = a;
    ++n; // '++n' 不是一个常量表达式
    return n * a;
}

int k = f(4); // OK，这是一个常量表达式。
              // 'f' 中的 'n' 可以被修改，因为其生存期
              // 在表达式求值期间开始。

constexpr int k2 = ++k; // 错误，不是一个常量表达式，不能修改
                        // 'k'，因为其生存期没有在
                        // 这个表达式内开始。

struct X
{
    constexpr X() : n(5)
    {
        n *= 2; // 不是一个常量表达式
    }
    int n;
};

constexpr int g()
{
    X x; // 'x' 的初始化是一个常量表达式
    return x.n;
}

constexpr int k3 = g(); 
// OK，这是一个常量表达式。
// 'x.n' 可以被修改，因为
// 'x' 的生存期在 'g()' 的求值期间开始。
```
另外，我想指出现在这样的代码也能编译通过：
```cpp


constexpr void add(X& x) { x.n++; }
constexpr int g()
{
    X x;
    add(x);
    return x.n;
}

```

现在，在constexpr函数中，C ++的重要部分正在发挥作用，并且函数内部允许constexpr计算的局部副作用。 constexpr常量计算器变得更加复杂，但仍然能够完成任务。

# 2013年：传奇的const函数和受欢迎的constexpr函数

目前，类的constexpr函数会自动标记为const函数。

在提案[N3598] constexpr member functions and implicit const中指出，类的constexpr函数不一定会隐式成为const函数。

随着constexpr计算中的可变性变得更加重要，这一点变得更加突出；但即使在此之前，它也妨碍了在constexpr和非-constexpr代码中使用相同的函数：

```cpp
struct B
{
    A a;
    constexpr B() : a() {}
    constexpr const A& getA() const /*implicit*/ { return a; }
    A& getA() { return a; } // 代码重复
};
```
有趣的是，提案提供了三个选项，其中选择了第二个：

1. 维持现状；缺点：代码重复
2. 被constexpr标记的函数不是隐式const的；缺点：破坏ABI（const是函数的mangled名称的一部分）
3. 添加新的限定符并编写constexpr A &getA() mutable { return a; }; 缺点：在声明末尾有一个新的术语