# Stage 1: Core Types & Error Handling

## Rationale
This stage establishes the foundational data structures and error handling mechanisms for the entire project. It corresponds to the public API defined in `expat.h` and the internal types in `internal.h`.

## Plan
1. Create a new Rust library crate named `expat`.
2. In `lib.rs`, define the core data structures:
    - `Parser` struct (empty for now)
    - `Error` enum, with variants corresponding to the `XML_Error` enum in `expat.h`.
    - Other enums and structs from `expat.h` as needed.
3. Create a `src/lib.rs` file with the initial code.
4. Create a `Cargo.toml` file for the new crate.
