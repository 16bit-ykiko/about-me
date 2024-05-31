from ctypes import *
from _typeshed import Incomplete
from collections.abc import Generator
from typing import Iterator, Iterable, Optional, Any


class c_interop_string(c_char_p):
    def __init__(self, p=...) -> None: ...
    @property
    def value(self): ...
    @classmethod
    def from_param(cls, param): ...
    @staticmethod
    def to_python_string(x, *args): ...


class TranslationUnitLoadError(Exception):
    ...


class TranslationUnitSaveError(Exception):
    ERROR_UNKNOWN: int
    ERROR_TRANSLATION_ERRORS: int
    ERROR_INVALID_TU: int
    save_error: Incomplete
    def __init__(self, enumeration, message) -> None: ...


class CachedProperty:
    wrapped: Incomplete
    __doc__: Incomplete
    def __init__(self, wrapped) -> None: ...
    def __get__(self, instance, instance_type: Incomplete | None = ...): ...


class _CXString(Structure):
    def __del__(self) -> None: ...

    @staticmethod
    def from_result(res: _CXString, fn: Any = None,
                    args: Any = None) -> _CXString: ...


class SourceLocation(Structure):
    @staticmethod
    def from_position(tu: TranslationUnit, file: File,
                      line: int, column: int) -> SourceLocation: ...

    @staticmethod
    def from_offset(tu: TranslationUnit, file: File,
                    offset: int) -> SourceLocation: ...

    @property
    def file(self) -> File: ...
    @property
    def line(self) -> int: ...
    @property
    def column(self) -> int: ...
    @property
    def offset(self) -> int: ...
    def __eq__(self, other: SourceLocation) -> bool: ...
    def __ne__(self, other: SourceLocation) -> bool: ...


class SourceRange(Structure):
    @staticmethod
    def from_locations(start: SourceLocation,
                       end: SourceLocation) -> SourceRange: ...

    @property
    def start(self) -> SourceLocation: ...
    @property
    def end(self) -> SourceLocation: ...
    def __eq__(self, other: SourceRange) -> bool: ...
    def __ne__(self, other: SourceLocation) -> bool: ...
    def __contains__(self, other: SourceLocation) -> bool: ...


class Diagnostic:
    Ignored: int
    Note: int
    Warning: int
    Error: int
    Fatal: int
    DisplaySourceLocation: int
    DisplayColumn: int
    DisplaySourceRanges: int
    DisplayOption: int
    DisplayCategoryId: int
    DisplayCategoryName: int
    ptr: Incomplete
    def __init__(self, ptr: Any) -> None: ...
    def __del__(self) -> None: ...
    @property
    def severity(self) -> int: ...
    @property
    def location(self) -> SourceLocation: ...
    @property
    def spelling(self) -> str: ...
    diag: Incomplete
    @property
    def ranges(self) -> Iterable[SourceRange]: ...
    @property
    def fixits(self) -> Iterable[FixIt]: ...
    diag_set: Incomplete
    @property
    def children(self) -> Iterable[Diagnostic]: ...
    @property
    def category_number(self) -> int: ...
    @property
    def category_name(self) -> str: ...
    @property
    def option(self) -> str: ...
    @property
    def disable_option(self) -> str: ...
    def format(self, options: int = ...) -> str: ...
    def from_param(self) -> Any: ...


class FixIt:
    range: Incomplete
    value: Incomplete
    def __init__(self, range: Any, value: Any) -> None: ...


class TokenGroup:
    def __init__(self, tu: TranslationUnit,
                 memory: Any, count: int) -> None: ...

    def __del__(self) -> None: ...

    @staticmethod
    def get_tokens(tu: TranslationUnit,
                   extent: SourceRange) -> Generator[Token, None, None]: ...


class TokenKind:
    value: int
    name: str
    def __init__(self, value: int, name: str) -> None: ...
    @staticmethod
    def from_value(value: int) -> Any: ...
    @staticmethod
    def register(value: int, name: str) -> None: ...


class BaseEnumeration:
    value: Incomplete
    def __init__(self, value: int) -> None: ...
    def from_param(self) -> int: ...
    @property
    def name(self) -> str: ...
    @classmethod
    def from_id(cls, id: int) -> Any: ...


class CursorKind(BaseEnumeration):
    @staticmethod
    def get_all_kinds() -> list[CursorKind]: ...
    def is_declaration(self) -> bool: ...
    def is_reference(self) -> bool: ...
    def is_expression(self) -> bool: ...
    def is_statement(self) -> bool: ...
    def is_attribute(self) -> bool: ...
    def is_invalid(self) -> bool: ...
    def is_translation_unit(self) -> bool: ...
    def is_preprocessing(self) -> bool: ...
    def is_unexposed(self) -> bool: ...

    ###
    # Declaration Kinds

    # A declaration whose specific kind is not exposed via this interface.
    #
    # Unexposed declarations have the same operations as any other kind of
    # declaration; one can extract their location information, spelling, find their
    # definitions, etc. However, the specific kind of the declaration is not
    # reported.
    UNEXPOSED_DECL: CursorKind

    # A C or C++ struct.
    STRUCT_DECL: CursorKind

    # A C or C++ union.
    UNION_DECL: CursorKind

    # A C++ class.
    CLASS_DECL: CursorKind

    # An enumeration.
    ENUM_DECL: CursorKind

    # A field (in C) or non-static data member (in C++) in a struct, union, or C++
    # class.
    FIELD_DECL: CursorKind

    # An enumerator constant.
    ENUM_CONSTANT_DECL: CursorKind

    # A function.
    FUNCTION_DECL: CursorKind

    # A variable.
    VAR_DECL: CursorKind

    # A function or method parameter.
    PARM_DECL: CursorKind

    # An Objective-C @interface.
    OBJC_INTERFACE_DECL: CursorKind

    # An Objective-C @interface for a category.
    OBJC_CATEGORY_DECL: CursorKind

    # An Objective-C @protocol declaration.
    OBJC_PROTOCOL_DECL: CursorKind

    # An Objective-C @property declaration.
    OBJC_PROPERTY_DECL: CursorKind

    # An Objective-C instance variable.
    OBJC_IVAR_DECL: CursorKind

    # An Objective-C instance method.
    OBJC_INSTANCE_METHOD_DECL: CursorKind

    # An Objective-C class method.
    OBJC_CLASS_METHOD_DECL: CursorKind

    # An Objective-C @implementation.
    OBJC_IMPLEMENTATION_DECL: CursorKind

    # An Objective-C @implementation for a category.
    OBJC_CATEGORY_IMPL_DECL: CursorKind

    # A typedef.
    TYPEDEF_DECL: CursorKind

    # A C++ class method.
    CXX_METHOD: CursorKind

    # A C++ namespace.
    NAMESPACE: CursorKind

    # A linkage specification, e.g. 'extern "C"'.
    LINKAGE_SPEC: CursorKind

    # A C++ constructor.
    CONSTRUCTOR: CursorKind

    # A C++ destructor.
    DESTRUCTOR: CursorKind

    # A C++ conversion function.
    CONVERSION_FUNCTION: CursorKind

    # A C++ template type parameter
    TEMPLATE_TYPE_PARAMETER: CursorKind

    # A C++ non-type template parameter.
    TEMPLATE_NON_TYPE_PARAMETER: CursorKind

    # A C++ template template parameter.
    TEMPLATE_TEMPLATE_PARAMETER: CursorKind

    # A C++ function template.
    FUNCTION_TEMPLATE: CursorKind

    # A C++ class template.
    CLASS_TEMPLATE: CursorKind

    # A C++ class template partial specialization.
    CLASS_TEMPLATE_PARTIAL_SPECIALIZATION: CursorKind

    # A C++ namespace alias declaration.
    NAMESPACE_ALIAS: CursorKind

    # A C++ using directive
    USING_DIRECTIVE: CursorKind

    # A C++ using declaration
    USING_DECLARATION: CursorKind

    # A Type alias decl.
    TYPE_ALIAS_DECL: CursorKind

    # A Objective-C synthesize decl
    OBJC_SYNTHESIZE_DECL: CursorKind

    # A Objective-C dynamic decl
    OBJC_DYNAMIC_DECL: CursorKind

    # A C++ access specifier decl.
    CXX_ACCESS_SPEC_DECL: CursorKind

    ###
    # Reference Kinds

    OBJC_SUPER_CLASS_REF: CursorKind
    OBJC_PROTOCOL_REF: CursorKind
    OBJC_CLASS_REF: CursorKind

    # A reference to a type declaration.
    #
    # A type reference occurs anywhere where a type is named but not
    # declared. For example, given:
    #   typedef unsigned size_type;
    #   size_type size;
    #
    # The typedef is a declaration of size_type (CXCursor_TypedefDecl),
    # while the type of the variable "size" is referenced. The cursor
    # referenced by the type of size is the typedef for size_type.
    TYPE_REF: CursorKind
    CXX_BASE_SPECIFIER: CursorKind

    # A reference to a class template, function template, template
    # template parameter, or class template partial specialization.
    TEMPLATE_REF: CursorKind

    # A reference to a namespace or namepsace alias.
    NAMESPACE_REF: CursorKind

    # A reference to a member of a struct, union, or class that occurs in
    # some non-expression context, e.g., a designated initializer.
    MEMBER_REF: CursorKind

    # A reference to a labeled statement.
    LABEL_REF: CursorKind

    # A reference to a set of overloaded functions or function templates
    # that has not yet been resolved to a specific function or function template.
    OVERLOADED_DECL_REF: CursorKind

    # A reference to a variable that occurs in some non-expression
    # context, e.g., a C++ lambda capture list.
    VARIABLE_REF: CursorKind

    ###
    # Invalid/Error Kinds

    INVALID_FILE: CursorKind
    NO_DECL_FOUND: CursorKind
    NOT_IMPLEMENTED: CursorKind
    INVALID_CODE: CursorKind

    ###
    # Expression Kinds

    # An expression whose specific kind is not exposed via this interface.
    #
    # Unexposed expressions have the same operations as any other kind of
    # expression; one can extract their location information, spelling, children,
    # etc. However, the specific kind of the expression is not reported.
    UNEXPOSED_EXPR: CursorKind

    # An expression that refers to some value declaration, such as a function,
    # variable, or enumerator.
    DECL_REF_EXPR: CursorKind

    # An expression that refers to a member of a struct, union, class, Objective-C
    # class, etc.
    MEMBER_REF_EXPR: CursorKind

    # An expression that calls a function.
    CALL_EXPR: CursorKind

    # An expression that sends a message to an Objective-C object or class.
    OBJC_MESSAGE_EXPR: CursorKind

    # An expression that represents a block literal.
    BLOCK_EXPR: CursorKind

    # An integer literal.
    INTEGER_LITERAL: CursorKind

    # A floating point number literal.
    FLOATING_LITERAL: CursorKind

    # An imaginary number literal.
    IMAGINARY_LITERAL: CursorKind

    # A string literal.
    STRING_LITERAL: CursorKind

    # A character literal.
    CHARACTER_LITERAL: CursorKind

    # A parenthesized expression, e.g. "(1)".
    #
    # This AST node is only formed if full location information is requested.
    PAREN_EXPR: CursorKind

    # This represents the unary-expression's (except sizeof and
    # alignof).
    UNARY_OPERATOR: CursorKind

    # [C99 6.5.2.1] Array Subscripting.
    ARRAY_SUBSCRIPT_EXPR: CursorKind

    # A builtin binary operation expression such as "x + y" or
    # "x <= y".
    BINARY_OPERATOR: CursorKind

    # Compound assignment such as "+=".
    COMPOUND_ASSIGNMENT_OPERATOR: CursorKind

    # The ?: ternary operator.
    CONDITIONAL_OPERATOR: CursorKind

    # An explicit cast in C (C99 6.5.4) or a C-style cast in C++
    # (C++ [expr.cast]), which uses the syntax (Type)expr.
    #
    # For example: (int)f.
    CSTYLE_CAST_EXPR: CursorKind

    # [C99 6.5.2.5]
    COMPOUND_LITERAL_EXPR: CursorKind

    # Describes an C or C++ initializer list.
    INIT_LIST_EXPR: CursorKind

    # The GNU address of label extension, representing &&label.
    ADDR_LABEL_EXPR: CursorKind

    # This is the GNU Statement Expression extension: ({int X=4; X;})
    StmtExpr: CursorKind

    # Represents a C11 generic selection.
    GENERIC_SELECTION_EXPR: CursorKind

    # Implements the GNU __null extension, which is a name for a null
    # pointer constant that has integral type (e.g., int or long) and is the same
    # size and alignment as a pointer.
    #
    # The __null extension is typically only used by system headers, which define
    # NULL as __null in C++ rather than using 0 (which is an integer that may not
    # match the size of a pointer).
    GNU_NULL_EXPR: CursorKind

    # C++'s static_cast<> expression.
    CXX_STATIC_CAST_EXPR: CursorKind

    # C++'s dynamic_cast<> expression.
    CXX_DYNAMIC_CAST_EXPR: CursorKind

    # C++'s reinterpret_cast<> expression.
    CXX_REINTERPRET_CAST_EXPR: CursorKind

    # C++'s const_cast<> expression.
    CXX_CONST_CAST_EXPR: CursorKind

    # Represents an explicit C++ type conversion that uses "functional"
    # notion (C++ [expr.type.conv]).
    #
    # Example:
    # \code
    #   x = int(0.5);
    # \endcode
    CXX_FUNCTIONAL_CAST_EXPR: CursorKind

    # A C++ typeid expression (C++ [expr.typeid]).
    CXX_TYPEID_EXPR: CursorKind

    # [C++ 2.13.5] C++ Boolean Literal.
    CXX_BOOL_LITERAL_EXPR: CursorKind

    # [C++0x 2.14.7] C++ Pointer Literal.
    CXX_NULL_PTR_LITERAL_EXPR: CursorKind

    # Represents the "this" expression in C++
    CXX_THIS_EXPR: CursorKind

    # [C++ 15] C++ Throw Expression.
    #
    # This handles 'throw' and 'throw' assignment-expression. When
    # assignment-expression isn't present, Op will be null.
    CXX_THROW_EXPR: CursorKind

    # A new expression for memory allocation and constructor calls, e.g:
    # "new CXXNewExpr(foo)".
    CXX_NEW_EXPR: CursorKind

    # A delete expression for memory deallocation and destructor calls,
    # e.g. "delete[] pArray".
    CXX_DELETE_EXPR: CursorKind

    # Represents a unary expression.
    CXX_UNARY_EXPR: CursorKind

    # ObjCStringLiteral, used for Objective-C string literals i.e. "foo".
    OBJC_STRING_LITERAL: CursorKind

    # ObjCEncodeExpr, used for in Objective-C.
    OBJC_ENCODE_EXPR: CursorKind

    # ObjCSelectorExpr used for in Objective-C.
    OBJC_SELECTOR_EXPR: CursorKind

    # Objective-C's protocol expression.
    OBJC_PROTOCOL_EXPR: CursorKind

    # An Objective-C "bridged" cast expression, which casts between
    # Objective-C pointers and C pointers, transferring ownership in the process.
    #
    # \code
    #   NSString *str = (__bridge_transfer NSString *)CFCreateString();
    # \endcode
    OBJC_BRIDGE_CAST_EXPR: CursorKind

    # Represents a C++0x pack expansion that produces a sequence of
    # expressions.
    #
    # A pack expansion expression contains a pattern (which itself is an
    # expression) followed by an ellipsis. For example:
    PACK_EXPANSION_EXPR: CursorKind

    # Represents an expression that computes the length of a parameter
    # pack.
    SIZE_OF_PACK_EXPR: CursorKind

    # Represents a C++ lambda expression that produces a local function
    # object.
    #
    #  \code
    #  void abssort(float *x, unsigned N) {
    #    std::sort(x, x + N,
    #              [](float a, float b) {
    #                return std::abs(a) < std::abs(b);
    #              });
    #  }
    #  \endcode
    LAMBDA_EXPR: CursorKind

    # Objective-c Boolean Literal.
    OBJ_BOOL_LITERAL_EXPR: CursorKind

    # Represents the "self" expression in a ObjC method.
    OBJ_SELF_EXPR: CursorKind

    # OpenMP 4.0 [2.4, Array Section].
    OMP_ARRAY_SECTION_EXPR: CursorKind

    # Represents an @available(...) check.
    OBJC_AVAILABILITY_CHECK_EXPR: CursorKind

    # Fixed point literal
    FIXED_POINT_LITERAL: CursorKind

    # OpenMP 5.0 [2.1.4, Array Shaping].
    OMP_ARRAY_SHAPING_EXPR: CursorKind

    # OpenMP 5.0 [2.1.6 Iterators]
    OMP_ITERATOR_EXPR: CursorKind

    # OpenCL's addrspace_cast<> expression.
    CXX_ADDRSPACE_CAST_EXPR: CursorKind

    # Expression that references a C++20 concept.
    CONCEPT_SPECIALIZATION_EXPR: CursorKind

    # Expression that references a C++20 concept.
    REQUIRES_EXPR: CursorKind

    # A statement whose specific kind is not exposed via this interface.
    #
    # Unexposed statements have the same operations as any other kind of statement;
    # one can extract their location information, spelling, children, etc. However,
    # the specific kind of the statement is not reported.
    UNEXPOSED_STMT: CursorKind

    # A labelled statement in a function.
    LABEL_STMT: CursorKind

    # A compound statement
    COMPOUND_STMT: CursorKind

    # A case statement.
    CASE_STMT: CursorKind

    # A default statement.
    DEFAULT_STMT: CursorKind

    # An if statement.
    IF_STMT: CursorKind

    # A switch statement.
    SWITCH_STMT: CursorKind

    # A while statement.
    WHILE_STMT: CursorKind

    # A do statement.
    DO_STMT: CursorKind

    # A for statement.
    FOR_STMT: CursorKind

    # A goto statement.
    GOTO_STMT: CursorKind

    # An indirect goto statement.
    INDIRECT_GOTO_STMT: CursorKind

    # A continue statement.
    CONTINUE_STMT: CursorKind

    # A break statement.
    BREAK_STMT: CursorKind

    # A return statement.
    RETURN_STMT: CursorKind

    # A GNU-style inline assembler statement.
    ASM_STMT: CursorKind

    # Objective-C's overall @try-@catch-@finally statement.
    OBJC_AT_TRY_STMT: CursorKind

    # Objective-C's @catch statement.
    OBJC_AT_CATCH_STMT: CursorKind

    # Objective-C's @finally statement.
    OBJC_AT_FINALLY_STMT: CursorKind

    # Objective-C's @throw statement.
    OBJC_AT_THROW_STMT: CursorKind

    # Objective-C's @synchronized statement.
    OBJC_AT_SYNCHRONIZED_STMT: CursorKind

    # Objective-C's autorelease pool statement.
    OBJC_AUTORELEASE_POOL_STMT: CursorKind

    # Objective-C's for collection statement.
    OBJC_FOR_COLLECTION_STMT: CursorKind

    # C++'s catch statement.
    CXX_CATCH_STMT: CursorKind

    # C++'s try statement.
    CXX_TRY_STMT: CursorKind

    # C++'s for (* : *) statement.
    CXX_FOR_RANGE_STMT: CursorKind

    # Windows Structured Exception Handling's try statement.
    SEH_TRY_STMT: CursorKind

    # Windows Structured Exception Handling's except statement.
    SEH_EXCEPT_STMT: CursorKind

    # Windows Structured Exception Handling's finally statement.
    SEH_FINALLY_STMT: CursorKind

    # A MS inline assembly statement extension.
    MS_ASM_STMT: CursorKind

    # The null statement.
    NULL_STMT: CursorKind

    # Adaptor class for mixing declarations with statements and expressions.
    DECL_STMT: CursorKind

    # OpenMP parallel directive.
    OMP_PARALLEL_DIRECTIVE: CursorKind

    # OpenMP SIMD directive.
    OMP_SIMD_DIRECTIVE: CursorKind

    # OpenMP for directive.
    OMP_FOR_DIRECTIVE: CursorKind

    # OpenMP sections directive.
    OMP_SECTIONS_DIRECTIVE: CursorKind

    # OpenMP section directive.
    OMP_SECTION_DIRECTIVE: CursorKind

    # OpenMP single directive.
    OMP_SINGLE_DIRECTIVE: CursorKind

    # OpenMP parallel for directive.
    OMP_PARALLEL_FOR_DIRECTIVE: CursorKind

    # OpenMP parallel sections directive.
    OMP_PARALLEL_SECTIONS_DIRECTIVE: CursorKind

    # OpenMP task directive.
    OMP_TASK_DIRECTIVE: CursorKind

    # OpenMP master directive.
    OMP_MASTER_DIRECTIVE: CursorKind

    # OpenMP critical directive.
    OMP_CRITICAL_DIRECTIVE: CursorKind

    # OpenMP taskyield directive.
    OMP_TASKYIELD_DIRECTIVE: CursorKind

    # OpenMP barrier directive.
    OMP_BARRIER_DIRECTIVE: CursorKind

    # OpenMP taskwait directive.
    OMP_TASKWAIT_DIRECTIVE: CursorKind

    # OpenMP flush directive.
    OMP_FLUSH_DIRECTIVE: CursorKind

    # Windows Structured Exception Handling's leave statement.
    SEH_LEAVE_STMT: CursorKind

    # OpenMP ordered directive.
    OMP_ORDERED_DIRECTIVE: CursorKind

    # OpenMP atomic directive.
    OMP_ATOMIC_DIRECTIVE: CursorKind

    # OpenMP for SIMD directive.
    OMP_FOR_SIMD_DIRECTIVE: CursorKind

    # OpenMP parallel for SIMD directive.
    OMP_PARALLELFORSIMD_DIRECTIVE: CursorKind

    # OpenMP target directive.
    OMP_TARGET_DIRECTIVE: CursorKind

    # OpenMP teams directive.
    OMP_TEAMS_DIRECTIVE: CursorKind

    # OpenMP taskgroup directive.
    OMP_TASKGROUP_DIRECTIVE: CursorKind

    # OpenMP cancellation point directive.
    OMP_CANCELLATION_POINT_DIRECTIVE: CursorKind

    # OpenMP cancel directive.
    OMP_CANCEL_DIRECTIVE: CursorKind

    # OpenMP target data directive.
    OMP_TARGET_DATA_DIRECTIVE: CursorKind

    # OpenMP taskloop directive.
    OMP_TASK_LOOP_DIRECTIVE: CursorKind

    # OpenMP taskloop simd directive.
    OMP_TASK_LOOP_SIMD_DIRECTIVE: CursorKind

    # OpenMP distribute directive.
    OMP_DISTRIBUTE_DIRECTIVE: CursorKind

    # OpenMP target enter data directive.
    OMP_TARGET_ENTER_DATA_DIRECTIVE: CursorKind

    # OpenMP target exit data directive.
    OMP_TARGET_EXIT_DATA_DIRECTIVE: CursorKind

    # OpenMP target parallel directive.
    OMP_TARGET_PARALLEL_DIRECTIVE: CursorKind

    # OpenMP target parallel for directive.
    OMP_TARGET_PARALLELFOR_DIRECTIVE: CursorKind

    # OpenMP target update directive.
    OMP_TARGET_UPDATE_DIRECTIVE: CursorKind

    # OpenMP distribute parallel for directive.
    OMP_DISTRIBUTE_PARALLELFOR_DIRECTIVE: CursorKind

    # OpenMP distribute parallel for simd directive.
    OMP_DISTRIBUTE_PARALLEL_FOR_SIMD_DIRECTIVE: CursorKind

    # OpenMP distribute simd directive.
    OMP_DISTRIBUTE_SIMD_DIRECTIVE: CursorKind

    # OpenMP target parallel for simd directive.
    OMP_TARGET_PARALLEL_FOR_SIMD_DIRECTIVE: CursorKind

    # OpenMP target simd directive.
    OMP_TARGET_SIMD_DIRECTIVE: CursorKind

    # OpenMP teams distribute directive.
    OMP_TEAMS_DISTRIBUTE_DIRECTIVE: CursorKind

    # OpenMP teams distribute simd directive.
    OMP_TEAMS_DISTRIBUTE_SIMD_DIRECTIVE: CursorKind

    # OpenMP teams distribute parallel for simd directive.
    OMP_TEAMS_DISTRIBUTE_PARALLEL_FOR_SIMD_DIRECTIVE: CursorKind

    # OpenMP teams distribute parallel for directive.
    OMP_TEAMS_DISTRIBUTE_PARALLEL_FOR_DIRECTIVE: CursorKind

    # OpenMP target teams directive.
    OMP_TARGET_TEAMS_DIRECTIVE: CursorKind

    # OpenMP target teams distribute directive.
    OMP_TARGET_TEAMS_DISTRIBUTE_DIRECTIVE: CursorKind

    # OpenMP target teams distribute parallel for directive.
    OMP_TARGET_TEAMS_DISTRIBUTE_PARALLEL_FOR_DIRECTIVE: CursorKind

    # OpenMP target teams distribute parallel for simd directive.
    OMP_TARGET_TEAMS_DISTRIBUTE_PARALLEL_FOR_SIMD_DIRECTIVE: CursorKind

    # OpenMP target teams distribute simd directive.
    OMP_TARGET_TEAMS_DISTRIBUTE_SIMD_DIRECTIVE: CursorKind

    # C++2a std::bit_cast expression.
    BUILTIN_BIT_CAST_EXPR: CursorKind

    # OpenMP master taskloop directive.
    OMP_MASTER_TASK_LOOP_DIRECTIVE: CursorKind

    # OpenMP parallel master taskloop directive.
    OMP_PARALLEL_MASTER_TASK_LOOP_DIRECTIVE: CursorKind

    # OpenMP master taskloop simd directive.
    OMP_MASTER_TASK_LOOP_SIMD_DIRECTIVE: CursorKind

    # OpenMP parallel master taskloop simd directive.
    OMP_PARALLEL_MASTER_TASK_LOOP_SIMD_DIRECTIVE: CursorKind

    # OpenMP parallel master directive.
    OMP_PARALLEL_MASTER_DIRECTIVE: CursorKind

    # OpenMP depobj directive.
    OMP_DEPOBJ_DIRECTIVE: CursorKind

    # OpenMP scan directive.
    OMP_SCAN_DIRECTIVE: CursorKind

    # OpenMP tile directive.
    OMP_TILE_DIRECTIVE: CursorKind

    # OpenMP canonical loop.
    OMP_CANONICAL_LOOP: CursorKind

    # OpenMP interop directive.
    OMP_INTEROP_DIRECTIVE: CursorKind

    # OpenMP dispatch directive.
    OMP_DISPATCH_DIRECTIVE: CursorKind

    # OpenMP masked directive.
    OMP_MASKED_DIRECTIVE: CursorKind

    # OpenMP unroll directive.
    OMP_UNROLL_DIRECTIVE: CursorKind

    # OpenMP metadirective directive.
    OMP_META_DIRECTIVE: CursorKind

    # OpenMP loop directive.
    OMP_GENERIC_LOOP_DIRECTIVE: CursorKind

    # OpenMP teams loop directive.
    OMP_TEAMS_GENERIC_LOOP_DIRECTIVE: CursorKind

    # OpenMP target teams loop directive.
    OMP_TARGET_TEAMS_GENERIC_LOOP_DIRECTIVE: CursorKind

    # OpenMP parallel loop directive.
    OMP_PARALLEL_GENERIC_LOOP_DIRECTIVE: CursorKind

    # OpenMP target parallel loop directive.
    OMP_TARGET_PARALLEL_GENERIC_LOOP_DIRECTIVE: CursorKind

    # OpenMP parallel masked directive.
    OMP_PARALLEL_MASKED_DIRECTIVE: CursorKind

    # OpenMP masked taskloop directive.
    OMP_MASKED_TASK_LOOP_DIRECTIVE: CursorKind

    # OpenMP masked taskloop simd directive.
    OMP_MASKED_TASK_LOOP_SIMD_DIRECTIVE: CursorKind

    # OpenMP parallel masked taskloop directive.
    OMP_PARALLEL_MASKED_TASK_LOOP_DIRECTIVE: CursorKind

    # OpenMP parallel masked taskloop simd directive.
    OMP_PARALLEL_MASKED_TASK_LOOP_SIMD_DIRECTIVE: CursorKind

    ###
    # Other Kinds

    # Cursor that represents the translation unit itself.
    #
    # The translation unit cursor exists primarily to act as the root cursor for
    # traversing the contents of a translation unit.
    TRANSLATION_UNIT: CursorKind

    ###
    # Attributes

    # An attribute whoe specific kind is note exposed via this interface
    UNEXPOSED_ATTR: CursorKind

    IB_ACTION_ATTR: CursorKind
    IB_OUTLET_ATTR: CursorKind
    IB_OUTLET_COLLECTION_ATTR: CursorKind

    CXX_FINAL_ATTR: CursorKind
    CXX_OVERRIDE_ATTR: CursorKind
    ANNOTATE_ATTR: CursorKind
    ASM_LABEL_ATTR: CursorKind
    PACKED_ATTR: CursorKind
    PURE_ATTR: CursorKind
    CONST_ATTR: CursorKind
    NODUPLICATE_ATTR: CursorKind
    CUDACONSTANT_ATTR: CursorKind
    CUDADEVICE_ATTR: CursorKind
    CUDAGLOBAL_ATTR: CursorKind
    CUDAHOST_ATTR: CursorKind
    CUDASHARED_ATTR: CursorKind

    VISIBILITY_ATTR: CursorKind

    DLLEXPORT_ATTR: CursorKind
    DLLIMPORT_ATTR: CursorKind
    CONVERGENT_ATTR: CursorKind
    WARN_UNUSED_ATTR: CursorKind
    WARN_UNUSED_RESULT_ATTR: CursorKind
    ALIGNED_ATTR: CursorKind

    ###
    # Preprocessing
    PREPROCESSING_DIRECTIVE: CursorKind
    MACRO_DEFINITION: CursorKind
    MACRO_INSTANTIATION: CursorKind
    INCLUSION_DIRECTIVE: CursorKind

    ###
    # Extra declaration

    # A module import declaration.
    MODULE_IMPORT_DECL: CursorKind
    # A type alias template declaration
    TYPE_ALIAS_TEMPLATE_DECL: CursorKind
    # A static_assert or _Static_assert node
    STATIC_ASSERT: CursorKind
    # A friend declaration
    FRIEND_DECL: CursorKind

    # A code completion overload candidate.
    OVERLOAD_CANDIDATE: CursorKind


class TemplateArgumentKind(BaseEnumeration):
    NULL: 'TemplateArgumentKind'
    TYPE: 'TemplateArgumentKind'
    DECLARATION: 'TemplateArgumentKind'
    NULLPTR: 'TemplateArgumentKind'
    INTEGRAL: 'TemplateArgumentKind'
    ...


class ExceptionSpecificationKind(BaseEnumeration):
    NONE: 'ExceptionSpecificationKind'
    DYNAMIC_NONE: 'ExceptionSpecificationKind'
    DYNAMIC: 'ExceptionSpecificationKind'
    MS_ANY: 'ExceptionSpecificationKind'
    BASIC_NOEXCEPT: 'ExceptionSpecificationKind'
    COMPUTED_NOEXCEPT: 'ExceptionSpecificationKind'
    UNEVALUATED: 'ExceptionSpecificationKind'
    UNINSTANTIATED: 'ExceptionSpecificationKind'
    UNPARSED: 'ExceptionSpecificationKind'
    ...


class Cursor(Structure):
    @staticmethod
    def from_location(tu: TranslationUnit,
                      location: SourceLocation) -> Cursor: ...

    def __hash__(self) -> int: ...
    def __eq__(self, other: Cursor) -> bool: ...
    def __ne__(self, other: Cursor) -> bool: ...
    def is_definition(self) -> bool: ...
    def is_const_method(self) -> bool: ...
    def is_converting_constructor(self) -> bool: ...
    def is_copy_constructor(self) -> bool: ...
    def is_default_constructor(self) -> bool: ...
    def is_move_constructor(self) -> bool: ...
    def is_default_method(self) -> bool: ...
    def is_deleted_method(self) -> bool: ...
    def is_copy_assignment_operator_method(self) -> bool: ...
    def is_move_assignment_operator_method(self) -> bool: ...
    def is_mutable_field(self) -> bool: ...
    def is_pure_virtual_method(self) -> bool: ...
    def is_static_method(self) -> bool: ...
    def is_virtual_method(self) -> bool: ...
    def is_abstract_record(self) -> bool: ...
    def is_scoped_enum(self) -> bool: ...
    def get_definition(self) -> Cursor: ...
    def get_usr(self) -> str: ...
    def get_included_file(self) -> File: ...
    @property
    def kind(self) -> CursorKind: ...
    @property
    def spelling(self) -> str: ...
    @property
    def displayname(self) -> str: ...
    @property
    def mangled_name(self) -> str: ...
    @property
    def location(self) -> SourceLocation: ...
    @property
    def linkage(self) -> LinkageKind: ...
    @property
    def tls_kind(self) -> TLSKind: ...
    @property
    def extent(self) -> SourceRange: ...
    @property
    def storage_class(self) -> StorageClass: ...
    @property
    def availability(self) -> AvailabilityKind: ...
    @property
    def access_specifier(self) -> AccessSpecifier: ...
    @property
    def type(self) -> Type: ...
    @property
    def canonical(self) -> Cursor: ...
    @property
    def result_type(self) -> Type: ...
    @property
    def exception_specification_kind(self) -> ExceptionSpecificationKind: ...
    @property
    def underlying_typedef_type(self) -> Type: ...
    @property
    def enum_type(self) -> Type: ...
    @property
    def enum_value(self) -> int: ...
    @property
    def objc_type_encoding(self) -> str: ...
    @property
    def hash(self) -> int: ...
    @property
    def semantic_parent(self) -> Cursor: ...
    @property
    def lexical_parent(self) -> Cursor: ...
    @property
    def translation_unit(self) -> TranslationUnit: ...
    @property
    def referenced(self) -> Cursor: ...
    @property
    def brief_comment(self) -> str: ...
    @property
    def raw_comment(self) -> str: ...
    def get_arguments(self) -> Generator[Cursor, None, None]: ...
    def get_num_template_arguments(self) -> int: ...
    def get_template_argument_kind(self, num: int) -> TemplateArgumentKind: ...
    def get_template_argument_type(self, num: int) -> Type: ...
    def get_template_argument_value(self, num: int) -> int: ...
    def get_template_argument_unsigned_value(self, num: int) -> int: ...
    def get_children(self) -> Iterator[Cursor]: ...
    def walk_preorder(self) -> Generator[Cursor, None, None]: ...
    def get_tokens(self) -> Generator[Token, None, None]: ...
    def get_field_offsetof(self) -> int: ...
    def is_anonymous(self) -> bool: ...
    def is_bitfield(self) -> bool: ...
    def get_bitfield_width(self) -> int: ...
    @staticmethod
    def from_result(res: Cursor, fn, args) -> Optional[Cursor]: ...
    @staticmethod
    def from_cursor_result(res: Cursor, fn, args) -> Optional[Cursor]: ...


class StorageClass:
    value: int
    def __init__(self, value: int) -> None: ...
    def from_param(self) -> int: ...
    @property
    def name(self) -> str: ...
    @staticmethod
    def from_id(id: int) -> StorageClass: ...

    INVALID: 'StorageClass'
    NONE: 'StorageClass'
    EXTERN: 'StorageClass'
    STATIC: 'StorageClass'
    PRIVATEEXTERN: 'StorageClass'
    OPENCLWORKGROUPLOCAL: 'StorageClass'
    AUTO: 'StorageClass'
    REGISTER: 'StorageClass'


class AvailabilityKind(BaseEnumeration):
    AVAILABLE: 'AvailabilityKind'
    DEPRECATED: 'AvailabilityKind'
    NOT_AVAILABLE: 'AvailabilityKind'
    NOT_ACCESSIBLE: 'AvailabilityKind'
    ...


class AccessSpecifier(BaseEnumeration):
    def from_param(self) -> int: ...
    INVALID: 'AccessSpecifier'
    PUBLIC: 'AccessSpecifier'
    PROTECTED: 'AccessSpecifier'
    PRIVATE: 'AccessSpecifier'
    NONE: 'AccessSpecifier'


class TypeKind(BaseEnumeration):
    @property
    def spelling(self) -> str: ...

    # Enum values
    Invalid: 'TypeKind'
    Unexposed: 'TypeKind'
    Void: 'TypeKind'
    Bool: 'TypeKind'
    Char_U: 'TypeKind'
    UChar: 'TypeKind'
    Char16: 'TypeKind'
    Char32: 'TypeKind'
    UShort: 'TypeKind'
    UInt: 'TypeKind'
    ULong: 'TypeKind'
    ULongLong: 'TypeKind'
    UInt128: 'TypeKind'
    Char_S: 'TypeKind'
    SChar: 'TypeKind'
    WChar: 'TypeKind'
    Short: 'TypeKind'
    Int: 'TypeKind'
    Long: 'TypeKind'
    LongLong: 'TypeKind'
    Int128: 'TypeKind'
    Float: 'TypeKind'
    Double: 'TypeKind'
    LongDouble: 'TypeKind'
    NullPtr: 'TypeKind'
    Overload: 'TypeKind'
    Dependent: 'TypeKind'
    ObjCId: 'TypeKind'
    ObjCClass: 'TypeKind'
    ObjCSel: 'TypeKind'
    Float128: 'TypeKind'
    Half: 'TypeKind'
    Ibm128: 'TypeKind'
    Complex: 'TypeKind'
    Pointer: 'TypeKind'
    BlockPointer: 'TypeKind'
    LValueReference: 'TypeKind'
    RValueReference: 'TypeKind'
    Record: 'TypeKind'
    Enum: 'TypeKind'
    Typedef: 'TypeKind'
    ObjCInterface: 'TypeKind'
    ObjCObjectPointer: 'TypeKind'
    FunctionNoProto: 'TypeKind'
    FunctionProto: 'TypeKind'
    ConstantArray: 'TypeKind'
    Vector: 'TypeKind'
    IncompleteArray: 'TypeKind'
    VariableArray: 'TypeKind'
    DependentSizedArray: 'TypeKind'
    MemberPointer: 'TypeKind'
    Auto: 'TypeKind'
    Elaborated: 'TypeKind'
    Pipe: 'TypeKind'
    OCLImage1dRO: 'TypeKind'
    OCLImage1dArrayRO: 'TypeKind'
    OCLImage1dBufferRO: 'TypeKind'
    OCLImage2dRO: 'TypeKind'
    OCLImage2dArrayRO: 'TypeKind'
    OCLImage2dDepthRO: 'TypeKind'
    OCLImage2dArrayDepthRO: 'TypeKind'
    OCLImage2dMSAARO: 'TypeKind'
    OCLImage2dArrayMSAARO: 'TypeKind'
    OCLImage2dMSAADepthRO: 'TypeKind'
    OCLImage2dArrayMSAADepthRO: 'TypeKind'
    OCLImage3dRO: 'TypeKind'
    OCLImage1dWO: 'TypeKind'
    OCLImage1dArrayWO: 'TypeKind'
    OCLImage1dBufferWO: 'TypeKind'
    OCLImage2dWO: 'TypeKind'
    OCLImage2dArrayWO: 'TypeKind'
    OCLImage2dDepthWO: 'TypeKind'
    OCLImage2dArrayDepthWO: 'TypeKind'
    OCLImage2dMSAAWO: 'TypeKind'
    OCLImage2dArrayMSAAWO: 'TypeKind'
    OCLImage2dMSAADepthWO: 'TypeKind'
    OCLImage2dArrayMSAADepthWO: 'TypeKind'
    OCLImage3dWO: 'TypeKind'
    OCLImage1dRW: 'TypeKind'
    OCLImage1dArrayRW: 'TypeKind'
    OCLImage1dBufferRW: 'TypeKind'
    OCLImage2dRW: 'TypeKind'
    OCLImage2dArrayRW: 'TypeKind'
    OCLImage2dDepthRW: 'TypeKind'
    OCLImage2dArrayDepthRW: 'TypeKind'
    OCLImage2dMSAARW: 'TypeKind'
    OCLImage2dArrayMSAARW: 'TypeKind'
    OCLImage2dMSAADepthRW: 'TypeKind'
    OCLImage2dArrayMSAADepthRW: 'TypeKind'
    OCLImage3dRW: 'TypeKind'
    OCLSampler: 'TypeKind'
    OCLEvent: 'TypeKind'
    OCLQueue: 'TypeKind'
    OCLReserveID: 'TypeKind'
    ExtVector: 'TypeKind'
    Atomic: 'TypeKind'


class RefQualifierKind(BaseEnumeration):
    def from_param(self) -> int: ...
    NONE: 'RefQualifierKind'
    LVALUE: 'RefQualifierKind'
    RVALUE: 'RefQualifierKind'


class LinkageKind(BaseEnumeration):
    def from_param(self) -> int: ...
    INVALID: 'LinkageKind'
    NO_LINKAGE: 'LinkageKind'
    INTERNAL: 'LinkageKind'
    UNIQUE_EXTERNAL: 'LinkageKind'
    EXTERNAL: 'LinkageKind'


class TLSKind(BaseEnumeration):
    def from_param(self) -> int: ...
    NONE: 'TLSKind'
    DYNAMIC: 'TLSKind'
    STATIC: 'TLSKind'


class Type(Structure):
    @property
    def kind(self) -> TypeKind: ...
    parent: Incomplete
    length: Incomplete
    def argument_types(self) -> Iterable[Type]: ...
    @property
    def element_type(self) -> Type: ...
    @property
    def element_count(self) -> int: ...
    @property
    def translation_unit(self) -> TranslationUnit: ...
    @staticmethod
    def from_result(res: Type, fn: Any, args: Any) -> Type: ...
    def get_num_template_arguments(self) -> int: ...
    def get_template_argument_type(self, num: int) -> Type: ...
    def get_canonical(self) -> Type: ...
    def is_const_qualified(self) -> bool: ...
    def is_volatile_qualified(self) -> bool: ...
    def is_restrict_qualified(self) -> bool: ...
    def is_function_variadic(self) -> bool: ...
    def get_address_space(self) -> int: ...
    def get_typedef_name(self) -> str: ...
    def is_pod(self) -> bool: ...
    def get_pointee(self) -> Type: ...
    def get_declaration(self) -> Cursor: ...
    def get_result(self) -> Type: ...
    def get_array_element_type(self) -> Type: ...
    def get_array_size(self) -> int: ...
    def get_class_type(self) -> Type: ...
    def get_named_type(self) -> Type: ...
    def get_align(self) -> int: ...
    def get_size(self) -> int: ...
    def get_offset(self, fieldname: str) -> int: ...
    def get_ref_qualifier(self) -> RefQualifierKind: ...
    def get_fields(self) -> Iterator[Cursor]: ...
    def get_exception_specification_kind(
        self) -> ExceptionSpecificationKind: ...

    @property
    def spelling(self) -> str: ...
    def __eq__(self, other: Any) -> bool: ...
    def __ne__(self, other: Any) -> bool: ...


class ClangObject:
    obj: Incomplete
    def __init__(self, obj) -> None: ...
    def from_param(self): ...


class _CXUnsavedFile(Structure):
    ...


class CompletionChunk:
    class Kind:
        name: Incomplete
        def __init__(self, name: str) -> None: ...
    cs: Incomplete
    key: int
    def __init__(self, completionString: CompletionString, key) -> None: ...
    def spelling(self) -> str: ...
    def kind(self) -> Kind: ...
    def string(self) -> Optional[CompletionString]: ...
    def isKindOptional(self) -> bool: ...
    def isKindTypedText(self) -> bool: ...
    def isKindPlaceHolder(self) -> bool: ...
    def isKindInformative(self) -> bool: ...
    def isKindResultType(self) -> bool: ...


class CompletionString(ClangObject):
    class Availability:
        name: str
        def __init__(self, name: str) -> None: ...

    def __len__(self) -> int: ...
    def num_chunks(self) -> int: ...
    def __getitem__(self, key: int) -> CompletionChunk: ...
    @property
    def priority(self) -> int: ...
    @property
    def availability(self) -> CompletionChunk.Kind: ...
    @property
    def briefComment(self) -> str: ...


class CodeCompletionResult(Structure):
    @property
    def kind(self): ...
    @property
    def string(self): ...


class CCRStructure(Structure):
    def __len__(self) -> int: ...
    def __getitem__(self, key): ...


class CodeCompletionResults(ClangObject):
    ptr: Incomplete
    def __init__(self, ptr) -> None: ...
    def from_param(self): ...
    def __del__(self) -> None: ...
    @property
    def results(self) -> CCRStructure: ...
    ccr: Incomplete
    @property
    def diagnostics(self) -> Iterable[Diagnostic]: ...


class Index(ClangObject):
    @staticmethod
    def create(excludeDecls: bool = ...) -> Index: ...
    def __del__(self) -> None: ...
    def read(self, path: str) -> TranslationUnit: ...
    def parse(self, path: str, args: list[str] | None = ...,
              unsaved_files: list[tuple[str, str]] | None = ..., options: int = ...) -> 'TranslationUnit': ...


class TranslationUnit(ClangObject):
    PARSE_NONE: int
    PARSE_DETAILED_PROCESSING_RECORD: int
    PARSE_INCOMPLETE: int
    PARSE_PRECOMPILED_PREAMBLE: int
    PARSE_CACHE_COMPLETION_RESULTS: int
    PARSE_SKIP_FUNCTION_BODIES: int
    PARSE_INCLUDE_BRIEF_COMMENTS_IN_CODE_COMPLETION: int

    @classmethod
    def from_source(cls, filename: str, args: Optional[list[str]] = ...,
                    unsaved_files: Optional[list[tuple[str, str]]] = None,
                    options: int = 0, index: Optional[Index] = None) -> TranslationUnit: ...

    @classmethod
    def from_ast_file(cls, filename: str,
                      index: Optional[Index] = None) -> TranslationUnit: ...
    index: Index
    def __init__(self, ptr, index: Index) -> None: ...
    def __del__(self) -> None: ...
    @property
    def cursor(self) -> Cursor: ...
    @property
    def spelling(self) -> str: ...
    def get_includes(self) -> Iterator[FileInclusion]: ...
    def get_file(self, filename: str) -> File: ...

    def get_location(self, filename: str,
                     position: tuple[int, int]) -> SourceLocation: ...

    def get_extent(self, filename: str,
                   locations: list[tuple[int, int]] | tuple[int, int]) -> SourceRange: ...
    tu: TranslationUnit
    @property
    def diagnostics(self) -> Iterable[Diagnostic]: ...
    def reparse(
        self, unsaved_files: Optional[list[tuple[str, str]]] = None, options: int = 0) -> None: ...

    def save(self, filename: str) -> None: ...

    def codeComplete(self, path: Any, line: int, column: int, unsaved_files: Optional[list[tuple[str, str]]] = None,
                     include_macros: bool = False, include_code_patterns: bool = False,
                     include_brief_comments: bool = False) -> Optional[CodeCompletionResults]: ...
    def get_tokens(self, locations: Optional[tuple[int, int]] = None,
                   extent: Optional[SourceRange] = None) -> Generator[Token, None, None]: ...


class File(ClangObject):
    @staticmethod
    def from_name(translation_unit: TranslationUnit,
                  file_name: str) -> File: ...

    @property
    def name(self) -> str: ...
    @property
    def time(self) -> int: ...
    @staticmethod
    def from_result(res: Any, fn: Any, args: Any) -> File: ...


class FileInclusion:
    source: File
    include: File
    location: SourceLocation
    depth: int
    def __init__(self, src, tgt, loc, depth) -> None: ...
    @property
    def is_input_file(self) -> bool: ...


class CompilationDatabaseError(Exception):
    ERROR_UNKNOWN: int
    ERROR_CANNOTLOADDATABASE: int
    cdb_error: Incomplete
    def __init__(self, enumeration, message) -> None: ...


class CompileCommand:
    cmd: Incomplete
    ccmds: Incomplete
    def __init__(self, cmd, ccmds) -> None: ...
    @property
    def directory(self): ...
    @property
    def filename(self): ...
    @property
    def arguments(self) -> Generator[Incomplete, None, None]: ...


class CompileCommands:
    ccmds: Incomplete
    def __init__(self, ccmds) -> None: ...
    def __del__(self) -> None: ...
    def __len__(self) -> int: ...
    def __getitem__(self, i): ...
    @staticmethod
    def from_result(res, fn, args): ...


class CompilationDatabase(ClangObject):
    def __del__(self) -> None: ...
    @staticmethod
    def from_result(res, fn, args): ...
    @staticmethod
    def fromDirectory(buildDir): ...
    def getCompileCommands(self, filename: str): ...
    def getAllCompileCommands(self): ...


class Token(Structure):
    @property
    def spelling(self) -> str: ...
    @property
    def kind(self) -> TokenKind: ...
    @property
    def location(self) -> SourceLocation: ...
    @property
    def extent(self) -> SourceRange: ...
    @property
    def cursor(self) -> Cursor: ...


class LibclangError(Exception):
    m: Incomplete
    def __init__(self, message) -> None: ...


class Config:
    library_path: Incomplete
    library_file: Incomplete
    compatibility_check: bool
    loaded: bool
    @staticmethod
    def set_library_path(path) -> None: ...
    @staticmethod
    def set_library_file(filename) -> None: ...
    @staticmethod
    def set_compatibility_check(check_status) -> None: ...
    def lib(self): ...
    def get_filename(self) -> str: ...
    def get_cindex_library(self): ...
    def function_exists(self, name): ...
