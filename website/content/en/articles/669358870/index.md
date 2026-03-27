---
series:
  - Reflection
series_order: 1
title: A Reflection Tutorial for C++ Programmers
date: "2023-11-29 01:14:02"
updated: "2024-10-21 01:35:13"
zhihu_article_id: "669358870"
zhihu_url: https://zhuanlan.zhihu.com/p/669358870
zhihu_column_id: c_1707545619290316800
zhihu_column_title: 编程语言中的反射
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

## What is Reflection?

The term Reflection is probably not new to anyone; perhaps you haven't used it, but you've certainly heard of it. However, like many other **idiomatic terms** in the CS field, there isn't a clear and precise definition for reflection. This leads to a situation where, for languages like C#, Java, and Python that have reflection, discussing it naturally brings to mind related facilities, APIs, and code examples in those languages, making it very concrete. But for languages like C, C++, and Rust, which don't have reflection, when reflection is discussed, people are often unsure what the other person is referring to, making it very abstract. For example, someone might tell me that Rust has reflection, and the example they provide is the introduction to [std::Any module](https://doc.rust-lang.org/stable/std/any/index.html) in Rust's official documentation. It mentions:

> Utilities for dynamic typing or type reflection

But the awkwardness lies in this: if you call it reflection, its functionality is very limited; if you say it's not, it's not entirely wrong to argue that it exhibits some form of it.

Similar situations often occur in C++. I'm sure you often hear views like these: C++ only has very weak reflection, namely RTTI (Run Time Type Information), but some C++ frameworks like QT and UE implement their own reflection. In recent discussions, online blogs, or C++ new standard proposals, you might again hear about:

- Static reflection
- Dynamic reflection
- Compile-time reflection
- Runtime reflection

Such a plethora of terms can be utterly confusing and disorienting. Moreover, prefixes like static, dynamic, compile time, and runtime are themselves idiomatic terms, often combined with various words, and have many meanings depending on the context.

Some readers might say, "I checked WIKI, and [reflection](https://en.wikipedia.org/wiki/Reflective_programming) clearly has a definition, as follows:"

> In computer science, reflective programming or reflection is the ability of a process to examine, introspect, and modify its own structure and behavior.

First, WIKI is also written by people and does not possess absolute authority; if you are not satisfied with this definition, you can modify it yourself. Secondly, the wording here is also very vague. What does "introspect" mean? Self-reflection, what does this term mean in CS? So this definition is also very awkward. What to do then? I choose to break it down into several processes for explanation, so we don't have to dwell on the conceptual question of "what **exactly is reflection**." Instead, by understanding these processes, you will naturally understand what reflection does.

## How to Understand Reflection?

Reflection in all languages can be seen as the following three steps:

### Generate Metadata

First, what is metadata? When we write code, we give names to variables, types, struct fields, etc. These names are primarily for the convenience of programmers to understand and maintain the source code. For C/C++, these names are usually discarded after compilation to save binary space, which is understandable. For a detailed discussion, please see [Why C/C++ compilers do not retain metadata](https://www.ykiko.me/en/articles/670190357).

However, gradually, we found that in some cases, this data is needed. For example, when serializing a struct into `json`, the struct field names are required, and when printing logs, we don't want to print enum values but rather the corresponding enum names directly. What to do? Early on, it could only be done through hard coding, i.e., manual writing, or perhaps some macros for more advanced cases. This is actually very inconvenient and not conducive to subsequent code maintenance.

Later, some languages, such as Java and C#, emerged. Their compilers retain a lot of data, including these names, during compilation. This data is called metadata. At the same time, there are also means to allow programmers to attach metadata to certain structures themselves, such as C#'s `attribute` and Java's `annotation`.

What about C++? Currently, C++ compilers only retain type names for implementing RTTI, i.e., the related facilities of `std::type_info` in the standard. Other information is erased by the compiler. What to do? Manually writing metadata is acceptable for a small number of classes, but when the project scale increases, for example, with dozens or hundreds of classes, it becomes very tedious and error-prone. In fact, we can run a script before actual compilation to generate this data, which is called Code Generation. For related content, please refer to [Freely control C++ code with clang tools](https://www.ykiko.me/en/articles/669360731).

### Query Metadata

After generation, the next step is to query the metadata. Many languages' built-in reflection modules, such as Python's `inspect`, Java's `Reflection`, and C#'s `System.Reflection`, actually encapsulate some operations, making it more convenient for users to avoid direct contact with raw metadata.

It is worth noting that the queries in the above cases all occur at runtime. Searching and matching based on strings at runtime is actually a relatively slow process, which is why we often say that calling methods via reflection is slower than calling them normally.

For C++, the compiler provides some limited interfaces for us to access (reflect) some information at compile time. For example, `decltype` can be used to get the type of a variable, and further determine whether two variable types are equal, whether they are a subclass of a certain type, etc., but the functionality is very limited.

However, you can generate metadata yourself using the method from the previous subsection, mark them all as `constexpr`, and then query them at compile time. In fact, C++26's static reflection follows this idea: the compiler generates metadata and exposes some interfaces for users to query. For related content, please see [Analysis of C++26 Static Reflection Proposal](https://www.ykiko.me/en/articles/661692275). The timing of the query is the distinction between so-called **dynamic reflection** and **static reflection**.

Of course, what can be done at compile time is certainly not as much as at runtime. For example, if you want to create a class instance based on a runtime type name, it's impossible to do so at compile time. But you can build dynamic reflection based on this static metadata. For related content, please see [Implementing Object in C++](https://www.ykiko.me/en/articles/670191053).

### Operate Metadata

Then, further operations are performed based on the metadata, such as code generation. In C++, this can be understood as compile-time code generation, while in Java and C#, it can be considered runtime code generation. See [Various ways to generate code](https://www.ykiko.me/en/articles/669359855) for details.

## Conclusion

Finally, let's use the three steps above to break down reflection in different languages:

- Python, JavaScript, Java, C#: Metadata is generated by the compiler/interpreter, standard libraries provide interfaces, users can query metadata at runtime, and thanks to the Virtual Machine (VM), code can be conveniently generated.
- Go: Metadata is generated by the compiler, standard libraries provide interfaces, users can query metadata at runtime. However, since Go is primarily AOT (Ahead-of-Time) compiled, runtime code generation is not convenient.
- Zig, C++26 Static Reflection: Metadata is generated by the compiler, standard libraries provide interfaces, users can query metadata at compile time. Similarly, since it's AOT compiled, runtime code generation is not convenient, but code generation can be performed at compile time.

QT and UE, on the other hand, generate their own metadata through code generation, encapsulate interfaces, and allow users to query metadata at runtime. The underlying principle is similar to Go's reflection.

I hope this series of tutorials is helpful to you! If there are any errors, please feel free to discuss them in the comments section. Thank you for reading.
