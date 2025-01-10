---
title: 'How to Elegantly Convert Enum to String in C++?'
date: 2024-01-29 17:03:28
updated: 2024-12-18 11:44:59
---

## Avoid Hardcoding

Define an `enum`

```cpp
enum Color {
    RED,
    GREEN,
    BLUE
};
```

Attempt to print

```cpp
Color color = RED;
std::cout << color << std::endl;
// output => 0
```

If we need to output enums as logs, we don't want to manually look up the corresponding strings based on the enum values when reviewing the logs, as it is cumbersome and unintuitive. We hope to directly output the strings corresponding to the enum values, such as `RED`, `GREEN`, `BLUE`.

Consider using an array as a `map`, where the enum values are the `keys` and the strings are the `values`. This way, we can directly find the corresponding string through the enum value.

```cpp
std::string_view color_map[] = {
    "RED",
    "GREEN",
    "BLUE"
};
```

However, when there are many enums, writing them manually is inconvenient and very tedious. **Specifically, if we want to add several enum definitions, the corresponding content in the string mapping table also needs to be modified. When the number reaches hundreds, there may be omissions. Or, when taking over someone else's project, you might find a large number of enums, making manual writing very time-consuming.**

We need to find a solution that can automatically make the relevant modifications. In other languages like Java, C#, and Python, this functionality can be easily achieved through reflection. However, C++ currently does not have reflection, so this approach is not feasible. Currently, there are three main solutions to this problem.

## Template Table Generation

The content introduced in this section has already been encapsulated by someone else and can be directly used via the [magic enum](https://github.com/Neargye/magic_enum) library. Below is mainly an analysis of the principles of this library. For convenience, it will be implemented in C++20, although C++17 is actually sufficient.

In the three major compilers, there are some special **macro variables**. `__PRETTY_FUNCTION__` in GCC and Clang, and `__FUNCSIG__` in MSVC. These macro variables are **replaced with the function signature during compilation**. If the function is a template function, the template instantiation information will also be output (you can also use [source_location](https://en.cppreference.com/w/cpp/utility/source_location/function_name) added in C++20, which has a similar effect to these macros).

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

Specifically, when the template parameter is an enum constant, the name of the enum constant will be output.

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

It can be observed that the enum name appears at a specific position. Through simple string trimming, we can obtain the desired content.

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

Test it

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

Successfully meets our requirements. However, this is not the end. This form requires the enum to be a template parameter, meaning it only supports compile-time constants. But in most cases, we use enums as runtime variables. What to do? Convert static to dynamic by generating a table. Consider generating an `array` through template metaprogramming, where each element is the string representation of the enum corresponding to the `index`. One issue is determining the size of this array, which requires us to obtain the number of enum items. **A straightforward method is to define a pair of start and end markers in the enum, so that the maximum number of enums can be obtained by subtraction**. However, often we cannot modify the enum definition. Fortunately, there is a small trick to solve this problem.

```cpp
constexpr Color color = static_cast<Color>(-1);
std::cout << enum_name<color>() << std::endl;
// output => (Color)2
```

It can be seen that if the integer does not have a corresponding enum item, the output will not be the corresponding enum name but a cast expression with parentheses. Therefore, by checking if the obtained string contains `)`, we can determine if the corresponding enum item exists. Recursive judgment can find the maximum enum value (this method has limited applicability, such as for scattered enum values, it may be more difficult).

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

Then generate a corresponding length array through `make_index_sequence`.

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

Test it

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

Further, consider supporting bitwidth enums, such as `RED | BLUE`, which will not be expanded here.

The disadvantage of this method is obvious. Generating tables through template instantiation can significantly slow down compilation speed. If there are many enums, on compilers with low constant evaluation efficiency, such as MSVC, it may increase compilation time by **tens of seconds or even longer**. Therefore, it is generally only suitable for small enums. The advantage is that it is lightweight and ready to use without any additional work.

## External Code Generation

Since manually writing string-to-enum conversions is troublesome, why not write a script to generate the code? Indeed, we can easily accomplish this using the python bindings of libclang. For specific usage of this tool, refer to [Use Clang Tools to Freely Manipulate C++ Code](https://www.ykiko.me/zh-cn/articles/669360731). Below is only the code to demonstrate the effect.

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

Test code

```cpp
// main.cpp
enum Color {
    RED,
    GREEN,
    BLUE
};
```

This is the final generated code, which can be directly generated into a `.cpp` file, placed in a fixed directory, and then run this script before building.

```cpp
std::string_view enum_to_string(Color value) {
    switch(value) {
case 0: return "RED";
case 1: return "BLUE";
case 2: return "GREEN";
}}
```

Advantages: Non-intrusive, suitable for large numbers of enums. Disadvantages: External dependencies, need to add code generation to the build process, which may complicate the build process.

## Macros

The above two methods are non-intrusive. That is, you might get someone else's library and cannot modify its code, so you have to do it this way. What if the enums are entirely defined by yourself? You can handle them specially during the definition phase to facilitate subsequent use. For example (the comment at the beginning of the code indicates the current file name):

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

Then, where you need to use it, modify the macro definition to generate the code.

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

In this way, you only need to add and modify the relevant content in the `def` file. Later, if you need to traverse the `enum`, you can directly define a macro to generate the code, which is very convenient. In fact, for large numbers of enums, many open-source projects adopt this approach. For example, when defining `TokenKind`, clang does this. The relevant code can be found in [Token.def](https://github.com/stuartcarnie/clang/blob/master/include/clang/Basic/TokenKinds.def). Since clang needs to adapt to multiple language front-ends, the total number of `TokenKind` is in the hundreds. Without this approach, adding and modifying `Token` would be very difficult.

## Summary

- Non-intrusive and the number of enums is small, compilation speed is not very important: use template table generation (requires at least C++17).
- Non-intrusive and the number of enums is large, compilation speed is important: use external code generation.
- Intrusive: directly use macros.

Year after year, we look forward to reflection, but it's still unclear when it will enter the standard. For those who want to learn about C++ static reflection in advance, you can read [C++26 Static Reflection Proposal Analysis](https://www.ykiko.me/zh-cn/articles/661692275). Or for those who don't know what reflection is, you can refer to this article: [A Reflection Tutorial for C++ Programmers](https://www.ykiko.me/zh-cn/articles/669358870).