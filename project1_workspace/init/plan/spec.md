# Refactoring Specification

## 1. System Topography
The Expat XML parser is a C library with a layered architecture. The core components are:
- **`xmltok.c`**: A low-level tokenizer that processes the raw XML byte stream and emits tokens.
- **`xmlrole.c`**: A role parser that interprets the tokens from `xmltok.c` within the context of the XML prolog and DTD, acting as a state machine.
- **`xmlparse.c`**: The main parser logic that orchestrates the tokenization and role parsing, manages the parser state, and invokes user-defined handlers.
- **`expat.h`**: The public API of the library, defining the `XML_Parser` and related functions.
- **`main.c`**: The CLI entry point that uses the Expat library to parse XML from standard input.

The system is designed for performance and low-level control, with a focus on callback-based event handling.

## 2. Module Cluster Map
The refactoring will be organized into the following modules, mirroring the original C architecture:

- **`lib.rs`**: The main library crate, containing the public API and core data structures.
- **`tokenizer.rs`**: The tokenizer module, responsible for lexical analysis of the XML input.
- **`role_parser.rs`**: The role parser module, implementing the state machine for the prolog and DTD.
- **`parser.rs`**: The main parser module, containing the `Parser` struct and the core parsing logic.
- **`main.rs`**: The CLI application that uses the parser library.

## 3. Staging Roadmap

### Stage 1: Core Types & Error Handling
* **Rationale**: This stage establishes the foundational data structures and error handling mechanisms for the entire project. It corresponds to the public API defined in `expat.h` and the internal types in `internal.h`.
* **Interface Points**:
    - `Parser` struct
    - `Error` enum
    - Other core enums and structs
* **Included Files**:
    - `expat.h`
    - `internal.h`

### Stage 2: Tokenizer/Lexer
* **Rationale**: This stage focuses on the lowest level of parsing: tokenization. It translates the logic from `xmltok.c` and the associated character classification tables.
* **Interface Points**:
    - `Tokenizer` struct
    - `Token` enum
* **Included Files**:
    - `xmltok.c`
    - `xmltok.h`
    - `xmltok_impl.h`
    - `ascii.h`
    - `asciitab.h`
    - `iasciitab.h`
    - `latin1tab.h`
    - `utf8tab.h`
    - `nametab.h`

### Stage 3: Role Parser & State Machine
* **Rationale**: This stage implements the higher-level parsing logic, including the state machine for the prolog and DTD, and the main parsing loop. It translates `xmlrole.c` and `xmlparse.c`.
* **Interface Points**:
    - `RoleParser` struct
    - `Parser::parse` method
* **Included Files**:
    - `xmlrole.c`
    - `xmlrole.h`
    - `xmlparse.c`

### Stage 4: CLI Integration
* **Rationale**: This stage creates the final command-line application that uses the new Rust parser library. It translates `main.c`.
* **Interface Points**:
    - `main` function
* **Included Files**:
    - `main.c`

## 4. Execution Risks
- **Complexity of the C code**: The Expat codebase is highly optimized and uses complex macros and pointer arithmetic, which can be challenging to translate to safe, idiomatic Rust.
- **Callback-based architecture**: The callback-based design of Expat can be tricky to replicate in Rust while maintaining safety and performance.
- **Output identity**: Ensuring that the Rust implementation produces 100% identical output to the original C version will require careful testing and attention to detail.
