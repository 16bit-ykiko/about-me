---
title: '使用 Clang 工具自由的支配 C++ 代码吧'
date: 2023-11-29 09:14:27
updated: 2024-11-30 18:01:57
series: ['Reflection']
series_order: 5
---

Clang 是 LLVM 项目提供的一个 C 语言家族的编译器前端。它最初开发的目的是替代 GNU Compiler Collection (GCC) 的 C 语言前端，目标是提供更快的编译速度、更好的诊断信息和更灵活的架构。Clang 包含一个 C、C++ 和 Objective-C 编译器前端，这些前端设计为可以嵌入到其他项目中。Clang 的一个重要特点是其模块化架构，使开发者能够更轻松地扩展和定制编译器的功能。Clang 被广泛应用于许多项目，包括 LLVM 自身、一些操作系统内核的开发以及一些编程语言的编译器实现。

除了作为编译器使用之外，Clang 还可以作为一个库提供，使开发者能够在其应用程序中利用编译器的功能，例如源代码分析和生成。Clang 可以用来获取 C++ 源文件的抽象语法树 (AST)，以便进一步处理这些信息。本文将介绍如何使用 Clang 工具。

## Installation & Usage 

目前，Clang 被划分为以下库和工具：libsupport、libsystem、libbasic、libast、liblex、libparse、libsema、libcodegen、librewrite、libanalysis。由于 Clang 本身是用 C++ 编写的，所以相关的接口都是 C++ 的。然而，由于 C++ 接口本身的复杂性和不稳定性（例如：在 Windows 上由 GCC 编译出来的 DLL 无法给 MSVC 使用，或者 Clang 自身版本升级导致 API 变动，从而出现不兼容性），官方并不推荐优先使用 C++ 接口。

除了 C++ 接口之外，官方还提供了一个叫做 [libclang](https://clang.llvm.org/doxygen/group__CINDEX.html) 的 C 语言接口，这个接口不仅使用起来相对简单，而且本身也比较稳定。唯一的缺点是无法获取完整的 C++ 抽象语法树 (AST)，不过鉴于 C++ 完整的语法树本身就极度复杂，很多时候我们只需要其中的一小部分信息，所以这个问题通常可以忽略，除非你真的有这方面的需求。

如果你想要使用 libclang，你需要先安装 LLVM 和 Clang。在 [LLVM Release](https://github.com/llvm/llvm-project/releases) 页面，有若干预发布的二进制包可以下载。如果你有定制化需求，请参考 [Getting Started](https://llvm.org/docs/GettingStarted.html#id4) 页面进行手动编译。安装完成后，只需将`llvm/lib`目录下的`libclang.dll`链接到程序中，并包含`llvm/include`目录下的`clang-c/Index.h`头文件即可使用。

然而，由于 C 语言没有一些高级抽象，操作字符串都很麻烦。如果大规模使用，还需要我们自己用 C++ 封装一层。幸好，官方基于这套 C 接口还提供了一个 Python 绑定，即 [clang](https://pypi.org/project/clang/) 这个包，这使得使用起来更加方便。然而，官方提供的 Python 绑定并没有打包 libclang 的这个 DLL，因此你仍然需要在电脑上手动配置 LLVM 的环境，这可能会有些麻烦。不过，社区中有人在 PyPI 上提供了打包好的包：[libclang](https://pypi.org/project/libclang/)。

于是如果你想使用 libclang 来获取 C++ 语法树，只需要

```bash
pip install libclang
```

什么额外的事情都不用做。本文就基于这个 python binding 的版本进行介绍。C 版本的 API 和 Python 版本的 API 基本是完全一致的，如果你觉得 Python 性能不够，你也可以参考这个教程对照着写 C 版本的代码。另外官方提供的包并没有 type hint，这样的话用 Python 写就没有代码补全，用起来也不舒服。我自己补了一个类型提示的 [cindex.pyi](https://github.com/16bit-ykiko/about-me/blob/main/code/cindex.pyi)，下载下来之后直接和 放在同一文件夹内就能有代码提示了。

## Quick Start 

示例的 C++ 源文件代码如下

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

解析它的 Python 代码如下

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

输出结果如下

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

前面的是语法树节点类型，后面是节点的内容。可以发现还是非常清晰的，几乎能和源代码一一对应。

## Basic Types 

注意，本文假定读者对语法树有一定的认识，不在这里做过多介绍了。如果不知道语法树是什么的话，可以看一下 [为什么说 C/C++ 编译器不保留元信息](https://16bit-ykiko.github.io/about-me/670190357)。下面对 cindex 中的一些常用类型做一些介绍

### Cursor 

相当于语法树的基本节点，整个语法树都是由`Cursor`组成的。通过`kind`属性返回一个`CursorKind`类型枚举值，就代表了这个节点实际对应的类型。

```python
for kind in CursorKind.get_all_kinds():
    print(kind)
```

这样可以打印出所有支持的节点类型，也可以直接去源码查看。`Cursor`还有一些其它的属性和方法让我们使用，常用的有如下这些：

```python
@property
def spelling(self) -> str:

@property
def displayname(self) -> str:

@property
def mangled_name(self) -> str:
```

获取节点的名字，例如一个变量声明的节点，它的`spelling`就是这个变量的名字。而`displayname`则是节点的简短名字，大多数时候和`spelling`是一样的。但是有些时候会有区别，例如一个函数的`spelling`会带上参数类型，例如`func(int)`，但是它的`displayname`就只是`func`。而`mangled_name`就是该符号经过 name mangling 之后用于链接的名字。

```python
@property
def type(self) -> Type:
```

节点元素的类型，例如一个变量声明的节点，它的`type`就是这个变量的类型。或者一个字段声明的节点，它的`type`就是这个字段的类型。返回类型为`Type`。

```python
@property
def location(self) -> SourceLocation:
```

节点的位置信息，返回类型为`SourceLocation`，其中携带了该节点在源码中的行数，列数，文件名等信息。

```python
@property
def extent(self) -> SourceRange:
```

节点的范围信息，返回类型为`SourceRange`，由两个`SourceLocation`组成，其中携带了该节点在源码中的起始位置和结束位置

```python
@property
def access_specifier(self) -> AccessSpecifier:
```

节点的访问权限，返回类型为`AccessSpecifier`。有`PUBLIC`, `PROTECTED`, `PRIVATE`, `NONE`, `INVALID`五种。

```python
def get_children(self) -> iterable[Cursor]:
```

获取所有子节点，返回类型为`Cursor`的`iterable`。这个函数是最常用的，因为我们可以通过递归的方式遍历整个语法树。

```python
def get_tokens(self) -> iterable[Token]:
```

获取代表该节点的所有`token`，返回类型为`Token`的`iterable`。`token`是语法树的最小单位，例如一个变量声明的节点，它的`token`就是`int`，`a`，`;`这三个。这个函数可以用来获取一些细节信息，例如获取整数字面量和浮点数字面量的值。

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

这些函数基本就见名知意了，例如`is_definition`就是判断该节点是否是一个定义，`is_const_method`就是判断该节点是否是一个`const`方法。

### Type 

如果该节点有类型的话，代表该节点的类型。常用的属性有

```python
@property
def kind(self) -> TypeKind:
```

类型的类型，返回类型为`TypeKind`。例如`INT`, `FLOAT`, `POINTER`, `FUNCTIONPROTO`等等。

```python
@property
def spelling(self) -> str:
```

类型的名字，例如`int`, `float`, `void`等等。

```python
def get_align(self) -> int:
def get_size(self) -> int:
def get_offset(self, fieldname: str) -> int:
```

获取类型的对齐，大小，字段偏移量等等。

以及一些`is`开头的函数，例如`is_const_qualified`, `is_function_variadic`, `is_pod`等等。这里也就不多说了。

### TranslationUnit 

一般来说一个 C++ 源文件就代表一个`TranslationUnit`，也就是我们常说的编译单元。

常用的有

```python
@property
def cursor(self) -> Cursor:
```

获取该`TranslationUnit`的根节点，也就是`TRANSLATION_UNIT`类型的`Cursor`。

```python
@property
def spelling(self) -> str:
```

获取该`TranslationUnit`的文件名。

```python
def get_includes(self, depth: int = -1) -> iterable[FileInclusion]:
```

获取该`TranslationUnit`的所有`include`，返回类型为`FileInclusion`的`list`，注意由于`include`的文件里面可能还会包含别的文件所以，可以用`depth`这个参数来限制，比如我只想获取第一层也就是直接包含的头文件可以这么写。

```python
index = CX.Index.create()
tu = index.parse('main.cpp', args=['-std=c++20'])
for file in tu.get_includes():
    if file.depth == 1:
        print(file.include.name)
```

这样就会打印出所有直接使用的头文件了。

### Index 

一个`Index`就是一个`TranslationUnit`的集合，并且最终被链接到一起，形成一个可执行文件或者库。

有一个静态方法`create`用于创建一个新的`Index` ，然后成员方法`parse`可以解析一个`C++`源文件，返回一个`TranslationUnit`。

```python
def parse(self, path: str,
                args: list[str] | None = ...,
                unsaved_files: list[tuple[str, str]] | None = ...,
                options: int = ...) -> TranslationUnit:
```

`path`是源文件路径，`args`是编译参数，`unsaved_files`是未保存的文件，`options`是一些定义在`TranslationUnit.PARSE_XXX`中的参数，例如`PARSE_SKIP_FUNCTION_BODIES`和`PARSE_INCOMPLETE`。可以用来定制化解析过程，加快解析速度，或者保留宏信息等。

## Examples 

### Namespace 

由于 clang 在解析的时候会把所有的头文件都展开，全部输出内容太多了。但是我们主要可能只是想要我们自己代码的信息，这时候就可以利用命名空间进行筛选了。示例如下：

```cpp
#include <iostream>

namespace local {
    struct Person {
        int age;
        std::string name;
    };
}
```

解析代码如下

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

写一个函数对类型空间名进行筛选，然后转发到我们之前那个函数就行，这样就只会输出我们想要的的命名空间里面的内容了。

### Class & Struct 

我们主要是获取它们里面的字段名，类型，方法名，类型等，示例如下：

```cpp
struct Person {
    int age;
    const char* name;

    void say_hello(int a, char b);
};
```

解析代码如下

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

可以获取 Doxygen 风格的注释

```python
@property
def brief_comment(self) -> str:

@property
def raw_comment(self) -> str:
```

`brief_comment`获取`@brief`后面的内容，`raw_comment`获取整个注释的内容。

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

解析代码如下

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

获取枚举名以及对应的枚举常量值，还有它的底层类型

```cpp
enum class Color{
    RED = 0,
    GREEN,
    BLUE
};
```

解析代码如下

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

C++11 加入了新的 attribute 语法：`[[ ... ]]`，可以用来给函数或者变量添加额外的信息。例如`[[nodiscard]]`和`[[deprecated]]`。但是我们有时候在自己定义一些标记来给我们的与预处理工具使用，比如标记一个类型需要不需要生成元信息，我们也希望这些标记也能被 libclang 识别出来。但是遗憾的是如果直接写不被标准支持的属性会被 libclang 忽略，也就是最终的 AST 中是没有它的

```cpp
struct [[Reflect]] Person{}; // ignored
```

一个可行的解决办法是利用`get_tokens`获取声明中的所有`token`，然后自己裁剪出来。比如这里获取到的结果就是`struct`,`[`,`[`,`Reflect`,`]`,`]`,`Person`,`{`,`}`，我们可以从中获取出我们想要的信息。

但是 clang 给我们提供了一种更好的办法。那就是利用`clang::annotate(...)`这个 clang 的扩展属性，例如像下面这样

```cpp
#define Reflect clang::annotate("reflect")

struct [[Reflect]] A {};
```

这样对于`A`这个`Cursor`来说，它的子节点中就会有一个`ANNOTATE_ATTR`的类型的`Cursor`，而`spelling`就是里面存的信息，这里就是`reflect`。这样我们就可以很方便的获取到我们自定义的属性了。而且 C++ 标准规定了，当编译器遇到一个不认识的 attribute 的时候，它会忽略这个 attribute，而不是报错。这样的话，这个属性它就只作用于我们的预处理器，不会影响到正常编译。

### Macro 

clang 在实际解析语法树之前，会把所有的预处理指令都替换成实际的代码。所以最后的语法树信息中就没有它们了。但是有些时候我们的确想要获取到这些信息，比如我们想要获取到`#define`的信息，这里需要把`parse`的`options`参数设为`TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD`。如果想要获取宏的内容就用`get_tokens`就行了。

```cpp
#define CONCAT(a, b) a#b
auto x = CONCAT(1, 2);
```

解析代码如下

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

有时候我们希望对源代码进行一些简单的修改，在某个位置插入一段代码或者删除一段代码。这时候我们可以使用`Rewriter`这个类。示例如下：

```cpp
void func(){
    int a = 1;
    int b = 2;
    int c = 3;
}
```

使用下面的代码对源文件进行修改

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

运行之后，`main.cpp`的内容就变成了

```cpp
void func() {
    int a = 100;
    ;
    [[maybe_unused]] int c = 3;
}
```

## Conclusion 

如果要获取类型的`size`, `align`, `offset`等 ABI 相关的内容，需要注意 platform。不同 ABI 的情况下它们的值可能不同，例如 MSVC 和 GCC 一般关于这些内容就不同，可以通过在编译参数中指定`-target`来指定目标平台。如果需要和 MSVC 一致的结果，可以使用`--target=x86_64-pc-windows-msvc`。如果是 GCC 的话，可以使用`--target=x86_64-pc-linux-gnu`。

前文提到，libclang 无法提供完整的 C++ 语法树。例如，它在解析 `Expr` 方面缺少许多接口。这意味着，如果你需要解析具体的表达式内容，那么使用其 C++ 接口可能更为适合，因为它提供了完整且复杂的语法树。

国内关于 Clang 工具具体使用的文章较少。本文尝试对一些常用功能进行了具体介绍，尽管并不十分完善。若有任何疑问，可直接阅读 `Index.h` 源码，其中的注释非常详尽。或者也可以在评论区留言，我会尽力解答。此外，若需要获取 libclang 不提供的信息，可使用 `get_tokens` 函数自行获取。例如，libclang 不支持获取整数和浮点数面值的值，这时可通过 `get_tokens` 手动获取。

在从语法树中提取这些信息后，你可以进一步处理它们，如生成元信息或直接生成代码等。当然，这些都是后话，具体取决于你的需求。

---

本文到这里就结束了，这是反射系列中的其中一篇，欢迎阅读系列中的其它文章！