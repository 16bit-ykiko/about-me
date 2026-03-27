---
title: "The Perfect Combination of Python and C++: Object Design in pybind11"
date: "2024-06-07 07:28:11"
updated: "2024-12-02 13:20:31"
zhihu_article_id: "702197261"
zhihu_url: https://zhuanlan.zhihu.com/p/702197261
zhihu_column_id: c_1656510843973046272
zhihu_column_title: 魅力C++
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

参加了 [Google Summer of Code 2024](https://summerofcode.withgoogle.com/programs/2024/projects/Ji2Mi97o)。主要的任务就是为一个 [Python 解释器](https://pocketpy.dev/) 实现 [pybind11](https://github.com/pybind/pybind11) 的兼容性接口。说是实现兼容性接口，实际上相当于重写 pybind11 了，所以最近一直在读它的源码。

> Some readers might not be familiar with pybind11. Simply put, pybind11 is middleware that facilitates interaction between Python and C++ code. For example, it allows embedding a Python interpreter in C++ or compiling C++ code into a dynamic library for Python to call. For more details, please refer to the official documentation.

Recently, I've basically clarified the overall operational logic of the framework. Looking back now, pybind11 truly lives up to its reputation as the de facto standard for C++ and Python binding, featuring many ingenious designs. Its interaction logic could also be fully applied to interactions between C++ and other GC-enabled languages, such as JS and C# (although there aren't things like jsbind11 and csharpbind11 yet). I might write a series of related articles soon, stripping away some tedious details to introduce some of the common ideas.

This article primarily discusses some interesting aspects of pybind11's object design.

## PyObject

As we all know, in Python, everything is an object, all `object`s. However, pybind11 actually needs to interact with specific Python implementations like CPython. So, what is the manifestation of "everything is an object" in CPython? The answer is `PyObject*`. Let's now "see" Python and understand how actual Python code operates within CPython.

Creating an object is essentially creating a `PyObject*`

```python
x = [1, 2, 3]
```

CPython has dedicated APIs to create objects of built-in types. The above statement would likely be translated into:

```c
PyObject* x = PyList_New(3);
PyList_SetItem(x, 0, PyLong_FromLong(1));
PyList_SetItem(x, 1, PyLong_FromLong(2));
PyList_SetItem(x, 2, PyLong_FromLong(3));
```

In this way, the role of `is` becomes easy to understand: it's used to determine if the values of two pointers are the same. The reason for so-called default shallow copying is simply that default assignment is just pointer assignment, not involving the elements it points to.

CPython also provides a series of APIs to operate on objects pointed to by `PyObject*`, for example:

```cpp
PyObject* PyObject_CallObject(PyObject *callable_object, PyObject *args);
PyObject* PyObject_CallFunction(PyObject *callable_object, const char *format, ...);
PyObject* PyObject_CallMethod(PyObject *o, const char *method, const char *format, ...);
PyObject* PyObject_CallFunctionObjArgs(PyObject *callable, ...);
PyObject* PyObject_CallMethodObjArgs(PyObject *o, PyObject *name, ...);
PyObject* PyObject_GetAttrString(PyObject *o, const char *attr_name);
PyObject* PyObject_SetAttrString(PyObject *o, const char *attr_name, PyObject *v);
int PyObject_HasAttrString(PyObject *o, const char *attr_name);
PyObject* PyObject_GetAttr(PyObject *o, PyObject *attr_name);
int PyObject_SetAttr(PyObject *o, PyObject *attr_name, PyObject *v);
int PyObject_HasAttr(PyObject *o, PyObject *attr_name);
PyObject* PyObject_GetItem(PyObject *o, PyObject *key);
int PyObject_SetItem(PyObject *o, PyObject *key, PyObject *v);
int PyObject_DelItem(PyObject *o, PyObject *key);
```

These functions generally have direct counterparts in Python, and their names indicate their purpose.

## handle

Since pybind11 needs to support operating on Python objects in C++, the primary task is to encapsulate these C-style APIs. This is specifically done by the `handle` type. `handle` is a simple wrapper around `PyObject*` and encapsulates some member functions, for example:

Roughly like this:

```cpp
class handle {
protected:
    PyObject* m_ptr;
public:
    handle(PyObject* ptr) : m_ptr(ptr) {}

    friend bool operator==(const handle& lhs, const handle& rhs) {
        return PyObject_RichCompareBool(lhs.m_ptr, rhs.m_ptr, Py_EQ);
    }

    friend bool operator!=(const handle& lhs, const handle& rhs) {
        return PyObject_RichCompareBool(lhs.m_ptr, rhs.m_ptr, Py_NE);
    }

    // ...
};
```

Most functions are simply wrapped like the above, but some functions are special.

## get/set

According to Bjarne Stroustrup, the father of C++, in "The Design and Evolution of C++", one reason for introducing reference (lvalue) types was to allow users to assign to return values, making operator overloading for `[]` more natural. For example:

```cpp
std::vector<int> v = {1, 2, 3};
int x = v[0]; // get
v[0] = 4;     // set
```

Without references, one would have to return pointers, and the above code would have to be written like this:

```cpp
std::vector<int> v = {1, 2, 3};
int x = *v[0]; // get
*v[0] = 4;     // set
```

In comparison, isn't using references much more elegant? This problem also exists in other programming languages, but not all languages adopt this solution. For example, Rust chooses automatic dereferencing, where the compiler automatically adds `*` to dereference at appropriate times, thus eliminating the need to explicitly write `*`. However, neither of these methods works for Python, because Python fundamentally has no concept of dereferencing, nor does it distinguish between lvalues and rvalues. So what's the solution? The answer is to distinguish between `getter` and `setter`.

For example, to overload `[]`:

```python
class List:
    def __getitem__(self, key):
        print("__getitem__")
        return 1

    def __setitem__(self, key, value):
        print("__setitem__")

a = List()
x = a[0] # __getitem__
a[0] = 1 # __setitem__
```

Python checks the syntactic structure; if `[]` appears on the left side of `=`, `__setitem__` will be called, otherwise `__getitem__` will be called. Many languages actually adopt similar designs, such as C#'s `this[]` operator overloading.

Even the `.` operator can be overloaded, simply by overriding `__getattr__` and `__setattr__`:

```python
class Point:
    def __getattr__(self, key):
        print(f"__getattr__")
        return 1

    def __setattr__(self, key, value):
        print(f"__setattr__")

p = Point()
x = p.x # __getattr__
p.x = 1 # __setattr__
```

pybind11 aims for `handle` to achieve a similar effect, i.e., calling `__getitem__` and `__setitem__` at appropriate times. For example:

```cpp
py::handle obj = py::list(1, 2, 3);
obj[0] = 4; // __setitem__
auto x = obj[0]; // __getitem__
x = py::int_(1);
```

The corresponding Python code is:

```python
obj = [1, 2, 3]
obj[0] = 4
x = obj[0]
x = 1
```

## accessor

Next, let's focus on how to achieve this effect. First, consider the return value of `operator[]`. Since `__setitem__` might need to be called, we return a proxy object here. It will store the `key` for subsequent calls.

```cpp
class accessor {
    handle m_obj;
    ssize_t m_key;
    handle m_value;
public:
    accessor(handle obj, ssize_t key) : m_obj(obj), m_key(key) {
        m_value = PyObject_GetItem(obj.ptr(), key);
    }
};
```

The next problem is how to distinguish between `obj[0] = 4` and `x = int_(1)`, so that the former calls `__setitem__` and the latter is a simple assignment to `x`. Notice the key difference between the two cases above: lvalue and rvalue.

```cpp
obj[0] = 4; // assign to rvalue
auto x = obj[0];
x = 1; // assign to lvalue
```

How can `operator=` call different functions based on the value category of its operand? This requires a somewhat less common trick: we know that a `const` qualifier can be added to a member function, allowing it to be called on a `const` object.

```cpp
struct A {
    void foo() {}
    void bar() const {}
};

int main() {
    const A a;
    a.foo(); // error
    a.bar(); // ok
}
```

Besides this, reference qualifiers `&` and `&&` can also be added. The effect is to require that the `expr` in `expr.f()` be an lvalue or an rvalue. This way, we can call different functions based on whether it's an lvalue or an rvalue.

```cpp
struct A {
    void foo() & {}
    void bar() && {}
};

int main() {
    A a;
    a.foo(); // ok
    a.bar(); // error

    A().bar(); // ok
    A().foo(); // error
}
```

Using this feature, we can achieve the above effect:

```cpp
class accessor {
    handle m_obj;
    ssize_t m_key;
    handle m_value;
public:
    accessor(handle obj, ssize_t key) : m_obj(obj), m_key(key) {
        m_value = PyObject_GetItem(obj.ptr(), key);
    }

    // assign to rvalue
    void operator=(handle value) && {
        PyObject_SetItem(m_obj.ptr(), m_key, value.ptr());
    }

    // assign to lvalue
    void operator=(handle value) & {
        m_value = value;
    }
};
```

## lazy evaluation

Furthermore, we want this proxy object to behave just like a `handle`, capable of using all of `handle`'s methods. This is simple: just inherit from `handle`.

```cpp
class accessor : public handle {
    handle m_obj;
    ssize_t m_key;
public:
    accessor(handle obj, ssize_t key) : m_obj(obj), m_key(key) {
        m_ptr = PyObject_GetItem(obj.ptr(), key);
    }

    // assign to rvalue
    void operator=(handle value) && {
        PyObject_SetItem(m_ptr, m_key, value.ptr());
    }

    // assign to lvalue
    void operator=(handle value) & {
        m_ptr = value;
    }
};
```

It seems to end here, but notice that our `__getitem__` is called in the constructor, meaning it will be invoked even if the retrieved value is not used later. There seems to be room for further optimization: can we make this evaluation lazy through some means? Only calling `__getitem__` when functions within `handle` actually need to be called?

Directly inheriting `handle` as it is currently won't work; it's impossible to insert a check before every member function call to decide whether to invoke `__getitem__`. We can have both `handle` and `accessor` inherit from a base class, which provides an interface to actually retrieve the pointer to be operated on.

```cpp
class object_api{
public:
    virtual PyObject* get() = 0;

    bool operator==(const handle& rhs) {
        return PyObject_RichCompareBool(get(), rhs.ptr(), Py_EQ);
    }

    // ...
};
```

Then, both `handle` and `accessor` inherit from this base class, and `accessor` can perform lazy evaluation of `__getitem__` here.

```cpp
class handle : public object_api {
    PyObject* get() override {
        return m_ptr;
    }
};

class accessor : public object_api {
    PyObject* get() override {
        if (!m_ptr) {
            m_ptr = PyObject_GetItem(m_obj.ptr(), m_key);
        }
        return m_ptr;
    }
};
```

This doesn't involve type erasure; it merely requires subclasses to expose an interface. Therefore, we can naturally use [CRTP](https://en.cppreference.com/w/cpp/language/crtp) to devirtualize.

```cpp
template <typename Derived>
class object_api {
public:
    PyObject* get() {
        return static_cast<Derived*>(this)->get();
    }

    bool operator==(const handle& rhs) {
        return PyObject_RichCompareBool(get(), rhs.ptr(), Py_EQ);
    }

    // ...
};

class handle : public object_api<handle> {
    PyObject* get() {
        return m_ptr;
    }
};

class accessor : public object_api<accessor> {
    PyObject* get() {
        if (!m_ptr) {
            m_ptr = PyObject_GetItem(m_obj.ptr(), m_key);
        }
        return m_ptr;
    }
};
```

This way, we've made the `__getitem__` call lazy without introducing additional runtime overhead.

## Conclusion

We often say that C++ is too complex, with too many dazzling features that often clash with each other. But looking at it from another perspective, having many features means users have more choices and more design space, allowing them to assemble brilliant designs like the one described above. I think it would be difficult for another language to achieve such an effect. Perhaps this is the charm of C++.

This article concludes here. Thank you for reading, and feel free to discuss in the comments section.
