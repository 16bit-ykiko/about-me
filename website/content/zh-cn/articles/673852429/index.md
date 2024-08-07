---
title: '手动优化 C++ 代码来加快编译速度？！'
date: 2023-12-23 15:32:28
updated: 2024-08-03 11:09:54
---

事情的起因是我最近在编写的一个库  [magic cpp](https://github.com/16bit-ykiko/magic-cpp) ，正在编写其中`enum`的相关部分。打算参考一下`magic enum`的相关实现，在翻 `issue`的时候翻到这么一个神奇的`PR` 

{{< linkcard url="https://github.com/Neargye/magic_enum/pull/227" title="​pull request" >}}

我们都知道`C++`的`constexpr/consteval`函数可以在编译期执行，目前编译器对此的实现大概是内部实现了一个小型的解释器，用来直接执行代码。然而这个解释器具体是什么表现我们无从得知，但是这个 pr 的作者仅仅改了几行代码就让编译速度提升了不少。

**原代码**

```cpp
char const* str = name.data();
  for (std::size_t i = name.size(); i > 0; --i) {
    if (!((name[i - 1] >= '0' && name[i - 1] <= '9') ||
          (name[i - 1] >= 'a' && name[i - 1] <= 'z') ||
          (name[i - 1] >= 'A' && name[i - 1] <= 'Z')
```

<br>** 优化代码**

```cpp
char const* str = name.data();
  for (std::size_t i = name.size(); i > 0; --i) {
    char c = str[i - 1];
    if (!((c >= '0' && c <= '9') ||
          (c >= 'a' && c <= 'z') ||
          (c >= 'A' && c <= 'Z')
```

这两份代码唯一的区别在于第二份代码对数组的元素`str[i - 1]`做了一次缓存。如果编译器在编译期解释执行这个函数的时候不执行任何优化，那么第一种写法每次判断都得额外寻一次址，相比之下第二种做了缓存的效果明显会快很多。这也和作者的测试结果相符合，优化后的写法编译更快。

作者还提到了，`STL`实现的许多容器有越界检测，但是在编译期这实际上是不必要的，编译期越界（读取未初始化的内存）的话会直接编译错误，例如下面这段代码

```cpp
constexpr char f()
{
    char a[3];
    return a[0];
}

constexpr auto c = f(); // compile error
```

直接编译错误，所以这些检测其实并没有任何实际的作用，反倒是无用的检查拖慢了`constexpr`函数的编译期执行速度，更好的办法是自己实现一份不带检查的编译期使用的数据结构。另外一个有关编译速度优化相关的`PR`是 这个 [compile-time optimization · Issue #219](https://github.com/Neargye/magic_enum/issues/219) 

---

实际上，如果对于运行期代码，编译器完全会把这两种代码优化成一种形式，我们是不用考虑这个问题的。但是这个`PR`的确表现出来一个问题，那就是C++编译器对于`constexpr expression`求值的效率问题，在以后`C++`引入静态反射之后，`constexpr`函数的使用会更加泛滥，如果编译器不能通过有效的手段加快它的执行速度，恐怕会更进一步加剧`C++`编译速度慢的问题。<br><br>后来我在`clang`的社区提出了这个 [问题](https://discourse.llvm.org/t/will-clang-do-some-optimization-when-evaluate-the-constexpr-expression-for-faster-compile-speed/75900) 。他们回复表示，目前（即`clang18`以及之前），`clang`的`constexpr expression`的求值效率的确是有问题的，现在的`tree evaluator`效率低下，并且在将来会有有一个新的 [Interpreter](https://clang.llvm.org/docs/ConstantInterpreter.html) 来解决这个问题，现在在`clang18`中可以用`-fexperimental-new-constant-interpreter`来开启这个实验性的功能。

这里有其主要贡献者 [Timm Baeder](https://www.redhat.com/en/authors/timm-baeder) 的两篇相关介绍文章：

- [A new constant expression interpreter for Clang](https://www.redhat.com/en/blog/new-constant-expression-interpreter-clang)
- [A new constant expression interpreter for Clang, Part 2](https://www.redhat.com/en/blog/new-constant-expression-interpreter-clang-part-2)


如果这个新的解释器被正式加入了，有关的情况应该会得到比较大的改善。**但是在那之前如果你的项目中大量使用了常量求值相关的代码，可能需要你手动进行优化编译期求值的代码来换取更快的编译速度**<br>

---

还剩下`gcc`和`msvc`的相关实现未调查，未完待续`......` 

