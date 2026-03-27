---
title: How to elegantly convert enum to string in C++?
date: "2024-01-29 09:03:28"
updated: "2025-07-08 08:16:05"
zhihu_article_id: "680412313"
zhihu_url: https://zhuanlan.zhihu.com/p/680412313
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

## no hard code

Define an `enum`

```cpp
enum Color {
    RED,
    GREEN,
    BLUE
};
```

Try to print

```cpp
Color color = RED;
std::cout << color << std::endl;
// output => 0
```

If we need enums as log output, we don't want to manually look up the corresponding string based on the enum value when viewing logs, which is troublesome and not intuitive. We want to directly output the string corresponding to the enum value, such as `RED`, `GREEN`, `BLUE`.

Manually write a `switch` to convert enum to string

```cpp
std::string enum_to_string(Color color) {
    switch(color) {
        case Color::RED: return "RED";
        case Color::GREEN: return "GREEN";
        case Color::BLUE: return "BLUE";
    }
    return "Unknown";
}
```

However, when there are many enums, manual writing is not convenient and very tedious. **Specifically, if we want to add several enum definitions, the corresponding content in the string mapping table also needs to be modified. When the number reaches hundreds, omissions are very likely. Or if we take over someone else's project and find that they have a lot of enums, with too much content, manual writing is very time-consuming.**

We need to find a solution that can automatically make the relevant modifications. In other languages, such as Java, C#, and Python, this functionality can be easily achieved through reflection. However, C++ currently does not have reflection, so this path is blocked. Currently, there are three main solutions to this problem.

## template

The content introduced in this section has already been encapsulated by others, and you can directly use the [magic_enum](https://github.com/Neargye/magic_enum) library. The following mainly analyzes the principle of this library. For convenience of demonstration, it will be implemented with C++20, but C++17 is actually sufficient.

In the three major mainstream compilers, there are some special **macro variables**. `__PRETTY_FUNCTION__` in GCC and Clang, and `__FUNCSIG__` in MSVC. These macro variables will be **replaced with the function signature during compilation**. If the function is a template function, the template instantiation information will also be output (you can also use `source_location` added to the C++20 standard, which has a similar effect to these macros).

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

In particular, when the template parameter is an enum constant, the name of the enum constant will be output.

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

As you can see, the enum name appears in a specific position. By simple string trimming, we can get the content we want.

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

This successfully meets our needs. But the story doesn't end here; this form requires the enum to be a template parameter, which means it only supports compile-time constants. However, most of the time, the enums we use are runtime variables. What to do? To convert static to dynamic, we just need to create a lookup table. Consider generating an `array` through template metaprogramming, where each element is the string representation of the enum corresponding to its `index`. One problem is how large this array should be, which requires us to get the number of enum items. **A more direct approach is to define a pair of start and end markers directly within the enum, so that subtracting them directly gives the maximum number of enums.** However, often we cannot modify the enum definition. Fortunately, there is a small trick to solve this problem.

```cpp
constexpr Color color = static_cast<Color>(-1);
std::cout << enum_name<color>() << std::endl;
// output => (Color)2
```

As you can see, if an integer does not have a corresponding enum item, then the corresponding enum name will not be output, but rather a parenthesized cast expression. This way, we just need to check if the resulting string contains `)` to know if the corresponding enum item exists. We can recursively determine the largest enum value (this search method has limited applicability, e.g., for scattered enum values, it might be relatively difficult).

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

Then, generate a corresponding length array using `make_index_sequence`.

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

Let's test it.

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

Further, we could consider supporting bitwidth enums, i.e., enums of the form `RED | BLUE`, but we won't go into that here.

The disadvantage of this method is obvious: generating a lookup table through template instantiation can significantly slow down compilation. If the number of items in the `enum` is large, on some compilers with low constant evaluation efficiency, such as MSVC, it may increase compilation time by **tens of seconds or even longer**. Therefore, it is generally only suitable for small enums. The advantage is that it is lightweight and ready to use, requiring no other actions.

## code generation

Since manually writing string-to-enum conversions is troublesome, why not write a script to generate the code? Indeed, we can easily accomplish this using libclang's Python bindings. For details on how to use this tool, you can refer to [Use clang tools to freely control C++ code](https://www.ykiko.me/en/articles/669360731). Below, only the code demonstrating the effect is shown.

```python
import clang.cindex as CX

def generate_enum_to_string(enum: CX.Cursor):
    branchs = ""
    for child in enum.get_children():
        branchs += f'case {child.enum_value}: return "{child.spelling}";\n'
    code = f"""
std::string_view {enum.spelling}_to_string({enum.spelling} color) {{
    switch(color) {{
{branchs}
    }}
}}"""
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

This is the final generated code. You can directly generate a `.cpp` file, place it in a fixed directory, and then run this script before building.

```cpp
std::string_view enum_to_string(Color color) {
    switch(color) {
case 0: return "RED";
case 1: return "BLUE";
case 2: return "GREEN";
    }
}
```

Advantages: Non-intrusive, can be used for a large number of enums. Disadvantages: Has external dependencies, requires integrating code generation into the build process. This might make the build process very complex.

## xmacro

The above two methods are non-intrusive. That is, you might get someone else's library and cannot modify its code, so you have to do it this way. What if you define the enums yourself entirely? In fact, you can handle them specially during the definition phase to facilitate subsequent use. For example (comments at the beginning of the code indicate the current filename):

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

Then, where it needs to be used, you can generate code by modifying the macro definition.

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

This way, you only need to add and modify relevant content in the `def` file. If you need to iterate through the `enum` later, you can also directly define a macro to generate the code, which is very convenient. In fact, for a large number of enums, many open-source projects adopt this solution. For example, when Clang defines `TokenKind`, it does so. Please refer to [Token.def](https://github.com/stuartcarnie/clang/blob/master/include/clang/Basic/TokenKinds.def) for the relevant code. Since Clang needs to adapt to multiple language frontends, the total number of `TokenKind`s reaches several hundred. If this approach were not used, adding and modifying `Token`s would be extremely difficult.

## conclusion

- Non-intrusive and a small number of enums, compilation speed is not very important: use template lookup tables (requires at least C++17).
- Non-intrusive and a large number of enums, compilation speed is important: use external code generation.
- Intrusive: directly use macros.

Year after year, we await reflection, still unsure when it will enter the standard. For those interested in learning about C++ static reflection in advance, you can read [Analysis of C++26 Static Reflection Proposal](https://www.ykiko.me/en/articles/661692275). Or for those who don't know what reflection is, you can refer to this article: [Reflection Tutorial for C++ Programmers](https://www.ykiko.me/en/articles/669358870).
