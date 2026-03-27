---
title: std::variant is hard to use!
date: "2023-07-25 07:19:25"
updated: "2024-07-20 14:31:19"
zhihu_article_id: "645810896"
zhihu_url: https://zhuanlan.zhihu.com/p/645810896
zhihu_column_id: c_1656510843973046272
zhihu_column_title: 魅力C++
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

`std::variant` was added to the standard library in C++17. This article will discuss the background of its inclusion and some issues related to its usage.

## sum type

First, let's discuss **sum types**, also known as [tagged unions](https://en.wikipedia.org/wiki/Tagged_union). A sum type is a type that can hold a value of only one of several possible types.

For example, if we have the following two types:

```cpp
struct Circle {
    double radius;
};

struct Rectangle {
    double width;
    double height;
};
```

Then a sum type of `Circle` and `Rectangle`, let's call it `Shape`, can be implemented in C as follows:

```cpp
struct Shape {
    enum Type { Circle, Rectangle } type;

    union {
        struct Circle circle;
        struct Rectangle rectangle;
    };
};
```

> This uses a feature called [anonymous union](https://en.cppreference.com/w/cpp/language/union#Anonymous_unions), which is equivalent to declaring a union member of the corresponding type and injecting its field names into the current scope.

This way, we can assign different types of values to a `Shape` variable, while also updating the `type` to record the type of the assigned value. When accessing, we can then use the `type` to determine which type to access it as. For example:

```cpp
void foo(Shape shape) {
    if(shape.type == Shape::Circle) {
        Circle c = shape.circle;
        printf("circle: radius is %f\n", c.radius);
    } else if(shape.type == Shape::Rectangle) {
        Rectangle r = shape.rectangle;
        printf("rectangle: width is %f, height is %f\n", r.width, r.height);
    }
}

int main() {
    Shape shape;
    shape.type = Shape::Circle;
    shape.circle.radius = 1.0;
    foo(shape);
    shape.type = Shape::Rectangle;
    shape.rectangle.width = 1.0;
    shape.rectangle.height = 2.0;
    foo(shape);
}
```

## not trivial

However, things are not so simple in C++. Consider the following code:

```cpp
struct Settings {
    enum class Type { int_, double_, string } type;

    union {
        int i;
        double d;
        std::string s;
    };
};

int main(){
    Settings settings;
    settings.type = Settings::Type::String;
    settings.s = std::string("hello");
}
```

This code actually won't compile. The compiler will report an error: `use of deleted function Settings::Settings()`. Why is the constructor for `Settings` deleted? This is because `std::string` has a non-trivial constructor. When a `union` contains members of non-trivial types, the compiler cannot correctly generate constructors and destructors (it doesn't know which member you intend to initialize or destroy). For more details, you can refer to the cppreference documentation on [union](https://en.cppreference.com/w/cpp/language/union).

How to solve this? We need to define the `union`'s constructor and destructor ourselves. For example, we can define an empty constructor and destructor for it, meaning they do nothing:

```cpp
union Value {
    int i;
    double d;
    std::string s;

    Value() {}
    ~Value() {}
};

struct Settings {
    enum class Type { int_, double_, string } type;
    Value value;
};
```

When using it, we are required to explicitly call the constructor to initialize a member using [placement new](https://en.cppreference.com/w/cpp/language/new#Placement_new). Similarly, we must manually call the destructor to destroy a member.

```cpp
int main(){
    Settings settings;

    settings.type = Settings::Type::string;
    new (&settings.value.s) std::string("hello");
    std::cout << settings.value.s << std::endl;
    settings.value.s.~basic_string();

    settings.type = Settings::Type::int_;
    new (&settings.value.i) int(1);
    std::cout << settings.value.i << std::endl;
    settings.value.i.~int();
}
```

> Note that you cannot **directly assign** here. This is because an assignment operation actually calls the member function `operator=`, and member functions can only be called on objects that have already been initialized.

From the code above, it's clear that directly using a union to represent a sum type in C++ is very cumbersome. Not only do you need to update `type` promptly, but you also need to correctly call constructors and destructors, and pay attention to the timing of assignments. Forgetting any of these steps can lead to undefined behavior, which is a major headache. Fortunately, C++17 provides `std::variant` to solve this problem.

## std::variant

Let's look directly at the code:

```cpp
#include <string>
#include <variant>

using Settings = std::variant<int, bool, std::string>;

int main() {
    Settings s = {1};
    s = true;
    s = std::string("hello");
}
```

The code above is completely well-defined. Through template metaprogramming, `variant` handles object construction and destruction at the appropriate times.

It has an `index` member function that can retrieve the index of the current active type within the list of types you provided.

```cpp
Settings s;
s = std::string("hello"); // s.index() => 2
s = 1; // s.index() => 0
s = true; // s.index() => 1
```

You can use `std::get` to retrieve the corresponding value from the `variant`.

```cpp
Settings s;
s = std::string("hello");
std::cout << std::get<std::string>(s); // => hello
```

Some might wonder, "If I already know it stores a `string`, why would I use `std::variant`?" Notice that `get` also has an overload where the template parameter is an integer. Can that solve this problem?

```cpp
std::cout << std::get<2>(s); // => hello
```

Oh, I see. Since I can get it directly using `index`, why not just write it like this?

```cpp
std::cout << std::get<s.index()>(s);
```

Unfortunately, while the idea is good, this won't work. Template parameters must be compile-time constants, and `variant`, as a means of type erasure, will have its `index` value determined at runtime. What to do then? To convert dynamic to static, you have to dispatch one by one. For example:

```cpp
if (s.index() == 0){
    std::cout << std::get<0>(s) << std::endl;
} else if (s.index() == 1){
    std::cout << std::get<1>(s) << std::endl;
} else if (s.index() == 2){
    std::cout << std::get<2>(s) << std::endl;
}
```

Using numbers for readability is quite poor. We can use `std::holds_alternative` to check based on type:

```cpp
if (std::holds_alternative<std::string>(s)){
    std::cout << std::get<std::string>(s) << std::endl;
} else if (std::holds_alternative<int>(s)){
    std::cout << std::get<int>(s) << std::endl;
} else if (std::holds_alternative<bool>(s)){
    std::cout << std::get<bool>(s) << std::endl;
}
```

While it works, there's too much redundant code. Is there a better way to operate on the value inside a `variant`?

## std::visit

The name `visit` actually comes from the `visitor` design pattern. Using it, we can write code like this:

```cpp
Settings s;
s = std::string("hello");
auto callback = [](auto&& value){ std::cout << value << std::endl; };
std::visit(callback, s); // => hello
settings = 1;
std::visit(callback, s); // => 1
```

Isn't that amazing? You just need to pass a `callback`, and you can directly access the value inside the `variant` without any manual dispatch. There's an iron rule in software engineering: complexity doesn't disappear, it just moves around, and this is no exception. In fact, `visit` internally instantiates a function for each type within the `variant` based on your `callback`, pre-builds a function table, and then at runtime, directly calls the function from that table based on the `index`.

More often, however, we want to do different things based on different types. This can be conveniently achieved through pattern matching in other languages:

**Haskell:**

```haskell
data Settings = IntValue Int | BoolValue Bool | StringValue String
  deriving (Show, Eq)

match :: Settings -> IO ()
match (IntValue x) = putStrLn $ "Int: " ++ show (x + 1)
match (BoolValue x) = putStrLn $ "Bool: " ++ show (not x)
match (StringValue x) = putStrLn $ "String: " ++ (x ++ " ")
```

**Rust:**

```rust
enum Settings{
    Int(i32),
    Bool(bool),
    String(String),
}

fn main(){
    let settings = Settings::Int(1);
    match settings{
        Settings::Int(x) => println!("Int: {}", x + 1),
        Settings::Bool(x) => println!("Bool: {}", !x),
        Settings::String(x) => println!("String: {}", x + " "),
    }
}
```

Unfortunately, as of C++23, C++ still lacks pattern matching. To achieve an effect similar to the code above in C++, there are currently two ways to simulate it:

**function overload:**

```cpp
template<typename ...Ts>
struct Overload : Ts... { using Ts::operator()...; };

template<typename ...Ts>
Overload(Ts...) -> Overload<Ts...>;

int main() {
    using Settings = std::variant<int, bool, std::string>;
    Overload overloads{
        [](int x) { std::cout << "Int: " << x << std::endl; },
        [](bool x) { std::cout << "Bool: " << std::boolalpha << x << std::endl; },
        [](std::string x) { std::cout << "String: " << x << std::endl; },
    };
    Settings settings = 1;
    std::visit(overloads, settings);
}
```

**if constexpr:**

```cpp
int main() {
    using Settings = std::variant<int, bool, std::string>;
    auto callback = [](auto&& value) {
        using type = std::decay_t<decltype(value)>;
        if constexpr(std::is_same_v<type, int>) {
            std::cout << "Int: " << value + 1 << std::endl;
        } else if constexpr(std::is_same_v<type, bool>) {
            std::cout << "Bool: " << !value << std::endl;
        } else if constexpr(std::is_same_v<type, std::string>) {
            std::cout << "String: " << value << std::endl;
        }
    };
    Settings settings = 1;
    std::visit(callback, settings);
}
```

Both methods are quite awkward. Using templates for such tricks not only slows down compilation but also results in less readable error messages. This also means that the current `variant` is very difficult to use, lacking accompanying language features to simplify its operations, and is deeply entangled with templates, making it daunting for users.
