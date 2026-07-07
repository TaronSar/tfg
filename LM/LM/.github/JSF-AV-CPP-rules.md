# JSF AV C++ Coding Standards — Complete Rule Reference

> Source: *Joint Strike Fighter Air Vehicle C++ Coding Standards*, Doc 2RDU00001 Rev C, December 2005.
> Full PDF at `JSF-AV-rules.pdf`.
>
> This document is a detailed reference for exhaustive code reviews. For a summary of the most impactful rules, see Section 4.1 of `copilot-instructions.md`.

## Rule Types

- **Should**: Advisory. Strongly recommended.
- **Will**: Mandatory intent, but does not require verification.
- **Shall**: Mandatory. Requires verification (automatic or manual).

Deviating from a "shall" rule requires documented approval and must be noted in the file (AV Rules 4–7).

---

## 1. General Design

| Rule | Level | Description |
|------|-------|-------------|
| **AV 1** | will | Max **200 logical source lines** per function/method. |
| **AV 2** | shall | No self-modifying code. |
| **AV 3** | shall | Cyclomatic complexity **≤ 20**. Exception: `switch` with many cases. Complexity = edges − nodes + 2. |

## 2. Language & Character Sets

| Rule | Level | Description |
|------|-------|-------------|
| **AV 8** | shall | All code shall conform to ISO/IEC 14882:2002(E) C++. No language extensions. |
| **AV 9** | will | Only C++ basic source character set (96 chars). |
| **AV 10** | will | Character types restricted to defined subset of ISO 10646-1. |
| **AV 11** | shall | Trigraphs shall not be used. |
| **AV 12** | will | Digraphs (`<%`, `%>`, `<:`, `:>`, `%:`, `%:%:`) shall not be used. |
| **AV 13** | shall | Multi-byte characters and wide string literals shall not be used. |
| **AV 14** | shall | Literal suffixes use uppercase (`64L` not `64l`). |
| **AV 15** | will | Run-time checks as per DO-178B; defensive programming for SEAL 1/2. |

## 3. Libraries

| Rule | Level | Description |
|------|-------|-------------|
| **AV 16** | shall | Only DO-178B level A certifiable libraries for safety-critical code. |
| **AV 17** | shall | `errno` shall not be used. Exception: third-party math libs if well-defined. |
| **AV 18** | shall | `<stdio.h>` shall not be used. |
| **AV 19** | shall | `<locale.h>` and `setlocale` shall not be used. |
| **AV 20** | shall | `setjmp`/`longjmp` shall not be used. |
| **AV 21** | shall | `<signal.h>` facilities shall not be used. |
| **AV 22** | shall | `<stdio.h>` input/output shall not be used. |
| **AV 23** | shall | `atof`, `atoi`, `atol` shall not be used. |
| **AV 24** | shall | `abort`, `exit`, `getenv`, `system` shall not be used. |
| **AV 25** | shall | `<time.h>` shall not be used. |

## 4. Preprocessor

| Rule | Level | Description |
|------|-------|-------------|
| **AV 26** | shall | Only `#ifndef`, `#define`, `#endif`, `#include` directives allowed. |
| **AV 27** | will | `#ifndef`/`#define`/`#endif` used only for include guards. |
| **AV 28** | will | `#ifndef`/`#endif` only for include guards (no conditional compilation). |
| **AV 29** | shall | No `#define` macros — use `inline` functions. |
| **AV 30** | shall | No `#define` constants — use `const`. |
| **AV 31** | will | `#define` only for include guards. |
| **AV 32** | will | `#include` only for header (`.h`) files. Exception: template implementation files. |
| **AV 33** | shall | Use `<filename.h>` notation (not `"filename.h"`). Relative paths OK. |

## 5. Header & Implementation Files

| Rule | Level | Description |
|------|-------|-------------|
| **AV 34** | should | Headers contain logically related declarations only. |
| **AV 35** | will | Every header must have an include guard mechanism. |
| **AV 36** | should | Minimize compilation dependencies. |
| **AV 37** | should | Headers include only required headers; let `.cpp` include the rest. |
| **AV 38** | should | Use forward declarations for pointer/reference-only dependencies. |
| **AV 39** | will | No non-const variable or function definitions in headers. Exception: `inline`, templates. |
| **AV 40** | shall | Implementation files include headers for all inline functions, types, templates used. |
| **AV 53** | will | Header files extension: `.h`. |
| **AV 53.1** | shall | No `'`, `\`, `/*`, `//`, or `"` in header file names. |
| **AV 54** | will | Implementation files extension: `.cpp`. |
| **AV 55** | should | Header name reflects the logical entity it declares. |
| **AV 56** | should | Implementation file name matches header; use suffixes for multiples (e.g. `Math_sqrt.cpp`). |

## 6. Style & Formatting

| Rule | Level | Description |
|------|-------|-------------|
| **AV 41** | will | Lines ≤ **120 characters**. |
| **AV 42** | will | One expression-statement per line. |
| **AV 43** | should | No tabs — use spaces. |
| **AV 44** | will | Indentation ≥ 2 spaces, consistent within file (project uses 4). |
| **AV 57** | will | Declare `public` → `protected` → `private` in that order. |
| **AV 58** | will | Functions with >2 params: first param on same line as function name, each additional on its own line. |
| **AV 59** | shall | Always use `{}` for `if`/`else if`/`else`/`while`/`do…while`/`for` bodies. Even if empty. |
| **AV 60** | will | Allman braces: `{` and `}` on own lines, same column. |
| **AV 61** | will | Nothing else on brace lines except comments. |
| **AV 62** | will | `*` and `&` attached to type: `int* p` not `int *p`. |
| **AV 63** | will | No spaces around `.` or `->`, no space between unary operator and operand. |
| **AV 152** | shall | One variable declaration per line. |

## 7. Naming Conventions

| Rule | Level | Description |
|------|-------|-------------|
| **AV 45** | will | Words in identifiers separated by `_`. |
| **AV 46** | will | Identifier significance ≥ 64 characters. |
| **AV 47** | will | Identifiers shall not begin with `_`. |
| **AV 48** | will | Identifiers shall not differ only by case, `O`/`0`/`D`, `I`/`1`/`l`, `S`/`5`, `Z`/`2`, `n`/`h`. |
| **AV 49** | will | Acronyms in identifiers: all uppercase (`RGB`, `IO`). |
| **AV 50** | will | Class/struct/enum/namespace/typedef: first word uppercase, rest lowercase. |
| **AV 51** | will | Function and variable names: all lowercase. |
| **AV 52** | shall | Constant and enumerator names: all lowercase. |

## 8. Classes

### 8.1 Interface & Access

| Rule | Level | Description |
|------|-------|-------------|
| **AV 64** | should | Class interface: complete and minimal. |
| **AV 65** | should | Use `struct` for entities without invariants. |
| **AV 66** | should | Use `class` for entities that maintain invariants. |
| **AV 67** | should | Public/protected data only in `struct`, not `class`. |
| **AV 68** | shall | Explicitly disallow (declare private) unneeded implicit member functions. |
| **AV 69** | will | Non-mutating member functions must be `const`. Default to `const`, add non-`const` only when needed. |
| **AV 70** | will | Use `friend` only when access to private members is needed and membership is impossible. |
| **AV 109** | should | Do not define functions in class spec unless intended to be inlined. |

### 8.2 Constructors, Destructors & Lifetime

| Rule | Level | Description |
|------|-------|-------------|
| **AV 70.1** | shall | No use of an object before its lifetime begins or after it ends. |
| **AV 71** | shall | No calls to externally visible operations until object is fully initialized. |
| **AV 71.1** | shall | Do not invoke class's virtual functions from constructors or destructors. |
| **AV 72** | should | Class invariant = postcondition of constructors, precondition of destructor, pre/postcondition of public methods. |
| **AV 73** | shall | No unnecessary default constructors. |
| **AV 74** | will | Initialize non-static members via member initialization list, not assignment. Exception: arrays, streams. |
| **AV 75** | shall | Member init list order matches declaration order. Base classes first. |
| **AV 76** | shall | Define copy ctor + assignment operator for classes with pointers or non-trivial destructors. |
| **AV 77** | shall | Copy ctor copies all data members/bases affecting invariant. |
| **AV 77.1** | shall | No member function defaults that produce the implicit copy ctor signature. |
| **AV 78** | shall | Base classes with virtual functions must have a virtual destructor. |
| **AV 79** | shall | All resources acquired by a class released in destructor (RAII). |

### 8.3 Assignment & Operators

| Rule | Level | Description |
|------|-------|-------------|
| **AV 80** | will | Use default copy/assignment when they offer reasonable semantics. |
| **AV 81** | shall | Assignment operator must handle self-assignment correctly. |
| **AV 82** | shall | `operator=` returns `*this` by reference. |
| **AV 83** | shall | Assignment copies all data members/bases affecting invariant. |
| **AV 84** | will | Operator overloading: use sparingly, follow natural meanings. `+=` means `+` then `=`. |
| **AV 85** | will | Opposites (`==`/`!=`): define both, one in terms of the other. |
| **AV 159** | shall | Do not overload `||`, `&&`, or unary `&`. |

### 8.4 Inheritance

| Rule | Level | Description |
|------|-------|-------------|
| **AV 86** | should | Use concrete types for simple independent concepts. |
| **AV 87** | should | Hierarchies based on abstract classes. |
| **AV 88** | shall | Multiple inheritance: n interfaces + m private implementations + ≤1 protected implementation. |
| **AV 88.1** | shall | Stateful virtual base explicitly declared at every level that accesses it. |
| **AV 89** | shall | A base class not both virtual and non-virtual in same hierarchy. |
| **AV 90** | should | Heavily-used interfaces: minimal, general, abstract. |
| **AV 91** | will | Public inheritance = "is-a". |
| **AV 92** | will | Subtypes must conform to Liskov Substitution Principle: derived preconditions ≥ weaker, postconditions ≥ stronger. |
| **AV 93** | will | "has-a"/"is-implemented-in-terms-of" via membership or non-public inheritance. |
| **AV 94** | shall | Do not redefine inherited non-virtual functions. |
| **AV 95** | shall | Never redefine inherited default parameters. |
| **AV 96** | shall | Arrays not treated polymorphically. |
| **AV 97** | shall | Arrays not used in interfaces — use Array class. |
| **AV 97.1** | shall | No `==`/`!=` with pointer to virtual member function. |

## 9. Namespaces

| Rule | Level | Description |
|------|-------|-------------|
| **AV 98** | should | Every nonlocal name (except `main`) in a namespace. |
| **AV 99** | will | Namespace nesting ≤ 2 levels. |
| **AV 100** | should | `using` declaration for few names, `using` directive for many. |

## 10. Templates

| Rule | Level | Description |
|------|-------|-------------|
| **AV 101** | shall | Review templates: (1) in isolation with assumptions on arguments, (2) for all actual instantiations. |
| **AV 102** | shall | Tests cover all actual template instantiations. |
| **AV 103** | should | Apply constraint checks to template arguments. |
| **AV 104** | shall | Template specialization declared before use. |
| **AV 105** | should | Minimize template dependence on instantiation context. |
| **AV 106** | should | Provide pointer-type specializations where appropriate. |

## 11. Functions

### 11.1 Declaration & Arguments

| Rule | Level | Description |
|------|-------|-------------|
| **AV 107** | shall | Functions declared at file scope only. |
| **AV 108** | shall | No unspecified number of arguments (ellipsis `...`). |
| **AV 110** | will | Max **7 arguments**. Exception: some constructors. |
| **AV 116** | should | Small concrete-type args (2–3 words): pass by value. |
| **AV 117** | should | Pass by reference if NULL not possible. `const T&` if not modified, `T&` if modified. |
| **AV 118** | should | Pass via pointer if NULL is possible. `const T*` if not modified, `T*` if modified. |

### 11.2 Return Values

| Rule | Level | Description |
|------|-------|-------------|
| **AV 111** | shall | Never return pointer/reference to non-static local object. |
| **AV 112** | should | Return values must not obscure resource ownership. |
| **AV 113** | shall | All execution paths in value-returning functions return a value. |
| **AV 114** | shall | All exit points via `return`. |
| **AV 115** | shall | Return type matches the function declaration. |

### 11.3 Overloading & Inlining

| Rule | Level | Description |
|------|-------|-------------|
| **AV 120** | should | Overloads: same semantics, same name, same purpose, differ by formal params. |
| **AV 121** | will | Inlining: small functions inlined, complex functions not. |
| **AV 122** | should | Trivial accessors/mutators should be inlined. |
| **AV 124** | should | Trivial forwarding functions should be inlined. |
| **AV 125** | should | Avoid unnecessary temporaries in operations on large/complex objects. |

## 12. Comments

| Rule | Level | Description |
|------|-------|-------------|
| **AV 126** | shall | Only C++ style comments (`//`). Exception: auto-generators. |
| **AV 127** | shall | Dead (commented-out) code shall be deleted. Exception: code in explanatory comments. |
| **AV 128** | should | Comments explaining code purpose, not obvious mechanics. |
| **AV 129** | should | Header comments describe externally visible behavior only. |
| **AV 130** | should | Suffix `//` comment for `}` in long compound statements. |
| **AV 131** | should | Do not state in comments what is better stated in code. |
| **AV 133** | will | Every source file: introductory comment (filename, contents, legal). |
| **AV 134** | will | Every function/method: comment with purpose, params, return, exceptions. |

## 13. Declarations, Definitions & Initialization

| Rule | Level | Description |
|------|-------|-------------|
| **AV 135** | shall | Inner scope identifiers shall not hide outer scope identifiers. |
| **AV 136** | will | Declare at the smallest feasible scope. |
| **AV 137** | should | File-scope declarations should be `static` where possible. |
| **AV 138** | will | Identifiers shall be given the narrowest possible linkage. |
| **AV 139** | will | External objects declared in only one file (use headers). |
| **AV 140** | will | `typedef` names represent types, avoid ambiguity. |
| **AV 141** | will | No inline declaration of class/struct/enum in definition. |
| **AV 142** | shall | All variables initialized before use. |
| **AV 143** | will | Variables introduced only when they can be initialized with meaningful values. |
| **AV 144** | shall | Pointers initialized at declaration (typically to `0`/`nullptr`). |

## 14. Types & Constants

| Rule | Level | Description |
|------|-------|-------------|
| **AV 145** | shall | Enumerator: `=` only for first element unless all are explicitly initialized. |
| **AV 146** | shall | Enumerations represent sets of related values. |
| **AV 147** | shall | Never manipulate floating-point bit representations directly. |
| **AV 148** | should | Enumeration types preferred over integer types for sets of related values. |
| **AV 149** | shall | No octal constants (except zero). |
| **AV 150** | will | Hexadecimal constants: uppercase A–F. |
| **AV 151** | will | No magic numbers; use symbolic constants. Exception: `0`, `1` in obvious contexts. |
| **AV 151.1** | shall | String literals assigned only to `const` pointers. |

## 15. Variables

| Rule | Level | Description |
|------|-------|-------------|
| **AV 153** | shall | Unions shall not be used. |
| **AV 154** | shall | Bit-field types: only explicitly signed/unsigned int. |
| **AV 155** | will | Bit-fields not for space packing; only hardware interfaces / protocol conformance. |
| **AV 156** | shall | Named bit-fields separated from unnamed by `int` boundaries. |

## 16. Operators

| Rule | Level | Description |
|------|-------|-------------|
| **AV 157** | shall | Right operand of `&&`/`||` shall not contain side effects. |
| **AV 158** | shall | Parenthesize non-obvious operator precedence, especially with `&&`/`||`. |
| **AV 160** | shall | No assignment in sub-expressions. Assignment only as standalone statement. |
| **AV 162** | shall | Do not mix signed and unsigned in arithmetic/comparisons. |
| **AV 163** | shall | Unsigned arithmetic shall not be used. |
| **AV 164** | shall | Shift RHS: 0 ≤ rhs < bit-width of LHS. |
| **AV 164.1** | shall | Left operand of `>>` shall not be negative. |
| **AV 165** | shall | Comma operator shall not be used. Exception: `for` loop. |
| **AV 166** | shall | `sizeof` not used on expressions with side effects. |
| **AV 167** | shall | No pointer subtraction unless both point to same array. |
| **AV 168** | shall | No comma operator. |

## 17. Pointers & References

| Rule | Level | Description |
|------|-------|-------------|
| **AV 169** | should | Avoid pointers-to-pointers when possible. |
| **AV 170** | shall | More than 2 pointer indirections shall not be used. |
| **AV 171** | shall | No pointer arithmetic via `+`, `-`, `++`, or `--`. Use containers/iterators. |
| **AV 173** | shall | No pointer-to-function casts to/from other types. |
| **AV 174** | shall | `0`/`nullptr`, not dereferenced. |
| **AV 175** | shall | Use `0` (or `nullptr`), never `NULL`. |
| **AV 176** | will | Use `typedef` for function pointer types. |
| **AV 215** | will | No pointer arithmetic. Exception: containers, iterators, allocators. |

## 18. Type Conversions

| Rule | Level | Description |
|------|-------|-------------|
| **AV 177** | should | Avoid user-defined conversion functions. |
| **AV 178** | shall | Downcast only via `dynamic_cast` (if RTTI) or type-safe mechanism. |
| **AV 179** | shall | No casting pointer-to-virtual-base to pointer-to-derived. |
| **AV 180** | shall | No implicit conversion that loses information. |
| **AV 181** | shall | No implicit `float`→`int` or `double`→`float` conversion without cast. |
| **AV 182** | shall | No implicit integral→floating conversion without cast. |
| **AV 183** | should | Avoid type casting entirely. |
| **AV 184** | shall | Float→int only if required by algorithm or hardware interface. |
| **AV 185** | shall | **Use C++ casts** (`static_cast`, `reinterpret_cast`, `const_cast`), never C-style casts. |

## 19. Flow Control

| Rule | Level | Description |
|------|-------|-------------|
| **AV 186** | shall | No `goto`. |
| **AV 187** | shall | No side effects in `&&`/`||` right operand. |
| **AV 188** | shall | Every non-empty `switch` label ends with `break`. |
| **AV 189** | shall | Every `switch` has a `default`. |
| **AV 190** | shall | `default` clause actions or comment explaining none. |
| **AV 191** | shall | `switch` variable: only enumeration or integer type. |
| **AV 192** | shall | `if`…`else if` chain must end with `else` (or comment explaining why not). |
| **AV 193** | shall | Every `case` in `switch`: ends with `break` or documented fall-through reason. |
| **AV 194** | shall | No unreachable code. |
| **AV 195** | shall | No empty `if`, `else if`, or `else` bodies except with `{}` and comment. |
| **AV 196** | shall | Control variable of numeric `for` not modified in body. |
| **AV 197** | shall | No `continue` in loops. Exception: early-exit for degenerate iterations. |
| **AV 198** | will | `for` init expression: only initialize the loop variable. |
| **AV 199** | will | `for` increment expression: only change the loop variable. |
| **AV 200** | will | No null init or increment in `for` — use `while` instead. |
| **AV 201** | shall | Iteration/selection conditions do not use assignment. |

## 20. Expressions

| Rule | Level | Description |
|------|-------|-------------|
| **AV 202** | shall | No floating-point equality comparisons (`==`, `!=`). |
| **AV 203** | shall | No unsigned wrapping or signed overflow relied upon. |
| **AV 204** | shall | Side-effect operations only: (1) standalone, (2) RHS of assignment, (3) in function invocation. |
| **AV 204.1** | shall | Expression value invariant under any evaluation order the standard permits. |
| **AV 205** | shall | `volatile` only for direct hardware interfaces. |

## 21. Memory & Resources

| Rule | Level | Description |
|------|-------|-------------|
| **AV 206** | shall | Allocation/deallocation from free store (`new`/`delete`) shall not be used. Exception: Where object lifetime dictates. |
| **AV 207** | will | No unencapsulated global data. |
| **AV 208** | shall | **No C++ exceptions** (`throw`, `catch`, `try`). |

## 22. Portable Code

| Rule | Level | Description |
|------|-------|-------------|
| **AV 209** | shall | `UniversalTypes` file defines all standard types (`bool`, `int8`, `int16`, `int32`, `int64`, `float32`, `float64`). |
| **AV 210** | shall | No assumptions about data memory layout (endianness, subobject ordering). |
| **AV 210.1** | shall | No assumptions about non-static data member order across access specifiers. |
| **AV 211** | shall | No assumptions about starting addresses of types. |
| **AV 212** | shall | No dependence on underflow/overflow behavior. |
| **AV 213** | shall | Parenthesize below arithmetic operators — no reliance on precedence. |
| **AV 214** | shall | No reliance on initialization order of non-local statics across translation units. |

## 23. Efficiency & Miscellaneous

| Rule | Level | Description |
|------|-------|-------------|
| **AV 216** | should | Do not prematurely optimize. Focus on correctness first (*"Premature optimization is the root of all evil" — Knuth*). |
| **AV 217** | should | Prefer compile/link-time errors over runtime errors. |
| **AV 218** | will | Compiler warning levels per project policies. |

## 24. Testing (Inheritance Hierarchies)

| Rule | Level | Description |
|------|-------|-------------|
| **AV 219** | shall | All base class tests applied to all derived class interfaces. Stronger derived postconditions substituted. |
| **AV 220** | shall | Structural coverage against *flattened* classes (all inherited + defined members). |
| **AV 221** | shall | Coverage of virtual function hierarchies: test every possible polymorphic resolution. |
