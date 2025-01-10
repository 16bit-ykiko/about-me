---
title: 'The Perfect Integration of Python and C++: Object Design in pybind11'
date: 2024-06-07 15:28:11
updated: 2024-12-02 21:20:31
---

I participated in [Google Summer of Code 2024](https://summerofcode.withgoogle.com/programs/2024/projects/Ji2Mi97o), where my main task was to implement a [pybind11](https://github.com/pybind/pybind11) compatibility interface for a [Python interpreter](https://pocketpy.dev/). While it's called implementing a compatibility interface, it essentially amounts to rewriting pybind11, so I've been diving deep into its source code recently.

> For readers who might not be familiar with pybind11, it is essentially a middleware that facilitates seamless interaction between Python and C++ code. For instance, embedding a Python interpreter within C++ or compiling C++ code into a dynamic library for Python to call. For more details, please refer to the official documentation.

I've recently managed to grasp the overall operational logic of the framework. Looking back, pybind11 truly lives up to its reputation as the de facto standard for binding C++ and Python, with many ingenious designs. Its interaction logic can also be applied to interactions between C++ and other GC languages, such as JS and C# (though there are no equivalents like jsbind11 or csharpbind11 yet). I might write a series of articles on this topic, stripping away some of the intricate details to introduce some of the shared concepts.

This article mainly discusses some interesting points about object design in pybind11.

## PyObject 

We all know that in Python, everything is an object, all instances of `object`. However, pybind11 actually needs to interact with specific implementations of Python like CPython. So, how is "everything is an object" reflected in CPython? The answer is `PyObject*`. Let's "see" Python and understand how actual Python code operates within CPython.

Creating an object essentially means creating a `PyObject*`.

```python
x = [1, 2, 3]
```

CPython has specific APIs to create objects of built-in types. The above statement would roughly translate to:

```c
PyObject* x = PyList_New(3);
PyList_SetItem(x, 0, PyLong_FromLong(1));
PyList_SetItem(x, 1, PyLong_FromLong(2)); 
PyList_SetItem(x, 2, PyLong_FromLong(3));
```

Thus, the role of `is` becomes clear—it checks whether the values of two pointers are the same. The reason for the default shallow copy is that the default assignment is merely a pointer assignment, not involving the elements it points to.

CPython also provides a series of APIs to manipulate the objects pointed to by `PyObject*`, such as:

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

These functions generally have direct counterparts in Python, and their purposes are evident from their names.

## handle 

Since pybind11 needs to support manipulating Python objects in C++, its primary task is to encapsulate these C-style APIs. This is specifically achieved by the `handle` type. `handle` is a simple wrapper around `PyObject*` and encapsulates some member functions, such as:

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

Most functions are simply wrapped like above, but some functions are special.

## get/set 

According to Bjarne Stroustrup, the father of C++, in "The Design and Evolution of C++", part of the reason for introducing reference (lvalue) types was to allow users to assign to return values, making the overloading of operators like `[]` more natural. For example:

```cpp
std::vector<int> v = {1, 2, 3};
int x = v[0]; // get
v[0] = 4;     // set
```

Without references, one would have to return pointers, and the above code would have to be written as:

```cpp
std::vector<int> v = {1, 2, 3};
int x = *v[0]; // get
*v[0] = 4;     // set
```

In comparison, using references is much more aesthetically pleasing, isn't it? This issue exists in other programming languages as well, but not all languages adopt this solution. For example, Rust chooses automatic dereferencing, where the compiler automatically adds `*` to dereference at appropriate times, thus eliminating the need to write the extra `*`. However, neither of these methods works for Python because Python doesn't have the concept of dereferencing, nor does it distinguish between lvalues and rvalues. So, what's the solution? The answer is to distinguish between `getter` and `setter`.

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

Python checks the syntactic structure; if `[]` appears on the left side of `=`, it calls `__setitem__`; otherwise, it calls `__getitem__`. Actually, many languages adopt similar designs, such as C#'s `this[]` operator overloading.

Even the `.` operator can be overloaded by overriding `__getattr__` and `__setattr__`:

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

pybind11 aims for the handle to achieve similar effects, calling `__getitem__` and `__setitem__` at appropriate times. For example:

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

Next, let's focus on how to achieve this effect. First, consider the return value of `operator[]`. Since it might need to call `__setitem__`, we return a proxy object here. It stores the `key` for subsequent calls.

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

The next question is how to distinguish between `obj[0] = 4` and `x = int_(1)`, so that the former calls `__setitem__` and the latter is a simple assignment to `x`. Notice the key difference between the two scenarios: lvalue and rvalue.

```cpp
obj[0] = 4; // assign to rvalue
auto x = obj[0]; 
x = 1; // assign to lvalue
```

How can `operator=` call different functions based on the value category of the operand? This requires a relatively rare trick. We all know that we can add a `const` qualifier to a member function to allow it to be called on const objects.

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

In addition, we can also add reference qualifiers `&` and `&&`, which require `expr.f()` to be an lvalue or rvalue, respectively. This allows us to call different functions based on whether the expression is an lvalue or rvalue.

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

Using this feature, we can achieve the desired effect.

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

Going further, we want this proxy object to behave just like a `handle`, able to use all methods of `handle`. This is simple; just inherit from `handle`.

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

At this point, it seems we're done. However, note that our `__getitem__` is called in the constructor, meaning that even if the fetched value isn't used later, it will still be called. There seems to be room for further optimization. Can we somehow lazy-evaluate this, only calling `__getitem__` when we need to call these functions within `handle`?

Currently, directly inheriting from `handle` certainly won't work. It's impossible to insert a check before every member function call to decide whether to call `__getitem__`. We can have both `handle` and `accessor` inherit from a base class, which has an interface to actually get the pointer to operate on.

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

Then, both `handle` and `accessor` inherit from this base class. Now, `accessor` can perform lazy evaluation of `__getitem__` here.

```cpp
class handle : public object_api {
    PyObject* get() override {
        return m_ptr;
    }
};

class accessor : public handle {
    PyObject* get() override {
        if (!m_ptr) {
            m_ptr = PyObject_GetItem(m_obj.ptr(), m_key);
        }
        return m_ptr;
    }
};
```

This doesn't involve type erasure; it just requires subclasses to expose an interface. Naturally, we can use [CRTP](https://en.cppreference.com/w/cpp/language/crtp) to devirtualize.

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

Thus, we've lazy-evaluated the call to `__getitem__` without introducing additional runtime overhead.

## Conclusion 

We often say that C++ is too complex, with a dazzling array of features that often conflict with each other. But from another perspective, having many features means users have more choices, more design space, and can assemble brilliant designs like the one above. It's hard to imagine another language achieving such effects. Perhaps this is the charm of C++.

This concludes the article. Thank you for reading, and feel free to discuss in the comments.