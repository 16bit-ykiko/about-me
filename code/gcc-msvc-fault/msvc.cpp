struct A {
    int f();
};

using MP = decltype(&A::f);

extern "C" int g(A& a, MP p) {
    return (a.*p)();
}

