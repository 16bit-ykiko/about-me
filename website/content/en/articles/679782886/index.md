---
title: 'Relocation Semantics in C++'
date: 2024-01-25 17:22:29
updated: 2024-12-18 11:45:31
---

As is well known, there are two special constructors in C++: the copy constructor and the move constructor.

The copy constructor was introduced as early as C++98 to copy an object. For types like `vector` that own resources, copying will also duplicate the resources it owns.

```cpp
std::vector<int> v1 = {1, 2, 3};
std::vector<int> v2 = v1; // copy
```

Of course, the overhead of copying can sometimes be very large and completely unnecessary. Therefore, the move constructor was introduced in C++11 to transfer the resources of one object to another. This significantly reduces overhead compared to direct copying.

```cpp
std::vector<int> v1 = {1, 2, 3};
std::vector<int> v2 = std::move(v1); // move
```

Note that in C++, move is referred to as *non-destructive move*. The C++ standard specifies that the state of an object after being moved is a *valid state*, and the implementation must ensure that its destructor can be called normally. **The moved object may still be used again** (whether it can be used depends on the implementation).

## Is That All?

Are these two constructors sufficient? Of course not. In fact, there is another widely used operation that can be called the **relocate** operation. Consider the following scenario:

Suppose you are implementing a `vector`, and capacity expansion is necessary. So you write a private member function `grow` to handle the expansion (the following code example temporarily ignores exception safety).

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

The above code is simple: first, allocate new memory via `malloc`, then initialize it by calling the move constructor on the newly allocated memory using [placement new](https://en.cppreference.com/w/cpp/language/new#Placement_new). Note, as mentioned earlier: move in C++ is non-destructive, so after calling the move constructor, the original object still needs to call the destructor to correctly end its lifetime. Finally, release the original memory and update the member variables.

*Note: The construction and destruction steps can also use `std::construct_at` and `std::destroy_at` added in C++20, which are essentially encapsulations of placement new and destroy.*

However, this implementation is not efficient. In C++, there is a concept called [trivially copyable](https://en.cppreference.com/w/cpp/named_req/TriviallyCopyable), which can be checked using the `is_trivially_copyable` trait. Types that satisfy this constraint can directly use `memcpy` or `memmove` to copy to create a new object. Consider the following example:

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

Not only does this save multiple function calls, but `memcpy` and `memmove` are highly optimized built-in functions (which can be vectorized via SIMD). Therefore, the efficiency is much higher compared to directly calling the copy constructor for duplication.

To make our `vector` faster, we can also apply this optimization. Using `if constexpr` added in C++17 for compile-time judgment, we can easily write the following code:

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

*Note: You can also consider directly using `uninitialized_move_n` and `destroy_n` added in C++17 to avoid reinventing the wheel. These functions have already undergone similar optimizations. However, due to pointer alias issues, they may at most optimize to `memmove`, whereas in this vector expansion scenario, it can be further optimized to `memcpy`, so self-optimization yields better results.*

## Overkill

This still feels a bit odd. Our main goal is to move all objects from the old memory to the new memory, but we are using the [trivially copyable](https://en.cppreference.com/w/cpp/named_req/TriviallyCopyable) trait, which seems too restrictive. There seems to be a significant difference between creating a new object entirely and placing the original object in a new location. Consider the following example. It seems that directly using `memcpy` for types like `std::string` is also feasible. Since the memory is manually managed and the destructor is manually called, there will be no multiple calls to the destructor.

```cpp
std::byte buffer[sizeof(std::string)];
auto& str1 = *std::construct_at((std::string*) buffer, "hello world");

std::byte new_buffer[sizeof(std::string)];
std::memcpy(new_buffer, buffer, sizeof(std::string));
auto& str2 = *(std::string*) new_buffer;

str2.~basic_string();
```

After carefully considering the data flow and destructor calls, there seems to be no issue. It seems we should look for a concept called trivially movable to relax the conditions, allowing more types to benefit from optimization. Unfortunately, there is currently no such concept in the C++ standard. To distinguish this from the existing move operation in C++, we call this operation relocate, which places the original object in a completely new location.

In fact, many well-known open-source components have implemented similar functionality through template specialization, such as:

- [BSL](https://github.com/bloomberg/bde/blob/962f7aa/groups/bsl/bslmf/bslmf_isbitwisemoveable.h#L8-L48)'s `bslmf::IsBitwiseMoveable<T>`
- [Folly](https://github.com/facebook/folly/blob/main/folly/docs/FBVector.md#object-relocation)'s `folly::IsRelocatable<T>`
- [QT](https://github.com/qt/qtbase/)'s `QTypeInfo<T>::isRelocatable`

By marking specific types, they can benefit from this optimization. However, the above optimization is only logically equivalent; strictly speaking, writing it this way in C++ is considered undefined behavior. So what can we do? We can only try to propose new proposals to modify the standard wording to support the above optimization.

## Current Status

This issue was discovered long ago, as evidenced by discussions on Zhihu:

- [Compared to malloc new / free old, how much performance advantage does realloc have?](https://www.zhihu.com/question/316026652/answer/623722536)
- [Why doesn't C++ vector's push_back expansion mechanism consider applying for memory in the space after the tail element?](https://www.zhihu.com/question/384869006/answer/1130101522)

There are quite a few similar questions. `realloc` will attempt to expand in place, and if it fails, it will try to allocate a new block of memory and then use `memcpy` to copy the original data to the new memory. Therefore, in the current C++ standard, if you want to directly use `realloc` for expansion, you must ensure that the object is trivially copyable. Of course, as mentioned earlier, this condition is quite strict, and a new concept needs to be introduced to relax the conditions.

The relevant proposal was first proposed in 2015, and the main active proposals in 2023 are the following four (targeting C++26):

- [std::is_trivially_relocatable](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2023/p1144r9.html)
- [Trivial Relocatability For C++26](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2024/p2786r4.pdf)
- [Relocating prvalues](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2023/p2785r3.html)
- [Nontrivial Relocation via a New owning reference Type](https://isocpp.org/files/papers/D2839R1.html#part-i-owning-references-and-defaulted-relocation-constructors)

They can be roughly divided into two factions: the conservative faction and the radical faction.

### Conservative Faction

The conservative faction's solution is to add the concepts of relocatable and trivially-relocatable, along with related traits for judgment.

If a type is move-constructible and destructible, then it is relocatable.

If a type satisfies one of the following conditions, then it is trivially-relocatable:

- It is a trivially-copyable type.
- It is an array of trivially-relocatable types.
- It is a class type declared with the `trivially_relocatable` attribute set to true.
- It is a class type that satisfies the following conditions:
  - No user-provided move constructor or move assignment operator.
  - No user-provided copy constructor or copy assignment operator.
  - No user-provided destructor.
  - No virtual member functions.
  - No virtual base classes.
  - Each member is either a reference or a trivially-relocatable type, and all base classes are trivially-relocatable types.

A new attribute, `trivially_relocatable`, can be used to explicitly mark a type as trivially-relocatable. It can take a constant expression as a parameter to support generic types.

```cpp
template<typename T>
struct [[trivially_relocatable(std::std::is_trivially_relocatable_v<T>)]] X { T t; };
```

Some new operations are also added:

```cpp
template<class T>
T *relocate_at(T* source, T* dest);

template<class T>
[[nodiscard]] remove_cv_t<T> relocate(T* source);
// ...
template<class InputIterator, class Size, class NoThrowForwardIterator>
auto uninitialized_relocate_n(InputIterator first, Size n, NoThrowForwardIterator result);
```

These functions are implemented by the compiler, and their effect is equivalent to move + destroy the original object. The compiler is allowed to optimize operations on trivially_relocatable types into `memcpy` or `memmove` under the as-if rule. For structures that cannot be optimized, such as those containing self-references, the move constructor + destructor will be called normally. This way, when implementing `vector`, you can directly use these standard library functions to enjoy the optimization.

The reason this proposal is called conservative is that it neither affects the original API nor the original ABI, making it highly compatible and easy to introduce.

### Radical Faction

The more radical approach is the main topic today, which advocates introducing the relocate constructor and a new keyword, `reloc`.

`reloc` is a unary operator that can be used for non-static local variables of functions. `reloc` performs the following operations:

- If the variable is a reference type, perfect forwarding is performed.
- If not, the source object is turned into a pure rvalue and returned.

Using `reloc` on an object and then using it again is considered a compilation error (the actual judgment rules are more detailed, see the relevant sections in the proposal).

A new constructor, the relocate constructor (relocation constructor), is introduced with the form `T(T)`, where the function parameter is a pure rvalue of type `T`. This function signature is chosen to complete the C++ value category system. Currently (C++17 and later), C++'s copy constructor creates objects from lvalues, the move constructor creates objects from xvalues, and the relocation constructor creates objects from prvalues. This fully covers all value categories, making it very friendly to overload resolution and semantically harmonious.

```cpp
struct X
{
    std::string s;
    X(X x): s(std::move(x.s)) {}
}
```

Another benefit is that currently, constructors declared as `T(T)` are not allowed, so there will be no conflict with existing code. One thing to note is that you may have heard people explain why the copy constructor's parameter must be a reference: if it is not a reference, function parameter passing also requires copying, leading to infinite recursion.

In fact, this explanation is outdated. Due to the mandatory [copy elision](https://en.cppreference.com/w/cpp/language/copy_elision) introduced in C++17, even if a type does not have a copy constructor or move constructor, it can still be directly constructed from a pure rvalue without any copy/move constructor calls.

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

The above code can be compiled by major compilers after enabling C++17. Therefore, the `T(T)` form of the constructor will not cause infinite recursion. This proposal also introduces the relocation assignment function with the form `T& operator=(T)`, where the function parameter is a pure rvalue of type `T`. Of course, there is also the concept of trivially-relocatable, allowing the relocation constructor that satisfies this condition to be optimized into `memcpy`. However, this is determined by the rules of the relocation constructor, and users cannot explicitly mark a type as trivially-relocatable via an attribute. I think this is not good; users should be allowed to manually mark a type as trivially-relocatable. Due to current implementation limitations, `tuple` must write a constructor, making it never trivially-copyable, and `pair` is also not trivially-copyable, which is clearly unreasonable. Therefore, I hope this proposal will support marking a type as trivially-relocatable via an attribute in the future.

Personally, I quite like this proposal. With it, I even feel that C++'s value category system can be associated with elegance. Before this, I always thought the value category system was chaotic and evil, a patch made to be compatible with old code. But if this proposal is accepted:

- Lvalue — copy construction
- Xvalue — move construction
- Prvalue — relocation construction

There is a sense of logical self-consistency and beauty. Other details in the proposal are more trivial and are omitted here. Interested readers can read it themselves.

## Why Hasn't It Entered the Standard After So Long?

Regarding why this issue has not been resolved after so many years, it is actually a long history, caused by defects in C++'s object model. Until the [implicit lifetime proposal](https://en.cppreference.com/w/cpp/language/lifetime) was accepted in C++20, even optimizing trivially-copyable types into `memcpy` in the initial expansion function implementation was undefined behavior.

Of course, don't be afraid when you hear undefined behavior, as if there is a psychological barrier. In fact, this has long been considered a defect in the standard, and this optimization has been widely practiced in various codebases, with its reliability already verified. It's just that the C++ standard has not had appropriate wording to describe this situation. Completely considering it as UB is certainly wrong, and using it without restrictions is also wrong. Therefore, the key issue is to find a suitable boundary between the two. I will write a dedicated article to introduce C++ object model-related content recently, so I won't expand on it here.

## Other Languages

C++ certainly has various shortcomings, and considering historical compatibility and other factors, the design cannot be too bold. What about new languages? How do they solve these problems?

### Rust

First, let's look at Rust, which has been quite popular recently. In fact, as long as the structure does not contain self-referential members, using `memcpy` to move the old object to new memory is almost always feasible. Additionally, Rust does not have multiple inheritance, virtual functions (complex virtual table structures), virtual inheritance, and other strange things (which are rarely used in practice), so almost all types can directly use `memcpy` to create a new object from the old one. Coincidentally, the move semantics in Safe Rust are destructive moves, so its default move implementation is directly `memcpy`, which is much cleaner.

However, the default move can only move local non-static variables. If a variable is a reference, you cannot move it. Fortunately, Safe Rust provides a [std::mem::take](https://doc.rust-lang.org/std/mem/fn.take.html) function to solve this problem:

```rust
use std::mem;

let mut v: Vec<i32> = vec![1, 2];

let old_v = mem::take(&mut v);
assert_eq!(vec![1, 2], old_v);
assert!(v.is_empty());
```

The effect is move + set the original object to empty, somewhat similar to move in C++. There are also [std::mem::swap](https://doc.rust-lang.org/std/mem/fn.swap.html) and [std::mem::replace](https://doc.rust-lang.org/std/mem/fn.replace.html) for other scenarios where moving from a reference is needed.

Although there may not be many such cases, what if a type contains a self-referential structure? In fact, allowing users to customize constructors is a relatively simple solution, but the Rust community seems to be quite averse to this. The current solution is through Pin, but