---
title: Deep Dive into Clang (Part 1)
date: "2025-02-04 21:00:55"
updated: "2025-02-05 05:13:00"
zhihu_article_id: "21319978959"
zhihu_url: https://zhuanlan.zhihu.com/p/21319978959
zhihu_column_id: c_1852831599382646784
zhihu_column_title: clice 开发日记
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

After the [article](https://www.ykiko.me/en/articles/13394352064) about clice was published, the response I received far exceeded my expectations, and many friends expressed a desire to participate in the development. While this enthusiasm is good, the barrier to entry is not low, mainly due to the difficulty of interacting with clang's API. What makes it difficult? On the one hand, there is relatively little information about clang on the internet, whether in Chinese or English communities (this is expected, as there is very little demand for it, so naturally few people discuss it). On the other hand, due to the complexity of the C++ language itself, many details require a deeper understanding of the language before they can be grasped, and connecting theory with implementation is not easy.

Therefore, I decided to write two articles about clang. The first article will introduce how to write code generation or static analysis tools based on clang, along with a comprehensive introduction to the clang AST. The second article will delve deeper into clang's architecture as a compiler, specifically the implementation details of various processes, and how clice uses clang. I hope these two articles will remove obstacles for readers who wish to participate in clice's development. If you are interested in contributing to clang or writing clang tools, you can also continue reading.

## Development environment

The first step is to set up the development environment. clang is a subproject of LLVM, and the LLVM project's build system is written in CMake and is relatively outdated, only allowing inclusion via `find_package`. This means we need to compile and install LLVM and clang beforehand. One way is to download pre-compiled binaries; LLVM's [releases](https://github.com/llvm/llvm-project/releases) provide pre-built packages for various platforms.

However, I highly recommend building a Debug version from source for easier debugging and development. The specific build instructions can be found in the [official LLVM documentation](https://llvm.org/docs/CMake.html), which I won't elaborate on here.

From the documentation, it's clear that there are many build parameters, and this is where it's easy to run into issues. I'll highlight some of the more important parameters here:

- `LLVM_ENABLE_PROJECTS` is used to specify which subprojects, besides LLVM itself, should be built. Here, we only need `clang`.
- `LLVM_TARGETS_TO_BUILD` is used to specify the target platforms supported by the compiler. The more you enable, the longer LLVM will take to compile. For development, `X86` is usually sufficient.
- `LLVM_BUILD_LLVM_DYLIB` is used to specify whether all LLVM build artifacts should be built as dynamic libraries. This is highly recommended. Building as dynamic libraries makes linking very fast, improving the development experience. Furthermore, if this option is not enabled, the binaries built in debug mode will be very large, potentially hundreds of GBs. Unfortunately, this option is currently not supported on Windows with the MSVC target, and related work is still in progress; see [llvm-windows-support](https://github.com/llvm/llvm-project/issues/109483). Therefore, it is recommended to develop on Linux or Windows using MinGW or WSL.
- `LLVM_USE_SANITIZER` is used to specify which [sanitizer](https://clang.llvm.org/docs/AddressSanitizer.html) to enable. This option is also largely unavailable with the MSVC target.

Also, absolutely do not use GNU's `ld` for linking; its memory consumption is very high, and it can easily run out of memory during concurrent linking. As a reference, my build command on Linux is as follows:

```bash
cmake \
    -G Ninja -S ./llvm \
    -B build-debug \
    -DLLVM_USE_LINKER=lld \
    -DCMAKE_C_COMPILER=clang \
    -DCMAKE_CXX_COMPILER=clang++ \
    -DCMAKE_BUILD_TYPE=Debug \
    -DBUILD_SHARED_LIBS=ON \
    -DLLVM_TARGETS_TO_BUILD=X86 \
    -DLLVM_USE_SANITIZER=Address \
    -DLLVM_ENABLE_PROJECTS="clang" \
    -DCMAKE_INSTALL_PREFIX=./build-debug-install
```

If the build is successful, the final binaries should be located in the `build-debug-install` directory of the LLVM project. Then, create a new directory for writing your tool's code, and in that directory, create a `CMakeLists.txt` file with the following content:

```cmake
cmake_minimum_required(VERSION 3.10)

project(clang-tutorial VERSION 1.0)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

set(CMAKE_PREFIX_PATH "${LLVM_INSTALL_PATH}")
find_package(LLVM REQUIRED CONFIG)
find_package(Clang REQUIRED CONFIG)
message(STATUS "Found LLVM ${LLVM_INCLUDE_DIRS}")

add_executable(tooling main.cpp)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fno-rtti -fno-exceptions -fsanitize=address")
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -fsanitize=address")

target_include_directories(tooling PRIVATE ${LLVM_INCLUDE_DIRS})
target_link_libraries(tooling PRIVATE
    LLVMSupport
    clangAST
    clangBasic
    clangLex
    clangFrontend
    clangSerialization
    clangTooling
)
```

The content is simple: it includes LLVM and clang header and library files. Note that `LLVM_INSTALL_PATH` is the path where you just installed LLVM. You can check if the path output by the `message` function is as expected.

Next, create a `main.cpp` file with the following content:

```cpp
#include "clang/Tooling/Tooling.h"

class ToolingASTConsumer : public clang::ASTConsumer {
public:
    void HandleTranslationUnit(clang::ASTContext& context) override {
        context.getTranslationUnitDecl()->dump();
    }
};

class ToolingAction : public clang::ASTFrontendAction {
public:
    std::unique_ptr<clang::ASTConsumer>
        CreateASTConsumer(clang::CompilerInstance& instance,
                          llvm::StringRef file) override {
        return std::make_unique<ToolingASTConsumer>();
    }
};

int main() {
    const char* content = R"(
    int main() {
        return 0;
    }
)";

    bool success =
        clang::tooling::runToolOnCode(std::make_unique<ToolingAction>(),
                                      content,
                                      "main.cpp");
    return !success;
}
```

Compile and run. The expected output should be:

```bash
TranslationUnitDecl 0x7dabb8df5508 <<invalid sloc>> <invalid sloc>
|-TypedefDecl 0x7dabb8e4e238 <<invalid sloc>> <invalid sloc> implicit __int128_t '__int128'
| `-BuiltinType 0x7dabb8df5d90 '__int128'
|-TypedefDecl 0x7dabb8e4e2b0 <<invalid sloc>> <invalid sloc> implicit __uint128_t 'unsigned __int128'
| `-BuiltinType 0x7dabb8df5dc0 'unsigned __int128'
|-TypedefDecl 0x7dabb8e4e698 <<invalid sloc>> <invalid sloc> implicit __NSConstantString '__NSConstantString_tag'
| `-RecordType 0x7dabb8e4e3b0 '__NSConstantString_tag'
|   `-CXXRecord 0x7dabb8e4e310 '__NSConstantString_tag'
|-TypedefDecl 0x7dabb8df61e0 <<invalid sloc>> <invalid sloc> implicit __builtin_ms_va_list 'char *'
| `-PointerType 0x7dabb8df6190 'char *'
|   `-BuiltinType 0x7dabb8df55e0 'char'
|-TypedefDecl 0x7dabb8e4e1c0 <<invalid sloc>> <invalid sloc> implicit __builtin_va_list '__va_list_tag[1]'
| `-ConstantArrayType 0x7dabb8e4e160 '__va_list_tag[1]' 1
|   `-RecordType 0x7dabb8df62e0 '__va_list_tag'
|     `-CXXRecord 0x7dabb8df6240 '__va_list_tag'
`-FunctionDecl 0x7dabb8e4e768 <main.cpp:2:5, line:4:5> line:2:9 main 'int ()'
  `-CompoundStmt 0x7dabb8e4e8e8 <col:16, line:4:5>
    `-ReturnStmt 0x7dabb8e4e8d0 <line:3:9, col:16>
      `-IntegerLiteral 0x7dabb8e4e8a8 <col:16> 'int' 0
```

With this, the development environment is set up, and you can happily proceed with clang development.

## AST

AST (Abstract Syntax Tree) is a data structure generated by the compiler during compilation to represent the grammatical structure of source code. It is an abstract layer of the source code, used to capture its syntactic information while removing specific details like semicolons, parentheses, etc. The small tool we wrote above compiles the input string and prints its AST. In fact, both static analysis tools and code generation tools are implemented by manipulating the AST. We need to know how to filter out nodes of interest from the AST and how to further obtain more detailed information about those nodes.

All AST nodes have the same lifecycle and may have complex inter-referencing relationships. For clang AST, although it's nominally called an Abstract Syntax Tree, it's actually a cyclic Graph. In this special scenario, using a memory pool to uniformly allocate memory for all AST nodes can greatly simplify node lifecycle management. clang also does this; all AST nodes are allocated via `clang::ASTContext`. Through `ASTContext::getTranslationUnitDecl`, we can obtain the root node of the AST, which, as the name suggests, represents a translation unit.

Before traversing the AST, we first need to understand the structure of the clang AST. The two most basic node types in clang are `Decl` and `Stmt`, with `Expr` being a subclass of `Stmt`. `Decl` represents declarations, such as variable declarations, function declarations, etc. `Stmt` represents statements, such as assignment statements, function call statements, etc. `Expr` represents expressions, such as addition expressions, function call expressions, etc.

Taking `int x = (1 + 2) * 3;` as an example, its AST structure is as follows:

```bash
`-VarDecl 0x7e0b3974e710 <main.cpp:2:1, col:19> col:5 x 'int' cinit
  `-BinaryOperator 0x7e0b3974e898 <col:9, col:19> 'int' '*'
    |-ParenExpr 0x7e0b3974e848 <col:9, col:15> 'int'
    | `-BinaryOperator 0x7e0b3974e820 <col:10, col:14> 'int' '+'
    |   |-IntegerLiteral 0x7e0b3974e7d0 <col:10> 'int' 1
    |   `-IntegerLiteral 0x7e0b3974e7f8 <col:14> 'int' 2
    `-IntegerLiteral 0x7e0b3974e870 <col:19> 'int' 3
```

As you can see, it's very clear and corresponds directly to the grammatical structure in the source code. Due to the complexity of C++ syntax, there are naturally many corresponding node types. You can find the inheritance graph of all node types in the clang source directory under `clang/AST/DeclNodes.td` and `clang/AST/StmtNodes.td`. Note that this is the source directory, not the installation directory. Files with the `.td` suffix are [LLVM TableGen](https://llvm.org/docs/TableGen) language, a special configuration file format used for code generation and similar tasks. Since LLVM disables exceptions and RTTI, but type conversions like `dynamic_cast` are very common when operating on AST nodes, LLVM implements its own similar mechanism through code generation. For related content, refer to the [LLVM Programmer's Manual](https://llvm.org/docs/ProgrammersManual.html#the-isa-cast-and-dyn-cast-templates).

Below, I will introduce some of the more important nodes and APIs in the AST (currently only a few, more will be added based on feedback).

### Cast

First, the most basic and important operation is downcasting node types. As mentioned earlier, related operations in LLVM share a common logic. The most commonly used API is `llvm::dyn_cast`. For example, if we want to check if a declaration is a function declaration:

```cpp
void foo(clang::Decl* decl) {
    if(auto FD = llvm::dyn_cast<clang::FunctionDecl>(decl)) {
        llvm::outs() << FD->getName() << "\n";
    }
}
```

Its usage is almost identical to C++ standard library's [dynamic_cast](https://en.cppreference.com/w/cpp/language/dynamic_cast).

### DeclContext

In C++, there are declarations where we can define other declarations internally, for example:

```cpp
namespace foo {

int x = 1;

}
```

Here, `foo` acts as the declaration context for `x`. To describe this relationship, in clang, all `Decl`s that can serve as a declaration context inherit from `DeclContext`. A typical example is the `NamespaceDecl` mentioned above. You can get all declarations within the context using the `DeclContext::decls()` member.

### Template

Handling templates is arguably the most complex part of the clang AST. Here's a brief introduction. All uninstantiated template declarations inherit from the `clang::TemplateDecl` class. By looking at the inheritance graph, there are types such as `ClassTemplate`, `FunctionTemplate`, `VarTemplate`, `TypeAliasTemplate`, `TemplateTemplateParm`, and `Concept`. These correspond to class templates, function templates, variable templates, type alias templates, template template parameters, and concepts in the C++ standard, respectively.

Wait, I have a question. How are member functions of class templates represented?

```cpp
template <typename T>
class Foo {
    void bar();
};
```

For example, what node is `bar` in the AST here? Dumping the AST reveals it's a regular `CXXMethodDecl`, just like ordinary member functions. In fact, `TemplateDecl` has a member `getTemplatedDecl`, which can retrieve the underlying type of the template. It essentially treats `T` as a normal type. Once the underlying declaration is obtained, everything is the same as with ordinary non-template types. The Parser only has some special handling when parsing [dependent names](https://en.cppreference.com/w/cpp/language/dependent_name).

All template instantiations are also represented in the AST, whether explicit or implicit. You can use `getSpecializationKind` to get the type of template instantiation. `TemplateSpecializationKind` is an enumeration type with `TSK_Undeclared`, `TSK_ImplicitInstantiation`, `TSK_ExplicitInstantiationDeclaration`, `TSK_ExplicitInstantiationDefinition`, `TSK_ExplicitSpecialization`, and `TSK_ExplicitInstantiation`. These correspond to undeclared instantiation (template instantiation is lazy), implicit instantiation, explicit instantiation declaration, explicit instantiation definition, explicit specialization, and explicit instantiation, respectively.

## Visitor

After gaining some basic understanding of the AST structure, we can now traverse the AST to collect information. The key class for this step is `clang::RecursiveASTVisitor`.

`RecursiveASTVisitor` is a typical application of [CRTP](https://en.cppreference.com/w/cpp/language/crtp). It performs a depth-first traversal of the entire AST by default and provides a set of interfaces that subclasses can override to change the default behavior. For example, the following code will traverse the AST and dump all function declarations.

```cpp
#include "clang/Tooling/Tooling.h"
#include "clang/AST/RecursiveASTVisitor.h"

class ToolingASTVisitor : public clang::RecursiveASTVisitor<ToolingASTVisitor> {
public:
    bool VisitFunctionDecl(clang::FunctionDecl* FD) {
        FD->dump();
        return true;
    }
};

class ToolingASTConsumer : public clang::ASTConsumer {
public:
    void HandleTranslationUnit(clang::ASTContext& context) override {
        ToolingASTVisitor visitor;
        visitor.TraverseAST(context);
    }
};
```

I won't go into too much detail about the working principle of `RecursiveASTVisitor` here; its documentation comments are sufficiently detailed. In short, if you only want to visit a certain node, override `VisitFoo`; if you want to customize the traversal behavior, for example, to filter out uninteresting nodes to speed up traversal, just override `TraverseFoo`, where `Foo` is the node type.

**Note that intuitively, traversal should be a read-only operation and thus thread-safe. However, clang AST caches some results during traversal, so concurrent multi-threaded traversal of the same AST is not thread-safe.**

## Preprocess

As you can see, there are no macro-related nodes in the AST node definitions. Nor are there any preprocessor directive nodes. In fact, clang's AST is built after complete preprocessing; both macro expansion and preprocessor directives have already been processed. But what if we want to get related information?

clang provides us with the `PPCallbacks` class, which allows us to override its relevant interfaces to obtain some information.

```cpp
#include "clang/Tooling/Tooling.h"
#include "clang/AST/RecursiveASTVisitor.h"

class ToolingPPCallbacks : public clang::PPCallbacks {
public:
    void MacroDefined(const clang::Token& MacroNameTok,
                      const clang::MacroDirective* MD) override {
        llvm::outs() << "MacroDefined: "
                     << MacroNameTok.getIdentifierInfo()->getName() << "\n";
    }
};

class ToolingAction : public clang::ASTFrontendAction {
public:
    std::unique_ptr<clang::ASTConsumer>
        CreateASTConsumer(clang::CompilerInstance& instance,
                          llvm::StringRef file) override {
        return std::make_unique<ToolingASTConsumer>();
    }

    bool BeginSourceFileAction(clang::CompilerInstance& instance) override {
        llvm::outs() << "BeginSourceFileAction\n";
        instance.getPreprocessor().addPPCallbacks(
            std::make_unique<ToolingPPCallbacks>());
        return true;
    }
};
```

The example above prints all macro definitions. `PPCallbacks` also provides many other interfaces, and the related comments are quite detailed, so you can use them as needed.

## Location

clang records detailed location information for nodes in the AST. The core class for representing location information is `clang::SourceLocation`. To store as much information as possible while reducing memory usage, it itself is just an ID, with the size of an `int`, making it very lightweight. The actual location information is stored in `clang::SourceManager`. When detailed information is needed, it must be decoded via `SourceManager`.

You can get the corresponding `SourceManager` via `ASTContext::getSourceManager`. Then we can dump the node's location information with the following code:

```cpp
void dump(clang::SourceManager& SM, clang::FunctionDecl* FD) {
    FD->getLocation().dump(SM);
}
```

Among the member functions of `SourceManager`, you will find many APIs prefixed with `spelling` or `expansion`. For example, `getSpellingLineNumber` and `getExpansionLineNumber`. What do these mean? First, it's important to realize that all `SourceLocation`s in the AST represent the starting position of a token. A token can originate in two ways: either directly corresponding to a token in the source code, or from a macro expansion. You can use `SourceLocation::isMacroID` to determine if a token's location is generated by a macro expansion.

For tokens generated by macro expansion, clang tracks two pieces of information: the location of the macro expansion, which is `ExpansionLocation`, and the location of the token that produced this expanded token, which is `SpellingLocation`.

For example, consider the following code:

```cpp
#define Self(name) name
int Self(x) = 1;
```

Using the following code to print the location information of the variable declaration:

```cpp
void dump(clang::SourceManager& SM, clang::SourceLocation location) {
    llvm::outs() << "is from macro expansion: " << location.isMacroID() << "\n";
    llvm::outs() << "expansion location: ";
    SM.getExpansionLoc(location).dump(SM);
    llvm::outs() << "spelling location: ";
    SM.getSpellingLoc(location).dump(SM);
}
```

The expected output is:

```bash
is from macro expansion: 1
expansion location: main.cpp:2:5
spelling location: main.cpp:2:10
```

In this variable declaration, `x` is generated by a macro expansion, so `isMacroID` is `true`. Its expansion location is the position of the macro expansion, which is the starting position of `Self(x)`. The spelling location, on the other hand, is the position of the token that produced `x` during expansion, which is the position of `x` within `Self(x)`.

In addition, according to the C++ standard, the [#line](https://en.cppreference.com/w/cpp/preprocessor/line) preprocessor directive can be used to change line numbers and filenames, for example:

```cpp
#include <string_view>

#line 10 "fake.cpp"
static_assert(__LINE__ == 10);
static_assert(__FILE__ == std::string_view("fake.cpp"));
```

Does this affect clang's location recording? The answer is yes. So, what if I want to get the real line number and filename? You can use `getPresumedLoc` to get the location information, whether modified by `#line` directives or not.

```cpp
void dump(clang::SourceManager& SM, clang::SourceLocation location) {
    /// The second argument determines whether the location is modified by
    /// `#line` directives.
    auto loc = SM.getPresumedLoc(location, true);
    llvm::outs() << loc.getFilename() << ":" << loc.getLine() << ":"
                 << loc.getColumn() << "\n";

    loc = SM.getPresumedLoc(location, false);
    llvm::outs() << loc.getFilename() << ":" << loc.getLine() << ":"
                 << loc.getColumn() << "\n";
}
```

The first output is the location information modified by the `#line` directive, while the second output is the real location information. **Note that clang uses UTF-8 as the default file encoding, and line and column calculations are also based on UTF-8.** What if I want to get the column information in UTF-16 encoding? VS Code actually uses this by default. You can use `getDecomposedLoc` to decompose `SourceLocation` into a `clang::FileID` and an offset relative to the start of the file. With the offset and the source file's text content, we can then calculate the column ourselves based on UTF-16 encoding.

Since `clang::FileID` was mentioned, let's continue with it. Like `SourceLocation`, it is also an ID, but it represents a file. We can use `getIncludeLoc` to get the location where the file was included (i.e., the position of the `#include` directive for the current file). Use `getFileEntryRefForID` to get information about the file it refers to, including its name, size, etc.

```cpp
void dump(clang::SourceManager& SM, clang::SourceLocation location) {
    auto [fid, offset] = SM.getDecomposedLoc(location);
    auto loc = SM.getIncludeLoc(fid);
    llvm::outs() << SM.getFileEntryRefForID(fid)->getName() << "\n";
}
```

> A header file might be included multiple times. Each inclusion results in a new `FileID`, but they all refer to the same underlying file.

## Conclusion

After understanding the above content, readers should find it easy to write a clang-based tool, such as a clang-based reflection code generator.

For clice, many language server requests are fulfilled by traversing the AST. For example, [SemanticTokens](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/), which provides code kind and modifier decorations for tokens in the source code, allowing editors to further highlight them based on themes.

How is this implemented? It's simply by traversing the AST and, based on the node type, returning the kind defined in the LSP standard, such as `variable` and `function`. Finally, the tokens are sorted by their position. The principle is very simple; the remaining task is to handle the many corner cases arising from the complexity of C++ syntax.

This concludes the article. Thank you for reading. Here are some additional reference documents from the official clang documentation:

- [LibTooling](https://clang.llvm.org/docs/LibTooling.html)
- [AST Matcher](https://clang.llvm.org/docs/LibASTMatchers.html)
- [Transformer](https://clang.llvm.org/docs/ClangTransformerTutorial.html)
- [Introduction to the Clang AST](https://clang.llvm.org/docs/IntroductionToTheClangAST.html)
- [Clang CFE Internals Manual](https://clang.llvm.org/docs/InternalsManual.html)
