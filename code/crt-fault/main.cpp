#include <iostream>
#include <vector>

std::vector<int> f();

int main()
{
    auto vec = f();
    std::cout << vec.size() << std::endl;
    return 0;
}
