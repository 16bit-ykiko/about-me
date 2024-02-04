#include <iostream>
#include <array>
#include <vector>

// type_list
template<typename ...Types>
struct type_list
{
    using type = type_list<Types...>;
};

// push_back
template<typename List, typename T>
struct list_push_back;

template<typename ...Types, typename T>
struct list_push_back<type_list<Types...>, T>
{
    using type = type_list<Types..., T>;
};

template <typename List, typename T>
using list_push_back_t = typename list_push_back<List, T>::type;

// push_front
template<typename List, typename T>
struct list_push_front;

template<typename ...Types, typename T>
struct list_push_front<type_list<Types...>, T>
{
    using type = type_list<T, Types...>;
};

template <typename List, typename T>
using list_push_front_t = typename list_push_front<List, T>::type;

// pop_back
template<typename List>
struct list_pop_back;

template<typename T, typename ...Types>
struct list_pop_back<type_list<T, Types...>>
{
    using type = list_push_front_t<typename list_pop_back<type_list<Types...>>::type, T>;
};

template<typename T>
struct list_pop_back<type_list<T>>
{
    using type = type_list<>;
};

template<typename List>
using list_pop_back_t = typename list_pop_back<List>::type;


template<std::size_t N>
struct reader
{
    friend auto counted_flag(reader<N>);
};

template<std::size_t N, typename T>
struct setter
{
    friend auto counted_flag(reader<N>) {return T{};}
};

template<auto N = 0, auto tag = []{}, bool condition = requires(reader<N> red){ counted_flag(red); }>
consteval auto count()
{
    if constexpr (!condition)
    {
        return N - 1;
    }
    else
    {
        return count<N + 1>();
    }
}

template<typename ...Ts>
consteval auto Set()
{
    return setter<0, type_list<Ts...>>{};
}

template<typename T,auto tag = []{}>
consteval auto push()
{
    constexpr auto len = count<0, tag>();
    using last = decltype(counted_flag(reader<len>{}));
    return setter<len + 1, list_push_back_t<last, T>>{};
}

template<auto tag = []{}>
consteval auto pop()
{
    constexpr auto len = count<0, tag>();
    using last = decltype(counted_flag(reader<len>{}));
    return setter<len + 1, list_pop_back_t<last>>{};
}

template<auto tag = []{}>
consteval auto value()
{
    constexpr auto len = count<0, tag>();
    using last = decltype(counted_flag(reader<len>{}));
    return last{};
}

struct Any
{
    void* data;
    std::size_t index;
};

template<typename T, auto tag = []{}>
constexpr auto make_any(T&& t)
{
    auto ls = push<std::decay_t<T>, tag>();
    return Any{new std::decay_t<T>(std::forward<T>(t)), count<0, tag>()};
}

template<typename ...Ts> requires (sizeof...(Ts) > 1)
constexpr auto make_any(Ts&& ...ts)
{
    return std::vector<Any>{make_any(std::forward<Ts>(ts))...};
}

template<typename Fn, typename T,auto tag = []{}>
constexpr auto Wrap(Fn&& fn, void* ptr)
{
    using ret = decltype(fn(*static_cast<T*>(ptr)));
    if constexpr (std::is_same_v<ret, void>)
    {
        fn(*static_cast<std::decay_t<T>*>(ptr));
        return Any{nullptr, 0};
    }
    else
    {
        push<ret,tag>();
        return Any{new ret(fn(*static_cast<T*>(ptr))), count<0, tag>()};
    }
}

template<typename Fn,auto tag = []{}>
constexpr auto visit(Fn&& fn, Any any)
{
    constexpr auto size = count<0, tag>();
    using Wrapper = Any(*)(Fn&&, void*);

    constexpr std::array<Wrapper, size> wrappers = []<typename ...Ts>(type_list<Ts...>)
    {
        return std::array<Wrapper, size> {Wrap<Fn, Ts>...};
    }(value<tag>());

    return wrappers[any.index](std::forward<Fn>(fn), any.data);
}

struct A
{
    friend std::ostream& operator<<(std::ostream& os, const A& a)
    {
        return os << "A";
    }
};


int main()
{
    Set<>();

    std::vector<Any> vec = make_any(1, std::string("hello"), 3.14);

    for(auto&& any : vec)
    {
        visit([](auto&& v){ std::cout << v << std::endl; }, any);
    }

    vec.push_back(make_any(std::string_view("world")));
    vec.push_back(make_any(A{}));

    std::cout << "-----------" << std::endl;
    for(auto&& any : vec)
    {
        visit([](auto&& v){ std::cout << v << std::endl; }, any);
    }

}
