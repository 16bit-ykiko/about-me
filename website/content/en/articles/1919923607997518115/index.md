---
title: Reflection for C++26!!!
date: "2025-06-21 17:33:11"
updated: "2025-07-08 09:07:33"
zhihu_article_id: "1919923607997518115"
zhihu_url: https://zhuanlan.zhihu.com/p/1919923607997518115
zhihu_column_id: c_1707545619290316800
zhihu_column_title: 编程语言中的反射
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

At the C++26 Sofia meeting, which just concluded yesterday, seven proposals related to **Static Reflection**:

- [Reflection for C++26](https://isocpp.org/files/papers/P2996R13.html)
- [Function Parameter Reflection](https://isocpp.org/files/papers/P3096R12.pdf)
- [Annotations for Reflection](https://isocpp.org/files/papers/P3394R4.html)
- [Splicing a base class subobject](https://isocpp.org/files/papers/P3293R3.html)
- [Expansion Statements](https://isocpp.org/files/papers/P1306R5.html)
- [define*static*{string,object,array}](https://isocpp.org/files/papers/P3491R3.html)
- [Error Handling in Reflection](https://isocpp.org/files/papers/P3560R2.html)

All passed plenary and were **officially incorporated into the C++26 standard**. This is an exciting moment. In my opinion, static reflection is undoubtedly the most important new feature in C++ in 20 years. It completely changes the previous pattern of metaprogramming using templates, making **meta programming** code as easy to read, write, and use as ordinary code logic, rather than the template-based DSLs of the past.

More than a year ago, when P2996R1 was released, I wrote an [article](https://www.ykiko.me/en/articles/661692275) introducing this exciting proposal for static reflection. After such a long time, the content of the static reflection proposal itself has changed significantly, the content of the article above is outdated, and many new auxiliary proposals have been added. So I decided to write a new article to introduce static reflection and its auxiliary proposals.

> If you want to try static reflection, there are two ways: one is through the [Compiler Explorer](https://godbolt.org/z/1977T9GfP) online editor, just set the compiler to P2996 clang. The other is to compile the P2996 branch of clang and libc++ from [https://github.com/bloomberg/clang-p2996/tree/p2996](https://github.com/bloomberg/clang-p2996/tree/p2996) yourself. Then, refer to the [use libc++](https://releases.llvm.org/16.0.0/projects/libcxx/docs/UsingLibcxx.html#id4) page and use the newly compiled libc++ as the standard library during compilation. Remember to enable the C++26 standard.

## What is Static Reflection?

First, what does reflection mean? This term, like many other idiomatic terms in computer science, does not have a detailed and precise definition. My reflection column discusses this issue in more detail; interested readers can read it themselves. The focus of this article is C++'s static reflection. Why emphasize "static"? Mainly because when we usually talk about reflection, we almost always refer to reflection in languages like Java, C#, and Python, and their implementations all involve type erasure and querying metadata at runtime. This approach, of course, has unavoidable runtime overhead, and this overhead clearly violates the C++ principle of zero-cost abstraction. To distinguish it from their reflection, the qualifier "static" is added, also indicating that C++'s reflection is completed at **compile time**.

## Everything as Value

Static reflection introduces two new syntaxes. The **reflection operator** `^^` can map most name entities to `std::meta::info`:

```cpp
constexpr std::meta::info rint = ^^int;
```

`std::meta::info` is a new, special, `consteval only` builtin type. It **can only exist at compile time**. You can think of it as a handle to this name entity within the compiler, and subsequent operations can be performed based on this opaque handle.

Specifically, `^^` supports the following four types of name entities:

- `::`: global namespace
- `namespace-name`: ordinary namespace
- `type-id`: type
- `id-expression`: most named things, such as variables, static member variables, fields, functions, templates, enums, etc.

So, how can this `handle` be converted back? Yes, it can, using the **splicer**: `[: :]` to convert `std::meta::info` back to a name entity.

For example:

```cpp
constexpr std::meta::info rint = ^^int;
using int2 = [:rint:];
```

Using `[:rint:]` maps `rint` back to the `int` type. The same applies to other name entities; `[:rint:]` can map them back. Note that in **some** contexts that might cause ambiguity, `typename` or `template` keywords need to be added before `[: :]` to resolve the ambiguity.

> Ambiguous situations basically still involve dependent names. That is, when `r` is a template parameter, it's impossible to directly determine whether `[:r:]` is an expression, a type, or a template, so manual disambiguation is required.

In summary, static reflection introduces two new operators: `^^` to get the `handle` of a name entity, and `[: :]` to map the `handle` back to the corresponding name entity.

## Meta Function

As we all know, merely obtaining a handle is not very useful; the key lies in operations based on that handle. For example, if you get a file handle, you can read its content or close the file based on that handle. In static reflection, these operations on handles are **meta functions**. The `<meta>` header provides a very wide range of functions for operating on these handles. Some of the most commonly used meta functions are introduced below.

> Reflection currently uses compile-time exceptions to handle errors encountered in meta functions.

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

A common requirement in **serialization** and **deserialization** is to get the members of a struct and then recursively serialize them. Before static reflection, we could only achieve this through various hacks, and it was not perfect. For example, [reflect-cpp](https://github.com/getml/reflect-cpp) supports getting data members of **aggregate classes** under C++20, and [magic-enum](https://github.com/Neargye/magic_enum) supports enum members with values in the range `[-127, 128]`. The implementation methods are very hacky and unfriendly to compilers, instantiating a large number of templates, leading to slower compilation, and also having many limitations.

Now, with static reflection, we can easily use these meta functions to get members of namespaces or types, and not just **data members**; **member functions** and aliases can also be easily obtained. It also supports getting **base class** information, which was previously impossible. Reverse operations are also supported, using `parent_of` to get the parent of a member, which is the namespace, class, or function that defines this entity.

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

Output `p: 3, 4`, successfully accessing members via reflection!

> The `access_context` parameter is used to control access permissions. It determines whether we can "see" private or protected members. `unchecked()` means full access, i.e., no access checks are performed. Besides `unchecked`, there is also `current`, which means using the access permissions of the current scope, and `unprivileged`, which can only access non-private members. The meta functions for getting members mentioned above will filter the returned results according to the access_context.

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

This feature is also something C++ programmers have long wished for: getting variable names, function names, and field names.

```cpp
constexpr auto rx = meta::nonstatic_data_members_of(^^Point, no_check)[0];
constexpr auto ry = meta::nonstatic_data_members_of(^^Point, no_check)[1];

static_assert(meta::identifier_of(rx) == "x");
static_assert(meta::identifier_of(ry) == "y");
```

This makes it easy to serialize to formats like JSON that require field names. `identifier_of` generally **only applies** to entities with simple names and directly returns the unqualified name of the named entity. `display_string_of`, on the other hand, might be more inclined to return the fully qualified name, such as its namespace prefix, and can also be used to handle template specializations like `vector<int>`. `source_location_of` further breaks the limitation of C++20's `std::source_location::current()` which can only get the current source location.

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

`offset_of` returns the offset information for a given field, consisting of two parts: `bytes` and `bits`. `total_bits` can be used to get the specific offset. This design primarily considers that fields might be bit-fields, so the offset is not necessarily just the number of bytes. `size_of` and `alignment_of`, as their names suggest, get the size and alignment. `bit_size_of` gets the size of a bit-field.

With this set of meta functions, there is no longer a need to use various hacky methods to get field offsets, such as `bit_cast` member pointers to get offsets based on ABI details. This is very useful in certain binary serialization scenarios.

### type operations

Next are operations related to types, which are key to simplifying template metaprogramming. Before this, since types could only be template parameters, we had to rely on ugly template DSLs to perform computations on types. A purely functional, variable-less, ugly DSL that uses template specialization for branching and template recursion for looping, which is why template metaprogramming has long been criticized. Now with static reflection, we can map types to values, operate on values, and simply write `consteval` functions, which are no different from normal code logic, except that the handle becomes `std::meta::info`.

First, let's talk about the equality of `std::meta::info`. Consider the following code:

```cpp
using int1 = int;
constexpr auto rint = ^^int;
constexpr auto rint1 = ^^int1;
```

Should `rint` and `rint1` be equal here? Undoubtedly, they represent the same **type**, but as we said before, `std::meta::info` is a `handle` representing an internal compiler representation. Clearly, the compiler tracks type alias information separately, so `rint` and `rint1` are actually handles for different name entities, meaning they are **not equal**. The complete rules for determining whether two `std::meta::info` are equal are omitted here; there are other cases to consider, and specific details can be found later in cppreference or the standard draft. For the examples in this article, understanding the alias example above is sufficient.

```cpp
namespace std::meta {
    consteval auto type_of(info r) -> info;
    consteval auto dealias(info r) -> info;
}
```

You can use `type_of` to get the type of a typed entity like a struct field, and `dealias` to get the underlying entity of an alias, such as the original entity of a type alias or namespace alias. This process is **recursive** and will resolve all aliases.

For example:

```cpp
using X = int;
using Y = X;
static_assert(^^int == dealias(^^Y));
```

The **template-form** traits originally defined in the `<type_traits>` header now have corresponding reflection versions in `<meta>`. The naming convention is to change the suffix from `_v` to `_type`, for example, `is_same_v` becomes `is_same_type`, and the `_t` suffix is simply removed.

There are too many functions in this part, so here are **some** as examples:

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

So now it's convenient to replace the previous `type_traits` versions with equivalent reflection versions. The code will be much easier to understand, and I will provide a few such examples at the end of the article.

### template arguments

In addition to the type operations mentioned above, we can now conveniently operate on templates:

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

Assuming `r` is a **template specialization**, `template_of` returns its template, and `template_arguments_of` returns its template arguments. `substitute` returns the reflection of the template specialization resulting from the given template and arguments (without triggering instantiation). With this set of functions, we no longer need to extract template arguments of template specializations through partial specialization; we can easily get the argument list.

We can also use them to write an `is_specialization_of` to determine if a type is a specialization of a certain template, which was previously impossible:

```cpp
consteval bool is_specialization_of(info templ, info type) {
    return templ == template_of(dealias(type));
}
```

> Why was this impossible before? This is because template parameters can be types (`typename`), values (`auto`), or template template parameters (`template`), and you couldn't enumerate all combinations of these three types of parameters. In that case, when writing `is_specialization_of`, the template signature to be checked would be fixed. For example, if it were `<typename T, template<typename...> HKT>`, then `HKT` could only be filled with type template parameters, and it wouldn't be able to handle `std::array`.

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

These meta functions produce a reflection of the **evaluated result** of the provided expression. One of the most common use cases for this type of reflection is as an argument to `std::meta::substitute` to construct a **template specialization**.

`reflect_constant(expr)` is equivalent to the following code:

```cpp
template <auto P>
struct C {};
```

Then we have:

```cpp
static_assert(reflect_constant(V) == template_arguments_of(^^C<V>)[0]);
constexpr auto rarray5 = substitute(^^std::array, {^^int, std::meta::reflect_constant(5)});
static_assert(rarray5 == ^^std::array<int, 5>);
```

`reflect_object(expr)` produces a reflection of the object referred to by `expr`. This is often used to obtain a reflection of a subobject, which can then be used as a non-type template parameter of a reference type.

```cpp
template <int &> void fn();

int p[2];
constexpr auto r = substitute(^^fn, {std::meta::reflect_object(p[1])});
```

`reflect_function(expr)` produces a reflection of the function referred to by `expr`. It is very useful for reflecting the properties of a function when only a reference to the function is available.

```cpp
consteval bool is_global_with_external_linkage(void(*fn)()) {
    std::meta::info rfn = std::meta::reflect_function(*fn);
    return (has_external_linkage(rfn) && parent_of(rfn) == ^^::);
}
```

`extract` is the reverse operation of the `reflect_xxx` series mentioned above, and can be used to restore a value's reflection to its corresponding C++ value.

- If `r` is a reflection of a value, `extract<ValueType>(r)` returns that value.
- If `r` is a reflection of an object, `extract<ObjectType&>(r)` returns a reference to that object.
- If `r` is a reflection of a function, `extract<FuncPtrType>(r)` returns a pointer to that function.
- If `r` is a reflection of a non-static member, `extract<MemberPtrType>(r)` returns a member pointer.

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

`define_aggregate` can be used to generate member definitions for an incomplete type, which is useful for implementing types with a variable number of members like `tuple` or `variant`. For example:

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

This is equivalent to:

```cpp
union U {
    int _0;
    char _1;
    double _2;
};
```

This makes it easy to implement a `variant` type without any template recursion instantiation.

### other functions

In addition to the functions listed above, there are many more functions for querying certain properties of `r`, which are mostly self-explanatory. Only a few are listed:

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

As you can see, a vast amount of information can be queried, including **storage class** and **linkage**, and even information like `user_declared` and `user_provided`.

## Function Reflection

The main reflection proposal discussed above did not cover function parameter reflection, meaning you couldn't get information like injected function parameter names. However, this information is very useful in certain scenarios, such as when binding C++ functions to Python using pybind11. P3096R12 introduced the following meta functions to allow reflection of function parameters:

```cpp
namespace std::meta {
    consteval vector<info> parameters_of(info r);
    consteval info variable_of(info r);
    consteval info return_type_of(info r);
}
```

If `r` is a reflection of a **function** or **function type**, then `return_type_of` returns the reflection of its return type, and `parameters_of` returns the reflection of its function parameters. For example:

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

Since we can already get parameter names and types, what is `variable_of` used for? `variable_of` can **only be used inside the reflected function** to get the reflection of the variable corresponding to that function parameter in the function definition. For example:

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

From this example, the difference between the two can be seen. C++ **implicitly ignores** `const` on function parameters in types. For example, `decltype(foo)` results in `void(int, float)`. Therefore, you can never observe this from outside the function. `parameters_of` reflects the function's **interface**, used to observe the function from outside, and its behavior is consistent with the above. `variable_of`, on the other hand, reflects the function's **definition**, used to observe the function from inside. If `decltype(x)` were used inside `foo`, it would be `const int`, without ignoring `const`, and `variable_of` behaves similarly.

There are other subtle differences. For example, in multiple declarations of the same function, the name of a function parameter might differ:

```cpp
void foo(int x);

void foo(int y);
```

In this case, `identifier_of(parameter)` would fail to evaluate, as it wouldn't know which of the multiple results to choose. However, `identifier_of(variable_of(parameter))` would not; it returns the parameter corresponding to the variable declaration in the function definition.

```cpp
namespace std::meta {
    consteval bool is_function_parameter(info r);
    consteval bool is_explicit_object_parameter(info r);
    consteval bool has_ellipsis_parameter(info r);
    consteval bool has_default_argument(info r);
}
```

The remaining functions query certain properties of function parameters, and their names are self-explanatory:

- `is_function_parameter`: Determines if a reflection is a function parameter reflection.
- `is_explicit_object_parameter`: Determines if a function parameter reflection is an **explicit object parameter** newly added in C++23.
- `has_ellipsis_parameter`: Determines if a function or function type contains `...`, i.e., C-style variadic arguments, such as C's `printf(const char*, ...)`.
- `has_default_argument`: Checks if a parameter has a default value.

## Annotations

The purpose of metaprogramming is to write **generic** code, such as automatically generating serialization code logic for a certain type, so that serialization can be done with a single line of code, for example:

```cpp
struct Point {
    int x;
    int y;
};

Point p = {1, 2};
auto data = json::serialize(p);
```

With static reflection, `json::serialize` can traverse the fields of `Point` and automatically generate serialization logic, thus completing serialization with a single line of code. We no longer need to write repetitive, tedious boilerplate serialization code ourselves. Generality is good, but sometimes we also want some customization capabilities.

Still using the JSON serialization example above, suppose the JSON field name we receive from the server is `"first-name"`, but C++ identifiers cannot contain `-`, so we might name the member `first_name`. It would be great if we could handle it specially during serialization, renaming the `first_name` member to `"first-name"`.

In other languages, metadata can be attached via `attribute` or `annotation`, and then read in the code. C++ also added `attribute`, with the syntax `[[...]]`, such as `[[nodiscard]]`. However, its primary design intent is to provide additional information to the compiler, not to allow users to attach and retrieve additional metadata.

To solve this problem, P3394R4 (Annotations for Reflection) proposes the introduction of reflectable **annotations** for C++26. Its syntax is very intuitive, using `[[=...]]` to add an annotation to an entity. **Any constant expression that can be a template argument** can be the content of an annotation.

For example:

```cpp
struct [[="A simple point struct"]] Point {
    [[=serde::rename("point_x")]]
    int x;

    [[=serde::rename("point_y")]]
    int y;
};
```

It additionally adds these three functions for interacting with annotations:

```cpp
namespace std::meta {
    consteval bool is_annotation(info);
    consteval vector<info> annotations_of(info item);
    consteval vector<info> annotations_of_with_type(info item, info type);
}
```

`is_annotation` determines if a reflection is an annotation reflection. `annotations_of` gets reflections of all annotations on a given entity, and `annotations_of_with_type` gets reflections of all annotations of a given `type` on a given entity. Once the annotation is obtained, `extract` can be used to unwrap the value and use it.

For example:

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

This way, we can pre-define some types in the serialization library, such as `serde::rename` in the previous example, and then check if the user's fields have these annotations to perform some special processing. This ensures both overall generality and local customizability, achieving both.

## Expansion Statement

Traditional `range-for` loops iterate over runtime sequences, while in metaprogramming, the need to iterate over compile-time sequences is becoming increasingly common. For example, iterating over a `tuple`, the biggest difference between such compile-time sequences and runtime sequences is that the **types of elements may differ**.

Before C++17, we could only accomplish such iteration through template recursion. C++17's addition of fold expressions slightly alleviated this situation, but still required writing a lot of complex template code to achieve this goal. Given how common iterating over compile-time sequences is, P1306R5 (Expansion Statements) introduced a new `template for` syntax to solve this problem.

Now you can easily and intuitively iterate over a `tuple`. In effect, it's equivalent to compile-time loop unrolling, instantiating the loop body once for each element.

```cpp
void print_all(std::tuple<int, char> xs) {
    template for (auto elem : xs) {
        std::println("{}", elem);
    }
}
```

The precise syntax definition is as follows:

```cpp
template for (init-statement(opt) for-range-declaration : expansion-initializer)
    compound-statement
```

- `init-statement(opt)`: Optional preceding initialization statement.
- `for-range-declaration`: Declaration of the loop variable.
- `expansion-initializer`: The sequence to iterate over.

`template for` supports three different types of sequences, in descending order of precedence:

- **Expression List**: `{ expression-list }`, iterates over each element in the list.

```cpp
template for (auto elem : {1, "hello", true}) { ... }
```

Pack expansion is also supported, and you can easily add content to parameter packs:

```cpp
void foo(auto&& ...args) {
    template for (auto elem : {args...}) { ... }

    template for (auto elem : {0, args..., 1}) { ... }
}
```

- **Constant Range**:

Requires the `range` length to be compile-time determined.

```cpp
void foo() {
    constexpr static std::array arr = {1, 2, 3};
    constexpr static std::span<const int> view = arr;

    template for (constexpr auto elem : view) { ... }
}
```

- **Tuple-like Destructuring**:

If neither of the above two conditions is met, the compiler will try to treat `expansion-initializer` as a **tuple-like** entity and destructure it (like structured binding `auto [a, b] = ...`).

```cpp
std::tuple t(1, "hello", true);
template for (auto elem : t) { ... }
```

> The loop variable declaration has an optional `constexpr`. If marked, it requires every element in the loop to be `constexpr`.

`template for` **also supports** `continue` and `break` statements, which can skip the remaining uninstantiated code.

### define static array

Okay, you've learned `template for`, so you're eager to write a function that can print any struct for debugging:

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

You find an error, saying that the initialization expression of `template for` is not a constant expression. Why is this? This is a long story. You'll find that the return value of `nonstatic_data_members_of` is actually a `vector`. We said earlier that C++ reflection is done at compile time. Is `vector` even usable at compile time? Indeed it is; C++20 allows dynamic memory allocation at compile time, so you can use `vector` in `constexpr/consteval` functions to handle intermediate states. However, the limitation is that memory allocated at compile time must be deallocated within the same compile-time evaluation context. If there is unreleased memory in **a single compile-time evaluation**, it will lead to a compilation error. This is understandable, after all, memory allocated at compile time has no meaning if it persists into runtime, right? And each top-level `constexpr` variable, template parameter, etc., including the initialization expression of `template for`, is considered **a separate constant evaluation**.

So the error above is easy to understand: the initialization expression of `template for` is considered a separate constant evaluation, but returning a `vector` results in unreleased compile-time memory, hence the error. So how to solve it? P3491R3 (`define_static_{string,object,array}`) introduces a set of functions as a temporary solution to this problem:

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

They can **elevate** compile-time allocated memory to **static storage duration**, meaning it has the same storage duration as global variables, and return a pointer or reference to that static storage duration, thereby solving this problem. So the code above only needs to use `std::define_static_array` to convert the `vector` to a `span` when getting `members`:

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

Every `vector` and `template for` location needs this interaction, which seems a bit redundant. However, there's no other way; this is actually just a temporary workaround. The truly complete solution is persistent constexpr allocation, which can automatically elevate unreleased compile-time content to static storage, but for various reasons, it hasn't progressed. Another article could be written about it, but I won't go into it further here. Interested readers can read: [The History of constexpr in C++! (Part Two)](https://www.ykiko.me/en/articles/683463723).

## Example

Finally, let's write a simple `to_string` function as a conclusion:

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

Our simple `to_string` function supports two types of annotations: `skip` to skip printing a field, and `rename` to rename that field. `get_annotation` is used to determine if a given entity has exactly one annotation of a given type; if so, it returns that annotation, otherwise it returns empty or throws an error. The processing logic in the `to_string` function is also straightforward: if `value` is a fundamental type or `string`, it simply calls `format` and returns the result. Otherwise, it recursively converts its fields, first checking if the field has the `skip` annotation, and if so, skipping it. If not, it checks if it has `rename`, and if so, uses the `rename`'s name, otherwise uses the field name.

Attempt to use:

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

Output:

```cpp
User { id: 101, username: Alice }
Order { order_id: 20240621, buyer: User { id: 101, username: Alice } }
```

As expected! The code is available on [Compiler Explorer](https://godbolt.org/z/1977T9GfP).

## Conclusion

This introductory article on static reflection concludes here. I have tried to cover some of the more important core features of reflection and provided suitable examples. Static reflection is concise, powerful, and easy to understand. It also symbolizes a significant milestone in C++'s decades-long evolution of `constexpr`. In closing, let me quote [Herb Sutter](https://herbsutter.com/2025/06/21/trip-report-june-2025-iso-c-standards-meeting-sofia-bulgaria/) to end this article:

> Until today, perhaps the most important single feature vote in C++ history was in July 2007 in Toronto, which decided to incorporate Bjarne Stroustrup and Gabriel Dos Reis’s first “constexpr” proposal into the C++11 draft. Looking back, we can see what a huge structural shift that brought to C++.
>
> I firmly believe that many years from now, when we look back at today, the day this reflection feature was first adopted into standard C++, we will view it as a pivotal date in the language’s history. Reflection will fundamentally improve how we write C++ code, and its extension to the language’s expressiveness will exceed any feature we’ve seen in at least 20 years, and will greatly simplify real-world C++ toolchains and environments. Even with just the partial reflection capabilities we have today, we can already reflect C++ types and use that information, plus ordinary `std::cout`, to generate arbitrary additional C++ source code, which is based on reflection information and can be compiled and linked into the same program at build time (in the future we will also get token injection capabilities, allowing us to directly generate C++ source code within the same source file). But we can actually generate anything: arbitrary binary metadata, such as .WINMD files; arbitrary other language code, such as automatically generating Python or JS bindings to wrap C++ types. All of this can be achieved with portable standard C++.
>
> This is a very big deal. Listen, everyone knows I’m biased towards C++, but I don’t like hyperbole, and I’ve never said anything like this. Today is truly unique: the transformative power of reflection is greater than the sum of all other 10 major features we’ve ever voted into the standard. Over the next decade (and beyond), it will dominate C++ development, and we will refine this feature by adding more capabilities (just as we’ve added capabilities to `constexpr` over time to make it complete), and learn how to use it in our programs and build environments.
