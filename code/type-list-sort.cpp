struct identity {
    int size;
};

using meta_value = const identity*;

template <typename T>
struct storage {
    constexpr inline static identity value = {sizeof(T)};
};

template <typename T>
struct self {
    using type = T;
};

template <meta_value value>
struct reader {
    friend consteval auto to_type(reader);
};

template <meta_value value, typename T>
struct setter {
    friend consteval auto to_type(reader<value>) { return self<T>{}; }
};

template <typename T>
consteval meta_value value_of() {
    constexpr auto value = &storage<T>::value;
    setter<value, T> setter;
    return value;
}

template <meta_value value>
using type_of = typename decltype(to_type(reader<value>{}))::type;

#include <algorithm>
#include <array>

template <typename... Ts>
struct type_list {};

template <std::array types, typename = std::make_index_sequence<types.size()>>
struct array_to_list;

template <std::array types, std::size_t... Is>
struct array_to_list<types, std::index_sequence<Is...>> {
    using result = type_list<type_of<types[Is]>...>;
};

template <typename List>
struct sort_list;

template <typename... Ts>
struct sort_list<type_list<Ts...>> {
    constexpr inline static std::array sorted_types = [] {
        std::array types{value_of<Ts>()...};
        std::sort(types.begin(), types.end(),
                  [](auto a, auto b) { return a->size < b->size; });
        return types;
    }();

    using result = typename array_to_list<sorted_types>::result;
};

using list = type_list<int, char, int, double, char, char, double>;
using sorted = typename sort_list<list>::result;
using expected = type_list<char, char, char, int, int, double, double>;
static_assert(std::is_same_v<sorted, expected>);
