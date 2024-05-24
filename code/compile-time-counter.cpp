#include <iostream>

template <std::size_t N>
struct reader {
    friend auto counted_flag(reader<N>);
};

template <std::size_t N>
struct setter {
    std::size_t value = N;

    friend auto counted_flag(reader<N>) {}
};

template <auto N = 0,
          auto tag = [] {},
          bool condition = requires(reader<N> red) { counted_flag(red); }>
consteval auto next() {
    if constexpr(!condition) {
        constexpr setter<N> s;
        return s.value;
    } else {
        return next<N + 1>();
    }
}

int main() {
    constexpr auto a = next();
    constexpr auto b = next();
    constexpr auto c = next();
    static_assert(a == 0 && b == 1 && c == 2);
    std::cout << a << b << c << std::endl;
}
