---
title: 'C++ 究竟代码膨胀在哪里？'
date: 2024-03-11 01:33:37
updated: 2024-03-13 09:59:23
---

相信读者经常能听见有人说 C++ 代码二进制膨胀严重，但是一般很少会有人指出具体的原因。在网络上一番搜索过后，发现深入讨论这个问题的文章的并不多。上面那句话更像是八股文的一部分，被口口相传，但是没什么人能说出个所以然。今天小编 ykiko 就带大家一起来探秘 C++ 代码膨胀那些事  (^ω^)

首先要讨论的是，什么叫做代码膨胀？如果一个函数被大量内联，那相比于不被内联，最终生成的可执行文件是更大了对吧。那这样算膨胀吗？我认为不算，这是我们预期范围内的，可接受的，正常行为。那反过来，不在我们预期范围内的，理论上能消除，但迫于现有的实现却没有消除的代码膨胀，我把它叫做"真正的代码膨胀"。后文所讨论的膨胀都是这个意思。

## 用 inline 标记函数会导致膨胀吗？ 

首先要明确，这里的`inline`是 C++ 中的`inline`，标准中规定的语义是，**允许一个函数的在多个源文件中定义**。被`inline`标记的函数可以直接定义在头文件中，即使被多个源文件`#include`，也不会导致链接错误，这样可以方便的支持 header-only 的库。

### 多份实例的情况 

既然可以在多个源文件中定义，那是不是就意味着每个源文件都有一份代码实例，会不会导致代码膨胀呢?

考虑如下示例，开头的注释表示文件名

```cpp
// src1.cpp
inline int add(int a, int b) {
    return a + b;
}

int g1(int a, int b) {
    return add(a, b);
}

// src2.cpp
inline int add(int a, int b) {
    return a + b;
}

int g2(int a, int b){
    return add(a, b);
}

// main.cpp
#include <cstdio>
extern int g1(int, int);
extern int g2(int, int);

int main() {
    return g1(1, 2) + g2(3, 4);
}
```

先尝试**不开优化**编译前两个文件，看看他们是不是各自保留了一份`add`函数

```bash
$ g++ -c src1.cpp -o src1.o
$ g++ -c src2.cpp -o src2.o
```

分别查看这两个文件里面的符号表

```bash
$ objdump -d src1.o | c++filt
$ objdump -d src2.o | c++filt
```

本地验证都通过上述命令直接查看符号表进行。但是为了方便展示，我会把 godbolt 对应的链接和截图放上来，它把很多影响阅读的不关键符号都省略了，看起来更加清晰。

![](https://pic4.zhimg.com/v2-0f8338487557d14a675e82276a73b9a3_r.jpg)

可以看到这两个 [源文件](https://godbolt.org/z/xoW8TTvP7) 分别保留了一份，`add`函数的实例。然后我们将它们链接成可执行文件

```bash
$ g++ main.o src1.o src2.o -o main.exe
$ objdump -d main.exe | c++filt
```

结果如下图所示

![](https://pic3.zhimg.com/v2-90853d7ae94867f68e8130b835c8f832_r.jpg)

发现链接器只保留了两份`add`实例中的一份，所以并没有**额外的代码膨胀**。并且 C++ 标准要求，内联函数在不同编译单元的定义必须相同，所以无论选哪一份代码保留都没区别。但是如果你问：万一定义不同呢？那就会导致 ODR 违反，严格意义来说算 undefined behavior，究竟保留哪一个可能就看具体实现了，甚至和链接顺序有关。关于 ODR 违反相关的内容，我最近可能会单独写一个文章介绍，这里就不说太多了。**只需要知道 C++ 标准保证 inline 函数在不同编译单元定义相同就行了**。

### 完全内联的情况 

前面我特意强调了，不打开优化，如果打开了优化会怎么样呢？仍然是上面的代码，我们尝试打开`O2`优化。最后的 [结果](https://godbolt.org/z/jfx8jrnzf) 如下图所示

![](https://pic1.zhimg.com/v2-ef6dc326331416c2a20e98a632a87150_r.jpg)

可能让人有点吃惊，打开`-O2`优化之后，`add`调用被完全内联。编译器最后连符号都没有给`add`生成，链接的时候自然也没有`add`。按照我们之前的定义来看，这种函数内联不属于代码膨胀，所以是没有**额外的**二进制膨胀开销的。

稍微偏个题，既然这两个文件都不生成`add`这个符号，那万一有别的文件引用了`add`这个符号，不就会导致编译失败吗？

考虑如下代码

```cpp
// src1.cpp
inline int add(int a, int b) {
    return a + b;
}

int g1(int a, int b) {
    return add(a, b);
}

// main.cpp
inline int add(int a, int b);

int main() {
    return g1(1, 2) + add(3, 4);
}
```

尝试编译链接上面的代码。发现不开优化可以链接通过。开了优化就会导致链接失败了。链接器会告诉你`undefined reference to add(int, int)`。**三大编译器的行为都是如此**，具体的原因上面已经解释过了，开了优化之后，编译器压根没生成`add`这个符号，链接的时候自然无法找到了。

但是我们想知道的是，这样做符合 C++ 标准吗？

三大编译器都这样，似乎没有不符合的道理。但是在 inline 那一小节并没有明确说明，而在 [One Definition Rule](https://en.cppreference.com/w/cpp/language/definition#One_Definition_Rule)  这里有如下两句话 

- For an inline function or inline variable(since C++17), a definition is required in every translation unit where it is odr-used. 
- a function is odr-used if a function call to it is made or its address is taken


两句话啥意思呢？意思就是，一个 inline 函数，如果在某个编译单元被 [odr-used](https://en.cppreference.com/w/cpp/language/definition#ODR-use) 了，那么这个编译单元必须要有该函数的定义。啥情况是 odr-used 呢？后面一句话就是在解释，如果**函数被调用**或者**取函数的地址**就算是 odr-used。

那我们看看之前的代码，在 main.cpp 中调用一个 inline 函数，但是却没有定义，所以其实是违背了 C++ 标准的约定的。到这里，算是松了一口气了。虽然有点反直觉，但是事实的确如此，三大编译器都没错！

### 其它情况 

我们这一小节主要讨论了两种情况：

- 第一种即`inline`函数在多个编译单元都有实例（生成符号），那么这时候目前主流的链接器都只会选择其中一份保留，不会有额外的代码膨胀
- 第二种情况是`inline`函数被完全内联，并且不生成符号。这时候就如同普通的函数被内联一样，不属于"额外的开销"


可能会有人觉得 C++ 优化怎么规则这么多啊。但是实际上核心的规则只有一条，那就是`as-if`原则，也就是编译器可以对代码进行任何优化，只要最后生成的代码运行效果和不优化的一样就行了。编译器绝大部分时候都是按照这个原则来进行优化的，只有少数几个例外可以不满足这个原则。上述对 inline 函数的优化也是满足这个原则的，如果不显式对 inline 函数取地址，那的确没必要保留符号。

另外， inline 虽然标准层面没有强制内联的语义了，但是实际上它会给编译器一些 hint，使得这个函数更容易被内联。这个 hint 是如何作用的呢？前面提到了，标准的措辞表明 inline 函数可以不生成符号。那相比之下，没有任何说明符限定的函数，则默认被标记为 extern ，必须要生成符号。**编译器肯定是更愿意内联可以不生成符号的函数的**。从这个角度出发，你可能会猜测 static 也会有类似的 hint 效果，实际情况的确如此。当然了，这些只是一个方面，实际上，判断函数是否被内联的计算会复杂的多。

注意：本小节，只讨论了仅被`inline`标记的函数，除此之外还有`inline static`和`inline extern`这样的组合，感兴趣的读者可以阅读官方文档或者自行尝试效果如何。

## 模板导致代码膨胀的真正原因？ 

如果有人给出 C++ 二进制膨胀的理由，那么几乎它的答案一定是模板。果真如此吗？模板究竟是怎么导致二进制膨胀的？在什么情况导致的？难道我用了就导致吗？

### 隐式实例化如同 inline 标记 

我们知道模板实例化发生在当前编译单元，实例化一份就会产生一份代码。考虑下面这个例子

```cpp
// src1.cpp
template <typename T>
int add(T a, T b) { return a + b; }

float g1() {
    return add(1, 2) + add(3.0, 4.0);
}

// src2.cpp
template <typename T>
int add(T a, T b) { return a + b; }

float g2() {
    return add(1, 2) + add(3.0, 4.0);
}

// main.cpp
extern float g1();
extern float g2();

int main() {
    return g1() + g2();
}
```

仍然不开优化，尝试编译 [编译结果](https://godbolt.org/z/aTxMsnK5n) 如下

![](https://pic4.zhimg.com/v2-5de99e270f381ff7f77f012ed72836bb_r.jpg)

可以看见就像被 inline 标记的函数那样，这两个编译单元都实例化了`add<int, int>`和`add<double, double>`，各有一份代码。然后在最终链接的时候，链接器只为每个模板实例化保留了一份代码。那我们尝试打开`-O2`，然后再看看情况。[结果](https://godbolt.org/z/edEd8Tvo4) 如下

![](https://pic2.zhimg.com/v2-5e915f5cb7b7fc25e00a5f6c8ae2fa95_r.jpg)

也和 inline 标记的效果一样，编译器直接把函数内联了，然后实例化出的函数的符号都扔了。那这样的话，要么内联了符号都没生成，要么生成了符号，最后函数合并了。和 inline 一样，这种情况似乎没有额外的膨胀啊，那经常说的模板膨胀，究竟膨胀在哪呢？

### 显式实例化和 extern 模板 

在介绍真正膨胀的原因之前，我们先来讨论一下显式实例化。

虽然链接器最后能合并多份相同的模板实例化。但是模板定义的解析，模板实例化，以及生成最终的二进制代码和链接器去除重复代码，这些都要编译时间的啊。有些时候，我们能确定，只是使用某几种固定模板参数的实例化，比如像标准库的`basic_string`几乎只有那几种固定的类型作为模板参数，如果每次个文件用到它们，都要进行模板实例化可能会大大增长编译时间。

那我们可以像非模板函数一样，把实现放在某一个源文件，其它文件引用这个源文件的函数吗？从上一小节的讨论来看，既然会生成符号，那应该就有办法链接到。但是不能保证一定生成啊，有什么办法保证生成符号吗？

答案就是 —— 显式实例化！

什么叫显式实例化？简单来说，如果一个模板，你直接使用。而不提前声明具体到何种类型，由编译器帮你生成声明，那就算隐式实例化。反之就叫做显式实例化。以函数模板为例，

```cpp
template <typename T>
void f(T a, T b) { return a + b; }

template void f<int>(int, int); // 显式实例化 f<int> 定义

void g()
{
    f(1, 2); // 调用之前显式实例化的 f<int>
    f(1.0, 2.0); // 隐式实例化 f<double>
}
```

相信还是很好理解的，而且**显式实例化定义**的话，编译器一定会为你保留符号。那接下来就是外部如何链接到这个显式实例化的函数了，有两种办法

一种是，直接显式实例化一个函数声明

```cpp
template <typename T>
void f(T a, T b);

template void f<int>(int, int); // 显式实例化 f<int> 仅声明
```

另一种是直接使用`extern`关键字实例化一个定义

```cpp
template <typename T>
void f(T a, T b){ return a + b; }

extern template void f<int>(int, int); // 显式实例化 f<int> 声明
// 注意不加 extern 就会显式实例化一个定义了
```

这两种都能正确引用到上面那个函数`f`，这样就可以调用其它文件的模板实例化了！

### 真正的模板膨胀开销 

接下来是最重要的部分了，我们将会介绍模板膨胀的真正原因。由于一些历史遗留问题，C++ 中`char`,`unsigned char`,`signed char`三种类型永远互不相同

```cpp
static_assert(!std::is_same_v<char, unsigned char>);
static_assert(!std::is_same_v<char, signed char>);
static_assert(!std::is_same_v<unsigned char, signed char>);
```

但是如果落实到到编译器最终实现上来，`char`要么`signed`，要么`unsigned`。假设我们编写一个模板函数

```cpp
template <typename T>
void f(T a, T b){ return a + b; }

void g()
{
    f<char>('a', 'a');
    f<unsigned char>('a', 'a');
    f<signed char>('a', 'a');
}
```

实例化三种类型的函数模板，那么其中必然有两个实例化是相同的代码。编译器会把函数类型不同，但是最后生成的二进制代码相同的两个函数合并吗？尝试一下，[结果](https://godbolt.org/z/KncEh3z5n) 如下

![](https://pic3.zhimg.com/v2-5c57236015036328a7e0f321aadf513a_r.jpg)

可以看到这里生成了两个完全一样的函数，但是并没有合并。当然，如果我们打开`-O2`优化，这样短的函数就会被内联掉了，也不会生成最终符号。就和第一小节说的那样，也就没有所谓的"模板膨胀开销"。实际代码编写中有很多这样的短小的模板函数，比如`vector`这种容器的`end`,`begin`,`operator[]`等等，它们大概率会被完全内联，从而没有"额外的膨胀"开销。

现在问题来了，如果函数没被没有内联呢？假设模板函数比较复杂，函数体较大。为了方便演示，我们暂时使用 GCC 的一个 attribute `[[gnu::noinline]]`来实现这种效果，然后打开 O2，再次编译上面的 [代码](https://godbolt.org/z/Exff5cnfj)

![](https://pic3.zhimg.com/v2-37da15bf141999c1bc8d6f7b07575f36_r.jpg)

可以看到虽然被优化的只剩一条指令，但是编译器还是生成了三份函数。实际上，真的不被编译器内联的函数体积可能比较大，情况可能比这个“伪装的大函数”糟糕的多。于是，这样的话就产生了所谓的"模板膨胀"。**本来能合并的代码却没有合并，这就是真正的模板膨胀开销所在**。

如果非常希望编译器/链接器合并这些相同的二进制代码怎么办呢？很遗憾，主流的工具链 ld / lld / ms linker 都不会做这种合并。目前唯一支持这个特性的链接器是 [gold](https://www.gnu.org/software/binutils/)，但是它只能用于链接 elf 格式的可执行文件，所以没法在 Windows 上面使用了。下面我展示一下：如何使用它合并相同的二进制代码

```cpp
// main.cpp
#include <cstdio>
#include <utility>

template <std::size_t I> 
struct X {
    std::size_t x;

    [[gnu::noinline]] void f() { 
        printf("X<%zu>::f() called\n", x); 
    }
};

template <std::size_t... Is> 
void call_f(std::index_sequence<Is...>) {
    ((X<Is>{Is}).f(), ...);
}

int main(int argc, char *argv[]) {
    call_f(std::make_index_sequence<100>{});
    return 0;
}
```

我这里通过模板生成了`100`个不同的类型，但是实际上它们底层都是`size_t`类型，所以进行最终编译生成的二进制代码是完全相同的。使用如下命令尝试编译它

```bash
$ g++ -O2 -ffunction-sections -fuse-ld=gold -Wl,--icf=all main.cpp -o main.o
$ objdump -d main.o | c++filt
```

使用`-fue-ld=gold`指定链接器，`-Wl,--icf=all`指定链接器选项。`icf`即意味着`identical code folding`，即相同代码折叠。因为链接器只在 section 级别上工作，所以 GCC 则需要配合开启`-ffunction-sections`，上面的编译器也可以替换成`clang` 

```bash
0000000000000740 <X<99ul>::f() [clone .isra.0]>:
 740:   48 89 fa                mov    %rdi,%rdx
 743:   48 8d 35 1a 04 00 00    lea    0x41a(%rip),%rsi
 74a:   bf 01 00 00 00          mov    $0x1,%edi
 74f:   31 c0                   xor    %eax,%eax
 751:   e9 ca fe ff ff          jmp    620 <_init+0x68>
 756:   66 2e 0f 1f 84 00 00    cs nopw 0x0(%rax,%rax,1)
 75d:   00 00 00 

0000000000000760 <void call_f<0..99>(std::integer_sequence<unsigned long, 0..99>) [clone .isra.0]>:
 760:   48 83 ec 08             sub    $0x8,%rsp
 764:   31 ff                   xor    %edi,%edi
 766:   e8 d5 ff ff ff          call   740 <X<99ul>::f() [clone .isra.0]>
 ... # 重复 98 次
 b48:   e9 f3 fb ff ff          jmp    740 <X<99ul>::f() [clone .isra.0]>
 b4d:   0f 1f 00                nopl   (%rax)
```

对输出内容进行了一些筛选，可以发现，gold 把二进制完全相同的 100 个模板函数合并成一个了，所谓的"模板膨胀"消失了。相比之下，前面那些那些不做这种合并的链接器，就自然就有额外的开销了。

但是 gold 并不是万能的，有些情况不能很好的处理。假设这 100 个函数，前`90%`的代码相同，但是最后`10%`的代码不相同，那么它就无能为力了。它只是简单的对比最终生成的二进制，然后合并完全相同的函数。那么还有其他的解决办法吗？**自动挡没有，咱们还有手动挡呢，咱写 C++ 的没什么别的擅长的，就擅长开手动挡。 **

### 手动优化模板膨胀问题 

下面以大家最常用的`vector`为例，展示一下解决模板膨胀的主要思路。前面已经提到了，像迭代器接口这样的短函数，我们是不需要去管的。我们主要来处理那些逻辑比较复杂的函数，对 vector 来说，首当其冲的就是扩容函数了

假设我们有如下`vector`代码

```cpp
template <typename T>
struct vector {
    T* m_Begin;
    T* m_End;
    T* m_Capacity;

    void grow(std::size_t n);
};
```

考虑一个`vector`扩容的朴素实现，暂不考虑异常安全

```cpp
template <typename T>
void vector<T>::grow(std::size_t n) {
    T* new_date = static_cast<T*>(::operator new(n * sizeof(T)));
    if constexpr (std::is_move_constructible_v<T>) {
        std::uninitialized_move(m_Begin, m_End, new_date);
    } else {
        std::uninitialized_copy(m_Begin, m_End, new_date);
    }
    std::destroy(m_Begin, m_End);
    ::operator delete(m_Begin);
}
```

逻辑看起来还挺简单的。但是毫无疑问，它算是一个较复杂的函数了，尤其是当对象的构造函数被内联的话，代码量也是比较大的。那如何合并呢？注意，合并模板的前提是找出不同模板实例的相同部分，如果一个函数为不同的类型生成完全不同的代码，那是没法合并的。

那对于`vector`来说，如果 T 里面的元素类型不同，扩容逻辑还能相同吗？考虑到构造函数调用，似乎没任何办法。关键点来了，这里需要介绍一个`trivially_relocatable`的概念，具体的讨论可以参考

{{< article link="zh-cn/articles/679782886" >}}

我们这里只说结果，如果一个类型是`trivially_relocatable`的，那么可以使用`memcpy`把它从旧内存移动到新内存，不需要调用构造函数了。

考虑编写如下的扩容函数

```cpp
void trivially_grow(char*& begin, char*& end, char*& capacity, std::size_t n, std::size_t size) {
    char* new_data = static_cast<char*>(::operator new(n * size));
    std::memcpy(new_data, begin, (end - begin) * size);
    ::operator delete(begin);
    begin = new_data;
    end = new_data + (end - begin);
    capacity = new_data + n;
}
```

然后将原来的`grow`实现转发到这个函数

```cpp
template <typename T>
void vector<T>::grow(std::size_t n) {
    if constexpr (is_trivially_relocatable_v<T>) {
        trivially_grow(reinterpret_cast<char*&>(m_Begin), reinterpret_cast<char*&>(m_End), 
                reinterpret_cast<char*&>(m_Capacity), n, sizeof(T));
    } else {
        // 原来的实现
    }
}
```

这样就完成了抽取公共逻辑。于是所有的`T`只要满足`trivially_relocatable`，就可以全都这共享一份代码了。而几乎所有不含有自引用的类型都符合这个条件，于是`99%`的类型都使用同一套扩容逻辑！这样的优化效果是非常显著的！实际上 LLVM 很多容器的源码，比如 `SmallVector`,`StringMap`等等，都使用了这样的技巧。另外如果你觉得上面的`reinterpret_cast`破坏了严格别名，用起来有点害怕，你可以通过继承来实现相同的效果（基类成员用`void*`），具体的代码就不展示了。

## 异常导致的代码膨胀！ 

为什么 LLVM 源码禁用异常？很多人可能会下意识的认为，原因是异常很慢，效率很低。但其实，根据 [LLVM Coding Standard](https://llvm.org/docs/CodingStandards.html#do-not-use-rtti-or-exceptions) 里面的内容，关闭异常和`RTTI`的主要目的是为了减少二进制大小。据说，打开异常和`RTTI`会导致 LLVM 的编译结果膨胀`10%-15%`，那么实际情况究竟如何？

目前主要的异常实现有两种，一种是 Itanium ABI 的实现，另一种则是 MS ABI 的实现。简单来说 MS ABI 采用运行时查找的办法，这样会导致异常在 Happy Path 执行也有的额外运行时开销，但是优点是最终生成的二进制代码相对较小。而 Itanium ABI 则是我们今天的主角，它号称零开销异常，Happy 路径没有任何额外的运行时开销。那古尔丹，代价是什么？代价就是非常严重的二进制膨胀。为什么会产生膨胀呢？简单来说，就是如果不想完全等到运行时去查找，那就得预先打表。由于异常的隐式传播特性，会导致表占用空间很大。具体实现细节非常复杂，不是本文的主题，放张图，大概感受一下

![](https://pic2.zhimg.com/v2-35106aada3a2e1e089d6aa685a2ad145_r.jpg)

那我们主要讨论什么呢？异常会导致二进制膨胀，这个没什么好怀疑的。我们主要看看如何减少异常产生的二进制膨胀，以 Itanium ABI 为例

先来看下面这段示例代码

```cpp
#include <vector>

void foo(); // 外部链接函数，可能抛出异常

void bar() {
    std::vector<int> v(12); // 拥有 non-trivial 的析构函数
    foo();
}
```

注意，这里`foo`是一个外部链接的函数，可能会抛出异常。另外就是`vector`的析构函数调用是在`foo`之后的。如果`foo`抛出异常，控制流不知道跳转到什么地方了，那么`vetcor`的析构函数可能被跳过调用了，如果编译器不做些特殊处理的话，就会导致内存泄露了。先只打开`-O2`看看程序编译的结果

```bash
bar():
        ...
        call    operator new(unsigned long)
        ...
        call    foo()
        ...
        jmp     operator delete(void*, unsigned long)
        mov     rbp, rax
        jmp     .L2
bar() [clone .cold]:
.L2:
        mov     rdi, rbx
        mov     esi, 48
        call    operator delete(void*, unsigned long)
        mov     rdi, rbp
        call    _Unwind_Resume
```

省略掉不重要的部分，和我们刚才猜的大致相同。那这个`.L2`是干嘛的呢？这个其实就是异常被`catch`处理完后会跳转到这个`L2`把之前没处理完的工作做完（这里就是析构之前未析构的对象），之后再`Resume`回到先前的位置。

我们稍微调整下代码，把`foo`调用移动到`vector`构造的前面，其它什么都不变

```bash
bar():
        sub     rsp, 8
        call    foo()
        mov     edi, 48
        call    operator new(unsigned long)
        ...
        jmp     operator delete(void*, unsigned long)
```

可以发现没有生成清理栈的代码了，很合理。原因很简单，如果`foo`抛出异常，控制流直接跳转走了，那`vector`都没构造呢，自然也不需要析构了。通过简单的调整调用顺序就减少了二进制大小！但是，只有这种特别简单的情况下，依赖关系才比较明显。如果实际抛出异常的函数很多的话，就很难分析了。

### noexcept 

先讨论 C++11 加入的这个`noexcept`。注意即使加了`noexcept`，这个函数还是可能会抛出异常的，如果该函数抛出异常，程序直接`terminate`。那你可能要问了，这玩意有啥用呢？我异常抛了，不捕获不也是`terminate`吗？

其实这个和 const 有点类似，你想改 const 变量，虽然是 undefined behavior，但是运行时随便改呀，限制不多。那你要问了， const 有什么意义？一个重要的意义是给编译器提供优化指示信息。编译器可以利用这个做 *constant folding（常量折叠）*  和 *common subexpression elimination（公共子表达式消除）* 。

`noexcept`也是类似的，它让编译器假设这个函数不会抛出异常，从而可以进行一些额外的优化。 还是第一个例子里面的代码为例，唯一的改变是把`foo`函数声明为了`noexcept`，然后再次编译

```bash
bar():
        push    rbx
        mov     edi, 48
        call    operator new(unsigned long)
        ...
        call    foo()
        ...
        jmp     operator delete(void*, unsigned long)
```

可以发现，用于异常处理的代码路径，同样没有了，这就是`noexpect`的功劳。 

### fno-exceptions 

终于讲到重头戏了：`-fno-exceptions`，注意这个选项非标准。但是三大编译器都有提供，不过具体的实现效果有些许差异。好像并没有十分详细的文档，我仅凭经验说一下 GCC 相关的，对于 GCC 来说，该选项会禁止用户的代码里面使用`try`,`catch`,`throw`等关键字，如果使用则导致编译错误。但是特别的，允许使用标准库。如果异常被抛出，就和`noexcept`一样，程序直接`terminate`。所以如果打开了这个选项，GCC 会默认假设所有函数不会抛出异常。

仍然是上面的例子，我们尝试打开`-fno-exceptions`，然后再次编译

```bash
bar():
        push    rbx
        mov     edi, 48
        call    operator new(unsigned long)
        ...
        call    foo()
        ...
        jmp     operator delete(void*, unsigned long)
```

可以发现和`noexcept`产生的效果类似，它们都会让编译器假设某个函数不会抛出异常，从而不需要生成清理栈的额外代码,达到减少程序二进制大小的效果。

---

这篇文章涉及到的话题跨度有点大，某些地方有错误在所难免，欢迎评论区讨论交流   (^ω^)