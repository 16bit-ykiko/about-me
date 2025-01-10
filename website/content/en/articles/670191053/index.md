---
title: 'Implementing Object in C++!'
date: 2023-12-03 23:40:52
updated: 2024-11-30 18:02:59
series: ['Reflection']
series_order: 3
---

## Static vs Dynamic

The terms static typing and dynamic typing are familiar to many. The key distinction lies in the timing of type checking. What does this mean?

Consider the following C++ code:

```cpp
std::string s = "123";
int a = s + 1;
```

We know that `string` cannot be directly added to `int`, so this should result in a TypeError. C++ checks for type errors at compile time, so this code will trigger a **compile-time error**.

Now, consider the corresponding Python code:

```python
s = "123"
a = s + 1
```

Python, on the other hand, checks for errors at runtime, so the above code will actually produce a **runtime error**.

It's important to emphasize the meanings of **compile time** and **runtime** in this context. These terms are often encountered, but their meanings can vary depending on the context. Here, we define them as follows:

- **Compile time**: Refers to the period when code is being compiled into target code, before the program is executed.
  - For AOT (Ahead-Of-Time) compiled languages like C++, this is the process of compiling C++ into machine code.
  - For JIT (Just-In-Time) compiled languages like C#/Java, this generally refers to the process of compiling source code into IR (Intermediate Representation).
  - For transpiled languages like TypeScript, this is the process of compiling TypeScript into JavaScript.

- **Runtime**: Refers to the period when the program is actually running, such as when machine code is executed on the CPU or bytecode is executed on a virtual machine.

Thus, C++, Java, C#, and TypeScript are considered statically typed languages. Python, although it also compiles source code into bytecode, does not perform type checking during this stage, so Python is considered a dynamically typed language.

However, this distinction is not absolute. The boundary between static and dynamic languages is not clear-cut. While C++, Java, C#, and TypeScript are statically typed, they provide various methods to bypass static type checking, such as `pointer` in C++, `Object` in Java/C#, and `Any` in TypeScript. Conversely, dynamically typed languages are increasingly incorporating static type checking, such as Python's `type hints` and JavaScript's TypeScript. Both paradigms are borrowing features from each other.

Currently, C++ only provides `std::any` for type erasure, but it is often not flexible enough. We desire more advanced features, such as accessing members by **field names**, calling functions by **function names**, and creating class instances by **type names**. The goal of this article is to construct a dynamic type in C++ similar to Java/C#'s `Object`.

## Meta Types

Here, we do not adopt the intrusive design (inheritance) used in Java/C#'s `Object`. Instead, we use a non-intrusive design called **fat pointer**. A fat pointer is essentially a structure containing a pointer to the actual data and a pointer to type information. In the case of inheritance, the virtual table pointer resides in the object's header.

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

The member functions will be implemented in subsequent sections. First, let's consider what is stored in the `Type` type.

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

The content here is straightforward. We store the type name, destructor, move constructor, copy constructor, field information, and method information in `Type`. Field information includes the field type and name, while method information includes the method name and function address. If further expansion is desired, information about parent classes and overloaded functions can also be included. Since this is just an example, we will not consider them for now.

## Function Type Erasure

To store member functions of different types in the same container, we must perform type erasure on the functions. All types of functions are erased to the type `Any(*)(void*, std::span<Any>)`. Here, `Any` is the type we defined earlier, `void*` represents the `this` pointer, and `std::span<Any>` is the function's parameter list. Now, we need to consider how to perform this function type erasure.

Take the member function `say` as an example:

```cpp
struct Person {
    std::string_view name;
    std::size_t age;

    void say(std::string_view msg) { std::cout << name << " say: " << msg << std::endl; }
};
```

First, for convenience, let's implement `Any`'s `cast`:

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

Using the feature in C++ that allows non-capturing `lambda` to implicitly convert to function pointers, we can easily implement this erasure.

```cpp
auto f = +[](void* object, std::span<Any> args) {
    auto& self = *static_cast<Person*>(object);
    self.say(args[0].cast<std::string_view>());
    return Any{};
};
```

The principle is simple: write a wrapper function to perform type conversion and forward the call. However, writing such forwarding code for each member function is cumbersome. We can consider using template metaprogramming to generate the code automatically, simplifying the type erasure process.

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

I won't explain the code here. If you don't understand, it's okay. Essentially, it automates the process of type erasure for member functions using template metaprogramming. Just know how to use it. Using it is very simple. Here, `&Person::say` is the pointer-to-member syntax. If you're not familiar, refer to [C++ Member Pointers Explained](https://www.ykiko.me/zh-cn/articles/659510753).

```cpp
auto f = type_ensure<&Person::say>();
// decltype(f) => Any (*)(void*, std::span<Any>)
```

## Type Information Registration

In fact, we need to generate a corresponding `Type` structure for each type to store its information, so that it can be accessed correctly. This functionality is handled by the `type_of` function mentioned earlier.

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

We provide a default implementation so that built-in basic types can automatically register some information. Then, we can specialize for custom types. Now, with this meta information, we can complete the implementation of `Any`'s member functions.

## Complete Implementation of Any

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

The implementation of `foreach` is to iterate over all `Field`s, get the offset and type, and then wrap it into an `Any` type. Note that this is just a simple wrapper; since we set the `flag`, this wrapper will not cause multiple destructions. `invoke` is to find the corresponding function from the member function list and call it.

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

The complete code is available on [Github](https://github.com/16bit-ykiko/blog/blob/main/code/dynamic-type-demo.cpp). With this, we have implemented a highly dynamic, non-intrusive `Any`.

## Extensions and Optimizations

This article provides a very simple introduction to the principles, and the scenarios considered are also very simple. For example, inheritance and function overloading are not considered, and there are several areas where runtime efficiency can be optimized. Nevertheless, the functionality I've implemented may still be more than you need. The main point of this article is to express that for a performance-focused language like C++, there are indeed scenarios where such dynamic features are needed. However, efficiency and generality are often contradictory. At the language level, because generality must be considered, efficiency often falls short. For example, `RTTI` and `dynamic_cast` are often complained about, but fortunately, compilers provide options to disable them. Similarly, my implementation may not fully fit your scenario, but understanding this not-too-difficult principle allows you to implement a version more suitable for your needs.

Possible extensions:

- Support modifying members by `name`.
- Add a global `map` to record information for all types, enabling the creation of class instances by class name.
- `...`

Possible optimizations:

- Reduce the number of `new` calls, or implement an object pool.
- Currently, too much meta information is stored; you can tailor it according to your needs.

Additionally, a current pain point is that all this meta information must be written manually, making it difficult to maintain. If the class definition is modified, the registration code must also be modified, or errors will occur. A practical solution is to use a code generator to automatically generate this mechanical code. For more on how to do this, refer to other articles in this series.