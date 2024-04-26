#include <iostream>

struct A
{
    int f() { return 42; }
};

using MP = decltype(&A::f);

extern "C" int g(A& a, MP p);

int main()
{
    A a;
    std::cout << g(a, &A::f) << std::endl;
    return 0;
}
