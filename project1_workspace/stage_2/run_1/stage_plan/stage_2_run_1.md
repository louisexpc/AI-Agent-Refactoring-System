# Stage 2, Run 1: Tokenizer Implementation

This stage focuses on translating the tokenization logic from Expat's C implementation into a Rust module.

## 1. Token Definition
- Define a `Token` enum in `tokenizer.rs` to represent the different types of XML tokens.

## 2. Character Classification Tables
- Translate the character classification tables from `asciitab.h`, `latin1tab.h`, and `utf8tab.h` into static arrays in `tokenizer.rs`.

## 3. Tokenizer Struct
- Define a `Tokenizer` struct in `tokenizer.rs` to manage the input stream and the tokenization process.

## 4. `next_token` Method
- Implement the `next_token` method on the `Tokenizer` struct, which will contain the core tokenization logic translated from `xmltok.c`.
