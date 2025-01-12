---
title: '各种姿势进行代码生成'
date: 2023-11-29 09:14:16
updated: 2024-11-30 18:01:14
series: ['Reflection']
series_order: 4
---

## 引入 

刚好拿最近的一个需求作为引入吧。我们都知道 markdown 可以用````lang````来填入代码块，并支持代码高亮。可是我想支持自己定义的代码高亮规则，遇到了如下问题：

- 有些网站对 markdown 渲染是静态的，不能运行脚本，所以没法直接调用那些 Javascript 的代码高亮库。例如 Github 上面对 markdown 文件的渲染
- 究竟支持哪些语言一般是由渲染引擎决定的，比如 Github 的渲染支持和 的所支持的就不同。如果要针对不同的渲染引擎写扩展，每个都得写一份，工作量太大了，而且相关的资料很少


那真就没有办法了吗？唉，办法还是有的，幸好大多数引擎都支持直接用 html 的规则，比如`<code>`来进行渲染

```html
<code style= "color: #5C6370;font-style: italic;">
# this a variable named &#x27;a&#x27;
</code>
```

这为我们添加自定义样式提供了可能。但是我们写 markdown 的源文件不能手写这种代码的啊。如果一个语句有三种不同颜色，如果是`let a = 3;`这样的语句，意味着光一句话我们就得写三个不同的`<span>`。非常难写，后面维护起来也不好维护，

事实上我们可以这么做，读取 markdown 的源文件，源文件就按照正常的 markdown 语法写，然后我们在读取的时候，遇到````lang````的时候，把文本提取出来，然后交给负责渲染的库渲染成 dom 文本，我选择的是`highlight.js`这个库。然后把原来的文本替换掉，单独输出在新的文件夹里，比如原来的叫文件夹叫 src，新的叫 out。这样的话源文件不需要任何修改，然后实际渲染的是 out 文件夹里面的内容就好了。每次我们更改完源文件，运行一下这个程序做一下转换就行了。

## 什么是Code Generation 

其实上面的案例就是一个典型的使用『代码生成』也即 code generation 解来决问题的案例。那究竟什么是代码生成呢？这其实也是一个含义相当广泛的词汇。一般来说

>  代码生成是指是指通过使用计算机程序来生成其他程序或代码的过程 

包括但不限于： 

- 编译器生成目标代码： 这是最典型的例子，其中编译器将高级编程语言的源代码翻译成机器可执行的目标代码
-  使用配置文件或 DSL 生成代码：通过特定的配置文件或领域特定语言 (DSL)，生成实际的代码。一个示例是使用 XML 配置文件来定义 UI 界面，然后生成相应的代码 
- 语言内建特性生成代码： 一些编程语言具有内建的特性，如宏、泛型等，可以在编译时或运行时生成代码。这样的机制可以提高代码的灵活性和重用性。 
- 外部代码生成器： 某些框架或库使用外部代码生成器来创建所需的代码。例如，Qt 框架使用元对象编译器 (MOC) 来处理元对象系统，生成与信号和槽相关的代码。


下面就这几点来举一些具体的例子：

## 编译时代码生成 

### 宏 

C 语言的 `marco`macro 就是一种最经典，也最简单的编译期代码生成技术。纯文本替换，比如我们想重复`"Hello World"`这个字符串 100 次。那怎么办呢？显然我们不想手动粘贴复制。考虑使用宏来完成这个工作

```c
#define REPEAT(x) (REPEAT1(x) REPEAT1(x) REPEAT1(x) REPEAT1(x) REPEAT1(x))
#define REPEAT1(x) REPEAT2(x) REPEAT2(x) REPEAT2(x) REPEAT2(x) REPEAT2(x)
#define REPEAT2(x) x x x x

int main(){
    const char* str = REPEAT("Hello world ");
}
```

这里主要运用了 C 语言中的一个特性就是`"a""b"`等价于`"ab"`。然后通过宏展开`5*5*4`刚好一百次，然后就轻松的完成了这个任务。 当然了`C`语言的宏由于其本质上只是 Token 替换，而且不允许使用者获取 Token 流进行输入分析，所以功能十分有限。尽管如此，还是有一些比较有意思的用法的。感兴趣的可以阅读下这篇文章[C/C++ 宏编程的艺术](https://zhuanlan.zhihu.com/p/152354031)。当然了宏可不止`C`语言有，其它的编程语言也是有的，而且还可以支持更强的特性。例如 Rust 中的宏灵活性就比`C`语言强很多，关键就在于 Rust 允许你对输入的 Token Stream 进行分析，而不是简简单单的执行替换了，你可以根据输入 Token 的不同选择生成不同的代码。更有甚者像 Lisp 中的宏就超级灵活了。

### 泛型/模板 

在一些编程语言中**泛型 (Generic) **也被看作是一种代码生成的技术，根据不同的类型生成实际不同的代码。当然这是最基础的了，一些编程语言还支持更强大的特性，比如在`C++`中还可以通过模板元编程进行一些高级的代码生成。典型的案例是在编译期打一个函数指针表（跳转表）

```cpp
template<std::size_t N, typename T, typename F>
void helper(T t, F f) { f(std::get<N>(t)); }

template<typename Tuple, typename Func>
constexpr void access(std::size_t index, Tuple&& tuple, Func&& f){
    constexpr auto length = std::tuple_size<std::decay_t<decltype(tuple)>>::value;
    using FuncType = void (*)(decltype(tuple), decltype(f));
    constexpr auto fn_table = []<std::size_t... I>(std::index_sequence<I...>){
        std::array<FuncType, length> table = { helper<I, decltype(tuple), decltype(f)>... };
        return table;
    }(std::make_index_sequence<length>{});
    return fn_table[index](std::forward<Tuple>(tuple), std::forward<Func>(f));
}

int main(){
    std::tuple a = { 1, 'a', "123" };
    auto f = [](auto&& v) { std::cout << v << std::endl; };
    std::size_t index = 0;
    access(index, a, f); // => 1
    index = 2;
    access(index, a, f); // => 123
}
```

这样我们就实现了根据运行期的`index`来访问`tuple`中的元素的效果了，具体原理就是手动打了一个函数指针表，然后根据索引来进行分派。

### 代码生成器 

上面两点说的都是语言内建的特性。然而在很多场景，语言内置的特性，不够灵活，并不能满足我们的需求。比如在`C++`中想整块整块的生成函数和类型，那么无论是宏还是模板都做不到。

但是代码就是源文件中的字符串而已，基于这一点想法。我们完全可以编写一个专门的程序用来生成这样的字符串。例如写一个`python`代码来生成上面那个`100`次`Hello World`的`C`程序

```python
s = "";
for i in range(100):
    s += '"Hello World "'

code = f"""
int main()
{{
    const char* str = {s};
}}"""

with open("hello.c", "w") as file:
    file.write(code)
```

好了，这样的话就生成了上面那个源文件。当然这只是最简单的应用。亦或者我们可以用`Protocol Buffer`来进行自动生成序列化和反序列化的代码。又或者我们可以从`AST`中获取信息，连类型的元信息都由代码生成器生成，这种程序的原理很简单，就是字符串拼接，而它的上限完全取决于你的代码是怎么写的。

但是更多时候还是语言内建的特性使用的更加方便一些，使用外部的代码生成器会让编译流程变得复杂一些。然而也有一些语言，将这个特性作为了语言内置的特性之一，比如`C#`的[code generation](https://learn.microsoft.com/en-us/dotnet/csharp/roslyn-sdk/source-generators-overview)。

## 运行期代码生成 

### exec 

好了，说了很多静态语言的特征。接下来让我们来看看足够动态的代码生成。 首先向我们走来的是`Python/JavaScript`等语言中的`eval`和`exec`等特性，这些特性允许我们在运行期直接把字符串加载为了代码并执行

- `eval`是一种将字符串解析为可执行代码的机制。在`Python`中，`eval`函数可以接受一个字符串作为参数，并执行其中的表达式，返回结果。这为动态计算和代码生成提供了强大的工具。


```python
result = eval("2 + 3")
print(result)  # 输出: 5
```

- `exec`与`eval`不同的是，`exec`可以执行多个语句，甚至包含函数和类的定义。


```python
Copy code
code_block = """
def multiply(x, y):
    return x * y

result = multiply(4, 5)
"""
exec(code_block)
print(result)  # 输出: 20
```

毫无疑问，仅仅通过字符串拼接就能在运行期生成代码，在合适的场景使用它们，可以轻松完成一些比较苛刻的需求。

### 动态编译 

现在有一个问题，`C`语言能做到上面的动态编译特性吗？当然你可能会说我们可以实现一个`C`语言的解释器，那自然不就行了。但其实其实有更简单的办法。

主要有两点：

- **运行期编译代码**


如果你的电脑上装了`gcc`，则可以通过下面运行两条命令

```bash
# 将源文件编译成目标文件
gcc -c source.c source.o 

# 将目标文件中的.text段提取出来，生成二进制文件
objcopy -O binary -j .text source.o source.bin
```

通过这样的方式就能获取`source.c`文件中代码的二进制形式了，但是光有代码还不行，我们需要执行它。

- **申请可执行内存 **


代码也是二进制数据，只要把刚才得到的代码数据写入一块内存，然后`jmp`过去执行不就行了？想法很直接，但是很遗憾，大多数操作系统对内存都是有保护的，一般的申请内存是不可执行的。如果尝试写入数据然后执行则会直接段错误。但是我们可以通过`VirtualAlloc`或者`mmap`来申请一块有执行权限内存，然后把代码写入进去，再执行就行了。

```cpp
// Windows
VirtualAlloc(NULL, size, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);

// Linux
mmap(NULL, size, PROT_READ | PROT_WRITE | PROT_EXEC, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
```

结合这两点然后稍作处理，就可以实现从命令行读取代码和输入，然后直接运行输出结果了

```cpp
#include <fstream>
#include <iostream>
#include <string>

#ifdef _WIN32
#include <Windows.h>
#define Alloc(size) VirtualAlloc(NULL, size, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE)
#elif __linux__
#include <sys/mman.h>
#define Alloc(size) mmap(NULL, size, PROT_READ | PROT_WRITE | PROT_EXEC, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0)
#endif

int main(int argc, char* argv[])
{
    std::ofstream("source.c") << argv[1];
    system("gcc -c source.c && objcopy -O binary -j .text source.o source.bin");

    std::ifstream file("source.bin", std::ios::binary);
    std::string source((std::istreambuf_iterator<char>(file)), {});

    auto p = Alloc(source.size());
    memcpy(p, source.c_str(), source.size());

    using Fn = int (*)(int, int);
    std::cout << reinterpret_cast<Fn>(p)(std::stoi(argv[2]), std::stoi(argv[3])) << std::endl;

    return 0;
}
```

最后的效果

```bash
.\main.exe "int f(int a, int b){ return a + b; }" 1 2
#  output: 3

.\main.exe "int f(int a, int b){ return a - b; }" 1 2
#  output: -1
```

完美实现

## 结束 

本文主要介绍了代码生成的一些基本概念和示例，以及一些简单的应用。代码生成是一种非常强大的技术，如果仅仅把眼光局限在编程语言内建的特性，很多时候我们无法完成一些复杂的需求，如果将眼光放宽广一些，则会意外发现新世界。这是反射系列文章中的一篇，欢迎阅读系列其它文章！