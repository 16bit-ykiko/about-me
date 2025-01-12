---
title: '在 C++ 中实现 Object!'
date: 2023-12-03 23:40:52
updated: 2024-11-30 18:02:59
series: ['Reflection']
series_order: 3
---

## 静态与动态 

静态类型和动态类型这两个词语相信大家都不陌生了，区分二者的关键在于类型检查的时机。什么意思呢？

假设我们有如下的 C++ 代码

```cpp
std::string s = "123";
int a = s + 1;
```

那我们知道，`string`是不能和`int`直接相加的，所以这里应该有一个 TypeError。C++ 在编译期检查类型错误，所以这段代码会触发一个 **compile time error（编译时错误）**。

考虑对应的 Python 代码

```python
s = "123"
a = s + 1
```

而 Python 则是在运行期检查错误，上述代码实际上会产生一个 **runtime error（运行时错误）**。

有必要强调一下这里的编译期 **compile time** 和 **runtime** 指代的含义。这些词可能经常会见到，但是在不同的上下文中可以含义不太一样，在我们这里：

- **compile time**：泛指将一种代码编译为目标代码的时候，这时候程序还没有运行起来
-   - 对于 AOT 编译的语言，例如 C++，就是把 C++ 编译成机器码的过程
  - 对于 JIT 编译的语言，例如如 C#/Java，一般是指把源码编译成 IR 的过程
  - 对于转译语言来说，例如 TypeScript，则是把 TypeScript 编译成 JavaScript 的过程

- **runtime**：泛指程序实际运行的时候，比如机器码在 CPU 上执行的时候，或者字节码在虚拟机上执行的时候


因此 C++，Java，C#，TypeScript 被称作静态类型的语言。而 Python 虽然也有把源码编译到字节码这个阶段，但是这个阶段不进行类型检查，所以 Python 被称作动态类型的语言。

然而这并不绝对，静态语言和动态语言之间的界限并没有那么清晰，虽然 C++，Java，C#，TypeScript 是静态类型的语言，但是都提供了若干方法来绕过静态类型检查，比如 C++ 的`pointer`，Java/C# 的`Object`， TypeScript 的`Any`。而动态类型语言也逐渐在引入静态类型检查，比如 Python 的`type hint`，JavaScript 的`TypeScript`等等，二者都在相互借鉴对方的特性。

目前 C++ 只提供了`std::any`来进行类型擦除，但是很多时候它不够灵活。我们想要一些更加高级的功能，比如通过**字段名访问成员**，通过**函数名调用函数**，通过**类型名创造类实例**。 本文的目标就是在 C++ 中构建出类似 Java/C# 中的`Object`那样的动态的类型。

## 元类型 

我们这里不采用类似 Java/C# 中`Object`那种侵入式设计（继承），而是采用被叫做 fat pointer 非侵入式设计。所谓 fat pointer 其实就是一个结构体，包含了一个指向实际数据的指针，以及一个指向类型信息的指针。如果是继承的话，则是这个虚表指针存在对象头部。

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

其中的成员函数将会在后面的章节逐步实现，接下来我们先来考虑这个`Type`类型里面存的是什么。

## 元信息 

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

这里的内容很简单，我们在`Type`里面中存了类型名，析构函数，移动构造，拷贝构造，字段信息和方法信息。字段信息里面存的是字段类型和字段名，方法信息里面存的是方法名和函数地址。如果希望进一步扩展的话，还可以把父类的信息和重载函数的信息也存进来。由于这里只是做一个示例，就暂时不考虑它们了。

## 函数类型擦除 

为了把不同类型的成员函数存在同一个容器里面，我们必须要对函数类型进行擦除。所有类型的函数都被擦除成了 `Any(*)(void*, std::span<Any>)`这个类型。这里的`Any`类型就是我们上面定义的`Any`类型，这里的`void*`其实代表就是`this`指针，而`std::span<Any>`则是函数的参数列表。现在我们要考虑如何进行这种函数类型擦除。

以下面给定的成员函数`say`为例：

```cpp
struct Person {
    std::string_view name;
    std::size_t age;

    void say(std::string_view msg) { std::cout << name << " say: " << msg << std::endl; }
};
```

首先为了方便书写，我们把`Any`的`cast`实现一下：

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

利用 C++ 中无捕获的`lambda`能隐式转换成函数指针这个特性，可以轻松实现这种擦除。

```cpp
auto f = +[](void* object, std::span<Any> args) {
    auto& self = *static_cast<Person*>(object);
    self.say(args[0].cast<std::string_view>());
    return Any{};
};
```

其实原理很简单，只要写一个 wrapper 函数进行一下类型转换，然后转发调用就行了。但是如果每个成员函数都要手写这么一大段转发代码还是很麻烦的。我们可以考虑通过模板元进行代码生成，自动生成上面的代码，简化类型擦除的这个过程。

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

这里的代码我就不解释了，如果看不懂也没关系。其实就是通过模板元，把成员函数类型擦除的这个过程自动化了一下。只要知道如何使用就行了，使用起来是非常简单的。这里的`&Person::say`是 pointer to member 的写法，不太熟悉的可以参考 [C++ 成员指针完全解析](https://www.ykiko.me/zh-cn/articles/659510753)。

```cpp
auto f = type_ensure<&Person::say>();
// decltype(f) => Any (*)(void*, std::span<Any>)
```

## 类型信息注册 

事实上我们需要给每个类型都生成一个对应的`Type`结构来保存它的信息，这样的话才能正确访问。而这个功能就由上文提到的`type_of`函数负责。

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

我们提供一个默认实现，这样的话如果用到了内置的基础类型可以自动注册一些信息。然后可以通过特化给自定义的类型提供实现，好了，现在有了这些元信息我们可以把`Any`的成员函数实现补充完整了。

## Any 完整实现 

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

`foreach`的实现就是遍历所有的`Field`然后获取偏移量和类型，然后把它包装成`Any`类型。注意这里只是简单包装一下，实际上由于我们设置了`flag`，这个包装并不会导致多次析构。`invoke`就是从成员函数列表里面找出对应的函数，然后调用。

## 示例代码 

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

完整代码放在 [Github](https://github.com/16bit-ykiko/blog/blob/main/code/dynamic-type-demo.cpp) 上了，至此我们就已经实现了一个极度动态，非侵入式的`Any`了。

## 扩展和优化 

本文给出的只是非常简单的原理介绍，考虑的情况也十分简单。比如这里没有考虑继承和函数重载，在运行效率上也有若干可以优化的地方。尽管如此，可能我写的功能对你来说仍然是过多的。本文想主要表达的意思是，对于 C++ 这种非常注重性能的语言来说，有时候的确会在一些场景需要这些比较动态的特性。然而高效性和通用性往往是矛盾的，语言层面因为要考虑通用性，所以效率往往不尽如人意。例如`RTTI`和`dynamic_cast`常常被人抱怨，不过好在编译器提供选项来关闭它们。同样的，我的实现也不一定完全符合你的场景，但是懂得这并不困难的原理之后你完全可以根据你的场景来实现一个更加适合你的版本。

可以扩展的点：

- 支持根据`name`来修改成员
- 添加一个全局的`map`用于记录所有类型的信息，从而支持根据类名创造类的实例
- `...` 


可以优化的点：

- 减少`new`的次数，或者自己实现一个对象池
- 或者目前储存的元信息过多，根据你自己的需求进行裁剪


除此之外，现在还有一个痛点是，这些元信息我们都要手写，很难维护。如果要修改类内的定义还得把这些注册代码一并修改，否则就会出错。这里一个实际可行的方案是使用代码生成器来自动生成这些机械的代码。关于如何进行这些操作，可以参考本系列的其它文章。