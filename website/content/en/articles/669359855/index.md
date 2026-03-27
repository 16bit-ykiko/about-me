---
series:
  - Reflection
series_order: 4
title: Various approaches to code generation
date: "2023-11-29 01:14:16"
updated: "2024-11-30 10:01:14"
zhihu_article_id: "669359855"
zhihu_url: https://zhuanlan.zhihu.com/p/669359855
zhihu_column_id: c_1707545619290316800
zhihu_column_title: 编程语言中的反射
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

## Introduction

Let's take a recent requirement as an introduction. We all know that Markdown can use `lang` to fill in code blocks and supports code highlighting. However, I wanted to support my own custom code highlighting rules and encountered the following problems:

- Some websites render Markdown statically and cannot run scripts, so it's impossible to directly call those Javascript code highlighting libraries. For example, how Markdown files are rendered on Github.
- Which languages are supported is generally determined by the rendering engine. For example, Github's rendering support is different from that of [another engine, implied]. If you want to write extensions for different rendering engines, you'd have to write one for each, which is too much work, and there's very little related documentation.

Is there really no way? Well, there is a way. Fortunately, most engines support direct use of HTML rules, such such as `<code>` for rendering.

```html
<code style="color: #5C6370;font-style: italic;">
  # this a variable named &#x27;a&#x27;
</code>
```

This provides us with the possibility of adding custom styles. But we can't manually write this kind of code in our Markdown source files. If a statement has three different colors, and it's a statement like `let a = 3;`, it means we'd have to write three different `<span>` tags for just one line. It's very difficult to write and hard to maintain later.

In fact, we can do this: read the Markdown source file, which is written according to normal Markdown syntax. Then, when we read it and encounter `lang`, we extract the text, hand it over to a rendering library (I chose `highlight.js`) to render it into DOM text. Then, we replace the original text and output it separately into a new folder. For example, if the original folder is `src`, the new one is `out`. This way, the source file doesn't need any modification, and the content in the `out` folder is what actually gets rendered. Every time we modify the source file, we just run this program to perform the conversion.

## What is Code Generation?

The case above is actually a typical example of solving a problem using "code generation". So, what exactly is code generation? This is also a very broad term. Generally speaking,

> Code generation refers to the process of using computer programs to generate other programs or code.

This includes, but is not limited to:

- **Compilers generating target code:** This is the most typical example, where a compiler translates source code written in a high-level programming language into machine-executable target code.
- **Generating code using configuration files or DSLs:** Actual code is generated through specific configuration files or Domain-Specific Languages (DSLs). An example is using XML configuration files to define a UI interface and then generating the corresponding code.
- **Language built-in features generating code:** Some programming languages have built-in features, such as macros, generics, etc., that can generate code at compile time or runtime. Such mechanisms can improve code flexibility and reusability.
- **External code generators:** Some frameworks or libraries use external code generators to create the required code. For example, the Qt framework uses the Meta-Object Compiler (MOC) to process the meta-object system and generate code related to signals and slots.

Below are some specific examples for these points:

## Compile-time Code Generation

### Macros

C language's `macro` is one of the most classic and simplest compile-time code generation techniques. It's pure text replacement. For example, if we want to repeat the string `"Hello World"` 100 times. What should we do? Obviously, we don't want to manually copy and paste. Consider using macros to accomplish this task.

```c
#define REPEAT(x) (REPEAT1(x) REPEAT1(x) REPEAT1(x) REPEAT1(x) REPEAT1(x))
#define REPEAT1(x) REPEAT2(x) REPEAT2(x) REPEAT2(x) REPEAT2(x) REPEAT2(x)
#define REPEAT2(x) x x x x

int main(){
    const char* str = REPEAT("Hello world ");
}
```

This primarily uses a feature in C language where `"a""b"` is equivalent to `"ab"`. Then, through macro expansion, `5*5*4` times, which is exactly one hundred, the task is easily completed. Of course, C language macros are very limited in functionality because they are essentially just token replacements and do not allow users to obtain the token stream for input analysis. Nevertheless, there are some interesting uses. If you're interested, you can read this article: [The Art of C/C++ Macro Programming](https://zhuanlan.zhihu.com/p/152354031). Of course, macros are not exclusive to C; other programming languages also have them, and they can support even stronger features. For example, Rust's macros are much more flexible than C's, mainly because Rust allows you to analyze the input Token Stream, rather than simply performing replacements. You can choose to generate different code based on different input tokens. Even more so, macros in languages like Lisp are super flexible.

### Generics/Templates

In some programming languages, **Generics** are also considered a code generation technique, generating actually different code based on different types. Of course, this is the most basic. Some programming languages also support more powerful features, such as C++'s template metaprogramming for advanced code generation. A typical case is building a function pointer table (jump table) at compile time.

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

This way, we have achieved the effect of accessing elements in a `tuple` based on a runtime `index`. The specific principle is to manually create a function pointer table and then dispatch based on the index.

### Code Generators

The two points above discuss language built-in features. However, in many scenarios, language built-in features are not flexible enough and cannot meet our needs. For example, in C++, if you want to generate entire functions and types, neither macros nor templates can achieve this.

But code is just strings in source files. Based on this idea, we can completely write a dedicated program to generate such strings. For example, write a Python code to generate the C program that prints "Hello World" 100 times.

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

Well, this generates the source file mentioned above. Of course, this is just the simplest application. Alternatively, we can use `Protocol Buffer` to automatically generate serialization and deserialization code. Or, we can obtain information from the `AST`, and even the type's meta-information is generated by the code generator. The principle of such programs is very simple: string concatenation, and its upper limit completely depends on how your code is written.

However, more often, language built-in features are more convenient to use. Using external code generators can complicate the compilation process. Nevertheless, some languages have incorporated this feature as one of their built-in characteristics, such as C#'s [code generation](https://learn.microsoft.com/en-us/dotnet/csharp/roslyn-sdk/source-generators-overview).

## Runtime Code Generation

### exec

Alright, we've talked a lot about static language features. Now let's look at sufficiently dynamic code generation. First up are features like `eval` and `exec` in languages like Python/JavaScript, which allow us to load strings directly as code and execute them at runtime.

- `eval` is a mechanism that parses a string into executable code. In Python, the `eval` function can accept a string as an argument, execute the expression within it, and return the result. This provides powerful tools for dynamic computation and code generation.

```python
result = eval("2 + 3")
print(result)  # Output: 5
```

- `exec`, unlike `eval`, can execute multiple statements, even including function and class definitions.

```python
code_block = """
def multiply(x, y):
    return x * y

result = multiply(4, 5)
"""
exec(code_block)
print(result)  # Output: 20
```

Undoubtedly, generating code at runtime merely by string concatenation can easily fulfill some demanding requirements when used in appropriate scenarios.

### Dynamic Compilation

Now, there's a question: can C language achieve the dynamic compilation features mentioned above? You might say we could implement a C language interpreter, and that would naturally do it. But in fact, there's a simpler way.

There are two main points:

- **Compile code at runtime**

If you have `gcc` installed on your computer, you can run the following two commands:

```bash
# Compile the source file into an object file
gcc -c source.c source.o

# Extract the .text section from the object file to generate a binary file
objcopy -O binary -j .text source.o source.bin
```

This way, you can obtain the binary form of the code in `source.c`. But having only the code is not enough; we need to execute it.

- **Allocate executable memory**

Code is also binary data. Couldn't we just write the code data we just obtained into a block of memory and then `jmp` to it to execute? The idea is straightforward, but unfortunately, most operating systems protect memory, and generally allocated memory is not executable. If you try to write data and then execute it, it will directly cause a segmentation fault. However, we can use `VirtualAlloc` or `mmap` to allocate a block of memory with execution permissions, then write the code into it, and execute it.

```cpp
// Windows
VirtualAlloc(NULL, size, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);

// Linux
mmap(NULL, size, PROT_READ | PROT_WRITE | PROT_EXEC, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
```

Combining these two points and making some minor adjustments, we can achieve reading code and input from the command line and then directly running and outputting the result.

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

The final effect:

```bash
.\main.exe "int f(int a, int b){ return a + b; }" 1 2
#  output: 3

.\main.exe "int f(int a, int b){ return a - b; }" 1 2
#  output: -1
```

Perfectly implemented.

## Conclusion

This article mainly introduced some basic concepts and examples of code generation, as well as some simple applications. Code generation is a very powerful technique. If we limit our perspective to only the built-in features of programming languages, many times we cannot fulfill complex requirements. If we broaden our perspective, we will unexpectedly discover a new world. This is one article in a series on reflection; welcome to read other articles in the series!
