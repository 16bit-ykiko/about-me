---
title: 'std::variant is Hard to Use!'
date: 2023-07-25 15:19:25
updated: 2024-07-20 22:31:19
---

`std::variant` was introduced into the C++ standard library in C++17. This article will discuss the background of its inclusion in the standard and some issues with its usage.

## Sum Type

First, let's discuss **sum types**, also known as [tagged unions](https://en.wikipedia.org/wiki/Tagged_union). A sum type is a type that can hold one of several possible types.

For example, consider the following two types:

```cpp
struct Circle {
    double radius;
};

struct Rectangle {
    double width;
    double height;
};
```

The sum type of `Circle` and `Rectangle`, let's call it `Shape`, can be implemented in C as follows:

```cpp
struct Shape {
    enum Type { Circle, Rectangle } type;

    union {
        struct Circle circle;
        struct Rectangle rectangle;
    };
};
```

> Here, we use a feature called [anonymous union](https://en.cppreference.com/w/cpp/language/union#Anonymous_unions), which declares a union member of the corresponding type and injects the field names into the current scope.

This allows us to assign values of different types to a variable of type `Shape`, while updating the `type` to reflect the current assignment. When accessing the value, we can determine how to access it based on the `type`. For example:

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

## Not Trivial

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

This code will not compile. The compiler will report an error: `use of deleted function Settings::Settings()`. Why is the constructor of `Settings` deleted? This is because the constructor of `std::string` is not trivial. When a `union` contains members of non-trivial types, the compiler cannot correctly generate constructors and destructors (it doesn't know which member to initialize or destruct). For more details, refer to the [union](https://en.cppreference.com/w/cpp/language/union) section on cppreference.

How can we solve this? We need to define the constructor and destructor for the `union` ourselves. For example, we can define an empty constructor and destructor that do nothing:

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

When using this, we need to explicitly call the constructor to initialize a member using [placement new](https://en.cppreference.com/w/cpp/language/new#Placement_new), and similarly, we need to manually call the destructor to destroy a member.

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

> Note that you cannot **directly assign** here. The assignment operation actually calls the member function `operator=`, and only objects that have already been initialized can call member functions.

From the above code, it's clear that directly using `union` to represent sum types in C++ is very cumbersome. Not only do you need to update the `type` in time, but you also need to correctly call constructors and destructors, and be careful about the timing of assignments. If any step is forgotten, it can lead to undefined behavior, which is very frustrating. Fortunately, C++17 provides `std::variant` to solve this problem.

## std::variant

Let's look at the code directly:

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

The above code is completely well-defined. Through template metaprogramming, `variant` handles object construction and destruction at the appropriate times.

It has an `index` member function that can get the index of the current type in the type list you provided.

```cpp
Settings s;
s = std::string("hello"); // s.index() => 2
s = 1; // s.index() => 0
s = true; // s.index() => 1
```

You can use `std::get` to retrieve the corresponding value from the `variant`:

```cpp
Settings s;
s = std::string("hello");
std::cout << std::get<std::string>(s); // => hello
```

Some might wonder, if I already know that it contains a `string`, why use `std::variant`? Note that `get` also has an overload with an integer template parameter. Can it solve this problem?

```cpp
std::cout << std::get<2>(s); // => hello
```

Oh, I see. So if I can use `index` directly to get the value, why not write it like this?

```cpp
std::cout << std::get<s.index()>(s);
```

Unfortunately, this won't work. Template parameters must be compile-time constants, and `variant`, as a type-erasure mechanism, has an `index` that is definitely a runtime value. What to do? Dynamic to static, you can only dispatch one by one. For example:

```cpp
if (s.index() == 0){
    std::cout << std::get<0>(s) << std::endl;
} else if (s.index() == 1){
    std::cout << std::get<1>(s) << std::endl;
} else if (s.index() == 2){
    std::cout << std::get<2>(s) << std::endl;
}
```

Using numbers is not very readable. We can use `std::holds_alternative` to make decisions based on types:

```cpp
if (std::holds_alternative<std::string>(s)){
    std::cout << std::get<std::string>(s) << std::endl;
} else if (std::holds_alternative<int>(s)){
    std::cout << std::get<int>(s) << std::endl;
} else if (std::holds_alternative<bool>(s)){
    std::cout << std::get<bool>(s) << std::endl;
}
```

Although this works, there's too much redundant code. Is there a better way to operate on the values inside a `variant`?

## std::visit

The name `visit` actually comes from the `visitor` pattern in design patterns. Using it, we can write the following code:

```cpp
Settings s;
s = std::string("hello");
auto callback = [](auto&& value){ std::cout << value << std::endl; };
std::visit(callback, s); // => hello
settings = 1;
std::visit(callback, s); // => 1
```

Isn't it magical? Just pass in a `callback`, and you can directly access the value inside the `variant` without any manual dispatching. In software engineering, there's a golden rule: complexity doesn't disappear, it just shifts. This is no exception. In fact, `visit` internally instantiates a function for each type in the `variant` for your `callback`, pre-generates a function table, and then at runtime, directly calls the function in the table based on the `index`.

But more often, we want to do different things based on different types. In other languages, this can be conveniently achieved through pattern matching.

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

Unfortunately, as of C++23, C++ still lacks pattern matching. To achieve similar effects in C++, there are currently two ways to simulate it:

**Function Overload:**

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

Both methods are somewhat awkward. Using templates for such tricks not only slows down compilation but also makes error messages harder to understand. This also means that `variant` is currently very difficult to use, lacking the necessary language facilities to simplify its operations, deeply entangled with templates, and discouraging to many.