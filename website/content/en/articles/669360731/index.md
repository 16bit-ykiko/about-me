---
title: 'Harness the Power of C++ Code with Clang Tools'
date: 2023-11-29 09:14:27
updated: 2024-11-30 18:01:57
series: ['Reflection']
series_order: 5
---

Clang is a compiler front-end for the C family of languages provided by the LLVM project. It was initially developed to replace the C front-end of the GNU Compiler Collection (GCC), aiming to offer faster compilation, better diagnostic information, and a more flexible architecture. Clang includes front-ends for C, C++, and Objective-C, designed to be embeddable in other projects. A key feature of Clang is its modular architecture, which allows developers to easily extend and customize the compiler's functionality. Clang is widely used in many projects, including LLVM itself, the development of some operating system kernels, and the implementation of compilers for some programming languages.

In addition to being used as a compiler, Clang can also be provided as a library, enabling developers to leverage the compiler's capabilities in their applications, such as source code analysis and generation. Clang can be used to obtain the Abstract Syntax Tree (AST) of C++ source files for further processing. This article will introduce how to use Clang tools.

## Installation & Usage 

Currently, Clang is divided into the following libraries and tools: libsupport, libsystem, libbasic, libast, liblex, libparse, libsema, libcodegen, librewrite, libanalysis. Since Clang itself is written in C++, the related interfaces are all in C++. However, due to the complexity and instability of C++ interfaces (for example, DLLs compiled by GCC on Windows cannot be used by MSVC, or API changes due to Clang version upgrades leading to incompatibility), the official does not recommend prioritizing the use of C++ interfaces.

In addition to C++ interfaces, the official also provides a C interface called [libclang](https://clang.llvm.org/doxygen/group__CINDEX.html), which is not only relatively simple to use but also quite stable. The only drawback is that it cannot obtain the complete C++ Abstract Syntax Tree (AST), but given that the complete syntax tree of C++ is extremely complex, often we only need a small part of the information, so this issue can usually be ignored unless you really have such a requirement.

If you want to use libclang, you need to install LLVM and Clang first. On the [LLVM Release](https://github.com/llvm/llvm-project/releases) page, there are several pre-release binary packages available for download. If you have customization needs, please refer to the [Getting Started](https://llvm.org/docs/GettingStarted.html#id4) page for manual compilation. After installation, simply link the `libclang.dll` from the `llvm/lib` directory to your program and include the `clang-c/Index.h` header file from the `llvm/include` directory to use it.

However, since C language lacks some high-level abstractions, even manipulating strings can be cumbersome. If used on a large scale, we need to encapsulate a layer in C++ ourselves. Fortunately, the official also provides a Python binding based on this C interface, namely the [clang](https://pypi.org/project/clang/) package, which makes it more convenient to use. However, the Python binding provided by the official does not package the libclang DLL, so you still need to manually configure the LLVM environment on your computer, which can be a bit troublesome. However, someone in the community has provided a packaged version on PyPI: [libclang](https://pypi.org/project/libclang/).

So if you want to use libclang to obtain the C++ syntax tree, you just need

```bash
pip install libclang
```

No additional steps are required. This article is based on this Python binding version. The C version API and the Python version API are basically identical. If you find Python performance insufficient, you can also refer to this tutorial to write C version code. Additionally, the official package does not provide type hints, so writing in Python lacks code completion and is not comfortable to use. I have added a type hint [cindex.pyi](https://github.com/16bit-ykiko/about-me/blob/main/code/cindex.pyi), which can be downloaded and placed in the same folder to enable code hints.

## Quick Start 

The example C++ source file code is as follows

```cpp
// main.cpp
struct Person {
    int age;
    const char* name;
};

int main() {
    Person person = {1, "John"};
    return 0;
}
```

The Python code to parse it is as follows

```python
import clang.cindex as CX

def traverse(node: CX.Cursor, prefix="", is_last=True):
    branch = "└──" if is_last else "├──"
    text = f"{str(node.kind).removeprefix('CursorKind.')}: {node.spelling}"

    if node.kind == CX.CursorKind.INTEGER_LITERAL:
        value = list(node.get_tokens())[0].spelling
        text = f"{text}{value}"

    print(f"{prefix}{branch} {text}")
    new_prefix = prefix + ("    " if is_last else "│   ")
    children = list(node.get_children())

    for child in children:
        traverse(child, new_prefix, child is children[-1])


index = CX.Index.create(excludeDecls=True)
tu = index.parse('main.cpp', args=['-std=c++20'])
traverse(tu.cursor)
```

The output is as follows

```bash
TRANSLATION_UNIT: main.cpp
├── STRUCT_DECL: Person
│   ├── FIELD_DECL: age
│   └── FIELD_DECL: name
└── FUNCTION_DECL: main
    └── COMPOUND_STMT:
        ├── DECL_STMT:
        │   └── VAR_DECL: person
        │       ├── TYPE_REF: struct Person
        │       └── INIT_LIST_EXPR:
        │           ├── INTEGER_LITERAL: 1
        │           └── STRING_LITERAL: "John"
        └── RETURN_STMT:
            └── INTEGER_LITERAL: 0
```

The front part is the syntax tree node type, and the back part is the node content. It can be seen that it is very clear and almost corresponds to the source code one by one.

## Basic Types 

Note, this article assumes that the reader has some understanding of syntax trees and will not introduce them in detail here. If you don't know what a syntax tree is, you can take a look at [Why C/C++ Compilers Do Not Retain Meta Information](https://16bit-ykiko.github.io/about-me/670190357). Below is an introduction to some commonly used types in cindex

### Cursor 

Equivalent to the basic node of the syntax tree, the entire syntax tree is composed of `Cursor`. The `kind` property returns a `CursorKind` type enumeration value, which represents the actual type corresponding to this node.

```python
for kind in CursorKind.get_all_kinds():
    print(kind)
```

This can print all supported node types, or you can directly view the source code. `Cursor` also has some other properties and methods for us to use, commonly used are as follows:

```python
@property
def spelling(self) -> str:

@property
def displayname(self) -> str:

@property
def mangled_name(self) -> str:
```

Get the name of the node, for example, for a variable declaration node, its `spelling` is the name of the variable. The `displayname` is the short name of the node, which is usually the same as `spelling`. But sometimes there are differences, for example, the `spelling` of a function will include the parameter types, such as `func(int)`, but its `displayname` is just `func`. The `mangled_name` is the name of the symbol after name mangling for linking.

```python
@property
def type(self) -> Type:
```

The type of the node element, for example, for a variable declaration node, its `type` is the type of the variable. Or for a field declaration node, its `type` is the type of the field. The return type is `Type`.

```python
@property
def location(self) -> SourceLocation:
```

The location information of the node, the return type is `SourceLocation`, which carries the line number, column number, file name and other information of the node in the source code.

```python
@property
def extent(self) -> SourceRange:
```

The range information of the node, the return type is `SourceRange`, composed of two `SourceLocation`, which carries the start and end positions of the node in the source code.

```python
@property
def access_specifier(self) -> AccessSpecifier:
```

The access permission of the node, the return type is `AccessSpecifier`. There are five types: `PUBLIC`, `PROTECTED`, `PRIVATE`, `NONE`, `INVALID`.

```python
def get_children(self) -> iterable[Cursor]:
```

Get all child nodes, the return type is `iterable` of `Cursor`. This function is the most commonly used, because we can traverse the entire syntax tree recursively.

```python
def get_tokens(self) -> iterable[Token]:
```

Get all `token`s representing the node, the return type is `iterable` of `Token`. `token` is the smallest unit of the syntax tree, for example, for a variable declaration node, its `token`s are `int`, `a`, `;`. This function can be used to obtain some detailed information, such as obtaining the values of integer literals and floating-point literals.

```python
def is_definition(self) -> bool:
def is_const_method(self) -> bool:
def is_converting_constructor(self) -> bool:
def is_copy_constructor(self) -> bool:
def is_default_constructor(self) -> bool:
def is_move_constructor(self) -> bool:
def is_default_method(self) -> bool:
def is_deleted_method(self) -> bool:
def is_copy_assignment_operator_method(self) -> bool:
def is_move_assignment_operator_method(self) -> bool:
def is_mutable_field(self) -> bool:
def is_pure_virtual_method(self) -> bool:
def is_static_method(self) -> bool:
def is_virtual_method(self) -> bool:
def is_abstract_record(self) -> bool:
def is_scoped_enum(self) -> bool:
```

These functions are basically self-explanatory, for example, `is_definition` is to determine whether the node is a definition, `is_const_method` is to determine whether the node is a `const` method.

### Type 

If the node has a type, it represents the type of the node. Commonly used properties are

```python
@property
def kind(self) -> TypeKind:
```

The type of the type, the return type is `TypeKind`. For example, `INT`, `FLOAT`, `POINTER`, `FUNCTIONPROTO`, etc.

```python
@property
def spelling(self) -> str:
```

The name of the type, for example, `int`, `float`, `void`, etc.

```python
def get_align(self) -> int:
def get_size(self) -> int:
def get_offset(self, fieldname: str) -> int:
```

Get the alignment, size, field offset, etc. of the type.

And some functions starting with `is`, such as `is_const_qualified`, `is_function_variadic`, `is_pod`, etc. I won't go into detail here.

### TranslationUnit 

Generally, a C++ source file represents a `TranslationUnit`, which is what we often call a compilation unit.

Commonly used are

```python
@property
def cursor(self) -> Cursor:
```

Get the root node of the `TranslationUnit`, which is the `Cursor` of type `TRANSLATION_UNIT`.

```python
@property
def spelling(self) -> str:
```

Get the file name of the `TranslationUnit`.

```python
def get_includes(self, depth: int = -1) -> iterable[FileInclusion]:
```

Get all `include`s of the `TranslationUnit`, the return type is a `list` of `FileInclusion`. Note that since the included files may contain other files, you can use the `depth` parameter to limit it. For example, if you only want to get the first layer, that is, the directly included header files, you can write it like this.

```python
index = CX.Index.create()
tu = index.parse('main.cpp', args=['-std=c++20'])
for file in tu.get_includes():
    if file.depth == 1:
        print(file.include.name)
```

This will print all directly used header files.

### Index 

An `Index` is a collection of `TranslationUnit`s, which are eventually linked together to form an executable file or library.

There is a static method `create` to create a new `Index`, and then the member method `parse` can parse a `C++` source file and return a `TranslationUnit`.

```python
def parse(self, path: str,
                args: list[str] | None = ...,
                unsaved_files: list[tuple[str, str]] | None = ...,
                options: int = ...) -> TranslationUnit:
```

`path` is the source file path, `args` is the compilation parameters, `unsaved_files` is the unsaved files, `options` are some parameters defined in `TranslationUnit.PARSE_XXX`, such as `PARSE_SKIP_FUNCTION_BODIES` and `PARSE_INCOMPLETE`. It can be used to customize the parsing process, speed up parsing, or retain macro information, etc.

## Examples 

### Namespace 

Since clang will expand all header files when parsing, the output content is too much. But we may mainly want the information of our own code, so we can use namespaces for filtering. The example is as follows:

```cpp
#include <iostream>

namespace local {
    struct Person {
        int age;
        std::string name;
    };
}
```

The parsing code is as follows

```python
import clang.cindex as CX

def traverse_my(node: CX.Cursor):
    if node.kind == CX.CursorKind.NAMESPACE:
        if node.spelling == "local":
            traverse(node) # forward to the previous function

    for child in node.get_children():
        traverse_my(child)

index = CX.Index.create()
tu = index.parse('main.cpp', args=['-std=c++20'])
traverse_my(tu.cursor)
```

Write a function to filter the namespace name, and then forward it to our previous function, so that only the content in the namespace we want will be output.

### Class & Struct 

We mainly want to get the field names, types, method names, types, etc. inside them, the example is as follows:

```cpp
struct Person {
    int age;
    const char* name;

    void say_hello(int a, char b);
};
```

The parsing code is as follows

```python
def traverse_class(node: CX.Cursor):
    match node.kind:
        case CX.CursorKind.STRUCT_DECL | CX.CursorKind.CLASS_DECL:
            print(f"Class: {node.spelling}:")
        case CX.CursorKind.FIELD_DECL:
            print(f"    Field: {node.spelling}: {node.type.spelling}")
        case CX.CursorKind.CXX_METHOD:
            print(f"    Method: {node.spelling}: {node.type.spelling}")
            for arg in node.get_arguments():
                print(f"        Param: {arg.spelling}: {arg.type.spelling}")

    for child in node.get_children():
        traverse_class(child)

# Class: Person:
#     Field: age: int
#     Field: name: const char *
#     Method: say_hello: void (int, char)
#         Param: a: int
#         Param: b: char
```

### Comment 

You can get Doxygen-style comments

```python
@property
def brief_comment(self) -> str:

@property
def raw_comment(self) -> str:
```

`brief_comment` gets the content after `@brief`, `raw_comment` gets the entire comment content.

```cpp
/**
 * @brief func description
 * @param param1
 * @return int
 */
int func(int param1){
    return param1 + 10000000;
}
```

The parsing code is as follows

```python
def traverse_comment(node: CX.Cursor):
    if node.brief_comment:
        print(f"brief_comment => {node.brief_comment}")
    if node.raw_comment:
        print(f"raw_comment => {node.raw_comment}")
    for child in node.get_children():
        traverse_comment(child)

# brief_comment => func description
# raw_comment => /**
#  * @brief func description
#  * @param param1
#  * @return int
#  */
```

### Enum 

Get the enumeration name and corresponding enumeration constant values, as well as its underlying type

```cpp
enum class Color{
    RED = 0,
    GREEN,
    BLUE
};
```

The parsing code is as follows

```python
def traverse_enum(node: CX.Cursor):
    if node.kind == CX.CursorKind.ENUM_DECL:
        print(f"enum: {node.spelling}, underlying type: {node.enum_type.spelling}")
        print(f"is scoped?: {node.is_scoped_enum()}")
        for child in node.get_children():
            print(f"    enum_value: {child.spelling}: {child.enum_value}")
    for child in node.get_children():
        traverse_enum(child)

# enum: Color, underlying type: int
# is scoped?: True
#     enum_value: RED: 0
#     enum_value: GREEN: 1
#     enum_value: BLUE: 2
```

### Attribute 

C++11 introduced a new attribute syntax: `[[ ... ]]`, which can be used to add additional information to functions or variables. For example, `[[nodiscard]]` and `[[deprecated]]`. But sometimes we define some markers ourselves for our preprocessing tools to use, such as marking whether a type needs to generate meta-information, and we also hope that these markers can be recognized by libclang. Unfortunately, if you directly write attributes not supported by the standard, they will be ignored by libclang, that is, they will not appear in the final AST.

```cpp
struct [[Reflect]] Person{}; // ignored
```

A feasible solution is to use `get_tokens` to get all `token`s in the declaration