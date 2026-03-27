---
title: Relocate Semantics in C++
date: "2024-01-25 09:22:29"
updated: "2024-12-18 03:45:31"
zhihu_article_id: "679782886"
zhihu_url: https://zhuanlan.zhihu.com/p/679782886
zhihu_column_id: c_1656510843973046272
zhihu_column_title: 魅力C++
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

As is well known, there are currently two special constructors in C++: the copy constructor and the move constructor.

The copy constructor was added in C++98 to copy an object. For resource-owning types like `vector`, copying involves copying the resources it owns.

```cpp
std::vector<int> v1 = {1, 2, 3};
std::vector<int> v2 = v1; // copy
```

Of course, the overhead of copying can sometimes be very large and completely unnecessary. Therefore, C++11 introduced the move constructor to transfer an object's resources to another object. This results in much lower overhead compared to direct copying.

```cpp
std::vector<int> v1 = {1, 2, 3};
std::vector<int> v2 = std::move(v1); // move
```

Note that move in C++ is called _non-destructive move_. The C++ standard specifies that the state of an object after being moved is a _valid state_, and the implementation must ensure that its destructor can be called normally. **A moved-from object may still be used again** (whether it can be used depends on the implementation).

## Is that all?

Are these two constructors enough? Certainly not. In fact, there's another widely used operation that can be called **relocate**. Consider the following scenario:

Suppose you are implementing a `vector`, and resizing is necessary. So you write a private member function `grow` for resizing (the following code example temporarily ignores exception safety).

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

The code above is simple: first, allocate new memory using `malloc`, then initialize objects in the newly allocated memory by calling the move constructor via [placement new](https://en.cppreference.com/w/cpp/language/new#Placement_new). Note, as mentioned earlier: move in C++ is non-destructive, so after calling the move constructor, the original object still needs its destructor called to correctly end its lifetime. Finally, free the original memory and update the member variables.

_Note: The construction and destruction steps can also use `std::construct_at` and `std::destroy_at` introduced in C++20, which are essentially wrappers for placement new and destroy._

However, this implementation is not efficient. In C++, there is a concept called [trivially copyable](https://en.cppreference.com/w/cpp/named_req/TriviallyCopyable), which can be checked using the `is_trivially_copyable` trait. For types satisfying this constraint, a new object can be created by directly using `memcpy` or `memmove`. Consider this example:

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

This not only saves multiple function calls, but `memcpy` and `memmove` themselves are highly optimized builtin functions (which can be vectorized using SIMD). Therefore, their efficiency is much higher compared to direct copying via copy constructors.

To make our `vector` faster, we can also apply this optimization. Using `if constexpr` introduced in C++17 for compile-time checks, we can easily write the following code:

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

_Note: One could also consider directly using `uninitialized_move_n` and `destroy_n` introduced in C++17 to avoid reinventing the wheel, as these functions already include similar optimizations. However, due to pointer aliasing issues, they might at most optimize to `memmove`. In the context of `vector` resizing, it can be further optimized to `memcpy`, so optimizing it ourselves yields better results._

## Overkill

This feels a bit strange. Our main goal is to move all objects from old memory to new memory, but we are using the [trivially copyable](https://en.cppreference.com/w/cpp/named_req/TriviallyCopyable) trait, which seems too restrictive. Creating a completely new object and relocating an existing object to a new position feel quite different. Consider the following example. It seems that directly `memcpy`ing types like `std::string` is also possible. Since we manually manage memory and manually call destructors, there won't be multiple destructor calls.

```cpp
std::byte buffer[sizeof(std::string)];
auto& str1 = *std::construct_at((std::string*) buffer, "hello world");

std::byte new_buffer[sizeof(std::string)];
std::memcpy(new_buffer, buffer, sizeof(std::string));
auto& str2 = *(std::string*) new_buffer;

str2.~basic_string();
```

Carefully considering the data flow and destructor calls, we find nothing amiss. It seems we should look for a concept called "trivially moveable" to relax the conditions and allow more types to be optimized. Unfortunately, there is no such concept in the current C++ standard. To distinguish it from the existing C++ move operation, we call this operation "relocate," meaning to place the original object in a completely new location.

In fact, many famous open-source components have also implemented similar functionalities through template specialization, such as:

- [BSL](https://github.com/bloomberg/bde/blob/962f7aa/groups/bsl/bslmf/bslmf_isbitwisemoveable.h#L8-L48)'s `bslmf::IsBitwiseMoveable<T>`
- [Folly](https://github.com/facebook/folly/blob/main/folly/docs/FBVector.md#object-relocation)'s `folly::IsRelocatable<T>`
- [QT](https://github.com/qt/qtbase/)'s `QTypeInfo<T>::isRelocatable`

By marking specific types, they can benefit from this optimization. However, the above optimization is only logically equivalent in our minds; strictly speaking, writing it this way is currently undefined behavior in C++. So what to do? We can only try to introduce a new proposal and modify the standard wording to support the above optimization.

## Current Status

First, this problem has been discovered a long time ago. For example, there have been related discussions on Zhihu for a while:

- [Compared to malloc new / free old, how much performance advantage does realloc have?](https://www.zhihu.com/question/316026652/answer/623722536)
- [Why doesn't C++ vector's push_back resizing mechanism consider allocating memory after the tail element?](https://www.zhihu.com/question/384869006/answer/1130101522)

There are quite a few similar issues. `realloc` attempts to resize in place; if it fails, it tries to allocate a new block of memory and then uses `memcpy` to copy the original data to the new memory. So, in the current C++ standard, if you want to use `realloc` directly for resizing, you must ensure that the object is trivially copyable. Of course, as mentioned earlier, this condition is quite strict, and a new concept needs to be introduced to relax it.

Related proposals were first put forward in 2015. The main active proposals in 2023 (all targeting C++26) are the following four:

- [std::is_trivially_relocatable](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2023/p1144r9.html)
- [Trivial Relocatability For C++26](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2024/p2786r4.pdf)
- [Relocating prvalues](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2023/p2785r3.html)
- [Nontrivial Relocation via a New owning reference Type](https://isocpp.org/files/papers/D2839R1.html#part-i-owning-references-and-defaulted-relocation-constructors)

They can roughly be divided into two factions: conservatives and radicals.

### Conservatives

The conservative solution is to add the concepts of `relocatable` and `trivially-relocatable`, along with corresponding traits for checking.

A type is `relocatable` if it is move-constructible and destructible.

A type is `trivially-relocatable` if it satisfies one of the following conditions:

- It is a trivially-copyable type.
- It is an array of trivially-relocatable types.
- It is a class type declared with the `trivially_relocatable` attribute having a true value.
- It is a class type satisfying the following conditions:
  - No user-provided move constructor or move assignment operator.
  - No user-provided copy constructor or copy assignment operator.
  - No user-provided destructor.
  - No virtual member functions.
  - No virtual base classes.
  - Every member is a reference or a trivially-relocatable type, and all base classes are trivially-relocatable types.

A new attribute, `trivially_relocatable`, can be used to explicitly mark a type as trivially-relocatable. It can take a constant expression as an argument to support generic types.

```cpp
template<typename T>
struct [[trivially_relocatable(std::std::is_trivially_relocatable_v<T>)]] X { T t; };
```

Some new operations have also been added:

```cpp
template<class T>
T *relocate_at(T* source, T* dest);

template<class T>
[[nodiscard]] remove_cv_t<T> relocate(T* source);
// ...
template<class InputIterator, class Size, class NoThrowForwardIterator>
auto uninitialized_relocate_n(InputIterator first, Size n, NoThrowForwardIterator result);
```

These functions are implemented by the compiler and effectively perform a move + destroy of the original object. They also allow the compiler, under the as-if rule, to optimize operations on trivially_relocatable types into `memcpy` or `memmove`. For structures that cannot be optimized, such as those containing self-references, the move constructor + destructor is called normally. This way, when implementing `vector`, using these standard library functions directly allows for optimization.

This proposal is called conservative primarily because it does not affect existing APIs or ABIs, offering strong compatibility and ease of introduction.

### Radicals

The more radical approach, which is the main topic today, advocates for introducing a relocate constructor and a new keyword `reloc`.

`reloc` is a unary operator that can be used on non-static local variables of functions. `reloc` performs the following operations:

- If the variable is a reference type, it performs perfect forwarding.
- Otherwise, it converts the source object into a prvalue and returns it.

Furthermore, an object that has been `reloc`ated is considered a compile-time error if used again (the actual rules for determination are more detailed; see the relevant sections in the proposal).

A new constructor, the relocate constructor, is introduced with the form `T(T)`, where the function parameter is a prvalue of type `T`. This signature was chosen to complete the C++ value category system. Currently (C++17) and beyond, C++ copy constructors create objects from lvalues, move constructors create objects from xvalues, and relocate constructors create objects from prvalues. This completely covers all value categories, is very friendly to overload resolution, and semantically harmonious.

```cpp
struct X
{
    std::string s;
    X(X x): s(std::move(x.s)) {}
}
```

Another benefit is that this form of constructor `T(T)` is currently disallowed, so it won't conflict with existing code. One point to note: you might have heard people explain why copy constructor parameters must be references. The reason given is that if it's not a reference, function arguments would also need to be copied, leading to infinite recursion.

In fact, this explanation is outdated. Due to mandatory [copy elision](https://en.cppreference.com/w/cpp/language/copy_elision) introduced in C++17, even if a type has no copy or move constructor, it can be constructed directly from a prvalue without any copy/move constructor calls.

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

The above code compiles successfully with major compilers when C++17 is enabled. Therefore, the `T(T)` form of constructor will not lead to infinite recursion here. This proposal also introduces a relocate assignment operator, with the form `T& operator=(T)`, where the function parameter is a prvalue of type `T`. Of course, there is also the concept of trivially-relocatable, which allows relocate constructors satisfying this condition to be optimized to `memcpy`. However, this is determined by rules like the relocate constructor itself, and users cannot explicitly mark it with an attribute. I think this is not ideal; users should be allowed to manually mark a type as trivially-relocatable. `tuple` cannot be trivially-copyable due to current implementation limitations, as it must have a constructor, and `pair` is also not trivially-copyable, which is clearly unreasonable. So I hope this proposal will eventually support marking a type as trivially-relocatable via an attribute.

I personally quite like this proposal. With it, I even feel that the C++ value category system can be associated with elegance. Before this, I always thought the value category system was chaotic and evil, a messy patch to maintain compatibility with old code. But if this proposal passes:

- Lvalue — Copy construction
- Xvalue — Move construction
- Prvalue — Relocate construction

This has a sense of complete logical self-consistency and beauty. Other details in the proposal are more trivial, so I will omit them here. Interested readers can read them themselves.

## Why has it taken so long to enter the standard?

Regarding why this problem has not been solved after so many years, it's actually a rather long history, caused by flaws in the C++ object model. Until the [implicit lifetime proposal](https://en.cppreference.com/w/cpp/language/lifetime) was accepted in C++20, even optimizing trivially-copyable types to `memcpy` in the initial `grow` function implementation was undefined behavior.

Of course, don't be afraid of "undefined behavior" as if it's an insurmountable obstacle. In fact, this has always been considered a defect in the standard. This optimization has long been widely practiced in various codebases, and its reliability has been verified. It's just that the C++ standard has never had appropriate wording to describe this situation. Considering it completely UB is certainly incorrect, and using it without restrictions is also incorrect. So the key is how to find an appropriate boundary between the two. I will write a dedicated article soon to introduce C++ object model related content, so I won't elaborate here.

## Other Languages

C++ certainly has its shortcomings. Considering historical compatibility and other factors, its design is constrained. What about new languages? How do they solve these problems?

### Rust

First, let's look at Rust, which has been quite popular recently. In fact, as long as a structure does not contain self-referential members, using `memcpy` to move an old object to new memory is almost always feasible. Additionally, Rust doesn't have things like multiple inheritance, virtual functions (complex vtable structures), or virtual inheritance (which are quite strange and rarely used in practice), so almost all types can directly use `memcpy` to create a new object from an old one. Conveniently, the move semantic in Safe Rust is a destructive move, so its default implementation of move is directly `memcpy`, which is much cleaner.

However, the default move can only move local non-static variables. If a variable is a reference, you cannot move it. But thankfully, Safe Rust provides a [std::mem::take](https://doc.rust-lang.org/std/mem/fn.take.html) function to solve this problem:

```rust
use std::mem;

let mut v: Vec<i32> = vec![1, 2];

let old_v = mem::take(&mut v);
assert_eq!(vec![1, 2], old_v);
assert!(v.is_empty());
```

The effect is move + empty the original object, which is quite similar to C++'s move. There are also [std::mem::swap](https://doc.rust-lang.org/std/mem/fn.swap.html) and [std::mem::replace](https://doc.rust-lang.org/std/mem/fn.replace.html) for other scenarios where moving from a reference is needed.

Although it might not happen often, what if a type contains a self-referential structure? In fact, allowing users to define custom constructors is a relatively simple solution, but the Rust community seems quite averse to it. The current solution is through Pin, but the Rust community also seems dissatisfied with this solution; it's hard to understand and hard to use. Future new designs should be related to linear types; relevant discussions can be found in [Changing the rules of Rust](https://without.boats/blog/changing-the-rules-of-rust/).

### Mojo

This language was also promoted on Zhihu some time ago, but it is still in a very early state. However, from the beginning, it considered providing four constructors:

- `__init__()`
- `__copy__()`
- `__move__()`
- `__take__()`

Among them, `copy` is similar to the copy constructor, `move` is similar to the relocate constructor, and `take` is similar to the current move constructor. More details are currently unavailable.
