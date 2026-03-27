---
title: "C++ Pointers to Members: A Comprehensive Guide"
date: "2023-10-04 06:50:12"
updated: "2024-12-18 03:24:06"
zhihu_article_id: "659510753"
zhihu_url: https://zhuanlan.zhihu.com/p/659510753
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

## Introduction

In C++, an expression like `&T::name` returns a pointer to member. It's occasionally used when writing code, but this concept might not be familiar to many. Consider the following code:

```cpp
struct Point {
    int x;
    int y;
};

int main() {
    Point point;
    *(int*)((char*)&point + offsetof(Point, x)) = 20;
    *(int*)((char*)&point + offsetof(Point, y)) = 20;
}
```

In C, we often access struct members by calculating their offsets in this manner. If encapsulated into a function, it could even be used to dynamically access struct members based on passed parameters. However, the code above results in undefined behavior in C++. For specific reasons, you can refer to this discussion on [Stack Overflow](https://stackoverflow.com/questions/66800315/can-i-manually-access-fields-by-their-raw-offset-in-c). But if we indeed have such a requirement, how can we implement it legally? C++ provides an abstraction for us: [pointers to members](https://en.cppreference.com/w/cpp/language/pointer#Pointers_to_members), which allows such operations legally.

## Usage

### pointer to data member

A pointer to a non-static member `m` of class `C` can be initialized with `&C::m`. When `&C::m` is used inside a member function of `C`, it can be ambiguous. That is, it could refer to taking the address of member `m` (`&this->m`), or it could refer to a pointer to member. To resolve this, the standard specifies that `&C::m` denotes a pointer to member, while `&(C::m)` or `&m` denotes taking the address of the member `m`. The corresponding member can be accessed using the operators `.*` and `->*`. The example code is as follows:

```cpp
struct C {
    int m;

    void foo() {
        int C::*x1 = &C::m;  // pointer to member m of C
        int* x2 = &(C::m);   // pointer to member this->m
    }
};

int main() {
    int C::*p = &C::m;
    // type of a member pointer is: T U::*
    // T is the type of the member, U is the class type
    // here, T is int, U is C

    C c = {7};
    std::cout << c.*p << '\n';  // same as c.m, print 7

    C* cp = &c;
    cp->m = 10;
    std::cout << cp->*p << '\n';  // same as cp->m, print 10
}
```

- A pointer to a data member of a base class can be implicitly converted to a pointer to a data member of a **non-virtually inherited** derived class.

```cpp
struct Base {
    int m;
};

struct Derived1 : Base {};  // non-virtual inheritance

struct Derived2 : virtual Base {};  // virtual inheritance

int main() {
    int Base::*bp = &Base::m;
    int Derived1::*dp = bp;   // ok, implicit cast
    int Derived2::*dp2 = bp;  // error

    Derived1 d;
    d.m = 1;
    std::cout << d.*dp << ' ' << d.*bp << '\n';  // ok, prints 1 1
}
```

- Dynamically access struct fields based on the passed pointer.

```cpp
struct Point {
    int x;
    int y;
};

auto& access(Point& point, auto pm) { return point.*pm; }

int main() {
    Point point;
    access(point, &Point::x) = 10;
    access(point, &Point::y) = 20;
    std::cout << point.x << ' ' << point.y << '\n';  // 10 20
}}
```

### pointer to member function

A pointer to a non-static member function `f` can be initialized with `&C::f`. Since the address of a non-static member function cannot be taken, `&(C::f)` and `&f` mean nothing. Similarly, the corresponding member function can be accessed using the operators `.*` and `->*`. If the member function is an overloaded function, to get the corresponding member function pointer, please refer to [How to get the address of an overloaded function](https://en.cppreference.com/w/cpp/language/overloaded_address). The example code is as follows:

```cpp
struct C {
    void foo(int x) { std::cout << x << std::endl; }
};

int main() {
    using F = void(int);         // function type
    using MP = F C::*;           // pointer to member function
    using T = void (C::*)(int);  // pointer to member function
    static_assert(std::is_same_v<MP, T>);

    auto mp = &C::foo;
    T mp2 = &C::foo;
    static_assert(std::is_same_v<decltype(mp), T>);

    C c;
    (c.*mp)(1);  // call foo, print 1

    C* cp = &c;
    (cp->*mp)(2);  // call foo, print 2
}
```

- A pointer to a member function of a base class can be implicitly converted to a pointer to a member function of a **non-virtually inherited** derived class.

```cpp
struct Base {
    void f(int) {}
};

struct Derived1 : Base {};  // non-virtual inheritance

struct Derived2 : virtual Base {};  // virtual inheritance

int main() {
    void (Base::*bp)(int) = &Base::f;
    void (Derived1::*dp)(int) = bp;   // ok, implicit cast
    void (Derived2::*dp2)(int) = bp;  // error
    Derived1 d;
    (d.*dp)(1);  // ok
}
```

- Dynamically call member functions based on passed parameters.

```cpp
struct C {
    void f(int x) { std::cout << x << std::endl;}
    void g(int x) { std::cout << x + 1 << std::endl;}
};

auto access(C& c, auto pm, auto... args){
    return (c.*pm)(args...);
}

int main(){
    C c;
    access(c, &C::f, 1); // 1
    access(c, &C::g, 1); // 2
}
```

## Implementation

First, it must be clear that the C++ standard does not specify how member pointers are implemented. In this regard, it's similar to virtual functions; the standard does not specify how virtual functions are implemented, only their behavior. Therefore, the implementation of member pointers is entirely **implementation defined**. Originally, it would be sufficient to understand how to use them without caring about the underlying implementation. However, there are too many incorrect articles on this topic online that have severely misled people, so clarification is necessary.

For the three major compilers, GCC follows the Itanium C++ ABI, MSVC follows the MSVC C++ ABI, and Clang can be configured for either ABI through different compilation options. For a detailed discussion of ABIs, please refer to [Thoroughly Understanding C++ ABI](https://www.ykiko.me/en/articles/692886292) and [How to make dynamic libraries generated by MSVC and GCC interchangeable](https://www.zhihu.com/question/653778109/answer/3480007666); we won't go into too much detail here.

- [Itanium ABI](https://itanium-cxx-abi.github.io/cxx-abi/abi.html#data-member-pointers) has public documentation, and the following descriptions mainly refer to this document.
- MSVC ABI has no public documentation, and the following descriptions mainly refer to the blog post [MSVC C++ ABI Member Function Pointers](https://rants.vastheman.com/2021/09/21/msvc/).

**Please note: This article is time-sensitive; future implementations may change. It is for reference only, and official documentation should be considered authoritative.**

First, let's try to print the value of a member pointer:

```cpp
struct C {
    int m;
    void foo(int x) { std::cout << x << std::endl;}
};

int main(){
    int C::* p = &C::m;
    void (C::* p2)(int) = &C::foo;
    std::cout << p << std::endl;  // 1
    std::cout << p2 << std::endl; // 1
}
```

The output is `1` for both. If you hover over `<<`, you'll find that an implicit type conversion to `bool` occurred. `<<` is not overloaded for member pointer types. We can only inspect their binary representation through other means.

## Itanium C++ ABI

### pointer to data member

Generally, a data member pointer can be represented by the following struct, indicating the offset relative to the object's base address. If it's `nullptr`, it stores `-1`. In this case, the size of the member pointer is `sizeof(ptrdiff_t)`.

```cpp
struct data_member_pointer{
    ptrdiff_t offset;
};
```

As mentioned earlier, the C++ standard does not allow member pointer conversion along virtual inheritance chains. Therefore, the offset required for conversion can be calculated at compile time based on the inheritance relationship, without needing to look up the vtable at runtime.

```cpp
struct A {
    int a;
};

struct B {
    int b;
};

struct C : A, B {};

void log(auto mp) {
    std::cout << "offset is "
              << *reinterpret_cast<ptrdiff_t*>(&mp)
              // or use std::bit_cast after C++20
              // std::bit_cast<std::ptrdiff_t>(mp)
              << std::endl;
}

int main() {
    auto a = &A::a;
    log(a);  // offset is 0
    auto b = &B::b;
    log(b);  // offset is 0

    int C::*c = a;
    log(c);  // offset is 0
    // implicit cast
    int C::*c2 = b;
    log(c2);  // offset is 4
}
```

### pointer to member function

On mainstream platforms, a member function pointer can generally be represented by the following struct:

```cpp
struct member_function_pointer {
    std::ptrdiff_t ptr;  // function address or vtable offset
    // if low bit is 0, it's a function address, otherwise it's a vtable offset
    ptrdiff_t offset;  // offset to the base(unless multiple inheritance, it's always 0)
};
```

This implementation relies on some assumptions made by most platforms:

- Considering address alignment, the lowest bit of a **non-static member function's address** is almost always 0.
- A null function pointer is 0, so a **null function pointer** can be distinguished from a **vtable offset**.
- The architecture is byte-addressable, and pointer size is even, so the **vtable offset is even**.
- As long as the vtable address, vtable offset, and function type are known, a function call can be made; the specific implementation details are determined by the compiler according to the ABI.

Of course, some platforms do not satisfy the above assumptions, such as certain cases on ARM32 platforms, where the implementation method differs from what we just described. So now you should better understand what "implementation-defined behavior" means: even with the same compiler, the implementation might differ across target platforms.

In my environment, x64 Windows, it conforms to the requirements of mainstream implementations. So, based on this ABI, a "de-sugaring" was performed.

```cpp
struct member_func_pointer {
    std::size_t ptr;
    ptrdiff_t offset;
};

template <typename Derived, typename Ret, typename Base, typename... Args>
Ret invoke(Derived& object, Ret (Base::*ptr)(Args...), Args... args) {
    Ret (Derived::*dptr)(Args...) = ptr;
    member_func_pointer mfp = *(member_func_pointer*)(&dptr);
    using func = Ret (*)(void*, Args...);

    void* self = (char*)&object + mfp.offset;
    func fp = nullptr;
    bool is_virtual = mfp.ptr & 1;

    if(is_virtual) {
        auto vptr = (char*)(*(void***)self);
        auto voffset = mfp.ptr - 1;
        auto address = *(void**)(vptr + voffset);
        fp = (func)address;
    } else {
        fp = (func)mfp.ptr;
    }

    return fp(self, args...);
}

struct A {
    int a;

    A(int a) : a(a) {}

    virtual void foo(int b) { std::cout << "A::foo " << a << b << std::endl; }

    void bar(int b) { std::cout << "A::bar " << a << b << std::endl; }
};

int main() {
    A a = {4};
    invoke(a, &A::foo, 3);  // A::foo 43
    invoke(a, &A::bar, 3);  // A::bar 43
}
```

## MSVC C++ ABI

MSVC's implementation for this is very complex and also extends the C++ standard. If you want a detailed and comprehensive understanding, it is still recommended to read the blog post mentioned above.

The C++ standard does not allow conversion of virtual base class member pointers to derived class member pointers, but MSVC does.

```cpp
struct Base {
    int m;
};

struct Derived1 : Base {};  // non-virtual inheritance

struct Derived2 : virtual Base {};  // virtual inheritance

int main() {
    int Base::*bp = &Base::m;
    int Derived1::*dp = bp;   // ok, implicit cast
    int Derived2::*dp2 = bp;  // ok in MSVC， error in GCC
}
```

To avoid wasting space, even within the same program, MSVC's member pointer size can vary (whereas in Itanium, due to uniform implementation, they are always the same size). MSVC handles different situations differently.

> Also note that MSVC's implementation of virtual inheritance differs from Itanium's. You can refer to the relevant introduction in the article [C++ Virtual Function and Virtual Inheritance Memory Model](https://zhuanlan.zhihu.com/p/41309205).

### pointer to data member

For non-virtual inheritance, the implementation is similar to GCC's, except for some size differences. In 64-bit programs, GCC uses 8 bytes, while MSVC uses 4 bytes. Both use `-1` to represent `nullptr`.

```cpp
struct data_member_pointer {
    int offset;
};
```

For virtual inheritance (a standard extension), an additional `voffset` needs to be stored. This is used at runtime to find the offset of the corresponding virtual base class member from the vtable.

```cpp
struct Base {
    int m;
};

struct Base2 {
    int n;
};

struct Base3 {
    int n;
};

struct Derived : virtual Base, Base2, Base3 {};

struct dmp {
    int offset;
    int voffset;
};

template <typename T>
void log(T mp) {
    dmp d = *reinterpret_cast<dmp*>(&mp);
    std::cout << "offset is " << d.offset << ", voffset is " << d.voffset << std::endl;
}

int main() {
    int Derived::*dp = &Base::m;
    log(dp);  // offset is 0, voffset is 4
    dp = &Base3::n;
    log(dp);  // offset is 4, voffset is 0
}
```

### pointer to member function

Member function pointers are even more complex, with four cases:

- Non-virtual inheritance, non-multiple inheritance

```cpp
struct member_function_ptr{
    void* address;
};
```

- Non-virtual inheritance, multiple inheritance

```cpp
struct member_function_ptr{
    void* address;
    int offset;
};
```

- Virtual inheritance, multiple inheritance

```cpp
struct member_function_ptr{
    void* address;
    int offset;
    int vindex;
};
```

- Unknown inheritance

```cpp
struct member_function_ptr{
    void*   address;
    int     offset;
    int     vadjust; // use to find vptr
    int     vindex;
};
```

Also note: In 32-bit programs, the calling convention for member functions is different from ordinary functions. So, if you want to convert to a function pointer and call it, you need to specify the calling convention in the function pointer, otherwise the call will fail.

## Conclusion

When discussing C++ issues, never take things for granted; your test results on a specific platform do not represent all possible implementations. Moreover, MSVC has already told you that even within the same program, your tests might not cover all cases. I was startled when I first discovered that MSVC's member function pointer sizes varied, thinking there was an issue with my code. If you wish to write a `std::function`-like container and want to perform SBO optimization, it's best to set the SBO size to `16` bytes or more to cover most member function pointers.

If member functions are needed as callbacks, it is recommended to wrap them with a lambda expression, like this:

```cpp
struct A {
    int a;

    void bar(int b) { std::cout << "A::bar " << a << b << std::endl; }
};

int main() {
    auto f = +[](A& a, int b) { a.bar(b); };
    // + is unary plus operator, use to cast a non-capturing lambda to a function pointer
    // f is function pointer
}
```

After C++23, if member functions are defined using [explicit this](https://en.cppreference.com/w/cpp/language/member_functions#Explicit_object_member_functions), then `&C::f` can directly obtain the function pointer for the corresponding member function, without needing an extra wrapper like above.

```cpp
struct A {
    void bar(this A& self, int b);
};

auto p = &A::bar;
// p is function pointer, rather than member function pointer
```
