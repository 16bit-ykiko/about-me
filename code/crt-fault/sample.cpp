#include <vector>

__declspec(dllexport) extern std::vector<int> f() { 
    return {1, 2, 3}; 
}
