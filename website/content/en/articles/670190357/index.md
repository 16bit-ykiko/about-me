---
title: 'Why Do C/C++ Compilers Not Retain Metadata?'
date: 2023-12-03 23:37:51
updated: 2024-11-30 18:08:55
series: ['Reflection']
series_order: 2
---

## What is Metadata?

Consider the following `Python` code, where we aim to automatically modify the corresponding field values based on the input string:

```python
class Person:
    def __init__(self, age, name):
        self.age = age
        self.name = name

person = Person(10, "xiaohong")
setattr(person, "age", 12)
setattr(person, "name", "xiaoming")
print(f"name: {person.name}, age: {person.age}") # => name: xiaoming, age: 12
```

`setattr` is a built-in function in `Python` that perfectly meets our needs. It modifies the corresponding value based on the input field name.

How can we achieve this in `C++`? `C++` does not have a built-in `setattr` function. Here is a code example (for now, let's consider only types that can be directly `memcpy`ed, i.e., `trivially copyable` types):

```cpp
struct Person
{
    int age;
    std::string_view name;
};

// Name -> Field offset, field size
std::map<std::string_view, std::pair<std::size_t, std::size_t>> fieldInfo = 
{
    {"age",  {offsetof(Person, age),  sizeof(int)}},
    {"name", {offsetof(Person, name), sizeof(std::string_view)}},
};

void setattr(Person* point, std::string_view name, void* data)
{
    if (!fieldInfo.contains(name))
    {
        throw std::runtime_error("Field not found");
    }
    auto& [offset, size] = fieldInfo[name];
    std::memcpy(reinterpret_cast<char*>(point) + offset, data, size);
}

int main()
{
    Person person = {.age = 1, .name = "xiaoming"};
    int age = 10;
    std::string_view name = "xiaohong";
    setattr(&person, "age", &age);
    setattr(&person, "name", &name);
    std::cout << person.age << " " << person.name << std::endl;
    // => 10 xiaohong
}
```

We have essentially implemented the `setattr` function ourselves, and this implementation seems to be generic. As long as we provide the `fieldInfo` for a specific type, it will work. The `fieldInfo` contains the field name, field offset, and field type size. This can be considered **metadata**. Additionally, metadata might include variable names, function names, etc. **These pieces of information do not directly participate in the program's execution but provide additional information about the program's structure, data, types, etc.** The content of metadata seems to be fixed and known to us since it exists in the program's source code. Does the `C/C++` compiler provide this functionality? The answer is: For programs in `debug` mode, some metadata might be retained for debugging purposes, but in `release` mode, nothing is retained. The benefit of this is obvious: since this information is not necessary for the program to run, not retaining it can significantly reduce the size of the binary executable.

## Why is this Information Unnecessary, and When is it Needed?

Next, I will use the `C` language as an example to correlate its source code with its binary representation. Let's see what information is actually needed for code execution.

### Variable Definition

```c
int value;
```

In fact, variable declarations do not have a direct binary representation. They merely inform the compiler to allocate a block of memory to store the variable named `value`. The size of the allocated memory is determined by its type. Therefore, if the type size is unknown at the time of variable declaration, a compilation error will occur.

```c
struct A;

A x; // error: storage size of 'x' isn't known
A* y; // ok the size of pointer is always known 

struct Node
{
    int val;
    Node next;
}; // error Node is not a complete type
// Essentially, the size of Node is still unknown at the time of its definition

struct Node
{
    int val;
    Node* next;
}; // ok
```

You might think this is somewhat similar to `malloc`, and indeed it is. The difference is that `malloc` allocates memory on the heap at runtime, whereas direct variable declarations typically allocate memory in the data segment or on the stack. The compiler might internally maintain a symbol table that maps variable names to their addresses. When you later operate on this variable, you are actually operating on this memory region.

### Built-in Operators

Built-in operators in `C` generally correspond directly to `CPU` instructions. As for how the `CPU` implements these operations, you can learn about digital electronics. Taking `x86_64` as an example, the possible correspondences are as follows:

```c
| Operator | Meaning | Operator | Meaning |
|----------|---------|----------|---------|
| +        | add     | *        | mul     |
| -        | sub     | /        | div     |
| %        | div     | &        | and     |
| \|       | or      | ^        | xor     |
| ~        | not     | <<       | shl     |
| >>       | shr     | &&       | and     |
| ||       | or      | !        | not     |
| ==       | cmp     | !=       | cmp     |
| >        | cmp     | >=       | cmp     |
| <        | cmp     | <=       | cmp     |
| ++       | inc     | --       | dec     |
```

Assignment is likely accomplished through the `mov` instruction, for example:

```c
a = 3; // mov [addressof(a)] 3
```

### Structures

```c
struct Point
{
    int x;
    int y;
}

int main()
{
    Point point;
    point.x = 1;
    point.y = 2;
}
```

The size of a structure can generally be calculated from its members, often considering memory alignment, and is determined by the compiler. For example, [msvc](https://learn.microsoft.com/en-us/cpp/c-language/storage-and-alignment-of-structures?view=msvc-170). But in any case, the size of the structure is known at compile time, and we can also obtain the size of a type or variable through `sizeof`. Therefore, the `Point point` variable definition here is straightforward: the type size is known, and memory is allocated on the stack.

Now, let's focus on structure member access. In fact, `C` has a macro that can obtain the offset of a structure member relative to the structure's starting address, called `offsetof` (even if we can't obtain it, the compiler internally calculates the field offsets, so the offset information is always known to the compiler). For example, here `offsetof(Point, x)` is `0`, and `offsetof(Point, y)` is `4`. Therefore, the above code can be understood as:

```c
int main()
{
    char point[sizeof(Point)]; // 8 = sizeof(Point)
    *(int*)(point + offsetof(Point, x)) = 1; // point.x = 1
    *(int*)(point + offsetof(Point, y)) = 2; // point.y = 2
}
```

The compiler might also maintain a symbol table for field names to offsets, and field names will eventually be replaced by `offset`. There is no need to retain them in the program.

### Function Calls

Function calls are generally implemented through the function call stack, which is too common to elaborate on. Function names are eventually replaced by function addresses.

### Summary

Through the above analysis, you may have noticed that in `C`, symbol names, type names, variable names, function names, structure field names, etc., are all replaced by numbers, addresses, offsets, etc. Losing them does not affect the program's execution. Therefore, they are discarded to reduce the size of the binary file. For `C++`, the situation is largely similar. `C++` only retains some metadata in special cases, such as `type_info`, and you can manually disable `RTTI` to ensure that such information is not generated.

When do we need to use this information? Obviously, the `setattr` introduced at the beginning requires it. When debugging a program, we need to know the variable names, function names, member names, etc., corresponding to an address to facilitate debugging, and we need this information at that time. When serializing a structure into `json`, we need to know its field names, and we need this information. When type erasure is performed to `void*`, we still need to know the actual type it corresponds to, and we need this information at that time. In summary, when we need to distinguish what a piece of binary content originally was at runtime, we need this information (of course, we also need it when we want to use this information for code generation at compile time).

## How to Obtain This Information?

The `C/C++` compiler does not provide us with an interface to obtain this information, but as mentioned earlier, this information is clearly in the source code. Variable names, function names, type names, field names. We can choose to manually understand the code and then manually store the metadata. For thousands of classes and dozens of member functions, it might take a few months to write. Just kidding, or we can write some programs, such as regular expression matching, to help us obtain this information? However, we have a better choice to obtain this information, and that is through the `AST`.

## AST (Abstract Syntax Tree)

`AST` stands for Abstract Syntax Tree. It is a data structure used in programming language processing to represent the abstract syntax structure of source code. The `AST` is the result of source code being processed by a parser, capturing the syntactic structure of the code but not all details, such as whitespace or comments. In the `AST`, each node represents a syntactic structure in the source code, such as variable declarations, function calls, loops, etc. These nodes are connected through parent-child and sibling relationships, forming a tree structure that is easier for computer programs to understand and process. If you have the `clang` compiler installed on your computer, you can use the following command to view the syntax tree of a source file:

```bash
clang -Xclang -ast-dump -fsyntax-only <your.cpp>
```

The output is as follows, with important information filtered out and irrelevant parts deleted:

```cpp
|-CXXRecordDecl 0x2103cd9c318 <col:1, col:8> col:8 implicit struct Point
|-FieldDecl 0x2103cd9c3c0 <line:4:5, col:9> col:9 referenced x 'int'
|-FieldDecl 0x2103e8661f0 <line:5:5, col:9> col:9 referenced y 'int'
`-FunctionDecl 0x2103e8662b0 <line:8:1, line:13:1> line:8:5 main 'int ()'
  `-CompoundStmt 0x2103e866c68 <line:9:1, line:13:1>
    |-DeclStmt 0x2103e866b30 <line:10:5, col:16>
    | `-VarDecl 0x2103e866410 <col:5, col:11> col:11 used point 'Point':'Point' callinit
    |   `-CXXConstructExpr 0x2103e866b08 <col:11> 'Point':'Point' 'void () noexcept'
    |-BinaryOperator 0x2103e866bb8 <line:11:5, col:15> 'int' lvalue '='
    | |-MemberExpr 0x2103e866b68 <col:5, col:11> 'int' lvalue .x 0x2103cd9c3c0
    | | `-DeclRefExpr 0x2103e866b48 <col:5> 'Point':'Point' lvalue Var 0x2103e866410 'point' 'Point':'Point'
    | `-IntegerLiteral 0x2103e866b98 <col:15> 'int' 1
    `-BinaryOperator 0x2103e866c48 <line:12:5, col:15> 'int' lvalue '='
      |-MemberExpr 0x2103e866bf8 <col:5, col:11> 'int' lvalue .y 0x2103e8661f0
      | `-DeclRefExpr 0x2103e866bd8 <col:5> 'Point':'Point' lvalue Var 0x2103e866410 'point' 'Point':'Point'
      `-IntegerLiteral 0x2103e866c28 <col:15> 'int' 2
```

Alternatively, if you have the `clangd` plugin installed in `vscode`, you can right-click on a block of code and select `show AST` to view the `ast` of that code snippet. You can see that the source code content is indeed presented to us in a tree structure. Since it is a tree, we can freely traverse the tree nodes and filter to obtain the information we want. The above two examples are visual outputs. Typically, there are also direct code interfaces to obtain this information. For example, `Python` has a built-in `ast` module to obtain it, and `C++` generally uses `clang`-related tools to obtain this content. If you want to know how to use `clang` tools specifically, you can refer to the article: [Use clang tools to freely control C++ code!](https://www.ykiko.me/zh-cn/articles/669360731)

If you are curious about how the compiler transforms source code into an `ast`, you can learn about the front-end content of compilation principles.

## How to Store This Information?

This question might sound confusing, but in fact, it is a question that only `C++` programmers need to consider.

Actually, everything is caused by `constexpr`. Storing information like this:

```cpp
struct FieldInfo
{
    std::string_view name;
    std::size_t offset;
    std::size_t size;
}；

struct Point
{
    int x;
    int y;
}；

constexpr std::array<FieldInfo, 2> fieldInfos =
{{
    {"x", offsetof(Point, x), sizeof(int)},
    {"y", offsetof(Point, y), sizeof(int)},
}};
```

Means that we can not only query this information at runtime but also at compile time.

Furthermore, it can be stored in template parameters, so that even types can be stored:

```cpp
template<fixed_string name, std::size_t offset, typename Type>
struct Field{};

using FieldInfos = std::tuple
<
    Field<"x", offsetof(Point, x), int>,
    Field<"y", offsetof(Point, y), int>
>;
```

This undoubtedly gives us more room for operation. So, what should we do next with this information? In fact, we can choose to generate code based on this information. For related content, you can browse other sections in the series of articles.