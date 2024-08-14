template <int N>
struct reader {
    friend auto flag(reader);
};

template <int N>
struct setter {
    friend auto flag(reader<N>) {}
};

template <int N = 0, auto seed = [] {}>
consteval auto next() {
    constexpr bool exist = requires { flag(reader<N>{}); };
    if constexpr(!exist) {
        setter<N> setter;
        return N;
    } else {
        return next<N + 1>();
    }
}

int main() {
    constexpr auto a = next();
    constexpr auto b = next();
    constexpr auto c = next();
    static_assert(a == 0 && b == 1 && c == 2);
}
