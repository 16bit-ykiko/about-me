---
title: 'std::variant 很难用！'
date: 2023-07-25 07:19:25
updated: 2024-07-20 14:31:19
---

`std::variant`于 C++17 加入标准库，本文将讨论其加入标准的背景，以及一些使用上的问题。

## sum type 

首先来讨论一下**和类型 (sum type)**，或者叫做 [tagged union](https://en.wikipedia.org/wiki/Tagged_union)。和类型就是只能在几种可能的类型中取值的类型。

例如我们有如下两个类型

```cpp
struct Circle {
    double radius;
};

struct Rectangle {
    double width;
    double height;
};
```

那么`Circle`和`Rectangle`的和类型，比如我们就叫`Shape`吧，在 C 语言中可以这么实现

```cpp
struct Shape {
    enum Type { Circle, Rectangle } type;

    union {
        struct Circle circle;
        struct Rectangle rectangle;
    };
};
```

>  这里使用了叫做 [anonymous union](https://en.cppreference.com/w/cpp/language/union#Anonymous_unions) 的特性，相当于声明了一个对应类型的 union 成员，并且把字段名字注入到当前作用域。  

这样我们就可以给`Shape`类型的变量赋不同类型的值，同时更新记录下赋值时的`type`。访问的时候反过来根据`type`来决定按照哪种类型访问即可。例如

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

但在 C++ 中事情就没这么简单了，考虑如下代码

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

这段代码其实没法通过编译，编译器会报错`use of deleted function Settings::Settings()`。为什么`Settings`的构造函数被删除了呢？这其实是因为`std::string`的构造函数是 not trivial 的，当`union`中含有 not trivial 的类型的成员的时候，编译器无法正确的生成构造函数和析构函数（不知道你要初始化或者析构哪个成员）。详情原因请见的可以参考 cppreference 上对 [union](https://en.cppreference.com/w/cpp/language/union) 的介绍。

怎么解决呢？那就是我们自己来定义`union`的构造函数和析构函数。比如我们可以给它定义一个空的构造函数和析构函数，也就是什么都不做

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

使用的时候则要求我们通过 [placement new](https://en.cppreference.com/w/cpp/language/new#Placement_new) 显式调用构造函数来初始化某个成员，同样的，我们也要手动调用析构函数来销毁某个成员。

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

>  注意，这里不能**直接赋值 (assign)**。因为赋值操作其实是在调用成员函数`operator=`，而只有已经初始化过后的对象才能调用成员函数。 

从上面的代码不难看出，如果要在 C++ 里面直接使用 union 来表示 sum type，非常麻烦。不仅要及时更新`type`，还要正确调用构造函数和析构函数，还要留意赋值的时机问题赋值。如果其中的某一步忘记了，就会导致 undefined behavior，这非常让人头疼。不过还好，C++17 给我们提供了`std::variant`来解决这个问题。

## std::variant 

直接看代码

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

上面的代码完全是 well defined，通过模板元编程，`variant`会在合适和时机处理对象的构造和析构。

它有一个`index`成员函数可以获取当前类型在你写的类型列表里面的索引。

```cpp
Settings s;
s = std::string("hello"); // s.index() => 2
s = 1; // s.index() => 0
s = true; // s.index() => 1
```

使用用`std::get`可以从`variant`里面取出对应的值

```cpp
Settings s;
s = std::string("hello");
std::cout << std::get<std::string>(s); // => hello
```

有些人可能会疑惑，我都提前知道里面存的是`string`了，为什么还要用`std::variant`呢？注意到`get`还有一个模板参数是整数的重载，它能解决这个问题吗？

```cpp
std::cout << std::get<2>(s); // => hello
```

哦，我懂了。那既然能直接用`index`来获取，那直接下面这样写不就好了？

```cpp
std::cout << std::get<s.index()>(s);
```

很遗憾，想法是好的，但是这样做是不行的。模板参数必须是编译期常量，而`variant`作为一种类型擦除的手段，其`index`肯定是运行时的值。怎么办呢？动态转静态，只能一个个分发。例如

```cpp
if (s.index() == 0){
    std::cout << std::get<0>(s) << std::endl;
} else if (s.index() == 1){
    std::cout << std::get<1>(s) << std::endl;
} else if (s.index() == 2){
    std::cout << std::get<2>(s) << std::endl;
}
```

用数字的可读性是比较糟糕的，我们可以用`std::holds_alternative`来根据类型做判断

```cpp
if (std::holds_alternative<std::string>(s)){
    std::cout << std::get<std::string>(s) << std::endl;
} else if (std::holds_alternative<int>(s)){
    std::cout << std::get<int>(s) << std::endl;
} else if (std::holds_alternative<bool>(s)){
    std::cout << std::get<bool>(s) << std::endl;
}
```

虽然能行，但是太多冗余代码了，有没有什么更好的办法来操作`variant`里面的值呢？

## std::visit 

`visit`这个名字其实就来源于设计模式里面的那个`visitor`模式。利用它，我们可以写出如下代码

```cpp
Settings s;
s = std::string("hello");
auto callback = [](auto&& value){ std::cout << value << std::endl; };
std::visit(callback, s); // => hello
settings = 1;
std::visit(callback, s); // => 1
```

是不是很神奇呢？只需要传入一个`callback`，就能直接访问到`variant`里面的值了，不需要手动进行任何分发。软件工程领域有一条铁律：复杂度不会消失，只会转移，这里也不例外。其实`visit`内部帮你把`callback`根据`variant`里面的每个类型实例化了一份函数，预先打好了函数表，然后再运行时根据`index`直接调用函数表里面的函数就行了。

但更多时候，我们其实是想根据不同类型做不同的事情。这在其它语言中可以方便的通过模式匹配做到

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

很可惜，截止 C++23，C++ 还是没有模式匹配。想要在 C++ 写出类似上面代码的效果，目前有两种方案来自己模拟：

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

无论是哪种方法都比较别扭，用模板来做这种 trick，不仅编译慢报错还不好看。这也意味着目前的`variant`非常不好用，没有配套的语言设施来简化其操作，和模板深深地纠缠在一起，让人望而却步。