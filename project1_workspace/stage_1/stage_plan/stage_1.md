# Stage 1: Core Data Structures and Types

## Rationale

Establish the foundational data structures and types that will be used throughout the Rust codebase. This includes structs for the parser, entities, and other core components, as well as enums for parser state and error codes.

## Interface Points

The data structures defined in this stage will be the primary interface between the different modules of the parser.

## Included Files

* `expat.h`
* `internal.h`

## Refactoring Plan

1.  Create a new Rust library named `expat`.
2.  Create a `src/lib.rs` file.
3.  Translate the C structs and enums from `expat.h` and `internal.h` into Rust structs and enums in `src/lib.rs`.
