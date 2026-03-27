---
series:
  - Reflection
series_order: 2
title: Why is it said that C/C++ compilers do not preserve metadata?
date: "2023-12-03 15:37:51"
updated: "2024-11-30 10:08:55"
zhihu_article_id: "670190357"
zhihu_url: https://zhuanlan.zhihu.com/p/670190357
zhihu_column_id: c_1707545619290316800
zhihu_column_title: 编程语言中的反射
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

## First, what is metadata?

Consider the following `python` code. We want to automatically modify the corresponding field value based on the input string.

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

`setattr` is a built-in `python` function that perfectly meets our needs. It modifies the corresponding value based on the input field name.

What if we want to implement this in `C++`? `C++` does not have a built-in function like `setattr`. Here's a code example. (For now, let's only consider types that can be directly `memcpy`'d, i.e., `trivially copyable` types).

```cpp
struct Person
{
    int age;
    std::string_view name;
};

// Name -> field offset, field size
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

We can see that we basically implemented the `setattr` function ourselves, and this implementation seems to be generic. We just need to provide the `fieldInfo` for specific types. This `fieldInfo` stores the field name, field offset, and field type size. It can be regarded as **metadata**. In addition, there might be variable names, function names, and so on. **This information does not directly participate in program execution but provides additional information about program structure, data, types, etc.** The contents stored in metadata also seem to be fixed patterns, all known information to us, because they exist in the program's source code. Does the `C/C++` compiler provide such functionality? The answer is: for programs in `debug` mode, some information might be retained for debugging, but in `release` mode, nothing is stored. The advantage of this is obvious, as this information is not essential for program execution, and not retaining it can significantly reduce the size of the binary executable.

## Why is this information unnecessary, and when is it needed?

Next, I will use the `C` language as an example to map its source code to its binary representation. What information is actually needed to execute the code?

### Variable Definition

```c
int value;
```

In fact, a variable declaration does not have a directly corresponding binary representation; it merely tells the compiler to allocate a block of space to store a variable named `value`. The exact amount of memory to allocate is determined by its type. Therefore, if the type size is unknown during variable declaration, a compilation error will occur.

```c
struct A;

A x; // error: storage size of 'x' isn't known
A* y; // ok the size of pointer is always konwn

struct Node
{
    int val;
    Node next;
}; // error Node is not a complete type
// This essentially means that when defining the Node type, its size is still unknown

struct Node
{
    int val;
    Node* next;
}; // ok
```

I believe you might have thought that this is somewhat similar to `malloc`, and indeed it is. The difference is that `malloc` allocates memory on the heap at runtime. Direct variable declarations generally allocate memory in the data segment or on the stack. The compiler might internally maintain a symbol table that maps variable names to their addresses. When you subsequently operate on this variable, you are actually operating on this memory region.

### Built-in Operators

Built-in operators in `C` language generally correspond directly to `CPU` instructions. To understand how the `CPU` implements these operations, you can study digital electronics. Taking `x86_64` as an example, the possible correspondences are as follows:

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

Assignment might be done via the `mov` instruction, for example:

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

The size of a structure can generally be calculated from its members according to specific rules, often considering memory alignment, and is determined by the compiler. For example, [msvc](https://learn.microsoft.com/en-us/cpp/c-language/storage-and-alignment-of-structures?view=msvc-170). But in any case, the size of the structure is known at compile time, and we can also get the size of a type or variable using `sizeof`. So, the `Point point` variable definition here is easy to understand: the type size is known, and a block of memory is allocated on the stack.

Now let's focus on structure member access. In fact, the `C` language has a macro that can get the offset of a structure member relative to the structure's starting address, called `offsetof` (even if we can't get it, the compiler will calculate the field offsets, so offset information is always known to the compiler). For example, here `offsetof(Point, x)` is `0`, and `offsetof(Point, y)` is `4`. So the above code can be understood as:

```c
int main()
{
    char point[sizeof(Point)]; // 8 = sizeof(Point)
    *(int*)(point + offsetof(Point, x)) = 1; // point.x = 1
    *(int*)(point + offsetof(Point, y)) = 2; // point.y = 2
}
```

The compiler might also maintain a symbol table of field name -> offset, and the field name will eventually be replaced by the `offset`. There is no need to keep it in the program.

### Function Calls

Generally implemented through the function call stack, which is too common to elaborate on. The function name will eventually be directly replaced by the function address.

### Summary

Through the above analysis, I believe you have discovered that symbol names, type names, variable names, function names, structure field names, and other information in `C` language are all replaced by numbers, addresses, offsets, etc. The absence of these has no impact on program execution. Therefore, they are discarded to reduce the size of the binary file. For `C++`, the situation is basically similar. `C++` only retains some metadata in special cases, such as `type_info`, and you can manually choose to disable `RTTI` to ensure that this information is not generated.

So when do we need to use this information? Obviously, the `setattr` introduced at the beginning requires it. When debugging a program, we need to know the variable name, function name, member name, etc., corresponding to an address to facilitate debugging, so we need it then. When serializing a structure to `json`, we need to know its field names, so we also need this information. After type erasure to `void*`, we still need to know what its actual corresponding type is, so we also need it then. In short, whenever we need to distinguish what a string of binary content originally was at runtime, we need this information (of course, if we want to use this information for code generation at compile time, it is also needed).

## How to get this information?

`C/C++` compilers do not provide us with interfaces to obtain this information, but as mentioned earlier, this information is clearly in the source code: variable names, function names, type names, field names. We can choose to manually understand the code and then manually store the metadata. Thousands of classes, dozens of member functions, it might take a few months to write. Just kidding, or we could write some programs, such as regular expression matching, to help us get this information? However, we actually have a better option to get this information, which is through `AST`.

## AST (Abstract Syntax Tree)

`AST` is an abbreviation for `Abstract Syntax Tree`. It is a data structure in programming language processing used to represent the abstract syntactic structure of source code. An `AST` is the result of source code being processed by a `parser`. It captures the grammatical structure of the code but does not include all details, such as whitespace or comments. In an `AST`, each node represents a syntactic construct in the source code, such as variable declarations, function calls, loops, etc. These nodes are connected by parent-child and sibling relationships, forming a tree-like structure that is easier for computer programs to understand and process. If you have the `clang` compiler installed on your computer, you can use the following command to view the syntax tree of a source file:

```bash
clang -Xclang -ast-dump -fsyntax-only <your.cpp>
```

The output is as follows; I have filtered out the important information, and irrelevant parts have been removed:

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

Or, if your `vscode` has the `clangd` plugin installed, you can right-click a block of code and then right-click `show AST` to view the `AST` of that code snippet. You can see that the source code content is indeed presented to us in a tree structure. Since it is a tree, we can freely traverse the nodes of the tree and filter to get the information we want. The two examples above are visual outputs; usually, there are also direct code interfaces to obtain them. For example, `python` has a built-in `ast` module to get them, and `C++` generally obtains this content through `clang`-related tools. If you want to know how to use `clang` tools specifically, you can refer to the article: [Let's freely control C++ code with clang tools!](https://www.ykiko.me/en/articles/669360731)

If you are curious about how the compiler transforms source code into an `AST`, you can study the frontend content of compiler design.

## How to store this information?

This question sounds a bit confusing, but in reality, only `C++` programmers might need to consider it.

In fact, it's all caused by `constexpr`. Storing the information like this:

```cpp
struct FieldInfo
{
    std::string_view name;
    std::size_t offset;
    std::size_t size;
};

struct Point
{
    int x;
    int y;
};

constexpr std::array<FieldInfo, 2> fieldInfos =
{{
    {"x", offsetof(Point, x), sizeof(int)},
    {"y", offsetof(Point, y), sizeof(int)},
}};
```

means that we can query this information not only at runtime but also at compile time.

Even more, it can be stored in template parameters, allowing types to be stored as well:

```cpp
template<fixed_string name, std::size_t offset, typename Type>
struct Field{};

using FieldInfos = std::tuple
<
    Field<"x", offsetof(Point, x), int>,
    Field<"y", offsetof(Point, y), int>
>;
```

This undoubtedly gives us greater operational flexibility. So, with this information, what should we do next? In fact, we can choose to generate code based on this information. Related content can be found in other sections of this series of articles.
