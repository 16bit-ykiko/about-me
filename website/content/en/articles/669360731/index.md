---
series:
  - Reflection
series_order: 5
title: Master your C++ code with Clang tools.
date: "2023-11-29 01:14:27"
updated: "2024-11-30 10:01:57"
zhihu_article_id: "669360731"
zhihu_url: https://zhuanlan.zhihu.com/p/669360731
zhihu_column_id: c_1707545619290316800
zhihu_column_title: 编程语言中的反射
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

Clang is a C-language family compiler frontend provided by the LLVM project. It was originally developed to replace the C language frontend of the GNU Compiler Collection (GCC), with the goal of providing faster compilation speeds, better diagnostic information, and a more flexible architecture. Clang includes C, C++, and Objective-C compiler frontends, which are designed to be embedded in other projects. A key feature of Clang is its modular architecture, which makes it easier for developers to extend and customize compiler functionality. Clang is widely used in many projects, including LLVM itself, the development of some operating system kernels, and the implementation of compilers for some programming languages.

In addition to being used as a compiler, Clang can also be provided as a library, allowing developers to leverage compiler features in their applications, such as source code analysis and generation. Clang can be used to obtain the Abstract Syntax Tree (AST) of C++ source files for further processing. This article will introduce how to use Clang tools.

## Installation & Usage

Currently, Clang is divided into the following libraries and tools: libsupport, libsystem, libbasic, libast, liblex, libparse, libsema, libcodegen, librewrite, libanalysis. Since Clang itself is written in C++, the related interfaces are all C++. However, due to the complexity and instability of the C++ interface itself (e.g., a DLL compiled by GCC on Windows cannot be used by MSVC, or API changes due to Clang version upgrades leading to incompatibility), the official recommendation is not to prioritize the C++ interface.

In addition to the C++ interface, the official project also provides a C language interface called [libclang](https://clang.llvm.org/doxygen/group__CINDEX.html). This interface is not only relatively simple to use but also quite stable. The only drawback is that it cannot obtain a complete C++ Abstract Syntax Tree (AST). However, given that a complete C++ AST is inherently extremely complex, and often we only need a small portion of its information, this issue can usually be ignored unless you genuinely have such a requirement.

If you want to use libclang, you need to install LLVM and Clang first. On the [LLVM Release](https://github.com/llvm/llvm-project/releases) page, several pre-built binary packages are available for download. If you have custom requirements, please refer to the [Getting Started](https://llvm.org/docs/GettingStarted.html#id4) page for manual compilation. After installation, you only need to link `libclang.dll` from the `llvm/lib` directory to your program and include the `clang-c/Index.h` header file from the `llvm/include` directory to use it.

However, since the C language lacks some high-level abstractions, manipulating strings can be cumbersome. For large-scale use, we would need to wrap it with a C++ layer ourselves. Fortunately, the official project also provides a Python binding based on this C interface, namely the [clang](https://pypi.org/project/clang/) package, which makes it even more convenient to use. However, the official Python binding does not package the libclang DLL, so you still need to manually configure the LLVM environment on your computer, which can be a bit troublesome. Nevertheless, someone in the community has provided a packaged version on PyPI: [libclang](https://pypi.org/project/libclang/).

So, if you want to use libclang to get a C++ syntax tree, you just need to

```bash
pip install libclang
```

No extra steps are required. This article will introduce it based on this Python binding version. The C version API and the Python version API are basically identical. If you feel that Python's performance is insufficient, you can also refer to this tutorial to write C version code. Additionally, the official package does not provide type hints, which means there's no code completion when writing in Python, making it less comfortable to use. I've added a type-hinted [cindex.pyi](https://github.com/16bit-ykiko/about-me/blob/main/code/cindex.pyi); just download it and place it in the same folder to get code completion.

## Quick Start

The example C++ source file code is as follows:

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

The Python code to parse it is as follows:

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

The output is as follows:

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

The first part is the syntax tree node type, and the second part is the node content. As you can see, it's very clear and almost corresponds one-to-one with the source code.

## Basic Types

Note that this article assumes the reader has some understanding of syntax trees and will not go into too much detail here. If you don't know what a syntax tree is, you can refer to [Why C/C++ Compilers Don't Retain Metadata](https://16bit-ykiko.github.io/about-me/670190357). Below are some common types in cindex.

### Cursor

Equivalent to a basic node in the syntax tree, the entire syntax tree is composed of `Cursor`s. The `kind` attribute returns a `CursorKind` enumeration value, which represents the actual type corresponding to this node.

```python
for kind in CursorKind.get_all_kinds():
    print(kind)
```

This can print all supported node types, or you can directly check the source code. `Cursor` also has other attributes and methods for us to use, commonly including the following:

```python
@property
def spelling(self) -> str:

@property
def displayname(self) -> str:

@property
def mangled_name(self) -> str:
```

Gets the name of the node. For example, for a variable declaration node, its `spelling` is the name of the variable. `displayname` is the short name of the node, which is the same as `spelling` most of the time. However, there are sometimes differences; for example, a function's `spelling` might include parameter types, such as `func(int)`, but its `displayname` would just be `func`. `mangled_name` is the name of the symbol after name mangling, used for linking.

```python
@property
def type(self) -> Type:
```

The type of the node element. For example, for a variable declaration node, its `type` is the type of the variable. Or for a field declaration node, its `type` is the type of the field. The return type is `Type`.

```python
@property
def location(self) -> SourceLocation:
```

The location information of the node, returning a `SourceLocation` type, which carries information such as the line number, column number, and filename of the node in the source code.

```python
@property
def extent(self) -> SourceRange:
```

The range information of the node, returning a `SourceRange` type, composed of two `SourceLocation`s, which carry the start and end positions of the node in the source code.

```python
@property
def access_specifier(self) -> AccessSpecifier:
```

The access specifier of the node, returning an `AccessSpecifier` type. There are five types: `PUBLIC`, `PROTECTED`, `PRIVATE`, `NONE`, `INVALID`.

```python
def get_children(self) -> iterable[Cursor]:
```

Gets all child nodes, returning an `iterable` of `Cursor`s. This function is the most commonly used because we can traverse the entire syntax tree recursively.

```python
def get_tokens(self) -> iterable[Token]:
```

Gets all `token`s representing this node, returning an `iterable` of `Token`s. A `token` is the smallest unit of a syntax tree. For example, for a variable declaration node, its `token`s are `int`, `a`, `;`. This function can be used to obtain detailed information, such as the values of integer and floating-point literals.

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

These functions are mostly self-explanatory. For example, `is_definition` checks if the node is a definition, and `is_const_method` checks if the node is a `const` method.

### Type

If the node has a type, this represents the type of that node. Common attributes include:

```python
@property
def kind(self) -> TypeKind:
```

The kind of the type, returning a `TypeKind`. For example, `INT`, `FLOAT`, `POINTER`, `FUNCTIONPROTO`, etc.

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

Gets the alignment, size, field offset, etc., of the type.

And some `is` prefixed functions, such as `is_const_qualified`, `is_function_variadic`, `is_pod`, etc. We won't elaborate on them here.

### TranslationUnit

Generally, a C++ source file represents a `TranslationUnit`, which is what we commonly refer to as a compilation unit.

Commonly used are:

```python
@property
def cursor(self) -> Cursor:
```

Gets the root node of this `TranslationUnit`, which is a `Cursor` of type `TRANSLATION_UNIT`.

```python
@property
def spelling(self) -> str:
```

Gets the filename of this `TranslationUnit`.

```python
def get_includes(self, depth: int = -1) -> iterable[FileInclusion]:
```

Gets all `include`s of this `TranslationUnit`, returning a `list` of `FileInclusion`s. Note that since included files might contain other files, you can use the `depth` parameter to limit this. For example, if you only want to get the first level, i.e., directly included header files, you can write it like this:

```python
index = CX.Index.create()
tu = index.parse('main.cpp', args=['-std=c++20'])
for file in tu.get_includes():
    if file.depth == 1:
        print(file.include.name)
```

This will print all directly used header files.

### Index

An `Index` is a collection of `TranslationUnit`s that are ultimately linked together to form an executable or library.

There is a static method `create` to create a new `Index`, and then the member method `parse` can parse a C++ source file, returning a `TranslationUnit`.

```python
def parse(self, path: str,
                args: list[str] | None = ...,
                unsaved_files: list[tuple[str, str]] | None = ...,
                options: int = ...) -> TranslationUnit:
```

`path` is the source file path, `args` are compilation arguments, `unsaved_files` are unsaved files, and `options` are parameters defined in `TranslationUnit.PARSE_XXX`, such as `PARSE_SKIP_FUNCTION_BODIES` and `PARSE_INCOMPLETE`. These can be used to customize the parsing process, speed up parsing, or retain macro information, etc.

## Examples

### Namespace

Since Clang expands all header files during parsing, the complete output is too extensive. However, we might primarily be interested in information from our own code. In such cases, we can use namespaces for filtering. Here's an example:

```cpp
#include <iostream>

namespace local {
    struct Person {
        int age;
        std::string name;
    };
}
```

The parsing code is as follows:

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

We write a function to filter by namespace name and then forward to our previous function. This way, only the content within the desired namespace will be output.

### Class & Struct

We mainly want to get their field names, types, method names, types, etc. Here's an example:

```cpp
struct Person {
    int age;
    const char* name;

    void say_hello(int a, char b);
};
```

The parsing code is as follows:

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

Doxygen-style comments can be retrieved:

```python
@property
def brief_comment(self) -> str:

@property
def raw_comment(self) -> str:
```

`brief_comment` gets the content after `@brief`, and `raw_comment` gets the entire comment content.

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

The parsing code is as follows:

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

Get the enum name, its corresponding enum constant values, and its underlying type.

```cpp
enum class Color{
    RED = 0,
    GREEN,
    BLUE
};
```

The parsing code is as follows:

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

C++11 introduced new attribute syntax: `[[ ... ]]`, which can be used to add extra information to functions or variables. Examples include `[[nodiscard]]` and `[[deprecated]]`. However, sometimes we define our own markers for our pre-processing tools, such as marking whether a type needs metadata generation. We also hope that these markers can be recognized by libclang. Unfortunately, if non-standard attributes are written directly, they will be ignored by libclang, meaning they won't appear in the final AST.

```cpp
struct [[Reflect]] Person{}; // ignored
```

A feasible solution is to use `get_tokens` to retrieve all `token`s in the declaration and then manually extract the desired information. For example, the result obtained here would be `struct`, `[`, `[`, `Reflect`, `]`, `]`, `Person`, `{`, `}`, from which we can extract the information we want.

However, Clang provides a better way: using the `clang::annotate(...)` Clang extension attribute. For example, like this:

```cpp
#define Reflect clang::annotate("reflect")

struct [[Reflect]] A {};
```

With this, for the `A` `Cursor`, its child nodes will include an `ANNOTATE_ATTR` type `Cursor`, and its `spelling` will contain the stored information, which is `reflect` in this case. This allows us to easily retrieve our custom attributes. Furthermore, the C++ standard specifies that when a compiler encounters an unrecognized attribute, it ignores it rather than reporting an error. This means the attribute only affects our preprocessor and does not interfere with normal compilation.

### Macro

Before actually parsing the syntax tree, Clang replaces all preprocessor directives with actual code. Therefore, these directives are no longer present in the final syntax tree information. However, sometimes we do want to obtain this information, for example, if we want to get information about `#define`. To do this, the `options` parameter of `parse` needs to be set to `TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD`. If you want to get the content of a macro, just use `get_tokens`.

```cpp
#define CONCAT(a, b) a#b
auto x = CONCAT(1, 2);
```

The parsing code is as follows:

```python
def traverse_macro(node: CX.Cursor):
    if node.kind == CX.CursorKind.MACRO_DEFINITION:
        if not node.spelling.startswith('_'):  # Exclude internal macros
            print(f"MACRO: {node.spelling}")
            print([token.spelling for token in node.get_tokens()])
    elif node.kind == CX.CursorKind.MACRO_INSTANTIATION:
        print(f"MACRO_INSTANTIATION: {node.spelling}")
        print([token.spelling for token in node.get_tokens()])

    for child in node.get_children():
        traverse_macro(child)

# MACRO: CONCAT
# ['CONCAT', '(', 'a', ',', 'b', ')', 'a', '#', 'b']
# MACRO_INSTANTIATION: CONCAT
# ['CONCAT', '(', '1', ',', '2', ')']
```

## Rewrite

Sometimes we want to make simple modifications to the source code, such as inserting or deleting a piece of code at a certain position. In such cases, we can use the `Rewriter` class. Here's an example:

```cpp
void func(){
    int a = 1;
    int b = 2;
    int c = 3;
}
```

Use the following code to modify the source file:

```python
def rewrite(node: CX.Cursor, rewriter: CX.Rewriter):
    if node.kind == CX.CursorKind.VAR_DECL:
        if node.spelling == "a":
            rewriter.replace_text(node.extent, "int a = 100")
        elif node.spelling == "b":
            rewriter.remove_text(node.extent)
        elif node.spelling == "c":
            rewriter.insert_text_before(node.extent.start, "[[maybe_unused]]")

    for child in node.get_children():
        rewrite(child, rewriter)


index = CX.Index.create()
tu = index.parse('main.cpp', args=['-std=c++20'])
rewriter = CX.Rewriter.create(tu)
rewrite(tu.cursor, rewriter)
rewriter.overwrite_changed_files()
```

After running, the content of `main.cpp` becomes:

```cpp
void func() {
    int a = 100;
    ;
    [[maybe_unused]] int c = 3;
}
```

## Conclusion

When retrieving ABI-related information such as type `size`, `align`, and `offset`, it's important to consider the platform. Their values might differ across different ABIs; for example, MSVC and GCC generally have different values for these. You can specify the target platform by using `-target` in the compilation arguments. If you need results consistent with MSVC, you can use `--target=x86_64-pc-windows-msvc`. For GCC, you can use `--target=x86_64-pc-linux-gnu`.

As mentioned earlier, libclang cannot provide a complete C++ syntax tree. For instance, it lacks many interfaces for parsing `Expr`essions. This means that if you need to parse specific expression content, using its C++ interface might be more suitable, as it provides a complete and complex syntax tree.

There are relatively few articles in China specifically on the practical use of Clang tools. This article attempts to provide a concrete introduction to some common functionalities, although it is not entirely comprehensive. If you have any questions, you can directly read the `Index.h` source code, which contains very detailed comments. Alternatively, you can leave a comment in the comments section, and I will do my best to answer. Furthermore, if you need information not provided by libclang, you can use the `get_tokens` function to retrieve it yourself. For example, libclang does not support getting the values of integer and floating-point literals, in which case you can manually retrieve them via `get_tokens`.

After extracting this information from the syntax tree, you can further process it, such as generating metadata or directly generating code. Of course, these are subsequent steps, depending on your specific needs.

---

This article concludes here. This is one of the articles in the reflection series; feel free to read other articles in the series!
