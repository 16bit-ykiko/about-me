---
series:
  - Reflection
series_order: 3
title: Implement Object in C++!
date: "2023-12-03 15:40:52"
updated: "2024-11-30 10:02:59"
zhihu_article_id: "670191053"
zhihu_url: https://zhuanlan.zhihu.com/p/670191053
zhihu_column_id: c_1707545619290316800
zhihu_column_title: 编程语言中的反射
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

## Static and Dynamic

The terms static typing and dynamic typing are probably familiar to everyone. The key to distinguishing between them lies in the timing of type checking. What does that mean?

Suppose we have the following C++ code:

```cpp
std::string s = "123";
int a = s + 1;
```

As we know, a `string` cannot be directly added to an `int`, so there should be a TypeError here. C++ checks for type errors at compile time, so this code will trigger a **compile time error**.

Consider the corresponding Python code:

```python
s = "123"
a = s + 1
```

Python, on the other hand, checks for errors at runtime, so the above code will actually produce a **runtime error**.

It's necessary to emphasize the meaning of **compile time** and **runtime** here. These terms might be encountered frequently, but their meanings can vary in different contexts. In our context:

- **compile time**: Generally refers to the process of compiling code into target code, before the program actually starts running.
  - For AOT-compiled languages, such as C++, it's the process of compiling C++ into machine code.
  - For JIT-compiled languages, such as C#/Java, it generally refers to the process of compiling source code into IR.
  - For transpiled languages, such as TypeScript, it's the process of compiling TypeScript into JavaScript.

- **runtime**: Generally refers to when the program is actually running, for example, when machine code is executed on a CPU, or bytecode is executed on a virtual machine.

Therefore, C++, Java, C#, and TypeScript are called statically typed languages. Although Python also has a stage where source code is compiled into bytecode, type checking is not performed at this stage, so Python is called a dynamically typed language.

However, this is not absolute; the boundary between static and dynamic languages is not so clear. Although C++, Java, C#, and TypeScript are statically typed languages, they all provide several ways to bypass static type checking, such as C++'s `pointer`, Java/C#'s `Object`, and TypeScript's `Any`. Dynamically typed languages are also gradually introducing static type checking, such as Python's `type hint` and JavaScript's `TypeScript`, etc. Both are borrowing features from each other.

Currently, C++ only provides `std::any` for type erasure, but often it's not flexible enough. We want more advanced features, such as **accessing members by field name**, **calling functions by function name**, and **creating class instances by type name**. The goal of this article is to build a dynamic type in C++ similar to Java/C#'s `Object`.

## Meta Type

Here, we don't adopt an intrusive design like Java/C#'s `Object` (inheritance), but rather a non-intrusive design called a fat pointer. A fat pointer is essentially a struct that contains a pointer to the actual data and a pointer to type information. In the case of inheritance, the vtable pointer would be present in the object header.

```cpp
class Any {
    Type* type;    // type info, similar to vtable
    void* data;    // pointer to the data
    uint8_t flag;  // special flag

public:
    Any() : type(nullptr), data(nullptr), flag(0) {}

    Any(Type* type, void* data) : type(type), data(data), flag(0B00000001) {}

    Any(const Any& other);
    Any(Any&& other);
    ~Any();

    template <typename T>
    Any(T&& value);  // box value to Any

    template <typename T>
    T& cast();  // unbox Any to value

    Type* GetType() const { return type; }  // get type info

    Any invoke(std::string_view name, std::span<Any> args);  // call method

    void foreach(const std::function<void(std::string_view, Any&)>& fn);  // iterate fields
};
```

The member functions will be implemented step by step in later sections. Next, let's consider what is stored inside this `Type` type.

## Meta Information

```cpp
struct Type {
    std::string_view name;       // type name
    void (*destroy)(void*);      // destructor
    void* (*copy)(const void*);  // copy constructor
    void* (*move)(void*);        // move constructor

    using Field = std::pair<Type*, std::size_t>;           // type and offset
    using Method = Any (*)(void*, std::span<Any>);         // method
    std::unordered_map<std::string_view, Field> fields;    // field info
    std::unordered_map<std::string_view, Method> methods;  // method info
};
```

The content here is simple: in `Type`, we store the type name, destructor, move constructor, copy constructor, field information, and method information. Field information stores the field type and field name, and method information stores the method name and function address. If we want to extend it further, we could also store parent class information and overloaded function information. Since this is just an example, we won't consider them for now.

## Function Type Erasure

To store member functions of different types in the same container, we must perform function type erasure. All types of functions are erased into the type `Any(*)(void*, std::span<Any>)`. Here, `Any` is the `Any` type we defined above, `void*` actually represents the `this` pointer, and `std::span<Any>` is the function's parameter list. Now we need to consider how to perform this function type erasure.

Let's take the given member function `say` as an example:

```cpp
struct Person {
    std::string_view name;
    std::size_t age;

    void say(std::string_view msg) { std::cout << name << " say: " << msg << std::endl; }
};
```

First, for convenience, let's implement `Any`'s `cast` method:

```cpp
template <typename T>
Type* type_of();  // type_of<T> returns type info of T

template <typename T>
T& Any::cast() {
    if(type != type_of<T>()) {
        throw std::runtime_error{"type mismatch"};
    }
    return *static_cast<T*>(data);
}
```

Leveraging the C++ feature where a non-capturing `lambda` can be implicitly converted to a function pointer, this erasure can be easily achieved.

```cpp
auto f = +[](void* object, std::span<Any> args) {
    auto& self = *static_cast<Person*>(object);
    self.say(args[0].cast<std::string_view>());
    return Any{};
};
```

The principle is actually very simple: just write a wrapper function to perform type conversion and then forward the call. However, manually writing such a large block of forwarding code for each member function is still cumbersome. We can consider using template metaprogramming for code generation to automatically generate the above code, simplifying the type erasure process.

```cpp
template <typename T>
struct member_fn_traits;

template <typename R, typename C, typename... Args>
struct member_fn_traits<R (C::*)(Args...)> {
    using return_type = R;
    using class_type = C;
    using args_type = std::tuple<Args...>;
};

template <auto ptr>
auto* type_ensure() {
    using traits = member_fn_traits<decltype(ptr)>;
    using class_type = typename traits::class_type;
    using result_type = typename traits::return_type;
    using args_type = typename traits::args_type;

    return +[](void* object, std::span<Any> args) -> Any {
        auto self = static_cast<class_type*>(object);
        return [=]<std::size_t... Is>(std::index_sequence<Is...>) {
            if constexpr(std::is_void_v<result_type>) {
                (self->*ptr)(args[Is].cast<std::tuple_element_t<Is, args_type>>()...);
                return Any{};
            } else {
                return Any{(self->*ptr)(args[Is].cast<std::tuple_element_t<Is, args_type>>()...)};
            }
        }(std::make_index_sequence<std::tuple_size_v<args_type>>{});
    };
}
```

I won't explain the code here; it's okay if you don't understand it. Essentially, it automates the process of member function type erasure using template metaprogramming. You just need to know how to use it, and it's very simple to use. `&Person::say` here is the syntax for a pointer to member; if you're not familiar with it, you can refer to [Complete Analysis of C++ Member Pointers](https://www.ykiko.me/en/articles/659510753).

```cpp
auto f = type_ensure<&Person::say>();
// decltype(f) => Any (*)(void*, std::span<Any>)
```

## Type Information Registration

In fact, we need to generate a corresponding `Type` struct for each type to store its information, so that it can be accessed correctly. This functionality is handled by the `type_of` function mentioned above.

```cpp
template <typename T>
Type* type_of() {
    static Type type;
    type.name = typeid(T).name();
    type.destroy = [](void* obj) { delete static_cast<T*>(obj); };
    type.copy = [](const void* obj) { return (void*)(new T(*static_cast<const T*>(obj))); };
    type.move = [](void* obj) { return (void*)(new T(std::move(*static_cast<T*>(obj)))); };
    return &type;
}

template <>
Type* type_of<Person>() {
    static Type type;
    type.name = "Person";
    type.destroy = [](void* obj) { delete static_cast<Person*>(obj); };
    type.copy = [](const void* obj) {
        return (void*)(new Person(*static_cast<const Person*>(obj)));
    };
    type.move = [](void* obj) {
        return (void*)(new Person(std::move(*static_cast<Person*>(obj))));
    };
    type.fields.insert({"name", {type_of<std::string_view>(), offsetof(Person, name)}});
    type.fields.insert({"age", {type_of<std::size_t>(), offsetof(Person, age)}});
    type.methods.insert({"say", type_ensure<&Person::say>()});
    return &type;
};
```

We provide a default implementation so that if built-in basic types are used, some information can be automatically registered. Then, through specialization, we can provide implementations for custom types. Now that we have this meta-information, we can complete the implementation of `Any`'s member functions.

## Complete Any Implementation

```cpp
Any::Any(const Any& other) {
    type = other.type;
    data = type->copy(other.data);
    flag = 0;
}

Any::Any(Any&& other) {
    type = other.type;
    data = type->move(other.data);
    flag = 0;
}

template <typename T>
Any::Any(T&& value) {
    type = type_of<std::decay_t<T>>();
    data = new std::decay_t<T>(std::forward<T>(value));
    flag = 0;
}

Any::~Any() {
    if(!(flag & 0B00000001) && data && type) {
        type->destroy(data);
    }
}

void Any::foreach(const std::function<void(std::string_view, Any&)>& fn) {
    for(auto& [name, field]: type->fields) {
        Any any = Any{field.first, static_cast<char*>(data) + field.second};
        fn(name, any);
    }
}

Any Any::invoke(std::string_view name, std::span<Any> args) {
    auto it = type->methods.find(name);
    if(it == type->methods.end()) {
        throw std::runtime_error{"method not found"};
    }
    return it->second(data, args);
}
```

The `foreach` implementation iterates through all `Field`s, gets their offset and type, and then wraps them into an `Any` type. Note that this is just a simple wrapper; in fact, because we set a `flag`, this wrapping will not lead to multiple destructions. `invoke` finds the corresponding function from the list of member functions and then calls it.

## Example Code

```cpp
int main() {
    Any person = Person{"Tom", 18};
    std::vector<Any> args = {std::string_view{"Hello"}};
    person.invoke("say", args);
    // => Tom say: Hello

    auto f = [](std::string_view name, Any& value) {
        if(value.GetType() == type_of<std::string_view>()) {
            std::cout << name << " = " << value.cast<std::string_view>() << std::endl;
        } else if(value.GetType() == type_of<std::size_t>()) {
            std::cout << name << " = " << value.cast<std::size_t>() << std::endl;
        }
    };

    person.foreach(f);
    // name = Tom
    // age = 18
    return 0;
}
```

The complete code is available on [Github](https://github.com/16bit-ykiko/blog/blob/main/code/dynamic-type-demo.cpp). With this, we have implemented an extremely dynamic, non-intrusive `Any`.

## Extensions and Optimizations

This article provides only a very simple introduction to the principles, and the scenarios considered are also quite basic. For example, inheritance and function overloading are not considered here, and there are several areas where runtime efficiency could be optimized. Nevertheless, the features I've written might still be excessive for your needs. The main point this article aims to convey is that for a performance-oriented language like C++, there are indeed scenarios where these more dynamic features are required. However, efficiency and generality are often contradictory; at the language level, because generality must be considered, efficiency is often not ideal. For instance, `RTTI` and `dynamic_cast` are often complained about, but fortunately, compilers provide options to disable them. Similarly, my implementation may not perfectly fit your scenario, but once you understand these not-so-difficult principles, you can certainly implement a version that is more suitable for your specific needs.

Points for extension:

- Support modifying members by `name`
- Add a global `map` to record information for all types, thereby supporting the creation of class instances by class name
- `...`

Points for optimization:

- Reduce the number of `new` calls, or implement your own object pool
- Or, if too much meta-information is currently stored, trim it according to your own needs

In addition, a current pain point is that all this meta-information has to be written manually, making it difficult to maintain. If internal class definitions are modified, these registration codes must also be modified, otherwise errors will occur. A practical solution here is to use a code generator to automatically generate this boilerplate code. For information on how to perform these operations, you can refer to other articles in this series.
