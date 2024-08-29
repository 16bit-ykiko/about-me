---
title: 'C++ 中的单例模式真的“单例”吗？'
date: 2024-05-09 18:08:28
updated: 2024-05-14 14:43:35
---

**单例模式 (Singleton Pattern)** 是一种常见的设计模式，往往应用于配置系统，日志系统，数据库连接池等需要确保对象唯一性的场景。但是单例模式真的能保证单例吗？如果唯一性得不到保证会产生什么后果呢？

既然写了这篇文章，那答案肯定是否了。知乎上已经有很多相关的讨论了，比如 [C++单例模式跨 DLL 是不是就是会出问题？](https://www.zhihu.com/question/425920019/answer/2254241454) 和 [动态库和静态库混合使用下的单例模式 BUG](https://zhuanlan.zhihu.com/p/354694011)。不过大部分都是遇到问题以后，贴一下解决方案，很零散，并没有系统分析问题产生的原因。于是，我写了这篇文章来详细讨论一下这个问题。

## 明确问题 

首先我们要明确讨论的问题，以 C++11 常见的单例模式实现为例：

```cpp
class Singleton {
public:
    Singleton(const Singleton&) = delete;
    Singleton& operator=(const Singleton&) = delete;

    static Singleton& instance() {
        static Singleton instance;
        return instance;
    }

private:
    Singleton() = default;
};
```

我们将默认构造设置为`private`并且显式`delete`拷贝构造和赋值运算符，这样的话用户只能通过`instance`这个函数来获取我们预先创建好的对象，不能自己通过构造函数创建一个对象。而使用静态局部变量是为了保证这个变量的初始化线程安全。

但其实，单例对象和一个普通的全局变量并没有什么区别。在 C++ 中，它们都属于 [静态储存期 (static storage duration)](https://en.cppreference.com/w/cpp/language/storage_duration)，编译器对它们的处理是类似的（只是初始化方式上有点区别）。而所谓的单例模式，只是在语言层面通过一些手段，防止用户不小心创建多个对象。

那我们讨论的问题其实可以等价为：**C++ 中的全局变量是唯一的吗？**

## 一个定义 

首先得区分变量的声明和定义。我们都知道，头文件中一般是不能写变量定义的。否则如果这个头文件被多个源文件包含，就会出现多个定义，链接的时候就会报`multiple definition of variable`的错误。所以我们一般会在头文件中使用`extern`声明变量，然后在对应的源文件中定义变量。

那编译器是如何处理全局变量定义的呢？

假设我们定义一个全局变量

```cpp
int x = 1;
```

其实不会产生任何的指令，编译器会在这个编译单元（每个源文件）编译产物的符号表中，增加一个符号`x`。在静态储存（具体的实现可能是 bss 段或者 rdata 段等等）中给符号`x`预留`4`字节的空间。视初始化方式（[静态初始化](https://en.cppreference.com/w/cpp/language/initialization#Static_initialization) 或者 [动态初始化](https://en.cppreference.com/w/cpp/language/initialization#Dynamic_initialization)）来决定这块内存的数据如何填充。

由于只有一个定义，那么这种情况肯定是全局唯一的了。

## 多个定义 

我们都知道 C++ 并没有官方的构建系统，不同的库使用不同的构建系统，就不方便互相使用了（目前的事实标准来看是 cmake）。这个现状使得 header-only 库变得越来越流行，`include`即用，谁不喜欢呢？但是 header-only 也就意味着所有的代码都写在头文件中，如何在头文件中定义变量并且使得它能直接被多个源文件包含而不导致链接错误呢？

在 C++17 之前，并没有直接的办法。但有一些间接的办法，考虑到`inline`函数或者模板函数的定义都可以出现在多个源文件中，并且 C++ 标准保证它们具有相同的地址（相关的讨论可以参考 [C++ 究竟代码膨胀在哪里？](https://www.ykiko.me/zh-cn/articles/686296374)）。于是只需要在这些函数中定义静态局部变量，效果上就相当于在头文件中定义变量了

```cpp
inline int& x() {
    static int x = 1;
    return x;
}

template<typename T = void>
int& y() {
    static int y = 1;
    return y;
}
```

在 C++17 之后，我们可以直接使用`inline`来标记变量，使得这个变量的定义可以出现在多个源文件中。使用它，我们就可以直接在头文件中定义变量了

```cpp
inline int x = 1;
```

我们知道，把变量标记为`static`也可以使得它在多个源文件中出现定义。那`inline`和`static`有什么区别呢？关键就在于，`static`标记的变量是内部链接的，每个编译单元都有自己的一份实例，你在不同的编译单元取的地址是不一样的。而`inline`标记的变量是外部链接的，C++ 标准保证你在不同编译单元取同一个`inline`变量的地址是一样的。

## 真的单例吗 

实践是检验真理的唯一标准，我们来实验一下，C++ 标准有没有骗我们呢？

示例代码如下

```cpp
// src.cpp
#include <cstdio>
inline int x = 1;

void foo() {
    printf("addreress of x in src: %p\n", &x);
}

// main.cpp
#include <cstdio>
inline int x = 1;
extern void foo();

int main() {
    printf("addreress of x in main: %p\n", &x);
    foo();
}
```

先简单一点，把这两个源文件一起编译成一个可执行文件，在 Windows(MSVC) 上和 Linux(GCC) 上分别尝试

```bash
# Windows:
addreress of x in main: 00007FF7CF84C000
addreress of x in src: 00007FF7CF84C000
# Linux:
addreress of x in main: 0x404018
addreress of x in src: 0x404018
```

可以发现确实是相同的地址。下面我们试一下把`src.cpp`编译成动态库，`main.cpp`链接这个库，编译运行。看看是不是像很多人说的那样，一遇到动态库就不行了呢？注意在 Windows 上要显式给`foo`加上`__declspec(dllexport)`，否则动态库不会导出这个符号。

```bash
# Windows:
addreress of x in main: 00007FF72F3FC000
addreress of x in src: 00007FFC4D91C000
# Linux:
addreress of x in main: 0x404020
addreress of x in src: 0x404020
```

夭寿啦，为什么 Windows 和 Linux 的情况不一样呢？

## 符号导出 

一开始，我简单的以为是动态库默认符号导出规则的问题。因为 GCC 编译动态库的时候，会默认把所有符号导出。而 MSVC 恰恰相反，默认不导出任何符号，全部都要手动导出。显然只有一个符号被导出了，链接器才能“看见”它，然后才能合并来自不同动态库的符号。

抱着这个想法，我尝试寻找在 GCC 上自定义符号导出的手段，最终找到了 [Visibility - GCC Wiki](https://gcc.gnu.org/wiki/Visibility)。在编译的时候使用`-fvisibility=hidden`，这样的话符号就都是默认 hidden（不导出）了。然后使用`__attribute__((visibility("default")))`或者它在 C++ 的等价写法`[[gnu::visibility("default")]]`来显式标记需要导出的符号。于是我修改了代码

```cpp
// src.cpp
#include <cstdio>
inline int x = 1;

[[gnu::visibility("default")]]
void foo () {
    printf("addreress of x in src: %p\n", &x);
}

// main.cpp
#include <cstdio>
inline int x = 1;

extern void foo();

int main() {
    printf("addreress of x in main: %p\n", &x);
    foo();
}
```

注意，我只导出了`foo`用于函数调用，这两个`inline`变量都没有导出。编译运行

```bash
addreress of x in main: 0x404020
addreress of x in src: 0x7f5a45513010
```

就像我们预期的那样，地址果然不一样。这就验证了：符号被导出，是链接器合并符号的必要条件，但是并不充分。如果在 Windows 上能通过改变默认符号导出规则，使得 inline 变量具有相同的地址，那么充分性就得到验证。当我满怀激动的开始尝试，却发现事情并非这么简单。

注意到 Windows 上的 GCC（MinGW64 工具链）仍然默认导出所有符号，按照设想，变量地址应该相同。尝试结果如下

```bash
addreress of x in main: 00007ff664a68130
addreress of x in src: 00007ffef4348110
```

可以发现结果并不相同，我不理解，并认为是编译器的 BUG。转而使用 MSVC，并且发现 CMake 提供了一个 [CMAKE_WINDOWS_EXPORT_ALL_SYMBOLS](https://cmake.org/cmake/help/latest/prop_tgt/WINDOWS_EXPORT_ALL_SYMBOLS.html) 选项，打开之后会自动导出所有符号（通过 dumpbin 实现的）。遂尝试，编译运行，结果如下

```bash
addreress of x in main: 00007FF60B11C000
addreress of x in src: 00007FFEF434C000
```

哦，结果还是不同，我意识到我的猜测出问题了。但是查阅了很久资料，也没找到为什么。后来还是在 TG 的 C++ 群提问，才得到了答案。

简单来说，在 ELF 不区分符号是来自哪个`.so`的，先加载谁就用谁，所以遇到多个`inline`变量就使用第一个加载的。但是 `PE` 文件的符号表指定了某个符号从哪个`dll`引入，这样就会导致只要一个变量`dllexport`了，那么这个 dll 一定会使用自己的变量。即使多个`dll`同时`dllexport`同一个变量，也没法合并，Windows 上 dll 的格式就限制了这件事情是做不到的。

动态库链接时的符号解析问题实际上可能还要复杂的得多，还有很多其它的情况，例如通过`dlopen`等函数主动加载动态库。之后有时间的话，可能会专门写一篇文章来分析这个事情，这里就不多说了。

## 不唯一如何？ 

为什么要保证“单例”变量的唯一性呢？这里拿 C++ 标准库来举例子

我们都知道 [type_info](https://en.cppreference.com/w/cpp/types/type_info) 可以用于运行时区分不同的类型，标准库的`std::function`和`std::any`这些类型擦除的设施就依赖于它来实现。它的`constructor`和`operator=`就被`deleted`了，我们只能通过`typeid(T)`来获取对应`type_info`对象的引用，对象的创建则由编译器来负责。

怎么样，是不是完全符合单例模式呢？下一个问题是，编译器是如何判断两个`type_info`对象是否相同的呢？一个典型的实现如下

```cpp
#if _PLATFORM_SUPPORTS_UNIQUE_TYPEINFO
    bool operator==(const type_info& __rhs) const {
      return __mangled_name == __rhs.__mangled_name;
    }
#else
    bool operator==(const type_info& __rhs) const {
      return __mangled_name == __rhs.__mangled_name ||
             strcmp(__mangled_name, __rhs.__mangled_name) == 0;
    }
#endif
```

上面的代码很好理解，如果保证`type_info`的地址是唯一的，那么直接比较`__mangled_name`就行了（它是`const char*`所以是指针比较）。若不然，就先比较地址然后比较类型名。具体到三大标准库的实现：

- [libstdc++](https://github.com/gcc-mirror/gcc/blob/master/libstdc%2B%2B-v3/libsupc%2B%2B/tinfo.cc#L39) 使用`__GXX_MERGED_TYPEINFO_NAMES`来控制是否启用
- [libc++](https://github.com/llvm/llvm-project/blob/main/libcxx/include/typeinfo#L197) 使用`_LIBCPP_TYPEINFO_COMPARATION_IMPLEMENTATION`来决定采用的方式（实际上还有一种特殊的 BIT_FLAG 模式）
- msvc stl (crt/src/vcruntime/std_type_info.cpp) 由于前面提到的 Windows 上 dll 的限制，总是使用第二种方式


举这个例子的目的是，为了说明，单例变量地址的唯一性会影响我们代码的编写方式。如果不唯一我们可能被迫要书写一些代码进行防御，可能会影响性能，而如果没写的话，甚至会直接导致逻辑错误。

## 解决方案 

只提出问题可不行，得要解决，如何确保单例唯一呢？

在 Linux 上就很简单了，如果同一个变量出现在多个动态库中，只要确保这些动态库都把这个符号设置为对外可见就行了。而编译器默认的行为也就是对外可见，所以基本上不用担心这个问题。

在 Windows 上呢？非常麻烦了，必须要确保只有一个 dll 使用`dllexport`导出了这个符号，其它所有的`dll`必须要使用`dllimport`。这件事情常常不太好做，你可能写着写着就忘记，是哪个 dll 负责导出的这个符号了。怎么办呢？那就是专门用一个 dll 来管理所有的单例变量，也就是说这个 dll 负责所有`dllexport`所有的单例变量，除此之外的 dll 都只 dllimport 就行了。之后添加和修改都在这个 dll 中进行，这样就比较好管理了。

到这文章就结束了，说实话我并不确定上面的讨论有没有覆盖所有的情形。如果有错误欢迎评论区留言讨论。