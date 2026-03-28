---
title: Reflection for C++26!!!
date: "2025-06-22 01:33:11"
updated: "2026-03-29 03:47:32"
zhihu_article_id: "1919923607997518115"
zhihu_url: https://zhuanlan.zhihu.com/p/1919923607997518115
zhihu_column_id: c_1707545619290316800
zhihu_column_title: 编程语言中的反射
---

在昨天刚才结束的 C++26 Sofia 会议上，有关**静态反射 (Static Reflection)** 的七个提案：

- [Reflection for C++26](https://isocpp.org/files/papers/P2996R13.html)
- [Function Parameter Reflection](https://isocpp.org/files/papers/P3096R12.pdf)
- [Annotations for Reflection](https://isocpp.org/files/papers/P3394R4.html)
- [Splicing a base class subobject](https://isocpp.org/files/papers/P3293R3.html)
- [Expansion Statements](https://isocpp.org/files/papers/P1306R5.html)
- [`define_static_{string,object,array}`](https://isocpp.org/files/papers/P3491R3.html)
- [Error Handling in Reflection](https://isocpp.org/files/papers/P3560R2.html)

全都通过了 plenary 得以被**正式纳入 C++26 标准**，这是一个令人激动的时刻。在我看来，静态反射无疑是 20 年来 C++ 最重要的一个新特性。它彻底改变了以前使用模板进行元编程的模式，让**元编程 (meta programming)** 的代码可以像普通的代码逻辑一样易于阅读、编写、使用，而不再是以前基于模板的 DSL。

在一年多前，P2996R1 的时候我就编写过一篇 [文章](https://www.ykiko.me/zh-cn/articles/661692275) 来介绍静态反射这个令人激动的提案。过了这么久，静态反射提案本身的内容有了较大的改变，上面文章的内容已经过时了，而且还新增了很多的附属提案。所以我决定编写一篇新文章来介绍静态反射及其附属提案的内容。

> 如果想体验静态反射，有两种方式，一种是通过 [Compiler Explorer](https://godbolt.org/z/1977T9GfP) 这个在线编辑器，把上面的编译器调成 P2996 Clang 就行了。另外一种是自己编译 [https://github.com/bloomberg/clang-p2996/tree/p2996](https://github.com/bloomberg/clang-p2996/tree/p2996) 这个 P2996 分支的 Clang 和 libc++。然后，参考 [use libc++](https://releases.llvm.org/16.0.0/projects/libcxx/docs/UsingLibcxx.html#id4) 这个页面，在编译的时候使用刚编译出的 libc++ 作为标准库，就可以本地使用了，记得要开启 C++26 标准。

## What is Static Reflection?

首先反射是指什么呢？这个词就像计算机科学领域很多其他的惯用词一样，并没有详细而准确的定义。关于这个问题，我的反射专栏进行了较多的讨论，感兴趣的读者可以自行阅读，本文的重点是 C++ 的 static reflection。为什么强调 static 呢？主要是因为平常我们谈论到反射的时候几乎总是指 Java，C#，Python 这些语言中的反射，而它们的实现方式无一不是把类型擦除，在运行期进行元信息的查询。这种方式当然有不可避免的运行时开销，而这种开销显然是违背了 C++ zero cost abstraction 的原则的。为了和它们的反射区分开来，故加上 static 作为限定词，也指示了 C++ 的反射是在**编译期**完成的。

## Everything as Value

静态反射引入了两种新的语法，可以用**反射运算符 (reflection operator)**: `^^` 将绝大多数 name entity 映射到 `std::meta::info`

```cpp
constexpr std::meta::info rint = ^^int;
```

`std::meta::info` 是一种新的、特殊的、`consteval only` 的 builtin 类型。它**只能存在于编译期**，你可以把它当成编译器中对这个 name entity 的 handle，后续可以基于这个不透明的 handle 做一些其他的操作。

具体来说 `^^` 支持下面四种 name entity，

- `::`：全局命名空间
- `namespace-name`：普通命名空间
- `type-id`：类型
- `id-expression`：绝大多数具有名字的东西，比如变量，静态成员变量，字段，函数，模板，枚举等

那怎么用这个 `handle` 还原回去呢？欸，可以的，使用**拼接器 (splicer)**：`[: :]` 将 `std::meta::info` 还原回 name entity。

例如

```cpp
constexpr std::meta::info rint = ^^int;
using int2 = [:rint:];
```

使用 `[:rint:]` 就将 `rint` 映射回了 `int` 类型，对于其他的 name entity 也是类似的，使用 `[:rint:]` 可以将它们映射回去。注意在**某些**可能造成歧义的上下文中需要在 `[: :]` 前面加上 `typename` 或者 `template` 关键字来消除歧义。

> 需要消歧义的地方基本上还是 dependent name 的情况，也就是说当 `r` 是模板参数的时候，没法直接确定 `[:r:]` 是表达式，还是类型，还是模板，所以要手动来消除歧义。

总结一下，静态反射引入了两种新的运算符，`^^` 用于获取 name entity 的 `handle`，`[: :]` 用于把 `handle` 映射回对应的 name entity。

## Meta Function

我们都知道，仅仅获取一个 handle 并没有什么用，关键在于基于 handle 的一些操作。例如获取了一个文件的 handle，可以基于这个 handle 读取内容或者关闭文件什么的。在静态反射中，对这些 handle 的操作就是**元函数 (meta function)**。在 `<meta>` 头文件中，提供了一组非常广泛的函数用于操作这些 handle。下面对其中一些非常常用的元函数进行介绍

> 反射目前使用编译期的异常来处理元函数中遇到的错误

### members

```cpp
namespace std::meta {
    consteval vector<info> members_of(info r, access_context ctx);
    consteval vector<info> bases_of(info type, access_context ctx);
    consteval vector<info> static_data_members_of(info type, access_context ctx);
    consteval vector<info> nonstatic_data_members_of(info type, access_context ctx);
    consteval vector<info> enumerators_of(info type_enum);

    consteval bool has_parent(info r);
    consteval info parent_of(info r);
}
```

在**序列化 (serialization)** 和**反序列化 (deserialization)** 中的一个常见诉求就是获取到某个 struct 的 members，然后递归进行序列化。在静态反射之前，我们只能通过各种 hack 的方式来做到这一点，而且并不完美。例如 [reflect-C++](https://github.com/getml/reflect-cpp) 支持 C++20 下获取**聚合类 (aggregate class)** 的数据成员 和 [magic-enum](https://github.com/Neargye/magic_enum) 支持枚举值在 `[-127, 128]` 范围内的枚举成员。实现方式非常的 hack 而且对编译器不友好，实例化大量模板导致编译速度降低，而且限制也很多。

现在在静态反射中，我们可以轻松的利用这几个元函数来获取命名空间或者类型的成员，而且不仅限于**数据成员**，**成员函数**和别名之类的成员也可以轻松获取，还可以获取**基类**信息，这在之前无论如何也是做不到的。也支持反向操作，通过 `parent_of` 获取某个成员的 parent，也就是定义这个 entity 的 namespace, class 或者 function。

```cpp
struct Point {
    int x;
    int y;
};

int main() {
    Point p = {1, 2};
    constexpr auto no_check = meta::access_context::unchecked();
    constexpr auto rx = meta::nonstatic_data_members_of(^^Point, no_check)[0];
    constexpr auto ry = meta::nonstatic_data_members_of(^^Point, no_check)[1];

    p.[:rx:] = 3;
    p.[:ry:] = 4;

    std::println("p: {}, {}", p.x, p.y);
}
```

输出 `p: 3, 4`，成功通过反射访问成员！

> `access_context` 参数用于控制访问权限，它决定了我们是否能「看到」私有或保护成员，`unchecked()` 则代表拥有完全的访问权限，也就是说不进行任何访问检查。除了 `unchecked` 以外还有 `current` 表示使用当前作用域的访问权限，以及 `unprivileged` 只能访问非私有成员。上述获取成员的元函数会根据 access_context 对返回结果进行过滤。

### identifiers

```cpp
namespace std::meta {
    consteval bool has_identifier(info r);

    consteval string_view identifier_of(info r);
    consteval u8string_view u8identifier_of(info r);

    consteval string_view display_string_of(info r);
    consteval u8string_view u8display_string_of(info r);

    consteval source_location source_location_of(info r);
}
```

这个功能也是 C++ 程序员心心念念已久的功能了，获取变量名，函数名，字段名。

```cpp
constexpr auto rx = meta::nonstatic_data_members_of(^^Point, no_check)[0];
constexpr auto ry = meta::nonstatic_data_members_of(^^Point, no_check)[1];

static_assert(meta::identifier_of(rx) == "x");
static_assert(meta::identifier_of(ry) == "y");
```

这样在序列化到 json 这样需要字段名的格式的时候也很简单了。`identifier_of` 一般**只能用于**拥有简单名字的 entity，并且直接返回这个 named entity 的不带**限定符 (qualifier)** 的名字。而 `display_string_of` 则可能更倾向于返回带全称限定的名字，比如它的命名空间前缀，也可以用于处理 `vector<int>` 这样的模板特化。`source_location_of` 则进一步突破了 C++20 加的 `std::source_location::current()` 只能获取当前源码位置的限制。

### offsets

```cpp
namespace std::meta {
    struct member_offset {
        ptrdiff_t bytes;
        ptrdiff_t bits;

        constexpr ptrdiff_t total_bits() const {
            return CHAR_BIT * bytes + bits;
        }

        auto operator<=>(const member_offset&) const = default;
    };

    consteval member_offset offset_of(info r);
    consteval size_t size_of(info r);
    consteval size_t alignment_of(info r);
    consteval size_t bit_size_of(info r);
}
```

`offset_of` 返回给定字段 offset 信息，由两部分构成：字节数 `bytes` 和位数 `bits`，用 `total_bits` 就可以获取具体的偏移了。这样设计的主要是考虑到字段可能是位域，偏移量不一定就是字节数。`size_of` 和 `alignment_of` 顾名思义就是获取 size 和 alignment。而 `bit_size_of` 则是获取位域的大小。

通过这一组元函数，也不再需要通过各种 hack 的手段获取字段偏移量了，比如 `bit_cast` 成员指针来根据 ABI 细节获取到偏移量。在某些二进制序列化的场景是十分有用的。

### type operations

接下来是有关 type 的操作了，这些操作就是简化模板元编程的关键所在。在这之前，由于类型只能作为模板参数，我们不得不基于丑陋的模板 DSL 来对类型做计算。一个纯函数式，没有变量，通过模板特化来表示分支，通过模板递归来表示循环的丑陋的 DSL，这也是模板元编程长期被人所诟病的原因。现在有了静态反射，我们可以把类型映射到值，只需要对值进行操作，普通的编写 consteval 函数就好了，和正常的代码逻辑没什么区别，只是 handle 变成了 `std::meta::info`。

首先这里要谈谈 `std::meta::info` 的相等性，考虑如下代码

```cpp
using int1 = int;
constexpr auto rint = ^^int;
constexpr auto rint1 = ^^int1;
```

这里的 `rint` 和 `rint1` 应该相等吗？毫无疑问它们表示相同的**类型**，但是前面我们说过，`std::meta::info` 是一个编译器内部表示的 `handle`，显然编译器会单独的跟踪类型别名的信息，所以 `rint` 和 `rint1` 其实是不同的 name entity 的 handle，那么它们**不相等**。关于判断两个 `std::meta::info` 是否相等的完整规则这里就略去了，有一些其他的 case 需要考虑，具体的细节可以之后去 cppreference 或者标准草案上查阅。对于本文的例子，理解上述这个别名的例子就足够了。

```cpp
namespace std::meta {
    consteval auto type_of(info r) -> info;
    consteval auto dealias(info r) -> info;
}
```

可以使用 `type_of` 来获取结构体字段等 typed entity 的类型，使用 `dealias` 获取一个别名的底层 entity，例如类型别名和命名空间别名原本的 entity，这个过程是**递归**的，会解开所有的别名。

例如

```cpp
using X = int;
using Y = X;
static_assert(^^int == dealias(^^Y));
```

原本定义在 `<type_traits>` 头文件中的**模板形式**的 trait 现在都在 `<meta>` 中有了对应的反射版本，命名规则是把后缀从 `_v` 改成 `_type`，例如 `is_same_v` 就变成了 `is_same_type`，`_t` 后缀则是直接删去后缀

这部分函数太多了，下面列出**一些**作为示例

```cpp
namespace std::meta {
    consteval info remove_const(info type);
    consteval info remove_volatile(info type);
    consteval info remove_cv(info type);
    consteval info add_const(info type);
    consteval info add_volatile(info type);
    consteval info add_cv(info type);

    consteval info remove_pointer(info type);
    consteval info add_pointer(info type);

    consteval info remove_cvref(info type);
    consteval info decay(info type);
}
```

所以现在可以方便的把以前的 `type_traits` 版本的处理，等价的换成反射的版本了。代码会好理解很多，在文章的最后我会给出几个这样的案例。

### template arguments

除了上述对类型的操作以外，现在我们也能方便的对模板进行操作了

```cpp
namespace std::meta {
    consteval info template_of(info r);
    consteval vector<info> template_arguments_of(info r);

    template <reflection_range R = initializer_list<info>>
    consteval bool can_substitute(info templ, R&& arguments);

    template <reflection_range R = initializer_list<info>>
    consteval info substitute(info templ, R&& arguments);
}
```

假设 `r` 是一个**模板特化 (template specialization)**，`template_of` 返回它的模板，`template_arguments_of` 返回它的模板参数。`substitute` 则是根据给定的模板和参数，返回替换结果的模板特化的反射（不触发实例化）。通过这组函数，我们不再需要通过偏特化的方式来萃取模板特化的模板参数，轻而易举就可以拿到参数列表了。

还可以通过它们编写一个 `is_specialization_of` 用来判断某个类型是不是某个模板的特化，而这在以前无论如何是做不到的

```cpp
consteval bool is_specialization_of(info templ, info type) {
    return templ == template_of(dealias(type));
}
```

> 为什么之前做不到这一点呢？这是因为模板参数可以是类型 (typename)，值 (auto)，模板模板参数 (template)，而你没法穷举出这三种参数的所有组合，这样的话在编写 `is_specialization_of` 的时候里面待判断的模板签名就是固定的了。假设是 `<typename T, template<typename...> HKT>` ，这样 `HKT` 就只能填入类型模板参数，比如 `std::array` 它就处理不了了。

### reflect value

```cpp
namespace std::meta {
    template<typename T>
    consteval auto reflect_constant(const T& expr) -> info;

    template<typename T>
    consteval auto reflect_object(T& expr) -> info;

    template<typename T>
    consteval auto reflect_function(T& expr) -> info;

    template<typename T>
    consteval auto extract(info) -> T;
}
```

这些元函数产生一个所提供表达式的**求值结果**的反射。这类反射最常见的用例之一是作为 `std::meta::substitute` 的参数，用来构建一个**模板特化 (specialization)**。

`reflect_constant(expr)` 等价于下面的代码

```cpp
template <auto P>
struct C {};
```

那么有

```cpp
static_assert(reflect_constant(V) == template_arguments_of(^^C<V>)[0]);
constexpr auto rarray5 = substitute(^^std::array, {^^int, std::meta::reflect_constant(5)});
static_assert(rarray5 == ^^std::array<int, 5>);
```

`reflect_object(expr)` 产生一个由 expr 所指代的对象的反射。这经常被用来获取一个子对象的反射，然后该反射可以被用作一个引用类型的非类型模板参数。

```cpp
template <int &> void fn();

int p[2];
constexpr auto r = substitute(^^fn, {std::meta::reflect_object(p[1])});
```

`reflect_function(expr)` 产生一个由 expr 所指代的函数的反射。当只有一个函数的引用可用时，它对于反射该函数的属性非常有用。

```cpp
consteval bool is_global_with_external_linkage(void(*fn)()) {
    std::meta::info rfn = std::meta::reflect_function(*fn);
    return (has_external_linkage(rfn) && parent_of(rfn) == ^^::);
}
```

`extract` 则是上述 `reflect_xxx` 系列的反向操作，可以用于把一个 value 的反射，还原到对应的 C++ 中的值

- 如果 `r` 是一个值的反射，`extract<ValueType>(r)` 返回该值
- 如果 `r` 是一个对象的反射，`extract<ObjectType&>(r)` 返回该对象的引用
- 如果 `r` 是一个函数的反射，`extract<FuncPtrType>(r)` 返回该函数的指针
- 如果 `r` 是一个非静态成员的反射，`extract<MemberPtrType>(r)` 返回成员指针

### define aggregate

```cpp
namespace std::meta {
    struct data_member_options {
        struct name_type {
            template <typename T> requires constructible_from<u8string, T>
            consteval name_type(T &&);

            template <typename T> requires constructible_from<string, T>
            consteval name_type(T &&);
        };

        optional<name_type> name;
        optional<int> alignment;
        optional<int> bit_width;
        bool no_unique_address = false;
    };

    consteval auto data_member_spec(info type,
                                  data_member_options options) -> info;
    template <reflection_range R = initializer_list<info>>
    consteval auto define_aggregate(info type_class, R&&) -> info;
}
```

可以用 `define_aggregate` 给一个不完整的类型生成成员定义，这对于实现 `tuple` 或者 `variant` 这样的可变成员数量的类型很有用，例如

```cpp
union U;
consteval {
    define_aggregate(^^U, {
        data_member_spec(^^int),
        data_member_spec(^^char),
        data_member_spec(^^double),
    });
}
```

相当于

```cpp
union U {
    int _0;
    char _1;
    double _2;
};
```

这样就可以方便的实现一个 `variant` 类型而无需任何模板递归实例化了。

### other functions

除了上面列出的这些函数以外，还有非常多的函数用于查询 `r` 的某些特性，基本上是见名知义，仅列出

```cpp
consteval auto is_public(info r) -> bool;
consteval auto is_protected(info r) -> bool;
consteval auto is_private(info r) -> bool;
consteval auto is_virtual(info r) -> bool;
consteval auto is_pure_virtual(info r) -> bool;
consteval auto is_override(info r) -> bool;
consteval auto is_final(info r) -> bool;
consteval auto is_deleted(info r) -> bool;
consteval auto is_defaulted(info r) -> bool;
consteval auto is_explicit(info r) -> bool;
consteval auto is_noexcept(info r) -> bool;
consteval auto is_bit_field(info r) -> bool;
consteval auto is_enumerator(info r) -> bool;
consteval auto is_const(info r) -> bool;
consteval auto is_volatile(info r) -> bool;
consteval auto is_mutable_member(info r) -> bool;
consteval auto is_lvalue_reference_qualified(info r) -> bool;
consteval auto is_rvalue_reference_qualified(info r) -> bool;
consteval auto has_static_storage_duration(info r) -> bool;
consteval auto has_thread_storage_duration(info r) -> bool;
consteval auto has_automatic_storage_duration(info r) -> bool;
consteval auto has_internal_linkage(info r) -> bool;
consteval auto has_module_linkage(info r) -> bool;
consteval auto has_external_linkage(info r) -> bool;
consteval auto has_linkage(info r) -> bool;
consteval auto is_class_member(info r) -> bool;
consteval auto is_namespace_member(info r) -> bool;
consteval auto is_nonstatic_data_member(info r) -> bool;
consteval auto is_static_member(info r) -> bool;
consteval auto is_base(info r) -> bool;
consteval auto is_data_member_spec(info r) -> bool;
consteval auto is_namespace(info r) -> bool;
consteval auto is_function(info r) -> bool;
consteval auto is_variable(info r) -> bool;
consteval auto is_type(info r) -> bool;
consteval auto is_type_alias(info r) -> bool;
consteval auto is_namespace_alias(info r) -> bool;
consteval auto is_complete_type(info r) -> bool;
consteval auto is_enumerable_type(info r) -> bool;
consteval auto is_template(info r) -> bool;
consteval auto is_function_template(info r) -> bool;
consteval auto is_variable_template(info r) -> bool;
consteval auto is_class_template(info r) -> bool;
consteval auto is_alias_template(info r) -> bool;
consteval auto is_conversion_function_template(info r) -> bool;
consteval auto is_operator_function_template(info r) -> bool;
consteval auto is_literal_operator_template(info r) -> bool;
consteval auto is_constructor_template(info r) -> bool;
consteval auto is_concept(info r) -> bool;
consteval auto is_structured_binding(info r) -> bool;
consteval auto is_value(info r) -> bool;
consteval auto is_object(info r) -> bool;
consteval auto has_template_arguments(info r) -> bool;
consteval auto has_default_member_initializer(info r) -> bool;

consteval auto is_special_member_function(info r) -> bool;
consteval auto is_conversion_function(info r) -> bool;
consteval auto is_operator_function(info r) -> bool;
consteval auto is_literal_operator(info r) -> bool;
consteval auto is_constructor(info r) -> bool;
consteval auto is_default_constructor(info r) -> bool;
consteval auto is_copy_constructor(info r) -> bool;
consteval auto is_move_constructor(info r) -> bool;
consteval auto is_assignment(info r) -> bool;
consteval auto is_copy_assignment(info r) -> bool;
consteval auto is_move_assignment(info r) -> bool;
consteval auto is_destructor(info r) -> bool;
consteval auto is_user_provided(info r) -> bool;
consteval auto is_user_declared(info r) -> bool;
```

可以看出可以查询的信息非常多，包括**储存期 (storage class)** 和 **链接 (linkage)**，乃至 `user_declared` 和 `user_provided` 这样的信息。

## Function Reflection

上面介绍了反射主体提案的内容，没有涉及的函数参数反射的部分，也就是说你没法获取到诸如函数参数名这样的信息。但是这个信息在某些场景比如在 pybind11 将 C++ 函数绑定到 Python 中还是非常有用的。P3096R12 允许引入了如下的元函数从而对允许反射函数参数

```cpp
namespace std::meta {
    consteval vector<info> parameters_of(info r);
    consteval info variable_of(info r);
    consteval info return_type_of(info r);
}
```

如果 `r` 是**函数**或者**函数类型**的反射，那么 `return_type_of` 返回它的返回值类型的反射，`parameters_of` 返回它的函数参数的反射。例如

```cpp
void foo(int x, float y);

constexpr auto param0 = meta::parameters_of(^^foo)[0];
static_assert(identifier_of(param0) == "x");
static_assert(type_of(param0) == ^^int);

constexpr auto param1 = meta::parameters_of(^^foo)[1];
static_assert(identifier_of(param1) == "y");
static_assert(type_of(param1) == ^^float);

static_assert(return_type_of(^^foo) == ^^void);
```

欸，既然这样都已经能获取参数名和参数类型了，`variable_of` 有什么用呢？`variable_of` **只能在被反射的函数内部**使用，用于获取函数定义中该函数参数对应的变量的反射，例如

```cpp
void foo(const int x, float y) {
    constexpr auto param0 = meta::parameters_of(^^foo)[0];
    static_assert(type_of(param0) == ^^int);
    static_assert(param0 != ^^x);

    constexpr auto var0 = meta::variable_of(param0);
    static_assert(type_of(var0) == ^^const int);
    static_assert(var0 == ^^x);
}
```

从这个例子中就可以看出二者的区别了。C++ 会**隐式忽略**掉类型中函数参数上的 `const`，例如 `decltype(foo)` 的结果就是 `void(int, float)`，于是你在函数的外部是永远观察不到这一点的，`parameters_of` 反射的是函数的**接口**，用于从函数外部反射观察函数，它的行为和上述行为保持一致。而 `variable_of` 反射的是函数**定义**，用于从函数内部观察函数，如果在 `foo` 内部 `decltype(x)` 的话，会发现是 `const int`，没有忽略 `const`，于是 `variable_of` 也是这样。

还有其他一些细致的区别，比如同一个函数的多次声明中，某个函数参数的名称不同：

```cpp
void foo(int x);

void foo(int y);
```

那么对 `identifier_of(parameter)` 会求值失败，不知道选择多个结果中的哪一个。但是 `identifier_of(variable_of(parameter))` 则不是，它返回函数定义中对应变量声明的参数。

```cpp
namespace std::meta {
    consteval bool is_function_parameter(info r);
    consteval bool is_explicit_object_parameter(info r);
    consteval bool has_ellipsis_parameter(info r);
    consteval bool has_default_argument(info r);
}
```

剩下这几个函数则是对函数参数的某些性质进行查询了，见名知义：

- `is_function_parameter`：判断某个反射是不是函数参数的反射
- `is_explicit_object_parameter`：判断某个函数参数的反射是不是 C++23 新加入的**显式对象参数 (explicit this)**
- `has_ellipsis_parameter`：判断一个函数或函数类型是否包含 `...`，即 C 风格的可变参数，例如 C 的 `printf(const char*, ...)`
- `has_default_argument`：检测某个参数是否有默认值

## Annotations

元编程的目的是为了编写**通用**的代码，比如自动为某个类型生成序列化的代码逻辑，从而一行代码就能完成序列化，比如

```cpp
struct Point {
    int x;
    int y;
};

Point p = {1, 2};
auto data = json::serialize(p);
```

通过静态反射，`json::serialize` 可以遍历 `Point` 的字段自动生成序列化逻辑，从而一行代码就能完成序列化。我们不再需要自己去编写重复的、繁琐的序列化样板代码。通用性是好的，但是有时候我们也想要一些定制的能力。

仍然是上面 json 序列化的例子，假设我们从服务器接收的 json 字段名是 `"first-name"`，但 C++ 的标识符不能包含 `-`，所以我们可能将成员命名为 `first_name`。如果能在序列化时特殊处理它，将 `first_name` 成员重命名为 `"first-name"` 就好了。

在别的语言中，可以通过 `attribute` 或 `annotation` 来附加元数据，然后在代码中读取这些元数据。C++ 也加入了 `attribute`，语法为 `[[...]]`，比如 `[[nodiscard]]`。但它主要的设计意图是为编译器提供额外的信息，而不是让用户附加额外的元数据并获取。

为了解决这个问题，P3394R4(Annotations for Reflection) 提案为 C++26 引入了可反射的**注解 (annotation)**。它的语法非常直观，使用 `[[=...]]` 为某个 entity 添加注解，**任意的可以作为模板参数的常量表达式**都可以作为注解的内容。

例如：

```cpp
struct [[="A simple point struct"]] Point {
    [[=serde::rename("point_x")]]
    int x;

    [[=serde::rename("point_y")]]
    int y;
};
```

它额外添加了下面这三个函数用于和注解进行交互

```cpp
namespace std::meta {
    consteval bool is_annotation(info);
    consteval vector<info> annotations_of(info item);
    consteval vector<info> annotations_of_with_type(info item, info type);
}
```

`is_annotation` 判断一个反射是不是注解的反射。`annotations_of` 获取给定 entity 上的所有注解的反射，`annotations_of_with_type` 则是获取给定 entity 上所有类型为 `type` 的注解的反射。获取到注解后再使用前面提到的 `extract` 解开值然后使用就行了。

例如

```cpp
struct Info {
    int a;
    int b;
};

[[=Info(1, 2)]] int x = 1;
constexpr auto rs = annotations_of(^^x)[0];
constexpr auto info = std::meta::extract<Info>(rs);
static_assert(info.a == 1 && info.b == 2);
```

这样的话我们就可以在序列化库中预先定义一些类型，比如前文案例中的 `serde::rename`，然后检测用户的字段上有没有这些 annotation 从而进行一些特殊的处理。这样既保证了整体的通用性，又提供了局部的定制性，两全其美。

## Expansion Statement

传统的 `range-for` 循环遍历运行期的序列，而在元编程中，遍历编译期序列的需求越来越常见。比如遍历 `tuple`，这种编译期序列和运行期序列的最大区别是元素的**类型可能不同**。

在 C++17 之前我们只能通过模板递归来完成这样的遍历，C++17 加入的折叠表达式稍微缓解了这一情况，但是仍然需要编写大量复杂的模板代码来完成这个目的。鉴于遍历编译期序列的操作如此之常见，P1306R5(Expansion Statements) 引入了新的语法 template for 来解决这个问题

现在你可以轻松直观地遍历一个 `tuple` 了，在效果上相当于编译期展开循环，并对其中的每个元素实例化一次循环体

```cpp
void print_all(std::tuple<int, char> xs) {
    template for (auto elem : xs) {
        std::println("{}", elem);
    }
}
```

精确的语法定义如下：

```cpp
template for (init-statement(opt) for-range-declaration : expansion-initializer)
    compound-statement
```

- `init-statement(opt)`：前置的初始化语句
- `for-range-declaration`: 循环变量的声明
- `expansion-initializer`: 用于循环的序列

template for 支持三种不同类型的序列，优先级从高到低：

- **表达式列表 (Expression List)**：`{ expression-list }`，遍历列表中的每一个元素

```cpp
template for (auto elem : {1, "hello", true}) { ... }
```

包展开也是支持的，还能轻松的往参数包中添加内容

```cpp
void foo(auto&& ...args) {
    template for (auto elem : {args...}) { ... }

    template for (auto elem : {0, args..., 1}) { ... }
}
```

- **常量范围 (Constant Range)**：

要求 `range` 的长度是编译期确定的

```cpp
void foo() {
    constexpr static std::array arr = {1, 2, 3};
    constexpr static std::span<const int> view = arr;

    template for (constexpr auto elem : view) { ... }
}
```

- **元组式解构 (Tuple-like Destructuring)**

如果上述两种情况都不满足，编译器会尝试将 `expansion-initializer` 视为一个**元组式 (tuple-like)** 的实体进行解构（就像结构化绑定 `auto [a, b] = ...` 那样）

```cpp
std::tuple t(1, "hello", true);
template for (auto elem : t) { ... }
```

> 循环变量声明上有可选的 constexpr，如果标记则要求循环中的每个元素都是 constexpr 的

template for **还支持** `continue` 和 `break` 语句，可以跳过剩余部分未实例化的代码

### `define_static_array`

好的，你现在已经学会 template for 了，于是想要兴致冲冲的编写一个能打印任何结构体的函数，用于调试

```cpp
void print_struct(auto&& value) {
    constexpr auto info = meta::remove_cvref(^^decltype(value));
    constexpr auto no_check = meta::access_context::unchecked();
    template for (constexpr auto e : meta::nonstatic_data_members_of(info, no_check)) {
        constexpr auto type = type_of(e);
        auto&& member = value.[:e:];
        if constexpr (is_class_type(type)) {
            print_struct(member);
        } else {
            std::println("{} {}", identifier_of(e), member);
        }
    }
}
```

发现报错了，说 template for 的初始化表达式不是常量表达式，这是为什么呢？这个事情就说来话长了。你会发现 `nonstatic_data_members_of` 的返回值竟然是一个 `vector`。我们前面说过 C++ 的反射是在编译期完成的，编译期还有 `vector` 用吗？还真有，C++20 允许了编译期的动态内存分配，于是你可以在 `constexpr/consteval` 函数中使用 `vector` 来处理中间状态了。但限制是编译期分配的内存必须在同一段编译期求值上下文中释放，如果在**一次编译期求值**中，有未释放的内存，则会导致编译错误。这个也可以理解，毕竟编译期分配的内存保留到运行期没任何含义了对吧。而每个 top level 的 constexpr 变量，模板参数等，包括 template for 的初始化表达式都视为**一次单独的常量求值**。

所以上面的错误就很好理解了，template for 的初始化表达式被视为一次单独的常量求值，但是返回 `vector` 导致还有未释放的编译期内存，于是报错了。那怎么解决呢？P3491R3(`define_static_{string,object,array}`) 引入了一组函数作为这个问题的临时解决方案：

```cpp
namespace std {
    template <ranges::input_range R>
    consteval const ranges::range_value_t<R>* define_static_string(R&& r);

    template <ranges::input_range R>
    consteval span<const ranges::range_value_t<R>> define_static_array(R&& r);

    template <class T>
    consteval const remove_cvref_t<T>* define_static_object(T&& r);
}
```

它们可以将编译期分配的内存**提升**到**静态储存期**，也就是说和全局变量的储存期相同，并返回该静态储存期的指针或者引用，从而解决这个问题，所以上面的代码只需要额外在获取 `members` 的时候使用 `std::define_static_array` 把 `vector` 转成 `span` 就行了

```cpp
void print_struct(auto&& value) {
    constexpr auto info = meta::remove_cvref(^^decltype(value));
    constexpr auto no_check = meta::access_context::unchecked();
    constexpr auto members =
        std::define_static_array(meta::nonstatic_data_members_of(info, no_check));
    template for (constexpr auto e : members) {
        constexpr auto type = type_of(e);
        auto&& member = value.[:e:];
        if constexpr (is_class_type(type)) {
            print_struct(member);
        } else {
            std::println("{} {}", identifier_of(e), member);
        }
    }
}
```

每个 `vector` 和 template for 的地方都需要这样交互，看起来有些冗余。不过也没办法，这其实只是一个临时的 workaround。真正完善的解决方案是 persistent constexpr allocation，它可以自动把编译期未释放的内容提升到静态储存，但是由于种种原因没有推进。关于它又可以写一篇文章来介绍了，这里就不继续展开了，感兴趣的读者可以阅读：[The History of constexpr in C++! (Part Two)](https://www.ykiko.me/zh-cn/articles/683463723)。

## Example

最后来编写一个简单的 `to_string` 函数作为结尾吧：

```cpp
#include <meta>
#include <print>
#include <string>
#include <vector>

namespace meta = std::meta;

namespace print_utility {

struct skip_t {};

constexpr inline static skip_t skip;

struct rename_t {
    const char* name;
};

consteval rename_t rename(std::string_view name) {
    return rename_t(std::define_static_string(name));
}

}  // namespace print_utility

/// annotations_of => annotations_of_with_type
consteval std::optional<std::meta::info> get_annotation(std::meta::info entity,
                                                        std::meta::info type) {
    auto annotations = meta::annotations_of_with_type(entity, type);
    if (annotations.empty()) {
        return {};
    } else if (annotations.size() == 1) {
        return annotations.front();
    } else {
        throw "too many annotations!";
    }
}

consteval auto fields_of(std::meta::info type) {
    return std::define_static_array(
        meta::nonstatic_data_members_of(type, meta::access_context::unchecked()));
}

template <typename T>
auto to_string(const T& value) -> std::string {
    constexpr auto type = meta::remove_cvref(^^T);
    if constexpr (!meta::is_class_type(type)) {
        return std::format("{}", value);
    } else if constexpr (meta::is_same_type(type, ^^std::string)) {
        return value;
    } else {
        std::string result;

        result += meta::identifier_of(type);
        result += " { ";

        bool first = true;

        template for (constexpr auto member : fields_of(type)) {
            if constexpr (get_annotation(member, ^^print_utility::skip_t)){
                continue;
            }

            if (!first) {
                result += ", ";
            }
            first = false;

            std::string_view field_name = meta::identifier_of(member);
            constexpr auto rename = get_annotation(member, ^^print_utility::rename_t);
            if constexpr (rename) {
                constexpr auto annotation = *rename;
                field_name = meta::extract<print_utility::rename_t>(annotation).name;
            }

            result += std::format("{}: {}", field_name, to_string(value.[:member:]));
        }

        result += " }";
        return result;
    }
}
```

我们这个简单的 `to_string` 函数支持两种 annotation，一种是 `skip` 跳过输出某个字段，一种是 `rename` 用于对这个字段进行重命名。`get_annotation` 用于判断给定的 entity 是否只有一个给定类型的 annotation，如果有就返回那个 annotation，否则返回空或者报错。在 `to_string` 函数中的处理逻辑也很直接，如果 `value` 是基本类型或者 `string`，简单的调用 `format` 返回结果。否则递归的转换它的字段，先检查字段有没有 `skip` 这个 annotation，有就跳过。如果没有的话，就检查它有没有 `rename`，如果有就使用 `rename` 的名字否则使用字段名。

尝试使用

```cpp
struct User {
    int id;
    std::string username;

    [[= print_utility::skip]]
    std::string password_hash;
};

struct Order {
    int order_id;

    [[= print_utility::rename("buyer")]]
    User user_info;
};

int main() {
    User u = {101, "Alice", "abcdefg"};
    Order o = {20240621, u};

    std::println("{}", to_string(u));
    std::println("{}", to_string(o));
}
```

输出

```cpp
User { id: 101, username: Alice }
Order { order_id: 20240621, buyer: User { id: 101, username: Alice } }
```

符合预期！代码放在 [Compiler Explorer](https://godbolt.org/z/1977T9GfP) 上了。

## Conclusion

到这里这篇关于静态反射的介绍文章就结束了，我尽量涵盖了反射中一些较为重要的核心特性，并附上合适的案例。静态反射是简洁的，强大的和易于理解的。这也象征着 C++ 数十年来 constexpr 演进取得了阶段性的里程碑。在文章的最后，让我引用 Herb Sutter 的 [一段话](https://herbsutter.com/2025/06/21/trip-report-june-2025-iso-c-standards-meeting-sofia-bulgaria/) 来结束这篇文章：

> 在今天之前，C++ 历史上最重要的单项特性投票或许是 2007 年 7 月在多伦多举行的那次，该投票决定将 Bjarne Stroustrup 和 Gabriel Dos Reis 的第一份 「constexpr」 提案纳入 C++11 草案。如今回首，我们可以看到那为 C++ 带来了多么巨大的结构性转变。<br><br>我坚信，在未来的许多年里，当我们回望今天，这个反射特性首次被采纳为标准 C++ 的日子，会视其为该语言历史上的一个关键日期。反射将从根本上改善我们编写 C++ 代码的方式，其对语言表达能力的扩展将超过我们至少 20 年来所见的任何特性，并将极大地简化现实世界中的 C++ 工具链和环境。即使仅凭我们今天拥有的部分反射能力，我们已经能够反射 C++ 类型，并利用这些信息加上普通的 std::cout 来生成任意额外的 C++ 源代码，这些代码基于反射信息，并且可以在程序构建时被编译并链接到同一程序中（未来我们还将获得 token injection 功能，从而可以在同一源文件中直接生成 C++ 源码）。但我们实际上可以生成任何东西：任意的二进制元数据，例如 .WINMD 文件；任意的其他语言代码，例如自动生成用于封装 C++ 类型的 Python 或 JS 绑定。所有这一切都可以通过可移植的标准 C++ 实现。<br><br>这是一件非常了不起的大事。听着，大家都知道我偏爱说 C++ 的好话，但我不喜欢夸大其词，也从未说过这样的话。今天确实是独一无二的：反射带来的变革性，比我们以往投票纳入标准的所有其他 10 个主要特性的总和还要大。在未来的十年（甚至更久）里，它将主导 C++ 的发展，我们将通过增加更多功能来完善这一特性（就像我们随着时间推移为 constexpr 添加功能以使其完备一样），并学习如何在我们的程序和构建环境中使用它。
