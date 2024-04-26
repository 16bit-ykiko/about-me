cmake -B build -DCMAKE_BUILD_TYPE=Release;
cmake --build build --config Release;
g++ .\gcc.cpp .\build\Release\msvc.lib -o main.exe;