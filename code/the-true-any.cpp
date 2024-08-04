#include <string>
#include <vector>
#include <iostream>

template <typename T>
struct self {
    using type = T;
};

template <int N>
struct reader {
    friend consteval auto at(reader);
};

template <int N, typename T>
struct setter {
    friend consteval auto at(reader<N>) {
        return self<T>{};
    }
};

template <int N>
using type_at = decltype(at(reader<N>{}))::type;

template <typename T, int N = 0>
consteval int lookup() {
    constexpr bool exist = requires { at(reader<N>{}); };
    if constexpr(exist) {
        if constexpr(std::is_same_v<T, type_at<N>>) {
            return N;
        } else {
            return lookup<T, N + 1>();
        }
    } else {
        setter<N, T> setter{};
        return N;
    }
}

template <int N = 0, auto seed = [] {}>
consteval int count() {
    constexpr bool exist = requires { at(reader<N>{}); };
    if constexpr(exist) {
        return count<N + 1, seed>();
    } else {
        return N;
    }
}

struct any {
    void* data;
    void (*destructor)(void*);
    std::size_t index;

    constexpr any(void* data, void (*destructor)(void*), std::size_t index) noexcept :
        data(data), destructor(destructor), index(index) {}

    constexpr any(any&& other) noexcept : data(other.data), destructor(other.destructor), index(other.index) {
        other.data = nullptr;
        other.destructor = nullptr;
    }

    constexpr ~any() {
        if(data && destructor) {
            destructor(data);
        }
    }
};

template <typename T, typename Decay = std::decay_t<T>>
auto make_any(T&& value) {
    constexpr int index = lookup<Decay>();
    auto data = new Decay(std::forward<T>(value));
    auto destructor = [](void* data) { delete static_cast<Decay*>(data); };
    return any{data, destructor, index};
}

template <typename Callback, auto seed = [] {}>
constexpr void visit(any& any, Callback&& callback) {
    constexpr std::size_t n = count<0, seed>();
    [&]<std::size_t... Is>(std::index_sequence<Is...>) {
        auto for_each = [&]<std::size_t I>() {
            if(any.index == I) {
                callback(*static_cast<type_at<I>*>(any.data));
                return true;
            }
            return false;
        };
        return (for_each.template operator()<Is>() || ...);
    }(std::make_index_sequence<n>{});
}

struct String {
    std::string value;

    friend std::ostream& operator<< (std::ostream& os, const String& string) {
        return os << string.value;
    }
};

int main() {
    std::vector<any> vec;
    vec.push_back(make_any(42));
    vec.push_back(make_any(std::string{"Hello world"}));
    vec.push_back(make_any(3.14));
    for(auto& any: vec) {
        visit(any, [](auto& value) { std::cout << value << ' '; });
        // => 42 Hello world 3.14
    }
    std::cout << "\n-----------------------------------------------------\n";
    vec.push_back(make_any(String{"\nPowerful Stateful Template Metaprogramming!!!"}));
    for(auto& any: vec) {
        visit(any, [](auto& value) { std::cout << value << ' '; });
        // => 42 Hello world 3.14
        // => Powerful Stateful Template Metaprogramming!!!
    }
    return 0;
}

