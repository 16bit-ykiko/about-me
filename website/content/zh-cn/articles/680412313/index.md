---
title: 'C++ 中如何优雅进行 enum 到 string 的转换 ？'
date: 2024-01-29 17:03:28
updated: 2024-12-18 11:44:59
---

## 拒绝硬编码 

定义一个`enum` 

```cpp
enum Color {
    RED,
    GREEN,
    BLUE
};
```

尝试打印

```cpp
Color color = RED;
std::cout << color << std::endl;
// output => 0
```

如果需要枚举作为日志输出，我们不希望在查看日志的时候，还要人工去根据枚举值去查找对应的字符串，麻烦并且不直观。我们希望直接输出枚举值对应的字符串，比如`RED`，`GREEN`，`BLUE`。

考虑使用一个数组当`map`，将枚举值作为`key`，将字符串作为`value`，这样就可以通过枚举值直接查找到对应的字符串了

```cpp
std::string_view color_map[] = {
    "RED",
    "GREEN",
    "BLUE"
};
```

但是当枚举数量很多的时候，手写并不方便，非常繁琐。**具体表现为，如果我们想增加若干枚举定义，那字符串映射表相应的内容也需要修改，当数量达到上百个的时候，很可以会有疏漏。或者接手一个别人的项目，发现他有一大堆枚举，内容太多，手写非常耗时间。**

需要寻找解决办法，能自动的进行相关的修改。在别的语言中，如 Java，C#，Python，可以轻松的通过反射实现这个功能。但是 C++ 目前并没有反射，故此路不通。目前这个问题主要有三种解决方案。

## 模板打表 

这一小节介绍的内容已经有人提前封装好了，可以直接使用 [magic enum](https://github.com/Neargye/magic_enum) 这个库。下面主要是对这个库的原理进行解析，为了方便展示，将用 C++20 实现，实际上 C++17 就可以。

在三大主流编译器中，有一些特殊**宏变量**。GCC 和 Clang 中的`__PRETTY_FUNCTION__`，MSVC 中的`__FUNCSIG__`。这几个宏变量会在**编译期间被替换成函数的签名**，如果该函数是模板函数则会将模板实例化的信息也输出（也可以使用 C++20 加入标准的 [source_location](https://en.cppreference.com/w/cpp/utility/source_location/function_name)，它具有和这些宏类似的效果）

```cpp
template <typename T>
void print_fn(){
#if __GNUC__ || __clang__
    std::cout << __PRETTY_FUNCTION__ << std::endl;
#elif _MSC_VER
    std::cout << __FUNCSIG__ << std::endl;
#endif
}

print_fn<int>(); 
// gcc and clang => void print_fn() [with T = int]
// msvc => void __cdecl print_fn<int>(void)
```

特别的，当模板参数是枚举常量的时候，会输出枚举常量的名称

```cpp
template <auto T>
void print_fn(){
#if __GNUC__ || __clang__
    std::cout << __PRETTY_FUNCTION__ << std::endl;
#elif _MSC_VER
    std::cout << __FUNCSIG__ << std::endl;
#endif
}

enum Color {
    RED,
    GREEN,
    BLUE
};

print_fn<RED>();
// gcc and clang => void print_fn() [with auto T = RED]
// msvc => void __cdecl print_fn<RED>(void)
```

可以发现，在特定的位置出现了枚举名。通过简单的字符串裁剪，便能得到我们想要的内容了

```cpp
template<auto value>
constexpr auto enum_name(){
    std::string_view name;
#if __GNUC__ || __clang__
    name = __PRETTY_FUNCTION__;
    std::size_t start = name.find('=') + 2;
    std::size_t end = name.size() - 1;
    name = std::string_view{ name.data() + start, end - start };
    start = name.rfind("::");
#elif _MSC_VER
    name = __FUNCSIG__;
    std::size_t start = name.find('<') + 1;
    std::size_t end = name.rfind(">(");
    name = std::string_view{ name.data() + start, end - start };
    start = name.rfind("::");
#endif
    return start == std::string_view::npos ? name : std::string_view{
            name.data() + start + 2, name.size() - start - 2
    };
}
```

进行测试

```cpp
enum Color {
    RED,
    GREEN,
    BLUE
};

int main(){
    std::cout << enum_name<RED>() << std::endl;
    // output => RED
}
```

成功满足我们的需求。但是事情并没有结束，这种形式要求枚举是模板参数，那就只支持编译期常量。但是其实绝大部分时候，我们用的枚举都是运行期变量，怎么办呢？静态转动态，只要打个表就行了，考虑通过模板元编程生成一个`array`，其中每个元素就是`index`对应枚举的字符串表示。一个问题是，这个数组应该多大，这就需要我们来获取枚举项的数量了。**一种比较直接的办法是，直接在枚举中定义一对用来标记的首尾项，这样直接相减就能获取到枚举的最大数量了**。但是很多时候，我们并不能修改枚举定义，还好这里有一个小 trick 能解决这个问题

```cpp
constexpr Color color = static_cast<Color>(-1);
std::cout << enum_name<color>() << std::endl;
// output => (Color)2
```

可以发现，如果这个整数没有对应的枚举项，那么最后就不会输出对应的枚举名，而是带有括号的强制转换表达式。这样只需要判断下得到的字符串中有没有`)`就知道对应的枚举项是否存在了。递归判断就可以找出最大的枚举值了（这样查找适用范围有限，如分散枚举值，可能相对困难一点）

```cpp
template<typename T, std::size_t N = 0> 
constexpr auto enum_max(){
    constexpr auto value = static_cast<T>(N);
    if constexpr (enum_name<value>().find(")") == std::string_view::npos)
        return enum_max<T, N + 1>();
    else
        return N;
}
```

然后通过`make_index_sequence`生成一个对应的长度数组就行了

```cpp
template<typename T> requires std::is_enum_v<T>
constexpr auto enum_name(T value){
    constexpr auto num = enum_max<T>();
    constexpr auto names = []<std::size_t... Is>(std::index_sequence<Is...>){
        return std::array<std::string_view, num>{ 
            enum_name<static_cast<T>(Is)>()... 
        };
    }(std::make_index_sequence<num>{});
    return names[static_cast<std::size_t>(value)];
}
```

测试一下

```cpp
enum Color {
    RED,
    GREEN,
    BLUE
};

int main(){
    Color color = RED;
    std::cout << enum_name(color) << std::endl;
    // output => RED
}
```

更进一步可以考虑支持 bitwidth enum，也就是`RED | BLUE`这种形式的枚举，这里就不继续展开了。

这种方法的缺点很明显，通过模板实例化来打表，其实会很大的拖慢编译速度。如果`enum`中的数量较多，在一些对常量求值效率较低的编译器上，如 MSVC，可能会增加**几十秒甚至更长**的编译时间。所以一般只适用于小型枚举。优点是轻量级，开箱即用，其它的什么也不用做。

## 外部代码生成 

既然手写字符串转枚举很麻烦，那么写个脚本生成代码不就行了？的确如此，我们可以使用 libclang 的 python bind 轻松的完成这项工作。具体如何使用这个工具，可以参考 [使用 clang 工具自由的支配 C++ 代码吧](https://www.ykiko.me/zh-cn/articles/669360731)，下面只展示实现效果的代码

```python
import clang.cindex as CX

def generate_enum_to_string(enum: CX.Cursor):
    branchs = ""
    for child in enum.get_children():
        branchs += f'case {child.enum_value}: return "{child.spelling}";\n'
    code = f"""
std::string_view {enum.spelling}_to_string({enum.spelling} value) {{
    switch(value) {{
{branchs}}}}}"""
    return code

def traverse(node: CX.Cursor):
    if node.kind == CX.CursorKind.ENUM_DECL:
        print(generate_enum_to_string(node))
        return

    for child in node.get_children():
        traverse(child)

index = CX.Index.create()
tu = index.parse('main.cpp')
traverse(tu.cursor)
```

测试代码

```cpp
// main.cpp
enum Color {
    RED,
    GREEN,
    BLUE
};
```

这是最后生成的代码，可以直接生成`.cpp`文件，放在固定目录下面，然后构建之前运行一下这个脚本就行了

```cpp
std::string_view enum_to_string(Color value) {
    switch(value) {
case 0: return "RED";
case 1: return "BLUE";
case 2: return "GREEN";
}}
```

优点，非侵入式，可以用于大数量的枚举。缺点，有外部依赖，需要将代码生成加入到编译流程里面。可能会使编译流程变得很复杂。

## 宏 

上面的两种方式都是非侵入式的。也就是说，可能你拿到了一个别人的库，不能修改它的代码，只好这么做了。如果是完全由自己定义枚举呢？其实可以在定义阶段就特殊处理，以方便后续的使用。比如（代码开头的注释表示当前文件名）：

```cpp
// Color.def
#ifndef COLOR_ENUM
#define COLOR_ENUM(...)
#endif

COLOR_ENUM(RED)
COLOR_ENUM(GREEN)
COLOR_ENUM(BLUE)

#undef COLOR_ENUM
```

然后在要使用的地方，通过修改宏定义来生成代码就行了

```cpp
// Color.h
enum Color {
#define COLOR_ENUM(x) x,
#include "Color.def"
};

std::string_view color_to_string(Color value){
    switch(value){
#define COLOR_ENUM(x) case x: return #x;
#include "Color.def"
    }
}
```

这样的话，只要在`def`文件里面进行相关的增加和修改就行了。之后如果要遍历`enum`什么的，也可以直接定义一个宏来生成代码就行了，非常方便。事实上，对于大数量的枚举，有很多开源项目都采取这种方案。例如 clang 在定义`TokenKind`的时候，就是这么做的，相关的代码请参考  [Token.def](https://github.com/stuartcarnie/clang/blob/master/include/clang/Basic/TokenKinds.def)。由于 clang 要适配多种语言前端，最后总计的`TokenKind`有几百个之多。如果不这样做，进行`Token`的增加和修改会十分困难。 

## 总结 

- 非侵入式且枚举数量较少，编译速度不是很重要，那就使用模板打表（至少要求 C++17）
- 非侵入式且枚举数量较多，编译速度很重要，那就使用外部代码生成
- 侵入式，可以直接使用宏


年年月月盼反射，还是不知道什么时候才能进入标准呢。想要提前了解 C++ 静态反射的小伙伴，可以看 [C++26 静态反射提案解析](https://www.ykiko.me/zh-cn/articles/661692275)。或者还不知道反射是什么的小伙伴，可以参考这篇文章的内容：[写给 C++ 程序员的反射教程](https://www.ykiko.me/zh-cn/articles/669358870)。