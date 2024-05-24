#include <array>
#include <vector>
#include <iostream>

// type_list
template <typename... Types>
struct type_list {
    using type = type_list<Types...>;
};

// push_back
template <typename List, typename T>
struct list_push_back;

template <typename... Types, typename T>
struct list_push_back<type_list<Types...>, T> {
    using type = type_list<Types..., T>;
};

template <typename List, typename T>
using list_push_back_t = typename list_push_back<List, T>::type;

// push_front
template <typename List, typename T>
struct list_push_front;

template <typename... Types, typename T>
struct list_push_front<type_list<Types...>, T> {
    using type = type_list<T, Types...>;
};

template <typename List, typename T>
using list_push_front_t = typename list_push_front<List, T>::type;

// pop_back
template <typename List>
struct list_pop_back;

template <typename T, typename... Types>
struct list_pop_back<type_list<T, Types...>> {
    using type =
        list_push_front_t<typename list_pop_back<type_list<Types...>>::type, T>;
};

template <typename T>
struct list_pop_back<type_list<T>> {
    using type = type_list<>;
};

template <typename List>
using list_pop_back_t = typename list_pop_back<List>::type;

// test for type_list
using list0 = type_list<int, double, char>;

using list1 = list_push_back_t<list0, bool>;
static_assert(std::is_same_v<list1, type_list<int, double, char, bool>>);

using list2 = list_push_front_t<list1, float>;
static_assert(std::is_same_v<list2, type_list<float, int, double, char, bool>>);

using list3 = list_pop_back_t<list2>;
static_assert(std::is_same_v<list3, type_list<float, int, double, char>>);

// counter
template <std::size_t N>
struct reader {
    friend auto counted_flag(reader<N>);
};

template <std::size_t N, typename T>
struct setter {
    friend auto counted_flag(reader<N>) { return T{}; }
};

template <auto tag = [] {}, auto N = 0,
          bool condition = requires(reader<N> red) { counted_flag(red); }>
consteval auto count() {
    if constexpr (!condition) {
        return N - 1;
    } else {
        return count<tag, N + 1>();
    }
}

template <typename... Ts>
consteval void Set() {
    setter<0, type_list<Ts...>> s [[maybe_unused]]{};
}

template <auto tag = [] {}>
using value = decltype(counted_flag(reader<count<tag>()>{}));

template <typename T, auto tag = [] {}>
consteval void push() {
    constexpr auto len = count<tag>();
    setter<len + 1, list_push_back_t<value<tag>, T>> s [[maybe_unused]]{};
}

template <auto tag = [] {}>
consteval void pop() {
    constexpr auto len = count<tag>();
    using last = value<tag>;
    setter<len + 1, list_pop_back_t<value<tag>>> s [[maybe_unused]]{};
}

// Any
struct Any {
    void* data;
    std::size_t index;
};

template <typename T, auto tag = [] {}>
constexpr auto make_any(T&& t) {
    push<std::decay_t<T>, tag>();
    return Any{new auto(std::forward<T>(t)), count<tag>()};
}

template <typename... Ts>
    requires(sizeof...(Ts) > 1)
constexpr auto make_any(Ts&&... ts) {
    return std::vector{make_any(std::forward<Ts>(ts))...};
}

template <typename Fn, typename T, auto tag = [] {}>
constexpr auto wrap(Fn&& fn, void* ptr) {
    auto& value = *static_cast<T*>(ptr);
    using ret = decltype(fn(value));
    if constexpr (std::is_same_v<ret, void>) {
        fn(value);
        return Any{nullptr, 0};
    } else {
        push<ret, tag>();
        return Any{new auto(fn(value)), count<tag>()};
    }
}

template <typename Fn, auto tag = [] {}>
constexpr auto visit(Fn&& fn, Any any) {
    constexpr auto size = count<tag>();
    using Wrapper = Any (*)(Fn&&, void*);

    constexpr auto wrappers = []<typename... Ts>(type_list<Ts...>) {
        return std::array<Wrapper, size>{wrap<Fn, Ts>...};
    }(value<tag>());

    return wrappers[any.index](std::forward<Fn>(fn), any.data);
}

struct A {
    friend std::ostream& operator<<(std::ostream& os, const A& a) {
        return os << "A";
    }
};

int main() {
    Set<>();

    std::vector<Any> vec = make_any(1, std::string("hello"), 3.14);

    for (auto&& any : vec) {
        visit([](auto&& v) { std::cout << v << std::endl; }, any);
    }

    std::cout << "--------------------------------" << std::endl;
    vec.push_back(make_any(std::string_view("world")));
    vec.push_back(make_any(A{}));

    for (auto&& any : vec) {
        visit([](auto&& v) { std::cout << v << std::endl; }, any);
    }
}