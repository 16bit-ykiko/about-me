---
title: 'Various Approaches to Code Generation'
date: 2023-11-29 09:14:16
updated: 2024-11-30 18:01:14
series: ['Reflection']
series_order: 4
---

## Introduction

Let's start with a recent requirement as an introduction. We all know that markdown can use ````lang```` to insert code blocks and supports syntax highlighting. However, I wanted to support custom syntax highlighting rules and encountered the following issues:

- Some websites render markdown statically and cannot run scripts, so it's not possible to directly call JavaScript syntax highlighting libraries. For example, rendering markdown files on Github.
- The languages supported are generally determined by the rendering engine. For instance, the languages supported by Github's rendering engine differ from others. Writing extensions for different rendering engines would require a lot of work, and there is little documentation available.

Is there really no solution? Well, there is a way. Fortunately, most engines support using HTML rules directly, such as `<code>` for rendering.

```html
<code style= "color: #5C6370;font-style: italic;">
# this a variable named &#x27;a&#x27;
</code>
```

This provides the possibility to add custom styles. However, we can't manually write such code in the markdown source file. If a statement has three different colors, such as `let a = 3;`, it means we have to write three different `<span>` tags for just one statement. It's very difficult to write and maintain.

In fact, we can do this: read the markdown source file, write the source file in normal markdown syntax, and when we encounter ````lang````, extract the text and pass it to a rendering library to render it into DOM text. I chose the `highlight.js` library. Then replace the original text and output it in a new folder, such as 'out' for the new folder and 'src' for the original. This way, the source file doesn't need any modification, and the actual rendering is done with the content in the 'out' folder. Every time we change the source file, we just need to run this program to do the conversion.

## What is Code Generation?

The above case is a typical example of using 'code generation' to solve problems. So what exactly is code generation? It is actually a very broad term. Generally speaking,

> Code generation refers to the process of using computer programs to generate other programs or code.

This includes but is not limited to:

- Compiler generating target code: This is the most typical example, where a compiler translates source code from a high-level programming language into machine-executable target code.
- Using configuration files or DSL to generate code: Generate actual code through specific configuration files or domain-specific languages (DSL). An example is using XML configuration files to define a UI interface, then generating the corresponding code.
- Language built-in features generating code: Some programming languages have built-in features such as macros, generics, etc., which can generate code at compile time or runtime. Such mechanisms can improve code flexibility and reusability.
- External code generators: Some frameworks or libraries use external code generators to create the required code. For example, the Qt framework uses the Meta-Object Compiler (MOC) to handle the meta-object system, generating code related to signals and slots.

Below are some specific examples for these points:

## Compile-time Code Generation

### Macros

The `macro` in C language is one of the most classic and simplest compile-time code generation techniques. Pure text replacement, for example, if we want to repeat the string `"Hello World"` 100 times. What should we do? Obviously, we don't want to manually copy and paste. Consider using macros to accomplish this task.

```c
#define REPEAT(x) (REPEAT1(x) REPEAT1(x) REPEAT1(x) REPEAT1(x) REPEAT1(x))
#define REPEAT1(x) REPEAT2(x) REPEAT2(x) REPEAT2(x) REPEAT2(x) REPEAT2(x)
#define REPEAT2(x) x x x x

int main(){
    const char* str = REPEAT("Hello world ");
}
```

Here, we mainly use a feature in C language where `"a""b"` is equivalent to `"ab"`. Then, through macro expansion, `5*5*4` exactly one hundred times, we easily complete this task. Of course, the macros in C language are essentially just token replacements and do not allow users to obtain the token stream for input analysis, so their functionality is very limited. Nevertheless, there are still some interesting uses. Those interested can read this article [The Art of Macro Programming in C/C++](https://zhuanlan.zhihu.com/p/152354031). Of course, macros are not unique to C language; other programming languages also have them and can support stronger features. For example, the flexibility of macros in Rust is much stronger than in C language, mainly because Rust allows you to analyze the input token stream, rather than simply performing replacements. You can generate different code based on different input tokens. Even more, macros in Lisp are super flexible.

### Generics/Templates

In some programming languages, **generics (Generic)** are also considered a code generation technique, generating actual different code based on different types. Of course, this is the most basic. Some programming languages support more powerful features, such as template metaprogramming in `C++` for some advanced code generation. A typical case is creating a function pointer table (jump table) at compile time.

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

This way, we achieve the effect of accessing elements in a `tuple` based on the runtime `index`. The specific principle is manually creating a function pointer table and dispatching based on the index.

### Code Generators

The above two points discuss language built-in features. However, in many scenarios, the built-in features of languages are not flexible enough to meet our needs. For example, in `C++`, if you want to generate functions and types in chunks, neither macros nor templates can do it.

But code is just strings in source files. Based on this idea, we can completely write a specialized program to generate such strings. For example, write a `python` code to generate the above `C` program that repeats `Hello World` 100 times.

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

This way, we generate the above source file. Of course, this is just the simplest application. Or we can use `Protocol Buffer` to automatically generate serialization and deserialization code. Or we can obtain information from the `AST`, and even the type's meta-information can be generated by the code generator. The principle of such programs is simple, just string concatenation, and their upper limit depends entirely on how your code is written.

But more often, language built-in features are more convenient to use. Using external code generators can complicate the compilation process. However, some languages have made this feature a built-in feature of the language, such as `C#`'s [code generation](https://learn.microsoft.com/en-us/dotnet/csharp/roslyn-sdk/source-generators-overview).

## Runtime Code Generation

### exec

Alright, we've talked a lot about static language features. Now let's look at some sufficiently dynamic code generation. First, let's look at features like `eval` and `exec` in languages like `Python/JavaScript`, which allow us to load strings as code and execute them at runtime.

- `eval` is a mechanism that parses strings into executable code. In `Python`, the `eval` function can take a string as a parameter and execute the expression within it, returning the result. This provides a powerful tool for dynamic computation and code generation.

```python
result = eval("2 + 3")
print(result)  # Output: 5
```

- `exec` is different from `eval` in that `exec` can execute multiple statements, even including function and class definitions.

```python
Copy code
code_block = """
def multiply(x, y):
    return x * y

result = multiply(4, 5)
"""
exec(code_block)
print(result)  # Output: 20
```

Undoubtedly, generating code at runtime through string concatenation can easily meet some demanding requirements in appropriate scenarios.

### Dynamic Compilation

Now there is a question, can `C` language achieve the above dynamic compilation features? Of course, you might say we can implement a `C` language interpreter, then naturally it can be done. But actually, there is a simpler way.

There are mainly two points:

- **Compile code at runtime**

If you have `gcc` installed on your computer, you can run the following two commands:

```bash
# Compile the source file into an object file
gcc -c source.c source.o 

# Extract the .text section from the object file to generate a binary file
objcopy -O binary -j .text source.o source.bin
```

This way, we can obtain the binary form of the code in the `source.c` file. But having the code is not enough; we need to execute it.

- **Allocate executable memory**

Code is also binary data. As long as we write the obtained code data into a block of memory and then `jmp` to execute it, it should work, right? The idea is straightforward, but unfortunately, most operating systems have memory protection, and generally allocated memory is not executable. If you try to write data and then execute it, it will directly cause a segmentation fault. But we can use `VirtualAlloc` or `mmap` to allocate a block of memory with execution permissions, write the code into it, and then execute it.

```cpp
// Windows
VirtualAlloc(NULL, size, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);

// Linux
mmap(NULL, size, PROT_READ | PROT_WRITE | PROT_EXEC, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
```

Combining these two points and making some adjustments, we can achieve reading code and input from the command line and directly running the output.

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

Perfect implementation.

## Conclusion

This article mainly introduces some basic concepts and examples of code generation, as well as some simple applications. Code generation is a very powerful technology. If we only focus on the built-in features of programming languages, we often cannot meet some complex requirements. If we broaden our perspective, we will unexpectedly discover a new world. This is one of the articles in the Reflection series, welcome to read other articles in the series!