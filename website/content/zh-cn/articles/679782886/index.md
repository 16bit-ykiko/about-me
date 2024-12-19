---
title: 'C++ 中的 relocate 语义'
date: 2024-01-25 09:22:29
updated: 2024-12-18 03:45:31
---

众所周知，现在 C++ 里面有两种特殊的构造函数，即 copy constructor 和 move constructor

copy constructor 早在 C++98 的时候就加入了，用来拷贝一个对象，像`vector`这种拥有资源的类型，拷贝的时候会把它拥有的资源也拷贝一份

```cpp
std::vector<int> v1 = {1, 2, 3};
std::vector<int> v2 = v1; // copy
```

当然了，拷贝的开销有些时候非常大，而且完全没必要。于是在 C++11 加入了 move constructor，用来把一个对象的资源转移到另一个对象上。这样相对于直接拷贝，开销是小得多的

```cpp
std::vector<int> v1 = {1, 2, 3};
std::vector<int> v2 = std::move(v1); // move
```

注意 C++ 中的 move 被叫做 *non-destructive move。* C++ 标准规定了，被移动过后的对象状态是一种 *valid state* ，实现需要保证它能够正常调用析构函数。**被移动的对象仍然可能被再次使用**（具体能否使用取决于实现）。

## 结束了？ 

有这两个构造函数就足够了吗？当然没有。事实上还有另一种广泛使用的操作，可以把它叫做 **relocate** 操作。考虑如下场景

假设你正在实现一个`vector`，扩容是必要的，于是你写了一个私有成员函数`grow`用来进行扩容（下面的代码示例暂时忽略异常安全）

```cpp
void grow(std::size_t new_capacity) 
{
    auto new_data = malloc(new_capacity * sizeof(T));
    for (std::size_t i = 0; i < m_Size; ++i) 
    {
        new (new_data + i) T(std::move(m_Data[i]));
        m_Data[i].~T();
    }
    free(m_Data); 
    m_Data = new_data;
    m_Capacity = new_capacity;
}
```

上面的代码很简单，先通过`malloc`分配新的内存，然后通过 [placement new](https://en.cppreference.com/w/cpp/language/new#Placement_new) 在新分配的内存上调用移动构造进行初始化。注意，正如前文提到的： C++ 中的 move 是 non-destructive 的，所以需要在调用完移动构造之后，原对象还需要调用析构函数，来正确的结束生存期。最后释放原来的内存，更新成员变量的值就行了。

*注：构造和析构的步骤也可以采用 C++20 加入的 std::construct_at 和 std::destroy_at，其实就是对 placement new 和 destroy 的封装。* 

但是这样的实现并不高效，在 C++ 中有一个 [trivially copyable](https://en.cppreference.com/w/cpp/named_req/TriviallyCopyable) 的概念，可以通过`is_trivially_copyable`这个 triat 来进行判断。满足这个约束的类型，可以直接使用`memcpy`或者`memmove`来进行拷贝得到一个新的对象。考虑下面这个例子：

```cpp
struct Point
{
    int x;
    int y;
}; 

static_assert(std::is_trivially_copyable_v<Point>);

Point points[3] = {{1, 2}, {3, 4}, {5, 6}};
Point new_points[3];
std::memcpy(new_points, points, sizeof(points));
```

不仅仅省去了多次函数调用，而且`memcpy`和`memmove`本身就是高度优化的 builtin 函数（可以通过 SIMD 进行向量化）。所以效率相比于直接调用拷贝构造进行复制效率会高很多。

为了让我们的`vector`更快，我们也可以做一下这种优化，利用 C++17 加入的`if constexpr`来做编译期判断，很轻松的写出下面的代码

```cpp
void grow(std::size_t new_capacity) 
{
    auto new_data = malloc(new_capacity * sizeof(T));
    if constexpr (std::is_trivially_copyable_v<T>) 
    {
        std::memcpy(new_data, m_Data, m_Size * sizeof(T));
    }
    else if constexpr (std::is_move_constructible_v<T>) 
    {
        for (std::size_t i = 0; i < m_Size; ++i) 
        {
            std::construct_at(new_data + i, std::move(m_Data[i]));
            std::destroy_at(m_Data + i);
        }
    }
    else if constexpr (std::is_copy_constructible_v<T>) 
    {
        for (std::size_t i = 0; i < m_Size; ++i) 
        {
            std::construct_at(new_data + i, m_Data[i]);
            std::destroy_at(m_Data + i);
        }
    } 
    free(m_Data); 
    m_Data = new_data;
    m_Capacity = new_capacity;
}
```

*注：也可以考虑直接使用 C++17 加入的 uninitialized_move_n 和 destroy_n 避免重新造轮子，这些函数已经进行过类似的优化了。不过由于指针 alisa 的问题，它们可能最多优化成memmove，而在这个vector扩容的场景，可以进一步优化成memcpy，所以还是自己优化效果更好。 * 

## 大材小用 

这样总感觉怪怪的，我们主要的目的是把就旧内存上的对象全部移动到新内存上，但是用的居然是 [trivially copyable](https://en.cppreference.com/w/cpp/named_req/TriviallyCopyable) 这个 trait，似乎约束过强了。完全创建一个新对象和把原来的对象放置到新的位置，感觉差别还挺大的。考虑下面这个例子。似乎直接对`std::string`这样的类型进行`memcpy`也是可以的。由于内存都是我们手动管理，析构函数也是我们手动调用，并不会出现多次调用析构函数的情况

```cpp
std::byte buffer[sizeof(std::string)];
auto& str1 = *std::construct_at((std::string*) buffer, "hello world");

std::byte new_buffer[sizeof(std::string)];
std::memcpy(new_buffer, buffer, sizeof(std::string));
auto& str2 = *(std::string*) new_buffer;

str2.~basic_string();
```

仔细思考一下数据的流向和析构函数的调用，发现没有任何不妥。似乎我们应该寻找一种叫做 trivially moveable 的概念，用来放宽松条件，从而使更多的类型得到优化。很可惜，目前 C++ 标准中并没有这样的概念。为了和 C++ 已经存在的 move 操作区分开来，我们把这种操作叫做 relocate，即把原本的对象放置在一个全新的位置。

事实上有很多著名的开源组件也都通过模板特化来实现了类似的功能，例如 

- [BSL](https://github.com/bloomberg/bde/blob/962f7aa/groups/bsl/bslmf/bslmf_isbitwisemoveable.h#L8-L48) 的`bslmf::IsBitwiseMoveable<T>` 
- [Folly](https://github.com/facebook/folly/blob/main/folly/docs/FBVector.md#object-relocation) 的`folly::IsRelocatable<T> ` 
- [QT](https://github.com/qt/qtbase/) 的`QTypeInfo<T>::isRelocatable` 


通过对特定的类型进行标记，使得它们可以拥有这种优化。但是，上面的优化只是在我们逻辑上认为相等，严格来说目前这样写在 C++ 中算是 undefined behavior。那怎么办？只能想办法通过新提案，修改标准措辞，来支持上面的优化。

## 现状 

首先这个问题早就被发现了，例如知乎上很久之前就有相关的讨论：

- [比起 malloc new / free old，realloc 在性能上有多少的优势?](https://www.zhihu.com/question/316026652/answer/623722536)
- [C++ vector 的 push_back 扩容机制为什么不考虑在尾元素后面的空间申请内存?](https://www.zhihu.com/question/384869006/answer/1130101522)


类似的问题还有挺多的。`realloc`会尝试在原地扩容，如果失败。就会尝试分配一块新的内存，然后用`memcpy`把原来的数据拷贝到新的内存上。所以在目前的 C++ 标准中，如果你想要直接使用`realloc`进行扩容的话，必须要保证对象是 trivially copyable 的。当然，前面已经说了，这个条件是比较苛刻的，需要引入新的概念来放宽条件。

相关的提案最早在 2015 年就被提出了，在 2023 年仍然活跃的提案主要有下面四个（目标都是 C++26）：

- [std::is_trivially_relocatable](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2023/p1144r9.html)
- [Trivial Relocatability For C++26](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2024/p2786r4.pdf)
- [Relocating prvalues](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2023/p2785r3.html)
- [Nontrivial Relocation via a New owning reference Type](https://isocpp.org/files/papers/D2839R1.html#part-i-owning-references-and-defaulted-relocation-constructors)


大概可以分为两派，保守派和激进派

### 保守派 

保守派的解决方案是添加 relocatable 和 trivally-relocatable 的概念，以及用来判断的相关 trait。

如果一个类型是 move-constructible 且 destructible 的，那么它就是 relocatable 的

如果一个类型满足下列条件之一，那么它就是 trivally-relocatable 的

- 是一个 trivially-copyable 的类型
- 是一个 trivally-relocatable 类型的数组
- 是一个用具有值为 true 的`trivially_relocatable`属性声明的类类型
- 是一个类类型，满足以下条件：
-   - 没有用户提供的移动构造函数或移动赋值运算符
  - 没有用户提供的复制构造函数或复制赋值运算符
  - 没有用户提供的析构函数
  - 没有虚拟成员函数
  - 没有虚基类
  - 每个成员都是引用或者 trivally-relocatable 类型，并且所有基类都是 trivally-relocatable 类型



可以通过新的 attribute ——`trivially_relocatable` 来显式标记一个类型为 trivally-relocatable，它可以用常量表达式作为参数，来支持泛型类型

```cpp
template<typename T>
struct [[trivially_relocatable(std::std::is_trivially_relocatable_v<T>)]] X { T t; };
```

还增加了一些新的操作：

```cpp
template<class T>
T *relocate_at(T* source, T* dest);

template<class T>
[[nodiscard]] remove_cv_t<T> relocate(T* source);
// ...
template<class InputIterator, class Size, class NoThrowForwardIterator>
auto uninitialized_relocate_n(InputIterator first, Size n, NoThrowForwardIterator result);
```

这些函数都是由编译器实现的，效果上等同于 move + destroy 原对象。并且允许编译器在满足 as-if 规则的前提下，把对 trivially_relocatable 的类型的操作优化成`memcpy`或者`memmove`。对于那些不能优化的结构，比如含有自引用的结构，就正常调用移动构造 + 析构函数就行了。这样在实现`vector`的时候，直接使用这些标准库提供的函数就可以享受优化了。

该提案之所以被称作保守派，最大的原因就是它既不影响原来的 API，也不影响原来的 ABI，具有较强的兼容性，引入进来十分方便。

### 激进派 

更为激进的就是今天的主角了，它主张引入 relocate constructor，并且引入了新的关键字`reloc`

`reloc`是一个一员运算符，可以用于函数非静态局部变量，`reloc`用于执行如下操作

- 如果变量是引用类型，则进行完美转发
- 如果不是则把源对象变成纯右值并返回


并且被`reloc`过后的对象，如果再次使用被认为是编译错误（实际判定的规则会更加详细，详见提案里面的相关小节）

然后引入了一个新的构造函数，即 relocate constructor（重定位构造函数），具有如下形式`T(T)`，函数参数是`T`类型的纯右值。选择这个作为函数签名是为了完善 C++ value category 体系。目前（C++17）及以后，C++ 的拷贝构造函数从 lvalue 创建对象，移动构造函数从 xvalue 创建对象，而重定位构造函数则是从 prvalue 创建对象。这样就完整的覆盖了所有的 value category，对于重载决议来说是十分友好的，语义上也十分和谐融洽。

```cpp
struct X
{
    std::string s;
    X(X x): s(std::move(x.s)) {}
}
```

另外一个好处是，目前这种`T(T)`声明的构造函数是不允许的，所以不会和现有的代码冲突。有一点需要注意，相信之前大家可能听人这样解释过，为什么拷贝构造函数的参数必须是引用？因为如果不是引用的话，函数传参也需要拷贝，就会导致无限递归。

事实上这种解释已经过时了，由于 C++17 引入的强制性的 [copy elision](https://en.cppreference.com/w/cpp/language/copy_elision)。即使一个类型没有拷贝构造函数和移动构造函数，它也可以直接从纯右值构造，并且没有任何拷贝/移动构造函数的调用

```cpp
struct X
{
    X() = default;
    X(const X&) = delete;
    X(X&&) = delete;
};

X f(){ return X{}; };

X x = f();
```

上述的代码在开启 C++17 之后各大编译器都能编译通过。所以这里`T(T)`的这种构造函数的形式并不会导致无限递归。该提案也引入了重定位赋值函数，具有如下形式`T& operator=(T)`，函数参数是`T`类型的纯右值。当然，也还有 trivially-relocatable 的概念，允许满足这个条件的重定位构造函数被优化为`memcpy`。但是，这是通过重定位构造函数等规则来进行判断的，用户不能显式通过 attribute 进行标记。我觉得这一点并不好，应该允许用户手动标记一个类型为 trivially-relocatable。`tuple`就是由于目前的实现限制，必须要写一个构造函数，从而导致永远不能是 trivially-copyable 的了，pair 居然也不是 trivially-copyable 的，显然这不合理。所以希望该提案以后能支持通过 attribute 来标记一个类型为 trivially-relocatable。

我个人是比较喜欢这个提案的，有了它以后，我甚至感觉 C++ 的 value category 系统能够和优雅挂钩了。在这之前，我一直觉得 value category 这个系统是混乱邪恶的，是为了兼容以前的旧代码打的烂补丁。但是如果该提案通过以后

- 左值 —— 拷贝构造
- 亡值 —— 移动构造
- 纯右值 —— 重定位构造


有一种逻辑完全自洽的美感。提案中其它的细节，就比较琐碎了，这里就省略了。感兴趣的读者可以自己阅读。

## 为什么过多这么久还没进入标准 

关于为什么过了这么多年这个问题仍然没有解决，其实这是一段相当长的历史，是 C++ 的对象模型存在缺陷导致的。直到 C++20 的 [隐式生存期提案](https://en.cppreference.com/w/cpp/language/lifetime) 被接受之前，在最开始的扩容函数实现中，连把 trivially-copyable 的类型优化为 memcpy 都是 undefined behavior。

当然，不要听到 undefined behavior 就害怕，觉得心里面有道坎一样。事实上这一直被认为是标准的缺陷，这种优化早已经广泛实践各大代码库之中了，可靠性已经得到验证。只是 C++ 标准一直没有合适的措辞来描述这种情况，完全认为是 UB 肯定是不对的，不加限制的使用也是不对的，所以问题的关键就是如何在这两者之间如何找出一个合适的边界了。最近我会专门写一篇文章来介绍 C++ 对象模型相关的内容，这里就不展开了。

## 其它语言 

C++ 固然有各种不足，考虑到历史兼容性等因素，导致设计放不开手脚。那新语言呢？它们是如何解决这些问题的？

### Rust 

首先先看最近比较火热的 Rust。其实，只要结构中不含有自引用的成员，那么使用`memcpy`把旧的对象移动到新的内存上，几乎总是可行的。另外，Rust 并没有什么多继承虚函数（虚表结构复杂）啦，虚继承啦，这种比较奇怪的东西（并且实际用到的地方很少），所以几乎所有的类型都可以直接使用`memcpy`来从旧对象创建一个新对象。刚好 Safe Rust 中的 move 语义还是 destructive move，所以它的 move 的默认实现就是直接`memcpy`，是清爽很多。

但是默认的移动只能移动局部非静态变量，如果一个变量是引用，那么你就没法移动它。不过还好 Safe Rust 提供了一个 [std::mem::take](https://doc.rust-lang.org/std/mem/fn.take.html) 函数用来解决这个问题：

```rust
use std::mem;

let mut v: Vec<i32> = vec![1, 2];

let old_v = mem::take(&mut v);
assert_eq!(vec![1, 2], old_v);
assert!(v.is_empty());
```

效果是，移动 + 原对象置空，比较类似于 C++ 中的 move。还有 [std::mem::swap](https://doc.rust-lang.org/std/mem/fn.swap.html) 和 [std::mem::replace](https://doc.rust-lang.org/std/mem/fn.replace.html) 用于其它需要从引用处进行移动的场景。

虽然可能情况不多，但是如果一个类型含有自引用的结构怎么办？事实上，允许用户自定义构造函数是一个比较简单的解决办法，但是 Rust 社区对此似乎比较反感。目前的解决方案是通过 Pin，不过 Rust 社区似乎对这个解决方案也不是很满意，它很难理解且很难使用。未来全新的设计应该和 linear type 有关，相关的讨论详见 [Changing the rules of Rust](https://without.boats/blog/changing-the-rules-of-rust/)。

### Mojo 

这个语言前些日子也在知乎上也宣传过一波，但是目前还处于完全早期的状态，不过一开始人家就考虑提供四种构造函数

- `__init__()`
- `__copy__()`
- `__move__()`
- `__take__()`


其中 copy 就类似于 拷贝构造函数，move 类似于重定位构造函数，take 则类似于现在的移动构造函数。更多的细节就无从得知了。