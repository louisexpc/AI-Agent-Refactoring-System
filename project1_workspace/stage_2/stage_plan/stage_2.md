# Stage 2: Tokenizer (Lexer)

## Rationale

Translate the low-level tokenizing logic from C to Rust. This is a critical step that is responsible for breaking the input stream of bytes into XML tokens.

## Interface Points

The tokenizer will provide a stream of tokens to the parser.

## Included Files

* `xmltok.c`
* `xmltok.h`
* `xmltok_impl.c`
* `xmltok_impl.h`
* `ascii.h`
* `asciitab.h`
* `iasciitab.h`
* `latin1tab.h`
* `utf8tab.h`
* `nametab.h`

## Refactoring Plan

1.  Create a new Rust module named `tokenizer`.
2.  Translate the C code from the included files into Rust code in the `tokenizer` module.
3.  The tokenizer should expose a function that takes a byte slice and returns an iterator of tokens.
