# Stage 3: Role Parser

This stage will implement the role parser, which takes tokens from the tokenizer and determines their grammatical role. This corresponds to `xmlrole.c`.

## 1. Role Parser Module

- Create a new `role_parser.rs` module.
- Define the `XML_ROLE` enum in this module, based on the enum in `xmlrole.h`.
- Implement the `XmlPrologStateInit` and `XmlTokenRole` functions.
- The role parser will be implemented as a state machine, similar to the C code.

## 2. Integration with Tokenizer

- The role parser will take tokens from the tokenizer module as input.
- The output of the role parser will be a "role" for each token, which will be used by the main parser in the next stage.

## 3. Unit Tests

- Create unit tests for the role parser to ensure that it correctly assigns roles to tokens in various sequences.
- Test the state transitions of the role parser's state machine.
