---
title: 深入探索 clang（上）
date: "2025-02-04 21:00:55"
updated: "2025-02-05 05:13:00"
zhihu_article_id: "21319978959"
zhihu_url: https://zhuanlan.zhihu.com/p/21319978959
zhihu_column_id: c_1852831599382646784
zhihu_column_title: clice 开发日记
---

在上一篇关于 clice 的 [文章](https://www.ykiko.me/zh-cn/articles/13394352064) 发布后，收到的反响远超我的预期，也有很多朋友说想要参与到开发中。有这份心是好的，但是参与进来的门槛却不低，主要难点就是在于和 clang 的 API 进行交互。难在哪呢？一方面在于无论是中文还是英文社区，互联网上关于 clang 的资料相对较少（这是预期的，因为相关的需求非常少，自然而然也就没什么人讨论了）。另一方面，由于 C++ 语言本身的复杂性，有很多细节需要对语言本身有较为深入的理解然后才能理解，把理论和实现联系起来也并不那么容易。

所以我决定编写两篇关于 clang 的文章，第一篇的内容是介绍如何基于 clang 编写相关的代码生成或者静态检查工具以及对 clang AST 较为全面的介绍。第二篇则会更加深入的介绍 clang 作为编译器本身的架构，具体到各个流程的实现细节，以及 clice 是如何使用 clang 的。希望这两篇文章能扫清读者们参与到 clice 的开发中的障碍。如果你是想为 clang 做贡献或者编写 clang 工具，那么也可以继续往下阅读。

## Development environment

第一步，首先就要搭建好开发环境。clang 是 llvm 的一个子项目，而 llvm 项目的构建是由 cmake 编写的，并且相对过时，只能通过 `find_package` 的方式来引入。这就意味着我们要提前编译安装好 llvm 和 clang。一种方式是下载编译好的二进制文件，llvm 的 [release](https://github.com/llvm/llvm-project/releases) 这里就有针对各个平台的预编译包。

不过我更推荐的方式是从源码构建 Debug 版本的二进制方便进行调试开发。具体的构建方式可以在 [llvm 的官方文档](https://llvm.org/docs/CMake.html) 找到，这里不过多赘述。

通过文档不难发现，它的构建有很多参数，这里是比较容易踩坑的地方。我这里把一些比较重要的参数重点强调一下：

- `LLVM_ENABLE_PROJECTS` 是用来指定要构建除了 llvm 本身之外的哪些子项目，我们这里只需要 `clang` 就行了
- `LLVM_TARGETS_TO_BUILD` 用于指定编译器支持的目标平台，开的越多编译 llvm 时间越长，对于开发来说一般选择 `X86` 就行了
- `LLVM_BUILD_LLVM_DYLIB` 用于指定是否把 llvm 构建产物都构建为动态库，强烈推荐开启。构建为动态库之后，链接速度就会非常快，可以改善开发体验。此外，如果不打开这个选项，那么最后在调试模式下构建出来的二进制文件会非常大，可能会有上百 GB。不过遗憾的是，这个选项目前在 Windows 上的 MSVC target 下不支持，相关的工作仍然进行中，参阅 [llvm-windows-support](https://github.com/llvm/llvm-project/issues/109483)。所以推荐开发平台是 Linux 或者 Windows 上使用 MinGW 或者 WSL
- `LLVM_USE_SANITIZER` 用于指定要开启的 [sanitizer](https://clang.llvm.org/docs/AddressSanitizer.html)，该选项在 MSVC target 下也几乎不可用。

另外千万不要使用 GNU 的 ld 来链接，它的内存占用非常高，并发链接的情况下很容易爆内存。然后呢，作为参考我在 Linux 上的构建命令如下

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

构建成功的话，最后的二进制文件应该就位于 llvm 项目的 `build-debug-install` 目录下了。然后新创建一个目录用于编写工具的代码，在该目录下创建一个 `CMakeLists.txt` 文件，内容如下

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

内容很简单，就是引入 llvm 和 clang 的头文件和库文件。注意这里的 `LLVM_INSTALL_PATH` 就是你刚才安装的 llvm 路径，可以留意 `message` 函数输出的路径是否是预期的。

再创建一个 `main.cpp` 文件，内容如下

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

编译运行，预期输出应该是

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

自此，开发环境就搭建好了，可以愉快的进行 clang 的开发了。

## AST

AST（Abstract Syntax Tree，抽象语法树）是编译器在编译过程中生成的一个数据结构，用来表示源代码的语法结构。它是源代码的一个抽象层次，用于捕捉源代码的语法信息，同时去除具体的细节，比如分号、括号等。上面我们编写的小工具的作用就是编译输入的字符串文本并打印它的 AST。其实无论是静态检查工具还是代码生成工具，都是通过操作 AST 来实现的。我们需要知道如何从 AST 中筛选出我们感兴趣的节点，以及如何进一步获取节点的相关的更详细的信息。

所有 AST 节点的生命周期都是相同的，并且相互之间可能有复杂的引用关系。对于 clang AST 来说，虽然名义上叫做 Abstract Syntax Tree 是一个 Tree，但实际上是一个有环的 Graph。在这个特殊的场景下，使用内存池统一分配所有 AST 节点的内存可以大大简化节点生命周期的管理。clang 也是这么做的，所有的 AST 节点都是通过 `clang::ASTContext` 来分配的。通过 `ASTContext::getTranslationUnitDecl` 我们就可以获取到 AST 的根节点，顾名思义，也就是代表一个编译单元。

在遍历 AST 之前，我们首先需要理解 clang AST 的结构。clang 中最基本的两个节点类型是 `Decl` 和 `Stmt`，而 `Expr` 是 `Stmt` 的子类。`Decl` 代表的是声明，比如变量声明、函数声明等。`Stmt` 代表的是语句，比如赋值语句、函数调用语句等。`Expr` 代表的是表达式，比如加法表达式、函数调用表达式等。

以 `int x = (1 + 2) * 3;` 为例，它的 AST 结构如下

```bash
`-VarDecl 0x7e0b3974e710 <main.cpp:2:1, col:19> col:5 x 'int' cinit
  `-BinaryOperator 0x7e0b3974e898 <col:9, col:19> 'int' '*'
    |-ParenExpr 0x7e0b3974e848 <col:9, col:15> 'int'
    | `-BinaryOperator 0x7e0b3974e820 <col:10, col:14> 'int' '+'
    |   |-IntegerLiteral 0x7e0b3974e7d0 <col:10> 'int' 1
    |   `-IntegerLiteral 0x7e0b3974e7f8 <col:14> 'int' 2
    `-IntegerLiteral 0x7e0b3974e870 <col:19> 'int' 3
```

可以发现，还是非常清晰的，能和源代码中的语法结构一一对应起来。由于 C++ 的语法非常复杂，自然对应的节点类型也是非常多的。可以在 clang 源码目录下的 `clang/AST/DeclNodes.td` 和 `clang/AST/StmtNodes.td` 找到所有节点类型的继承图。注意是源码目录，而不是安装目录，`.td`后缀的文件是 [llvm taben gen](https://llvm.org/docs/TableGen) 语言，是一种特殊格式的配置文件，用于进行代码生成之类的工作。由于 llvm 是关闭异常和 RTTI 的，但是诸如 `dynamic_cast` 这样的类型转换在对 AST 节点进行操作的时候又是非常常见的，所以 llvm 就通过代码生成自己实现了一套类似的机制。相关的内容可以参考 [LLVM Programmer's Manual](https://llvm.org/docs/ProgrammersManual.html#the-isa-cast-and-dyn-cast-templates)。

下面对于 AST 中一些比较重要的节点和 API 进行介绍（暂时只有很少一些，之后会根据反馈进行补充）

### Cast

首先最基础也是最重要的一个操作就是节点类型的 downcast 了，如前文所述相关的操作在 llvm 中共用一套逻辑。用的最做的 API 就是 `llvm::dyn_cast` 了，例如我们想判断一个声明是不是函数声明

```cpp
void foo(clang::Decl* decl) {
    if(auto FD = llvm::dyn_cast<clang::FunctionDecl>(decl)) {
        llvm::outs() << FD->getName() << "\n";
    }
}
```

用法和 C++ 标准库的 [dynamic_cast](https://en.cppreference.com/w/cpp/language/dynamic_cast) 几乎完全一致。

### DeclContext

在 C++ 中，有一些我们可以在一些内部定义其它的声明的声明，例如

```cpp
namespace foo {

int x = 1;

}
```

这是 `foo` 就作为 `x` 的声明上下文，为了描述这种关系，在 clang 中所有能作为声明上下文的 `Decl` 都会继承 `DeclContext`。典型案例就是上面说的 `NamespaceDecl` 了。可以通过 `DeclContext::decls()` 这个成员获取上下文中所有的声明。

### Template

对于模板的处理可谓是 clang AST 中最复杂的部分了，这里做一些简略的介绍。所有未实例化的模板声明都会继承 `clang::TemplateDecl` 这个类。通过查看继承图，有如下几个类型 `ClassTemplate`, `FunctionTemplate`, `VarTemplate`, `TypeAliasTemplate`, `TemplateTemplateParm` 和 `Concept`。分别对应 C++ 标准中的类模板、函数模板、变量模板、类型别名模板、模板模板参数和概念。

欸，我有一个疑问。类模板的成员函数是如何表示的呢？

```cpp
template <typename T>
class Foo {
    void bar();
};
```

比如这里的 `bar` 在 AST 里面是什么节点。dump AST 就可以发现它是一个普通的 `CXXMethodDecl`，和普通的成员函数是一样的。实际上 `TemplateDecl` 有一个成员 `getTemplatedDecl`，可以获取到该模板类型的底层类型。其实就是把 `T` 当成一个普通类型来处理的。获取到底层声明之后一切就和普通的非模板类型一样了。只是 Parser 在解析 [dependent name](https://en.cppreference.com/w/cpp/language/dependent_name) 的时候会有一些特殊的处理。

所有模板的实例化同样在 AST 中有对应的表示，无论是显式实例化还是隐式实例化。可以通过 `getSpecializationKind` 来获取该模板实例化的类型。`TemplateSpecializationKind` 是一个枚举类型，有 `TSK_Undeclared`, `TSK_ImplicitInstantiation`, `TSK_ExplicitInstantiationDeclaration`, `TSK_ExplicitInstantiationDefinition`, `TSK_ExplicitSpecialization` 和 `TSK_ExplicitInstantiation`。分别对应未声明的实例化（模板实例化是 lazy 的）、隐式实例化、显式实例化声明、显式实例化定义、显式特化和显式实例化。

## Visitor

在对 AST 的结构有了一些基本认识后，我们就可以来遍历 AST 收集信息了。进行这一步的关键类是 `clang::RecursiveASTVisitor`。

`RecursiveASTVisitor` 是一个 [CRTP](https://en.cppreference.com/w/cpp/language/crtp) 的典型应用。它默认对整个 AST 进行深度优先遍历，并且提供了一组接口允许子类重写以改变默认行为。例如下面的代码就会遍历 AST 并且 dump 所有的函数声明。

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

关于 `RecursiveASTVisitor` 的工作原理这里就不过多介绍了，它的注释文档足够详细。简而言之，如果只是希望访问某个节点，重写 `VisitFoo`，如果想自定义遍历行为，例如过滤掉不感兴趣的节点以加快遍历速度，重写 `TraverseFoo` 就好了，其中 `Foo` 是节点的类型。

**注意，直觉上来说遍历应该是个只读操作，应该是线程安全的。但是 clang AST 在遍历的时候会对一些结果做 cache，所以多线程并发遍历同一个 AST 并不线程安全。**

## Preprocess

可以发现，在 AST 节点的定义中并没有任何和宏有关的节点。当然也没有预处理指令之类的节点。实际上 clang 的 AST 的构建是在完整的预处理之后进行的，无论是宏展开还是预处理指令都已经被处理掉了。但是如果我们想要获取相关的信息怎么办呢？

clang 为我们提供了 `PPCallback` 这个类，允许我们重写里面的相关接口来获取一些信息。

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

上面的示例的效果就是打印出所有的宏定义。`PPCallbacks` 还提供了很多其它的接口，相关的注释也较为详细，可以按需使用。

## Location

clang 会在 AST 中详细的记录节点的位置信息。表示位置信息的核心类是 `clang::SourceLocation`。为了在减少内存占用的同时能储存尽量多的信息，它本身只相当于一个 ID，大小只有 int 非常轻量。实际的位置信息则被储存在 `clang::SourceManager` 中。在需要详尽的信息的时候，需要通过 `SourceManager` 来进行解码。

通过 `ASTContext::getSourceManager` 可以获取到对应的 `SourceManager`。然后就我们可以通过如下代码 dump 出节点的位置信息

```cpp
void dump(clang::SourceManager& SM, clang::FunctionDecl* FD) {
    FD->getLocation().dump(SM);
}
```

在 `SourceManager` 的成员函数中，你会发现很多 API 的前缀都带了 spelling 或者 expansion。比如 `getSpellingLineNumber` 和 `getExpansionLineNumber`。这是什么意思呢？首先要意识到一件事，AST 中所有的 `SourceLocation` 都代表的是一个 token 开始的起始位置。而一个 token 的来源有两种，一种就是直接对应源码中的一个 token，另一种则是来自于宏展开。可以通过 `SourceLocation::isMacroID` 来判断这个 token 的位置是不是由宏展开产生的。

对于由宏展开产生的 token，clang 会跟踪它的两个信息。一个是宏展开的位置也就是 `ExpansionLocation`，另一个则展开产生该 token 的 token 的位置，也就是 `SpellingLocation`。

例如对于下述代码

```cpp
#define Self(name) name
int Self(x) = 1;
```

使用如下代码打印出变量声明的位置信息

```cpp
void dump(clang::SourceManager& SM, clang::SourceLocation location) {
    llvm::outs() << "is from macro expansion: " << location.isMacroID() << "\n";
    llvm::outs() << "expansion location: ";
    SM.getExpansionLoc(location).dump(SM);
    llvm::outs() << "spelling location: ";
    SM.getSpellingLoc(location).dump(SM);
}
```

预期输出是

```bash
is from macro expansion: 1
expansion location: main.cpp:2:5
spelling location: main.cpp:2:10
```

该变量声明中 `x` 是由宏展开产生的，所以 `isMacroID` 就是 `true`。它的 expansion location 就是宏展开的位置，也就是 `Self(x)` 的起始位置。而 spelling location 则是展开产生 `x` 的 token 的位置，也就是 `Self(x)` 中 `x` 的位置。

除此之外，根据 C++ 标准，还可以通过 [#line](https://en.cppreference.com/w/cpp/preprocessor/line) 预处理指令来改变行号和文件名，例如

```cpp
#include <string_view>

#line 10 "fake.cpp"
static_assert(__LINE__ == 10);
static_assert(__FILE__ == std::string_view("fake.cpp"));
```

这个会影响 clang 的位置记录吗？答案是肯定的。那么如果我想获取到真实的行号和文件名呢？可以通过 `getPresumedLoc` 来获取被 `#line` 指令修改过后或者没有修改过的位置信息。

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

第一个输出的就是被 `#line` 指令修改过后的位置信息，而第二个输出的就是真实的位置信息。**注意，clang 默认使用的文件编码是 UTF-8，计算 line 和 column 也是按照 UTF-8 来计算的。** 那假设我想获取到 UTF-16 编码下的 column 信息呢？实际上 vscode 默认用的就是这个，可以通过 `getDecomposedLoc` 来把 `SourceLocation` 分解为 `clang::FileID` 和相对于文件起始位置的 offset。有了 offset 之后结合源文件的文本内容，我们就可以自己根据 UTF-16 编码来计算 column 了。

既然提到了 `clang::FileID` 那我们就接着说它。它和 `SourceLocation` 类似，也是一个 ID，只不过它代表的是一个文件。我们可以通过 `getIncludeLoc` 来获取到引入该文件的位置（也就是 `#include` 当前文件的预处理指令位置）。使用 `getFileEntryRefForID` 获取到它所引用的文件的信息，包括文件名，大小等。

```cpp
void dump(clang::SourceManager& SM, clang::SourceLocation location) {
    auto [fid, offset] = SM.getDecomposedLoc(location);
    auto loc = SM.getIncludeLoc(fid);
    llvm::outs() << SM.getFileEntryRefForID(fid)->getName() << "\n";
}
```

> 一个头文件可能被包含多次，每次被包含都是一个新的 FileID，但是底层引用的是相同的文件。

## Conclusion

在理解了上面这些内容之后，读者应该不难编写一个基于 clang 的工具了，例如一个基于 clang 的反射代码生成器。

对于 clice 来说，很多的语言服务器请求都是通过遍历 AST 来完成的。例如 [SemanticTokens](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/)，它的效果是为源码中的 token 提供代码 kind 和 modifier 修饰，使得编辑器可以进一步根据主题进行高亮。

那么如何实现它呢？其实就是遍历 AST，然后根据节点类型，返回 LSP 标准中定义的 kind，比如 variable 和 function。最后在根据 token 的位置进行排序就行了。原理十分简单，剩下的内容就是处理由于 C++ 语法的复杂性所来带的很多 corner case 了。

到这里文章就结束了，感谢阅读。这里还有一些来自于 clang 官方的参考文档：

- [LibTooling](https://clang.llvm.org/docs/LibTooling.html)
- [AST Macther](https://clang.llvm.org/docs/LibASTMatchers.html)
- [Transformer](https://clang.llvm.org/docs/ClangTransformerTutorial.html)
- [Introduction to the Clang AST](https://clang.llvm.org/docs/IntroductionToTheClangAST.html)
- [Clang CFE Internals Manual](https://clang.llvm.org/docs/InternalsManual.html)
