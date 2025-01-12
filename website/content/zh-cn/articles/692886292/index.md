---
title: '彻底理解 C++ ABI'
date: 2024-04-17 02:19:38
updated: 2024-12-22 19:05:57
---

Application Binary Interface，也就是我们常说的 ABI，是个让人感觉到既熟悉又陌生的概念。熟悉在哪里？讨论问题的时候经常会讨论到它，看文章的时候经常会提到它，有时候又要处理它导致的兼容性。陌生在哪里？如果有人问你什么是 ABI，你会发现你知道它是怎么一回事，但是要用严谨的语言去描述它有些困难。最后只好照着 [WIKI](https://en.wikipedia.org/wiki/Application_binary_interface) 说：ABI 就是两个二进制程序模块之间的接口。有问题吗？没有问题，作为一个概括性的描述，已经足够了。但是让人感觉到有些空洞。

这一情况在 CS 领域并不少见，笔者之前写的讨论 [反射](https://www.ykiko.me/zh-cn/articles/669358870) 的文章也遇到完全相同的情况。究其根本，CS 本来就不是一门力求严谨性的学科，很多概念都没有严格的定义，更多的是约定俗成的说法。所以我们就不去纠结定义，而是就实际出发，来看看这些所谓的二进制接口究竟有哪些，又有哪些因素会影响它们的稳定性。

## CPU & OS 

最终的可执行文件最后都是要运行在特定 CPU 上的特定操作系统的。如果 CPU 的指令集不同，那肯定会导致二进制不兼容，比如 [ARM](https://en.wikipedia.org/wiki/ARM_architecture_family) 上的程序没法**直接**运行在 x64 处理器上（除非借助一些虚拟化技术）。如果指令集兼容呢？比如 x64 处理器就兼容 x86 的指令集，那 x86 程序一定能运行在 x64 操作系统上吗？这时候就要看操作系统了，具体来说，要考虑到 **Object File Format**（目标文件格式），**Data Representation**（数据表示）， **Function Calling Convention**（函数调用约定）和 **Runtime Library**（运行时库）等因素。这几点就可以看做是操作系统层面的 ABI 规定。第四点我们后面有专门的一节来讨论，下面以 x64 平台为例，就前三点进行讨论。

> x64, x86-64, x86_64, AMD64 和 Intel 64 是一个意思，都是指 x86 指令集的 64 位版本。 

**x64 平台上主要有两套常用的 ABI**：

- 用于 64 位 Windows 操作系统上的 [Windows x64 ABI](https://learn.microsoft.com/en-us/cpp/build/x64-software-conventions?view=msvc-170)
- 用于 64 位 Linux 以及一众 UNIX-like 的操作系统上的 [x86-64 System V ABI](https://gitlab.com/x86-psABIs/x86-64-ABI)


而从一个动态库里面调用某个函数可以简单的看成下面这个三个步骤：

- 按照某种格式解析动态库
- 根据符号名从解析结果中查找函数地址
- 函数参数传递，调用函数


### Object File Format 

以何种格式解析动态库？这就是 ABI 中对 Object File Format 的规定起作用的地方了。如果你希望自己写一个链接器，那么最后生成的可执行文件就需要满足对应平台的格式要求。Windows x64 使用的可执行文件格式是 [PE32+](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format) ，也就是 PE32（Portable Executable 32-bit）格式的`64`位版本。System V ABI 使用的则是 [ELF（Executable Linkable Format）](https://en.wikipedia.org/wiki/Executable_and_Linkable_Format) 格式的可执行文件。通过使用一些 parse 库（当然感兴趣的话也可以自己写），例如 [pe-parse](https://github.com/trailofbits/pe-parse) 和 [elfio](https://github.com/serge1/ELFIO)，对实际的可执行文件进行解析，得到其中的符号表，我们便能拿到函数名与函数地址的映射关系了。

### Data Representation 

拿到函数地址之后，接下来就是怎么进行调用了。在调用之前，首先得传参对吧。那传参的时候就特别要注意 Data Representation（数据表示）表示的一致性，什么意思呢？

假设我把下面这个文件编译成动态库

```cpp
struct X{
    int a;
    int b;
};

int foo(X x){
    return x.a + x.b;
}
```

结果后续版本升级导致结构体内容发生变动了，用户代码里面看到的结构体定义变成了

```cpp
struct X{
    int a;
    int b;
    int c;
};
```

然后仍然去尝试链接旧版本代码编译出的动态库，并调用里面的函数

```cpp
int main(){
    int n = foo({1, 2, 3});
    printf("%d\n", n);
}
```

能成功吗？当然会失败了。这种错误可以看成所谓的 ODR（One Definition Rule）违反，更多的示例会在后面的章节中讨论。

上面的情况属于用户主动变更代码导致的 ODR 违反，那如果我不主动变更代码，能确保结构体布局的稳定性吗？那这就由 ABI 中 Data Representation 来进行相关保证了。例如：规定一些基础类型的大小和对齐， Windows x64 规定`long`是`32`位，而 System V 则规定`long`是`64`位。规定`struct`和`union`的大小和对齐等等。

> 注意 C 语言标准仍然是不规定 ABI 的，对于 System V ABI 来说，其主要使用 C 语言的术语和概念编写，所以可以认为提供了针对 C 语言的 ABI。而 Windows x64 ABI 在 C 和 C++ 之间并没有太过明显的界限。 

### Function Calling Convention 

接下来就到函数传参这一步了。我们知道，函数不过就是一段二进制数据，执行函数其实就是跳转到函数的入口地址，然后执行那一段代码，最后执行完了再跳转回来就行了。而传参无非就是找一块地方，存放数据，**使得调用前后都能访问到这个地方来取数据**。有哪些位置可以选择呢？主要有下面四个选项： 

- global（全局变量） 
- heap（堆） 
- register（寄存器） 
- stack（栈）


使用全局变量进行传参，听起来很魔幻，实际上平常写代码的时候经常把一些需要反复传递的参数改成全局变量，例如`config`这种的。但是，显然不是所有参数都适合使用全局变量传参，如果考虑到线程安全就要更加注意了。

使用堆进行传参，似乎也很不可思议，但其实 C++20 加入的无栈协程就把协程的状态（函数参数，局部变量）保存在堆上。不过对于普通的函数调用来说，如果每次传参都要动态内存分配，确实有些奢侈了。

所以我们主要还是考虑使用寄存器和栈进行传参。多一种选择总是好的，但是在这里并不好。如果调用方觉得应该使用寄存器传参，于是把参数存到寄存器里面去了。而被调用方觉得应该使用栈传参，所以取数据的时候是从栈里面取的。不一致就出现了，很可能从栈里面独到的就是垃圾值，导致代码逻辑错误，程序直接崩溃。

如何保证调用方和被调用方传参的位置一致呢？相信你已经猜到了，这就是 Function Calling Convention（函数调用约定）发挥作用的地方。 

具体来说，调用约定规定下面这些内容： 

- 函数参数传递顺序，从左到右还是从右到左？ 
- 函数参数和返回值传递的方式，通过栈还是寄存器？ 
- 哪些寄存器在调用者调用前后是保持不变的？ 
- 谁负责清理栈帧，调用者还是被调用者？ 
- 如何处理 C 语言的 [variadic](https://en.cppreference.com/w/c/variadic) 函数？
- `...`


在`32`位程序中，有很多调用约定，像什么`__cdecl`，`__stdcall`，`__fastcall`，`__thiscall`等等，当时的程序可谓是饱受兼容性之苦。而在`64`位程序中，已经基本完成统一。主要有两种调用约定，也就是 Windows x64 ABI 和 x86-64 System V ABI 分别规定的调用约定（不过并没有个正式的名字）。**需要强调的是函数传参方式只和调用约定有关，和代码优化等级无关。你也不想不同优化等级编译出来的代码，链接到一起之后跑不起来吧。**

介绍具体的规定是有些无聊的，感兴趣的读者可以自行查阅对应文档的相关小节，下面主要讨论一些比较有意思的话题。

> 注意：下面这些讨论只适用于函数调用实际发生的情况，如果函数被完全内联，函数传参这一行为并不会发生。目前 C++ 代码的内联优化主要发生在同一编译单元内（单个文件），对于跨编译单元的代码，必须要打开 LTO（Link Time Optimization）才行，跨动态库的代码目前还不能内联。 

- **小于16字节大小的结构体值传递效率比引用效率更高**


这个说法由来已久，但是我始终没有找到依据。终于，最近在研究调用约定的时候，让我找到原因了。首先如果结构体大小小于等于`8`字节，那么可以直接塞进一个`64`位寄存器里面传参，**通过寄存器传参比通过引用传参要少几次访存**，效率要高一些，没什么问题。那对于`16`字节呢？System V ABI 允许将一个`16`字节大小的结构体拆两个`8`个字节的部分，然后分别使用寄存器传递。那么在这种情况下传值确实比传引用要高一些，观察下面的 [代码](https://godbolt.org/z/5Ph34x1cK)

```cpp
#include <cstdio>

struct X {
    size_t x;
    size_t y;
};

extern void f(X);
extern void g(const X&);

int main() {
    f({1, 2}); // pass by value
    g({1, 2}); // pass by reference
}
```

最后生成的代码如下所示

```x86asm
main:
        sub     rsp, 24
        mov     edi, 1
        mov     esi, 2 
        call    f(X)
        movdqa  xmm0, XMMWORD PTR .LC0[rip]
        mov     rdi, rsp
        movaps  XMMWORD PTR [rsp], xmm0
        call    g(X const&)
        xor     eax, eax
        add     rsp, 24
        ret
.LC0:
        .quad   1
        .quad   2
```

> System V ABI 规定了前六个整形参数，依次可以使用`rdi`，`rsi`，`rdx`，`rcx`，`r8`，`r9`寄存器传递，而 Windows x64 ABI 规定了前四个整形参数，依次可以使用`rcx`，`rdx`，`r8`，`r9`寄存器传递。如果过寄存器用完了，就通过栈传递。整形参数即`char`，`short`，`int`，`long`，`long long`等基础整数类型外加指针类型。浮点参数和 SIMD 类型的参数则有专门的寄存器负责，这里不过多涉及了。 

可以发现`1`,`2`分别通过寄存器`edi`和`esi`传递给了`f`函数，而`g`则是把临时变量的地址传递给了`g`函数。但是这只是 System V ABI，对于 Windows x64 ABI 来说，**只要结构体的大小大于8字节，只能通过引用传递。**同样的代码，在 Windows 上编译的结果如下

```x86asm
main:
        sub     rsp, 56                             
        lea     rcx, QWORD PTR [rsp+32]
        mov     QWORD PTR [rsp+32], 1
        mov     QWORD PTR [rsp+40], 2
        call    void f(X)                   
        lea     rcx, QWORD PTR [rsp+32]
        mov     QWORD PTR [rsp+32], 1
        mov     QWORD PTR [rsp+40], 2
        call    void g(X const &)
        xor     eax, eax
        add     rsp, 56                        
        ret     0
```

可以看到两次函数调用产生的代码完全相同，也就是说对于 Windows x64 ABI 来说，大于`8`字节的结构体无论是通过引用传递还是值传递，生成的代码都是一样的。

- **unique_ptr 和 raw_ptr 的效率完全一致**


好吧在此之前我一直对此深信不疑，毕竟`unique_ptr`只是对裸指针简单包装一层嘛。直到看了 CPPCON 上 [There are no zero-cost abstractions](https://www.bilibili.com/video/BV1qp421y75W/?spm_id_from=333.999.0.0) 这个令人深省的 talk，才意识到完全是我想当然了。这里不谈异常导致的额外开销（析构函数导致编译器必须额外生成清理栈帧的代码），仅仅讨论一个 C++ 对象（小于`8`字节）能使用寄存器传参吗？对于一个完全 [trivial](https://en.cppreference.com/w/cpp/language/classes#Trivial_class) 的类型来说，是没问题的，它表现得和一个 C 语言的结构体几乎完全一样。不过不满足呢？

比如自定义了拷贝构造函数，还能放寄存器里面吗？其实从逻辑上就不能，为什么呢？我们知道，C++ 是允许我们对函数参数取地址的，那如果参数是整形，那么它通过寄存器传参，那取地址的结果哪里来的呢？实验一下，就知道了

```cpp
#include <cstdio>

extern void f(int&);

int g(int x) {
    f(x);
    return x;
}
```

生成的对应汇编如下

```x86asm
g(int):
        sub     rsp, 24
        mov     DWORD PTR [rsp+12], edi
        lea     rdi, [rsp+12]
        call    f(int&)
        mov     eax, DWORD PTR [rsp+12]
        add     rsp, 24
        ret
```

可以发现，这里把`edi`（用于传递第一个整形参数）里面的值拷贝到了 `rsp+12` 这个地址，也就是栈上，之后把这个地址传递给了`f`。也就是说，如果一个函数参数通过寄存器传递，如果在某些情况下需要它的地址，编译器会把这个参数拷贝到栈上。**但是无论如何，用户是观察不到这些拷贝过程的，因为它们的拷贝构造函数是trivial的。不影响最终代码执行结果的任何优化都是符合 as if 原则的。**

那么如果这个对象有用户定义的拷贝构造函数，假设参数通过寄存器传递，就可能会导致额外的拷贝构造函数调用，并且用户可以观察到这个副作用。显然这是不合理的，所以不允许拥有自定义拷贝构造函数的对象通过寄存器传参，那通过栈传递呢？实际上也会遇到类似的拷贝困境。于是最终这类对象只能通过引用传递了。**注意，给拷贝构造显式标记为delete也算是自定义拷贝构造函数。**

所以对于`unique_ptr`来说，只能通过引用传递，无论你函数签名写成`void f(unique_ptr<int>)`还是`void f(unique_ptr<int>&)`，最后在传参处生成的二进制代码都是一样的。但是裸指针却可以通过寄存器安全的传递。综上所述，`unique_ptr`和裸指针的效率并不是完全一致的。

> 实际上对于一个非 trivial 的 C++ 对象，究竟能否使用寄存器传参的实际情况更复杂一些，相关的内容参考对应 ABI 中的相关小节，这里不过多描述。另外 C++ 对象如何传递这部分规定，究竟属于操作系统的 ABI 还是 C++ 编译器 ABI 这个问题也并不是很明确。 

## C++ Standard 

终于说完了操作系统层面的保证，由于偏向底层，涉及到较多汇编，对于不那么熟悉汇编的读者，读起来可能有些困难。不过接下来的内容基本就和汇编没什么关系了，可以放心阅读。

我们都知道 C++ 标准没有明确规定 ABI，但并不是完全没有规定，它对于编译器的实现是有一些要求的，例如：

- 结构体成员地址按照声明顺序 [递增](https://en.cppreference.com/w/c/language/struct#Explanation)，这保证了编译器不会对结构体成员进行重新排序
- 满足 [Standard Layout](https://en.cppreference.com/w/cpp/language/data_members#Standard-layout) 约束的结构体需要与相应的 C 结构体布局兼容
- 满足 [Trivially Copyable](https://en.cppreference.com/w/cpp/types/is_trivially_copyable) 约束的结构体可以使用`memmove`或者`memcpy`进行拷贝得到一个完全相同的全新对象
- `...`


另外，由于 C++ 一直在推出新的版本。同一份代码，我使用新标准和旧标准分别进行编译，得到的结果相同吗（不考虑使用宏控制 C++ 版本进行条件编译的影响）？这就要看 C++ 标准层面对 ABI 兼容性的保证了，事实上，C++ 标准尽可能的保证**向后兼容性**。也就是说，两段代码，使用旧标准和新标准编译出来的代码是完全一样的。

然而，也有极少数的例外，例如（我只找得到这些，欢迎评论区补充）：

- C++17 把`noexcept`作为函数类型的一部分，这会影响函数最后生成的 mangling name
- C++20 引入的`no_unique_address`，MSVC 目前仍然没直接支持，因为会导致 ABI Broken


更多时候，C++ 新版本会在加入新的语言特性的同时带来新的 ABI，而不会影响旧的代码，例如 C++23 加入的两个新特性：

### Explicit Object Parameter 

在 C++23 之前，事实上没有**合法**的手段获取一个成员函数的地址，我们唯一能做的就是获取成员指针（关于成员指针是什么，可以参考这篇 [文章](https://www.ykiko.me/zh-cn/articles/659510753) 的内容）

```cpp
struct X {
    void f(int);
};

auto p = &X::f; 
// p is a pointer to member function of X
// type of p is void (X::*)(int)
```

想要获取使用成员函数作为回调函数，只能使用 lambda 表达式包装一层

```cpp
struct X {
    void f(int);
};

using Fn = void(*)(X*, int);
Fn p = [](A* self, int x) { self->f(x); };
```

这其实很麻烦，没有任何必要，而且这层包装可能会导致额外的函数调用开销。某种程度上这算是个历史遗留问题，`32`位系统上对成员函数的调用约定有些特殊（广为人知的`thiscall`），而 C++ 中并没有调用约定相关的内容，所以搞了个成员函数指针这么个东西。旧的代码为了 ABI 兼容性已经无法改变，但是新的可以，C++23 加入了显式对象参数，我们现在可以明确`this`的传入方式了，甚至可以使用值传递

```cpp
struct X {
    // 这里的 this 只是个标记作用，为了和旧语法区分开来
    void f(this X self, int x); // pass by value
    void g(this X& self, int x); // pass by reference
};
```

被显式`this`标记的函数也可以直接获取函数地址了，就和普通的函数一样

```cpp
auto f = &X::f; // type of f is void(*)(X, int)
auto g = &X::g; // type of g is void(*)(X*, int)
```

所以新代码可以都采用这种写法，只有好处，没有坏处。

### Static Operator() 

标准库中有一些仿函数，里面什么成员都没有，只有一个`operator()`，例如`std::hash`

```cpp
template <class T>
struct hash {
    std::size_t operator()(T const& t) const;
};
```

尽管这是个空的结构体，但是由于`operator()`是成员函数，所以有一个隐式`this`参数。在非内联调用的情况下仍然需要传递一个无用的空指针。这个问题在 C++23 中得到了解决，可以直接定义`static operator()`，从而避免这个问题

```cpp
template <class T>
struct hash {
    static std::size_t operator()(T const& t);
};
```

`static`也就意味着这是个静态函数了，使用上还是和原来一样

```cpp
std::hash<int> h;
std::size_t n = h(42);
```

但这里只是拿`hash`举个例子，实际上标准库的代码为了 ABI 兼容性已经不会改动了。新代码可以使用这个特性，来避免不必要的`this`传递。

## Compiler Specific 

接下来就到了重头戏了，实现定义的部分，这部分似乎是被人诟病最多的内容了。然而事实真的如此吗？让我们一点点往下看。

### De Facto Standard 

C++ 中的一些抽象最终是要落实到实现上的，而标准有没有规定如何实现，那这部分内容就由编译器自由发挥，例如：

- name mangling 的规则（为了实现函数重载和模板函数）
- 复杂类型的布局（例如含有虚继承）
- 虚函数表的布局
- RTTI 的实现
- 异常处理 
- `...`


如果编译器对这些部分的实现不同，那么最后不同编译器编译出的二进制产物自然是互不兼容，不能混用的。

> 在上世纪`90`年代，那时候还是 C++ 发展的黄金时期，各个厂商都致力于实现自己的编译器并扩大基本盘，争夺用户。出于竞争关系，不同编译器之间使用不同的 ABI 是很常见的行为。随着时代的发展，它们中的大多数已经退出了历史舞台，要么停止更新，要么仅做维护，不再跟进 C++ 的新标准。浪潮过后，留下的只有 GCC，Clang 和 MSVC 这三大编译器。 

在今天，C++ 编译器的 ABI 已经基本得到统一，主流的 ABI 只有两套：

- Itanium C++ ABI，具有公开透明的 [文档](https://itanium-cxx-abi.github.io/cxx-abi/abi.html) 
- MSVC C++ ABI，并没有官方的文档，这里有一份非正式的 [版本](https://link.zhihu.com/?target=http://www.openrce.org/articles/files/jangrayhood.pdf)


> 尽管名为 Itanium C++ ABI，但它实际上是用于 C++ 的跨架构 ABI，除了 MSVC 之外，几乎所有的 C++ 编译器都在使用它，尽管在异常处理方面的细节略有不同。历史上，C++ 编译器都以各自的方式处理 C++ ABI。当英特尔大力推广 Itanium 时，他们希望避免不兼容问题，因此，他们为 Itanium 上的所有 C++ 供应商创建了一个标准化的 ABI。后来，由于各种原因，GCC 需要修改其内部 ABI，而且鉴于它已经支持了 Itanium ABI（为 Itanium 处理器），他们选择将 ABI 定义扩展到所有架构，而不是创建自己的 ABI。从那时起，所有主要的编译器除了 MSVC 都采用了跨架构的 Itanium ABI，并且即使 Itanium 处理器本身不再接收维护，该 ABI 仍然得到了维护。  

在 Linux 平台上，GCC 和 Clang 都使用 Itanium ABI，所以两个编译器编译出来的代码就具有互操作性，可以链接到一起并运行。而在 Windows 平台上，情况则稍微复杂些，默认的 MSVC 工具链使用自己的 ABI。但是除了 MSVC 工具链以外，还有人把 GCC 移植到 Windows 上了，也就是我们熟知的 [MinGW](https://www.mingw-w64.org/) 工具链，它使用的仍然是 Itanium ABI。这两套 ABI 互不兼容，编译出来的代码不能直接链接到一起。而 Windows 平台上的 Clang 可以通过编译选项控制使用这两种 ABI 的其中的一种。

> 注意：MinGW 既然在 Windows 上运行，那它生成的代码的调用约定自然是尽量遵守 Windows x64 ABI 的，最终生成的可执行文件格式也是 PE32+。但是它的使用的 C++ ABI 仍然是 Itanium ABI，这两者并没有必然关联。 

考虑到 C++ 巨大的 codebase，这两套 C++ ABI 已经基本稳定，不会再改动了，**所以我们现在其实可以说 C++ 编译器具有稳定的 ABI**。怎么样，是不是和网上主流的说法不同？但是事实的确就摆在这里。

> MSVC 从 [2015](https://learn.microsoft.com/en-us/cpp/porting/binary-compat-2015-2017?view=msvc-170) 的版本往后开始保证 ABI 稳定。GCC 从 3.4 开始使用 Itanium ABI 并保证 ABI 稳定。 

### Workaround 

尽管基础的 ABI 不再改变，但是升级编译器版本仍然可能会导致编译出来的库发生 ABI Broken，为什么呢？

这其实不难理解，首先编译器也是软件，只要是软件就可能有 BUG。有时候为了修复 BUG，会被迫做出一些 ABI Broken（一般会在新版本的发行介绍中详细说明）。例如 GCC 有一个编译选项 [-fabi-version](https://gcc.gnu.org/onlinedocs/gcc/C_002b_002b-Dialect-Options.html#index-fabi-version) 用于专门控制这些不同的版本，其中一些内容如下：

- 版本`7`首次出现在 G++ 4.8 中，它将`nullptr_t`视为内建类型，并修正了默认参数作用域中 Lambda 表达式的名称编码
- 版本`8`首次出现在 G++ 4.9 中，修正了带有函数 CV 限定符的函数类型的替换行为
- 版本`9`首次出现在 G++ 5.2 中，修正了`nullptr_t`的对齐方式


另外对于用户来说，也可能之前为了绕过编译器的 BUG，编写了一些特殊的代码，我们一般把这个叫做 workaround。当 BUG 被修复之后，这些 workaround 很可能起到反作用。从而导致 ABI 出现不兼容

### Important Options 

除此之外，编译器还提供了一些列选项用来控制编译器的行为，这些选项可能会影响 ABI，比如：

- -fno-strict-aliasing：关闭严格别名
- -fno-exceptions：关闭异常
- -fno-rtti：关闭 RTTI
- `...`


给不同选项编译出来的库链接到一起的时候，尤其要兼容性问题。例如你的代码关闭了严格别名，但是依赖的外部库开启了严格别名，很可能指针错误的传播，从而导致程序出错。

我最近就遇到了这种情况，我在给 LLVM 的一些函数编写 Python Wrapper，通过 [pybind11](https://github.com/pybind/pybind11)。而 pybind11 要求必须打开 RTTI，但是 LLVM 默认构建是关闭异常和 RTTI 的，所以最后代码就链接不到一块去了。一开始我是自己编译了一份开 RTTI 的 LLVM，这会导致二进制膨胀，后来发现没必要这样做。我其实没有用到 LLVM 里面类型的 RTTI 信息，只是由于写在同一个文件里面，编译器认为我用到了。于是把使用到 LLVM 部分的代码单独编译成一个动态库，再和使用 pybind11 部分的代码一起链接就解决了。

## Runtime & Library 

这一小节主要讨论的就是，一个 C++ 程序依赖的库的 ABI 稳定性。**理想情况下是，对于一个可执行程序，使用新版本的动态库替换旧版本的动态库，仍然不影响它运行。**

三大 C++ 编译器都有自己的标准库 

- MSVC 对应的是 [msvc stl](https://github.com/microsoft/STL) 
- GCC 对应的是 [libstdc++](https://github.com/gcc-mirror/gcc/tree/master/libstdc%2B%2B-v3) 
- Clang 对应的是 [libc++](https://github.com/llvm/llvm-project/tree/main/libcxx)


我们在前面提到过，C++ 标准尽量保证 ABI 向后兼容。即使是从 C++98 到 C++11 这样的大更新，旧代码的 ABI 也没有受到太大影响，导致 ABI Break Change 的措辞改变更是完全找不到。

但是对于 C++ 标准库来说情况就有些不一样了，从 C++98 到 C++11，标准库经历了一次大的 ABI Break Change。标准库中修改了对一些容器实现的要求，例如`std::string`。这导致原来广泛使用的 COW 实现不符合新标准，于是在 C++11 中不得不采用新实现。这也就导致了 C++98 和 C++11 之间的标准库 ABI Broken。不过在这之后，标准库的 ABI 一般相对稳定，各家实现也尽量保证。参考 [stl](https://learn.microsoft.com/en-us/cpp/porting/binary-compat-2015-2017?view=msvc-170)，[libstdc++](https://gcc.gnu.org/onlinedocs/libstdc++/manual/abi.html) 和 [libc++](https://libcxx.llvm.org/DesignDocs/ABIVersioning.html) 相关的页面以获取详细介绍。

另外由于 RTTI 和 Exception 一般可以关掉，所以这两项功能可能由单独的运行时库来负责，比如 MSVC 的 [vcruntime](https://docs.microsoft.com/en-us/cpp/c-runtime-library/crt-library-features?view=msvc-170) 和 libc++ 的 [libcxxabi](https://libcxxabi.llvm.org/)。

> 值得一提的是，libcxxabi 中还包含了对静态局部变量初始化的支持，涉及到的主要函数是 **cxa_guard_acquire, **cxa_guard_release。使用它们来保证静态局部变量只在运行时初始化一次，如果对具体的实现感到好奇，可以查阅相关源码。 

还有就是负责一些底层功能的运行时库，比如 [libgcc](https://gcc.gnu.org/onlinedocs/gccint/Libgcc.html) 和 [compiler-rt](https://compiler-rt.llvm.org/)。

除了标准库以外，C++ 程序一般还需要链接 C 运行时 

- 在 Windows 上，必须链接 [CRT](https://learn.microsoft.com/en-us/cpp/c-runtime-library/compatibility?view=msvc-170) 
- 在 Linux 上 取决于所使用的发行版和编译环境，可能会链接 [glibc](https://www.gnu.org/software/libc/) 或者 [musl](https://musl.libc.org/) 


C 运行时除了提供 C 标准库的实现外，还负责程序的初始化和清理。它负责调用`main`函数，并管理程序的启动和终止过程，包括执行一些必要的初始化和清理工作。对于大多数在操作系统上的软件来说，链接它是必须的。

最理想的状态自然是，升级编译器的时候把这些对应的运行时库版本也升级，避免不必要的麻烦。但是在实际项目中，依赖关系可能十分复杂，可能会引发连锁反应。

## User Code 

最后我们来谈谈用户代码自身的改变导致的 ABI 问题，如果希望将你的库以二进制形式进行分发，那么当用户量达到一定程度之后，ABI 兼容性就很重要了。

在第一小节讨论调用约定的时候，就提到过变更结构体定义导致的 ABI 不兼容问题。那如果既想要保证 ABI 兼容，又想要为以后得扩展留下空间怎么办呢？答案就是在运行时处理了

```cpp
struct X{
    size_t x;
    size_t y;
    void* reserved;
};
```

通过一个`void*`指针为以后的扩展预留空间。可以根据它来判断不同的版本，比如

```cpp
void f(X* x) {
    Reserved* r = static_cast<Reserved*>(x->reserved);
    if (r->version == ...) {
        // do something
    } else if (r->version == ...) {
        // do something else
    }
}
```

这样就能在添加新的功能的同时而不影响原有的代码。

在对外暴露接口的时候，对于函数参数中有自定义析构函数的类型，也要格外注意。假设我们要暴露`std::vector`作为返回值，例如把下面这个简单的代码编译成动态库，并且使用`\MT`选项来静态链接 Windows CRT。

```cpp
__declspec(dllexport) std::vector<int> f() {
    return {1, 2, 3};
}
```

然后我们写一个源文件，链接到刚才编译的这个动态库，调用这个函数

```cpp
#include <vector>

std::vector<int> f();

int main() {
    auto vec = f();
}
```

编译运行，发现直接崩溃了。如果关闭`\MT`重新编译一遍动态库，然后运行，发现一切正常。很奇怪，为什么依赖的动态库静态链接 CRT 会导致代码崩溃？

思考一下上面的代码不难发现，`vec`的构造实际上发生在动态库里面，而析构则是发生在`main`函数里面。更进一步，其实就是内存是在动态库里面分配的，释放是在`main`函数里面。但是每一份 CRT 都有自己的`malloc`，`free`（类似于不同进程间的内存）。**你不能把 CRT A 分配的内存交给 CRT B 释放**，这就是问题的根源。所以之后不静态链接到 CRT 就没事了，它们用的都是同一个`malloc`，`free`。不仅仅是 WIndows CRT，对于 Linux 上的 glibc 或者 musl 也是一样的。示例代码放在 [这里](https://github.com/16bit-ykiko/about-me/tree/main/code/crt-fault)，感兴趣的可以自己试试。

### extern "C" 

对于任何带有自定义析构函数的 C++ 类型都可能出现上面那种情况，**由于种种原因，构造函数和析构函数的调用跨越动态库边界，RAII 的约定被打破，导致严重的错误。**

如何解决呢？那自然是函数参数和返回值都不使用带有析构函数的类型了，只使用 POD 类型。

例如上面那个例子需要改成

```cpp
using Vec = void*;

__declspec(dllexport) Vec create_Vec() {
    return new std::vector<int>;
}

__declspec(dllexport) void destroy_Vec(Vec vec) {
    delete static_cast<std::vector<int>*>(vec);
}
```

然后使用就得这样

```cpp
using Vec = void*;

Vec create_Vec();
void destroy_Vec(Vec vec);

int main() {
    Vec vec = create_Vec();
    destroy_Vec(vec);
}
```

其实我们就是在按照 C 风格的 RAII 来进行封装。更进一步，如果想要解决 C 和 C++ 由于 mangling 不同而导致的链接问题，可以使用`extern "C"`来修饰函数

```cpp
extern "C" {
    Vec create_Vec();
    void destroy_Vec(Vec vec);
}
```

这样的话 C 语言也可以使用上述的导出函数了。

但是如果代码量很大的话，把全部的函数都封装成这样的 API 显然不太现实，那就只能把 C++ 的类型暴露在导出接口中，然后小心地管理依赖项（比如所有依赖库全都静态链接）。具体选择哪一种方式，还是要看项目大小和复杂度，然后再做定夺。

## Conclusion 

到这里，我们终于讨论完了影响 C++ 程序 ABI 的主要因素。可以清楚地看到，C++ 标准、编译器厂商和运行时库都在尽力维护 ABI 的稳定性，C++ ABI 并没有很多人说的那么不堪，那么不稳定。对于小型项目而言，带源码静态链接，几乎不会有任何的兼容性问题。对于那些历史悠久的大型项目来说，由于复杂的依赖关系，升级某些库的版本可能会导致程序崩溃。**但这并不是 C++ 的错，对于大型项目的管理，早已超出了单纯的语言层面，不能指望通过更换编程语言来解决这些问题**。实际上，学习软件工程就是在学习如何应对巨大的复杂度，如何保证复杂系统的稳定性。

文章到这就结束了，感谢您的阅读。作者水平有限，并且这篇文章内容跨度较大，如有错误欢迎评论区留言讨论。

一些其它的参考资料：

- [An Overview of ABI in Different Platforms](https://www.agner.org/optimize/calling_conventions.pdf)
- [WIndows x64 ABI](https://learn.microsoft.com/en-us/cpp/build/x64-software-conventions?view=msvc-170)
- [System V x64 ABI](https://gitlab.com/x86-psABIs/x86-64-ABI)
- [Itanium C++ ABI](https://itanium-cxx-abi.github.io/cxx-abi/abi.html)
- [MinGW x64 Software Convention](https://sourceforge.net/p/mingw-w64/wiki2/MinGW%20x64%20Software%20convention/)
- [MacOS x64 ABI](https://developer.apple.com/documentation/xcode/writing-64-bit-intel-code-for-apple-platforms)
- [ARM ABI](https://developer.arm.com/Architectures/Application%20Binary%20Interface)
- [WIndows ARM64 ABI](https://learn.microsoft.com/en-us/cpp/build/arm64-windows-abi-conventions?view=msvc-170)
- [RISCV ABI](https://d3s.mff.cuni.cz/files/teaching/nswi200/202324/doc/riscv-abi.pdf)
- [Go Internal ABI](https://go.googlesource.com/go/+/refs/heads/dev.regabi/src/cmd/compile/internal-abi.md)
