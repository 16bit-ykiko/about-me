---
series:
  - Constexpr
series_order: 2
title: The History of constexpr in C++! (Part Two)
date: "2024-02-22 14:15:32"
updated: "2024-11-30 10:28:59"
zhihu_article_id: "683463723"
zhihu_url: https://zhuanlan.zhihu.com/p/683463723
zhihu_column_id: c_1656510843973046272
zhihu_column_title: 魅力C++
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

Prequel: [The History of constexpr in C++! (Part One)](https://www.ykiko.me/en/articles/682031684)

## 2015-2016: Syntactic Sugar for Templates

In C++, there are many templates that support [full specialization](https://en.cppreference.com/w/cpp/language/template_specialization), but not many that support [partial specialization](https://en.cppreference.com/w/cpp/language/partial_specialization). In fact, only class templates and variable templates support it. Variable templates can actually be seen as syntactic sugar for class templates, so rounding it up, only class templates truly support partial specialization. The lack of partial specialization can make some code very difficult to write.

Suppose we want to implement a `destroy_at` function whose effect is to call the object's destructor. Specifically, if the destructor is trivial, we omit this meaningless destructor call.

Intuitively, we could write code like this:

```cpp
template<typename T, bool value = std::is_trivially_destructible_v<T>>
void destroy_at(T* p) { p->~T(); }

template<typename T>
void destroy_at<T, true>(T* p) {}
```

Unfortunately, clangd can already smartly remind you: **Function template partial specialization is not allowed**. Function templates cannot be partially specialized, so what to do? Of course, you can wrap it in a class template to solve the problem, but having to add an extra layer every time this situation arises is truly unacceptable.

The old-fashioned way to solve this problem was to use SFINAE:

```cpp
template<typename T, std::enable_if_t<(!std::is_trivially_destructible_v<T>)>* = nullptr>
void destroy_at(T* p) { p->~T(); }

template<typename T, std::enable_if_t<std::is_trivially_destructible_v<T>>* = nullptr>
void destroy_at(T* p) {}
```

The specific principle will not be elaborated here. Although it reduces one layer of wrapping, there are still many elements unrelated to the code's logic. `std::enable_if_t` here is a typical example, severely impacting code readability.

Proposal [N4461](https://open-std.org/JTC1/SC22/WG21/docs/papers/2015/n4461.html) aimed to introduce `static_if` (borrowed from D language) to control code generation at compile time, compiling only the branches actually used into the final binary. This would allow writing code like the following, where the condition for `static_if` must be a constant expression:

```cpp
template<typename T>
void destroy_at(T* p){
    static_if(!std::is_trivially_destructible_v<T>){
        p->~T();
    }
}
```

The logic is very clear, but the committee is generally cautious about adding new keywords. Later, `static_if` was renamed to `constexpr_if`, and then it evolved into the form we are familiar with today and entered [C++17](https://en.cppreference.com/w/cpp/language/if#Constexpr_if):

```cpp
if constexpr (...){...}
else if constexpr (...){...}
else {...}
```

Cleverly avoiding new keywords, the C++ committee really likes keyword reuse.

## 2015: constexpr lambda

Proposal [N4487](https://open-std.org/JTC1/SC22/WG21/docs/papers/2015/n4487.pdf) discussed the possibility of supporting constexpr lambdas, especially hoping to use lambda expressions in constexpr computations, and included an experimental implementation.

In fact, supporting constexpr lambda expressions is not difficult. We all know that lambdas are very transparent in C++, essentially just anonymous function objects. If function objects can be constexpr, then supporting constexpr lambdas is a natural consequence.

The only thing to note is that lambdas can capture variables. What happens when a constexpr variable is captured?

```cpp
void foo() {
    constexpr int x = 3;
    constexpr auto foo = [=]() { return x + 1; };
    static_assert(sizeof(foo) == 1);
}
```

Intuitively, since `x` is a constant expression, there's no need to allocate space for it. Thus, `f` would have no members, and in C++, the size of an empty class is at least `1`. The code above seems reasonable, but as mentioned in the previous part of the article, constexpr variables can also occupy memory, and we can explicitly take their address.

```cpp
void foo() {
    constexpr int x = 3;
    constexpr auto foo = [=]() { return &x + 1; };
    static_assert(sizeof(foo) == 4);
}
```

In this case, the compiler has to allocate memory for `x`. The actual rules for this are more complex; interested readers can refer to [lambda capture](https://en.cppreference.com/w/cpp/language/lambda#Lambda_capture). This proposal was eventually accepted and entered [C++17](<https://en.cppreference.com/w/cpp/language/lambda#Lambda_capture:~:text=This%20function%20is%20constexpr%20if%20the%20function%20call%20operator%20(or%20specialization%2C%20for%20generic%20lambdas)%20is%20constexpr.>).

## 2017-2019: Compile-time and Run-time... Different?

By continuously relaxing constexpr restrictions, more and more functions can be executed at compile time. However, functions with external linkage (i.e., `extern` functions) cannot be executed at compile time under any circumstances. Most functions inherited from C are like this, such as `memcpy`, `memmove`, etc.

Suppose I wrote a constexpr `memcpy`:

```cpp
template <typename T>
constexpr T* memcpy(T* dest, const T* src, std::size_t count) {
    for(std::size_t i = 0; i < count; ++i) {
        dest[i] = src[i];
    }
    return dest;
}
```

While it can be used at compile time, compile-time execution efficiency is not a concern, but run-time efficiency would certainly be inferior to the standard library's implementation. It would be ideal if my implementation could be used at compile time and the externally linked standard library functions at run time.

Proposal [P0595](https://open-std.org/JTC1/SC22/WG21/docs/papers/2017/p0595r0.html) aimed to add a new magic function, `constexpr()`, to determine if the current function is being executed at compile time. It was later renamed to `is_constant_evaluated` and entered C++20. Its usage is as follows:

```cpp
constexpr int foo(int x) {
    if(std::is_constant_evaluated()) {
        return x;
    } else {
        return x + 1;
    }
}
```

This way, different logic can be implemented for compile-time and run-time. We can wrap externally linked functions, exposing them internally as constexpr function interfaces, which allows for code reuse and ensures run-time efficiency, achieving the best of both worlds.

The only problem is, if the `foo` above runs at run time, you'll find that the first branch is still compiled, although the compiler might eventually optimize away the `if(false)` branch. However, this branch will still undergo syntax checking and similar work. If templates are used inside, template instantiation will still be triggered (potentially even leading to unexpected instantiations causing compilation errors), which is clearly not what we want. What if we try to rewrite the above code using `if constexpr`?

```cpp
constexpr int foo(int x) {
    if constexpr(std::is_constant_evaluated()) {
        // ...
    }
}
```

This way of writing is considered **obviously incorrect**, because the condition of `if constexpr` can only be evaluated at compile time, so `is_constant_evaluated` will always return `true` here, which contradicts our initial goal. Therefore, proposal [P1938R3](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2021/p1938r3.html) proposed adding new syntax to solve this problem:

```cpp
if consteval /* !consteval */ {
    // ...
} else {
    // ...
}
```

The code looks straightforward: one branch for compile-time, one for run-time. This upgraded version was eventually accepted and added to C++23.

## 2017-2019: Efficient Debugging

One of the most criticized problems with C++ templates is that error messages are very poor and difficult to debug. After an inner template instantiation fails, the entire instantiation stack is printed, easily generating hundreds or thousands of lines of errors. However, things haven't really improved for constexpr functions; if a constexpr function's constant evaluation fails, the entire function call stack is also printed.

```cpp
constexpr int foo(){ return 13 + 2147483647; }
constexpr int bar() { return oo(); }
constexpr auto x = bar();
```

Error message:

```cpp
in 'constexpr' expansion of 'bar()'
in 'constexpr' expansion of 'foo()'
error: overflow in constant expression [-fpermissive]
  233 | constexpr auto x = bar();
```

If functions are nested too deeply, the error messages are also very bad. Unlike templates, constexpr functions can also run at run time. So, we could debug the code at run time and then execute it at compile time. However, considering the `is_constant_evaluated` added in the previous section, this approach isn't entirely feasible because the code logic might differ between compile-time and run-time. Proposal [P0596](https://open-std.org/JTC1/SC22/WG21/docs/papers/2017/p0596r0.html) aimed to introduce `constexpr_trace` and `constexpr_assert` to facilitate compile-time debugging. Although the vote was unanimously in favor, it has not yet entered the C++ standard.

## 2017: Compile-time Mutable Containers

Although previous proposals allowed constexpr functions to use and modify variables, dynamic memory allocation was still not permitted. If data of unknown length needed to be processed, a large array would typically be allocated on the stack, which was fine. However, in practice, many functions rely on dynamic memory allocation, making support for `vector` in constexpr functions essential.

At the time, directly allowing `new`/`delete` in constexpr functions seemed too surprising. So, proposal [P0597](https://open-std.org/JTC1/SC22/WG21/docs/papers/2017/p0597r0.html) came up with a compromise: first provide a magic container called `std::constexpr_vector`, implemented by the compiler, which supports use and modification in constexpr functions.

```cpp
constexpr constexpr_vector<int> x;  // ok
constexpr constexpr_vector<int> y{ 1, 2, 3 };  // ok

constexpr auto series(int n) {
    std::constexpr_vector<int> r{};
    for(int k; k < n; ++k) {
        r.push_back(k);
    }
    return r;
}
```

This didn't completely solve the problem; users still needed to rewrite their code to support constant evaluation. Judging from the section on supporting loops in constexpr functions, such additions that increase language inconsistency are unlikely to be added to the standard. Eventually, a better proposal replaced it, which will be mentioned later.

## 2018: True Compile-time Polymorphism?

Proposal [P1064R0](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2018/p1064r0.html) aimed to support virtual function calls in constant evaluation. Oh, dynamic memory allocation isn't even supported yet, so why virtual function calls? Actually, polymorphic pointers can be created without relying on dynamic memory allocation; they can point to objects on the stack or static storage.

```cpp
struct Base {
    virtual int foo() const { return 1; }
};

struct Derived : Base {
    int foo() const override { return 2; }
};

constexpr auto foo() {
    Base* p;
    Derived d;
    p = &d;
    return p->foo();
}
```

There seems to be no reason to reject the compilation of the above code. Since it's executed at compile time, the compiler can certainly know that `p` points to `Derived`, and then call `Derived::f`, which presents no practical difficulty. Indeed, a new proposal [P1327R1](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2018/p1327r1.html) further aimed for `dynamic_cast` and `typeid` to also be usable in constant evaluation. Ultimately, both were accepted and added to [C++20](https://en.cppreference.com/w/cpp/language/constexpr#:~:text=it%20must%20not%20be%20virtual), and these features can now be freely used at compile time.

## 2017-2019: True Dynamic Memory Allocation!

In the demo video [constexpr everything](https://www.youtube.com/watch?v=HMB9oXFobJc), an example of processing `JSON` objects at compile time was shown:

```cpp
constexpr auto jsv= R"({
    "feature-x-enabled": true,
    "value-of-y": 1729,
    "z-options": {"a": null,
        "b": "220 and 284",
         "c": [6, 28, 496]}
 })"_json;

if constexpr (jsv["feature-x-enabled"]) {
    // feature x
} else {
    // feature y
}
```

The hope was to directly use constant string parsing to act as configuration files (string literals can be introduced via `#include`). The authors were severely impacted by the inability to use STL containers and wrote their own alternatives. By using `std::array` to implement containers like `std::vector` and `std::map`, without dynamic memory allocation, they could only pre-calculate the required size (potentially leading to multiple traversals) or allocate a large block of memory on the stack.

Proposal [P0784R7](https://open-std.org/JTC1/SC22/WG21/docs/papers/2019/p0784r7.html) revisited the possibility of supporting standard library containers in constant evaluation.

There were three main difficulties:

- Destructors cannot be declared constexpr (for constexpr objects, they must be trivial).
- Inability to perform dynamic memory allocation/deallocation.
- Inability to use [placement new](https://en.cppreference.com/w/cpp/language/new#Placement_new) to call object constructors in constant evaluation.

Regarding the first issue, the authors quickly discussed and resolved it with frontend developers from MSVC, GCC, Clang, EDG, and others. Starting with C++20, types that meet the [literal type](https://en.cppreference.com/w/cpp/named_req/LiteralType) requirements can have constexpr destructors, rather than strictly requiring trivial destructors.

The second issue was not simple to address. Many undefined behaviors in C++ are caused by incorrect memory handling; scripting languages, which cannot directly manipulate memory, are much safer by comparison. However, for code reuse, the constant evaluator in C++ compilers had to directly manipulate memory. Since all information is known at compile time, it is theoretically possible to guarantee that memory errors (out of range, double free, memory leak, ...) will not occur during constant evaluation. If they do, compilation should be aborted and an error reported.

The constant evaluator needs to track meta-information for many objects to find these errors:

- Record which field of a `union` is active; accessing an inactive member leads to undefined behavior, as clarified by [P1330](https://open-std.org/JTC1/SC22/WG21/docs/papers/2018/p1330r0.pdf).
- Correctly record the object's [lifetime](https://en.cppreference.com/w/cpp/language/lifetime); accessing uninitialized memory or already destructed objects is not allowed.

At the time, converting `void*` to `T*` was not allowed in constant evaluation, so naturally:

```cpp
void* operator new(std::size_t);
```

was not supported in constant evaluation. Instead, the following was used:

```cpp
// new => initialize when allocate
auto pa = new int(42);
delete pa;

// std::allocator => initialize after allocate
std::allocator<int> alloc;
auto pb = alloc.allocate(1);
alloc.deallocate(pb, 1);
```

Both return `T*` and are implemented by the compiler, which was sufficient for supporting standard library containers.

For the third issue, a magic function, [std::construct_at](https://en.cppreference.com/w/cpp/memory/construct_at), was added. Its purpose is to call an object's constructor at a specified memory location, replacing `placement new` in constant evaluation. This allows us to first allocate memory via `std::allocator` and then construct objects via `std::construct_at`. This proposal was eventually accepted and entered [C++20](https://en.cppreference.com/w/cpp/memory/construct_at), simultaneously making `std::vector` and `std::string` available in constant evaluation (other containers are theoretically possible, but current implementations don't support them yet; if you really want them, you'll have to roll your own).

Although dynamic memory allocation is supported, it's not without restrictions. **Memory allocated during a constant evaluation must be fully deallocated before that constant evaluation ends; there must be no memory leaks, otherwise it will result in a compilation error.** This type of memory allocation is called _transient constexpr allocations_. The proposal also discussed _non-transient allocation_, where memory not released at compile time would be converted to static storage (essentially residing in the data segment, like global variables). However, the committee deemed this possibility "too brittle" and, for various reasons, it has not yet been adopted.

## 2018: More constexpr

At the time, many proposals merely aimed to mark certain parts of the standard library as `constexpr`. These were not discussed in this article because they followed the same pattern.

Proposal [P1002](https://open-std.org/JTC1/SC22/WG21/docs/papers/2018/p1002r1.pdf) aimed to support `try-catch` blocks in constexpr functions. However, `throw` was not allowed, which was intended to enable more member functions of standard library containers to be marked as `constexpr`.

```cpp
constexpr int foo(){
    throw 1;
    return 1;
}

constexpr auto x = foo();  // error

// expression '<throw-expression>' is not a constant expression
//    233 |     throw 1;
```

If `throw` occurs at compile time, it directly leads to a compilation error. Since `throw` won't happen, no exception will naturally be caught.

## 2018: Guarantee Compile-time Execution!

Sometimes we want to guarantee that a function executes at compile time:

```cpp
extern int foo(int x);

constexpr int bar(int x){ return x; }

foo(bar(1)); // evaluate at compile time ?
```

In fact, `g` could theoretically execute at either compile time or run time. To guarantee its compile-time execution, we would need to write more code:

```cpp
constexpr auto x = bar(1);
foo(x);
```

This guarantees `g` executes at compile time. Similarly, such meaningless local variables are redundant. Proposal [P1073](https://open-std.org/JTC1/SC22/WG21/docs/papers/2018/p1073r0.html) aimed to add a `constexpr!` specifier to ensure a function executes at compile time, causing a compilation error if not met. This specifier was eventually renamed to [consteval](https://en.cppreference.com/w/cpp/language/consteval) and entered C++20.

```cpp
extern int foo(int x);

consteval int bar(int x){ return x; }

foo(bar(1)); // ensure evaluation at compile time
```

`consteval` functions cannot obtain pointers or references outside of a constant evaluation context. The compiler backend neither needs nor should be aware of the existence of these functions. In fact, this proposal also laid the groundwork for static reflection, which is planned for future inclusion in the standard, and will add many functions that can only be executed at compile time.

## 2018: Default constexpr?

At the time, many proposals merely aimed to mark certain parts of the standard library as `constexpr`. These were not discussed in this article because they followed the same pattern.

Proposal [P1235](https://open-std.org/JTC1/SC22/WG21/docs/papers/2018/p1235r0.pdf) aimed to mark all functions as implicitly constexpr:

- non: Mark methods as constexpr if possible.
- constexpr: Same as current behavior.
- constexpr(false): Cannot be called at compile time.
- constexpr(true): Can only be called at compile time.

This proposal was ultimately not accepted.

## 2020: Stronger Dynamic Memory Allocation?

As previously mentioned, memory allocation is now allowed in constexpr functions, and containers like `std::vector` can also be used in constexpr functions. However, due to transient memory allocation, global `std::vector`s cannot be created:

```cpp
constexpr std::vector<int> v{1, 2, 3};  // error
```

Therefore, if a constexpr function returns a `std::vector`, it can only be wrapped an extra layer to convert this `std::vector` into a `std::array` and then used as a global variable:

```cpp
constexpr auto f() { return std::vector<int>{1, 2, 3}; }

constexpr auto arr = [](){
    constexpr auto len = f().size();
    std::array<int, len> result{};
    auto temp = f();
    for(std::size_t i = 0; i < len; ++i){
        result[i] = temp[i];
    }
    return result;
};
```

Proposal [P1974](https://open-std.org/JTC1/SC22/WG21/docs/papers/2020/p1974r0.pdf) proposed using `propconst` to support non-transient memory allocation, thus eliminating the need for the aforementioned extra wrapping code.

The principle of non-transient memory allocation is simple:

```cpp
constexpr std::vector vec = {1, 2, 3};
```

The compiler would compile the above code into something similar to this:

```cpp
constexpr int data[3] = {1, 2, 3};
constexpr std::vector vec{
    .begin = data,
    .end = data + 3,
    .capacity = data + 3
};
```

Essentially, it changes pointers that would normally point to dynamically allocated memory to point to static memory. The principle is not complex; the real challenge is ensuring program correctness. **Clearly, the `vec` above should not have its destructor called even at program termination, otherwise it would lead to a segmentation fault.** This problem is simple to solve: we can stipulate that **any variable marked `constexpr` will not have its destructor called**.

However, consider the following scenario:

```cpp
constexpr unique_ptr<unique_ptr<int>> ppi {
    new unique_ptr<int> { new int { 42 } }
};

int main(){
    ppi.reset(new int { 43 }); // error, ppi is const
    auto& pi = *ppi;
    pi.reset(new int { 43 }); // ok
}
```

Since `ppi` is `constexpr`, its destructor should not be called. Attempting to call `reset` on `ppi` is not allowed because a `constexpr` marked variable implies `const`, and `reset` is not a `const` method. However, calling `reset` on `pi` is allowed because the outer `const` does not affect inner pointers.

If `pi` were allowed to call `reset`, this would clearly be a run-time call, performing dynamic memory allocation at run time. And since `ppi`'s destructor is not called, `pi`'s destructor inside it would also not be called, leading to a memory leak. This approach should clearly not be allowed.

The solution, naturally, is to find a way to prohibit `pi` from calling `reset`. The proposal introduced the `propconst` keyword, which can propagate the outer `constexpr` to the inner parts, making `pi` also `const`, thus preventing `reset` from being called and avoiding code logic issues.

Unfortunately, it has not yet been accepted into the standard. Since then, there have been new proposals hoping to support this feature, such as [P2670R1](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2023/p2670r1.html), and related discussions are ongoing.

## 2021: constexpr Classes

Many types in the C++ standard library, such as `vector`, `string`, and `unique_ptr`, have all their methods marked as constexpr and can truly execute at compile time. Naturally, we hope to directly mark an entire class as constexpr, which would save the repetitive writing of specifiers.

Proposal [P2350](https://open-std.org/JTC1/SC22/WG21/docs/papers/2021/p2350r1.pdf) aimed to support this feature, where all methods in a `class` marked `constexpr` are implicitly marked as constexpr:

```cpp
// before
class struct {
    constexpr bool empty() const { /* */ }

    constexpr auto size() const { /* */ }

    constexpr void clear() { /* */ }
};

// after
constexpr struct SomeType {
    bool empty() const { /* */ }

    auto size() const { /* */ }

    void clear() { /* */ }
};
```

There's an interesting story related to this proposal – before knowing of its existence, I (the original author of the article) proposed the same idea on [stdcpp.ru](https://stdcpp.ru/).

During the standardization process, many nearly identical proposals can emerge almost simultaneously. This demonstrates the correctness of the [theory of multiple discovery](https://en.wikipedia.org/wiki/Multiple_discovery): certain ideas or concepts appear independently among different groups of people, as if they are floating in the air, and who discovers them first is not important. If the community is large enough, these ideas or concepts will naturally evolve.

## 2023: Compile-time Type Erasure!

In constant evaluation, converting `void*` to `T*` has always been disallowed, which prevented type-erased containers like `std::any` and `std::function` from being used in constant evaluation. The reason is that `void*` could be used to bypass the type system, converting one type to an unrelated type:

```cpp
int* p = new int(42);
double* p1 = static_cast<float*>(static_cast<void*>(p));
```

Dereferencing `p1` would actually be undefined behavior, so this conversion was prohibited (**note that `reinterpret_cast` has always been disabled in constant evaluation**). However, this approach clearly harmed correct usage, because implementations like `std::any` would obviously not convert a `void*` to an unrelated type, but rather convert it back to its original type. Completely disallowing this conversion was unreasonable. Proposal [P2738R0](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2023/p2738r0.pdf) aimed to support this conversion in constant evaluation. Theoretically, the compiler could record the original type of a `void*` pointer at compile time and report an error if the conversion was not to the original type.

This proposal was eventually accepted and added to C++26. Now, `T*` -> `void*` -> `T*` conversions are allowed:

```cpp
constexpr void f(){
    int x = 42;
    void* p = &x;
    int* p1 = static_cast<int*>(p); // ok
    float* p2 = static_cast<float*>(p); // error
}
```

## 2023: Support for placement new?

As mentioned earlier, to support `vector` in constant evaluation, `construct_at` was added to call constructors in constant evaluation. It has the following form:

```cpp
template<typename T, typename... Args>
constexpr T* construct_at(T* p, Args&&... args);
```

While it solved the problem to some extent, it doesn't fully provide the functionality of `placement new`:

- value initialization

```cpp
new (p) T(args...) // placement new version
construct_at(p, args...) // construct_at version
```

- default initialization

```cpp
new (p) T // placement new version
std::default_construct_at(p) // P2283R1
```

- list initialization

```cpp
new (p) T{args...} // placement new version
// construct_at version doesn't exist
```

- designated initialization

```cpp
new (p) T{.x = 1, .y = 2} // placement new version
// construct_at version cannot exist
```

Proposal [P2747R1](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2023/p2747r1.html) aims to directly support `placement new` in constant evaluation. It has not yet been added to the standard.

## 2024-∞: The Future is Limitless!

As of now, C++'s constant evaluation supports a rich set of features, including conditions, variables, loops, virtual function calls, dynamic memory allocation, and more. However, due to the C++ versions used in daily development, many features might not be available yet. You can conveniently check which version supports which features [here](https://en.cppreference.com/w/cpp/feature_test#:~:text=P2564R3-,__cpp_constexpr,-constexpr).

There are still many possibilities for constexpr in the future. For example, perhaps functions like `memcpy` could also be used in constant evaluation? Or perhaps **some implementations** of current `small_vector`s cannot become constexpr **without any code changes**, because they use `char` arrays to provide storage for objects on the stack (to avoid default construction):

```cpp
constexpr void foo(){
    std::byte buf[100];
    std::construct_at(reinterpret_cast<int*>(buf), 42); // no matter what
}
```

However, currently, objects cannot be directly constructed on `char` arrays in constant evaluation. Furthermore, could the [implicit lifetime](https://en.cppreference.com/w/cpp/named_req/ImplicitLifetimeType) introduced in C++20 manifest in constant evaluation? These are theoretically possible to implement, only requiring the compiler to record more meta-information. And in the future, anything is possible! Ultimately, we might truly be able to constexpr everything!
