---
title: 'A Reflection Tutorial for C++ Programmers'
date: 2023-11-29 09:14:02
updated: 2024-10-21 09:35:13
series: ['Reflection']
series_order: 1
---

## What is Reflection?

The term "Reflection" is likely familiar to many, even if you haven't used it, you've probably heard of it. However, like many other **jargon** in the field of computer science, there isn't a clear and precise definition for reflection. This leads to situations where, for languages like C#, Java, and Python that have reflection, discussing reflection naturally brings to mind the corresponding facilities, APIs, and code examples in those languages, making it very concrete. However, for languages like C, C++, and Rust that lack reflection, when people talk about reflection, there's often uncertainty about what exactly is being referred to, making it very abstract. For example, someone once told me that Rust has reflection, citing the official Rust documentation's introduction to the [std::Any module](https://doc.rust-lang.org/stable/std/any/index.html), which mentions:

> Utilities for dynamic typing or type reflection

But the awkwardness lies in the fact that if you consider it as reflection, its functionality is quite limited; if you say it's not, well, you could argue that it somewhat embodies reflection.

Similar situations frequently occur in C++. You might often hear opinions like: C++ only has very weak reflection, namely RTTI (Run Time Type Information), but some frameworks like QT and UE have implemented their own reflection. In recent discussions, blogs, or proposals for new C++ standards, you might also hear terms like:

- Static reflection
- Dynamic reflection
- Compile-time reflection
- Runtime reflection

These terms can be quite confusing and overwhelming. Moreover, prefixes like static, dynamic, compile-time, and runtime are themselves jargon, often combined with various terms, carrying many meanings depending on the context.

Some readers might say, "I checked Wikipedia, and [reflection](https://en.wikipedia.org/wiki/Reflective_programming) does have a definition, as follows:

> In computer science, reflective programming or reflection is the ability of a process to examine, introspect, and modify its own structure and behavior.

First, Wikipedia is written by people and isn't absolutely authoritative; if you're dissatisfied with this definition, you can modify it yourself. Second, the wording here is quite vague. What does introspection (introspect) mean? Self-reflection, but what does that mean in the context of computer science? So this definition is also quite awkward. What to do then? I choose to break it down into several processes for explanation, so we don't have to struggle with the conceptual question of "**what exactly is reflection**." Instead, by understanding these processes, you'll naturally grasp what reflection is doing.

## How to Understand Reflection?

Reflection in all languages can be seen as the following three steps:

### Generate Metadata

First, what is metadata (Metadata)? When we write code, we name variables, types, struct fields, etc. These names are mainly for programmers to understand and maintain the source code. For C/C++, these names are usually discarded after compilation to save binary space, which is understandable. For a detailed discussion, see [Why C/C++ Compilers Do Not Retain Metadata](https://www.ykiko.me/zh-cn/articles/670190357).

But gradually, we found that in some cases, we need this data. For example, when serializing a struct into `json`, we need the struct field names, or when printing logs, we don't want to print enum values but the corresponding enum names. What to do? Early on, the only way was through hard coding, i.e., writing it manually, or using macros for more advanced cases. This was quite inconvenient and not conducive to future code maintenance.

Later, some languages, like Java and C#, their compilers would retain a lot of data, including these names, during compilation. This data is called metadata (Metadata). Additionally, there are ways for programmers to attach metadata to certain structures themselves, such as C#'s `attribute` and Java's `annotation`.

What about C++? Currently, C++ compilers only retain type names for implementing RTTI, i.e., facilities related to `std::type_info` in the standard. Other information is stripped away by the compiler. What to do? Manually writing metadata is acceptable for a small number of classes, but as the project scale increases, such as having dozens or hundreds of classes, it becomes very tedious and error-prone. In fact, we can run a script before actual compilation to generate this data, known as code generation (Code Generation). For related content, see [Using Clang Tools to Freely Manipulate C++ Code](https://www.ykiko.me/zh-cn/articles/669360731).

### Query Metadata

After generation, the next step is querying metadata. Many languages' built-in reflection modules, such as Python's `inspect`, Java's `Reflection`, and C#'s `System.Reflection`, essentially encapsulate some operations, making it more convenient for users to access metadata without directly dealing with raw data.

It's worth noting that the queries in the above cases occur at runtime. Searching and matching based on strings at runtime is a relatively slow process, which is why we often say that reflective method calls are slower than normal method calls.

For C++, the compiler provides some limited interfaces for us to access (reflect) some information at compile time, such as using `decltype` to get a variable's type, further determining if two variable types are equal, or if one is a subclass of another, but the functionality is quite limited.

However, you can generate metadata yourself as described in the previous section, mark them as constexpr, and then query them at compile time. In fact, C++26's static reflection follows this approach, with the compiler generating metadata and exposing some interfaces for users to query. For related content, see [C++26 Static Reflection Proposal Analysis](https://www.ykiko.me/zh-cn/articles/661692275). The timing of the query is what distinguishes **dynamic reflection** from **static reflection**.

Of course, what can be done at compile time is certainly less than what can be done at runtime. For example, creating a class instance based on a runtime type name is something that can't be done at compile time. But you can build dynamic reflection based on these static metadata. For related content, see [Implementing Object in C++](https://www.ykiko.me/zh-cn/articles/670191053).

### Operate Metadata

Then, based on the metadata, further operations can be performed, such as code generation. In C++, this can be understood as compile-time code generation, while in Java and C#, it can be considered runtime code generation. For details, see [Various Ways to Generate Code](https://www.ykiko.me/zh-cn/articles/669359855).

## Conclusion

Finally, let's break down reflection in different languages using the above three steps:

- Python, JavaScript, Java, C#: Metadata is generated by the compiler/interpreter, standard libraries provide interfaces, users can query metadata at runtime, and with the presence of a virtual machine (VM), code generation is convenient.
- Go: Metadata is generated by the compiler, standard libraries provide interfaces, users can query metadata at runtime. However, since Go is mainly AOT (Ahead-of-Time) compiled, runtime code generation is not convenient.
- Zig, C++26 static reflection: Metadata is generated by the compiler, standard libraries provide interfaces, users can query metadata at compile time. Similarly, since it's AOT compiled, runtime code generation is not convenient, but compile-time code generation is possible.

As for QT and UE, they generate metadata through code generation, encapsulate interfaces, and users can query metadata at runtime. The implementation principle is similar to Go's reflection.

I hope this tutorial series is helpful to you! If there are any errors, feel free to discuss them in the comments. Thank you for reading.