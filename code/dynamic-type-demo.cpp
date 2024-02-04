#include <span>
#include <vector>
#include <iostream>
#include <functional>
#include <unordered_map>

struct Type;

class Any;

template <typename T>
Type* type_of();

class Any
{
    Type* type;    // pointer to type information
    void* data;    // pointer to data
    uint8_t flag;  // special flag

public:
    Any() : type(nullptr), data(nullptr), flag(0) {}

    Any(Type* type, void* data) : type(type), data(data), flag(0B00000001) {}

    Any(const Any& other);

    Any(Any&& other);

    template <typename T>
    Any(T&& value);  // used for boxing value

    ~Any();

    template <typename T>
    T& cast();  // used for type casting

    Type* GetType() const { return type; } 

    Any invoke(std::string_view name, std::span<Any> args);  // call method by name

    void foreach(const std::function<void(std::string_view, Any)>& fn);  // iterate over fields
};

struct Type
{
    using Destroy = void (*)(void*);
    using Construct = void* (*)(void*);
    using Method = Any (*)(void*, std::span<Any>);
    using Field = std::pair<Type*, std::size_t>;

    std::string_view name;                                 // type name
    Destroy destroy;                                       // destructor
    Construct copy;                                        // copy constructor
    Construct move;                                        // move constructor
    std::unordered_map<std::string_view, Field> fields;    // field information
    std::unordered_map<std::string_view, Method> methods;  // method information
};

template <typename T>
T& Any::cast()
{
    if(type != type_of<T>()) { throw std::runtime_error{"type mismatch"}; }
    return *static_cast<T*>(data);
}

template <typename T>
struct member_fn_traits;

template <typename R, typename C, typename... Args>
struct member_fn_traits<R (C::*)(Args...)>
{
    using return_type = R;
    using class_type = C;
    using args_type = std::tuple<Args...>;
};

template <auto ptr>
auto* type_ensure()
{
    using traits = member_fn_traits<decltype(ptr)>;
    using class_type = typename traits::class_type;
    using result_type = typename traits::return_type;
    using args_type = typename traits::args_type;

    return +[](void* object, std::span<Any> args) -> Any
    {
        auto self = static_cast<class_type*>(object);
        return [=]<std::size_t... Is>(std::index_sequence<Is...>)
        {
            if constexpr(std::is_void_v<result_type>)
            {
                (self->*ptr)(args[Is].cast<std::tuple_element_t<Is, args_type>>()...);
                return Any{};
            }
            else
            {
                auto result = (self->*ptr)(args[Is].cast<std::tuple_element_t<Is, args_type>>()...);
                return Any{result};
            }
        }(std::make_index_sequence<std::tuple_size_v<args_type>>{});
    };
}

struct Person
{
    std::string_view name;
    std::size_t age;

    void say(std::string_view msg) { std::cout << name << " say: " << msg << std::endl; }
};

// register type information for Person
template <typename T>
Type* type_of()
{
    static Type type;
    type.name = typeid(T).name();
    type.destroy = [](void* obj) { delete static_cast<T*>(obj); };
    type.copy = [](void* obj) { return (void*)(new T(*static_cast<T*>(obj))); };
    type.move = [](void* obj) { return (void*)(new T(std::move(*static_cast<T*>(obj)))); };
    return &type;
}

template <>
Type* type_of<Person>()
{
    static Type type;
    type.name = "Person";
    type.destroy = [](void* obj) { delete static_cast<Person*>(obj); };
    type.copy = [](void* obj) { return (void*)(new Person(*static_cast<Person*>(obj))); };
    type.move = [](void* obj) { return (void*)(new Person(std::move(*static_cast<Person*>(obj)))); };
    type.fields.insert({
        "name",
        {type_of<std::string_view>(), offsetof(Person, name)}
    });
    type.fields.insert({
        "age",
        {type_of<std::size_t>(), offsetof(Person, age)}
    });
    type.methods.insert({"say", type_ensure<&Person::say>()});
    return &type;
};

Any::Any(const Any& other)
{
    type = other.type;
    data = type->copy(other.data);
    flag = 0;
}

Any::Any(Any&& other)
{
    type = other.type;
    data = type->move(other.data);
    flag = 0;
}

template <typename T>
Any::Any(T&& value)
{
    type = type_of<std::decay_t<T>>();
    data = new std::decay_t<T>(std::forward<T>(value));
    flag = 0;
}

Any::~Any()
{
    if(!(flag & 0B00000001))
    {
        if(data && type) { type->destroy(data); }
    }
}

void Any::foreach(const std::function<void(std::string_view, Any)>& fn)
{
    for(auto& [name, field]: type->fields) 
    { 
        fn(name, Any(field.first, static_cast<char*>(data) + field.second)); 
    }
}

Any Any::invoke(std::string_view name, std::span<Any> args)
{
    auto it = type->methods.find(name);
    if(it == type->methods.end()) { throw std::runtime_error{"method not found"}; }
    return it->second(data, args);
}

int main()
{
    Any person = Person{"Tom", 18};

    std::vector<Any> args = {std::string_view{"Hello"}};
    
    person.invoke("say", args);

    auto f = [](std::string_view name, Any value)
    {
        if(value.GetType() == type_of<std::string_view>())
        {
            std::cout << name << " = " << value.cast<std::string_view>() << std::endl;
        }
        else if(value.GetType() == type_of<std::size_t>())
        {
            std::cout << name << " = " << value.cast<std::size_t>() << std::endl;
        }
    };

    person.foreach(f);
    return 0;
}
