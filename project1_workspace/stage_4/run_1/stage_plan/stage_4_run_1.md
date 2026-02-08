# Stage 4: State Machine & Parser

This is the core of the parser, where the tokenizer and role parser are brought together to drive the parsing process. This stage will manage the parser's state, handle entities and attributes, and call the appropriate user-defined handlers.

## 1. Parser Module

- Create a new `parser.rs` module.
- Implement the main `XML_Parser` struct, which will hold the complete state of the parser.
- Implement the `XML_Parse` function, which will be the main entry point for parsing.

## 2. State Management

- The `XML_Parser` struct will manage the parser's state, including the tag stack, entity handling, and attribute parsing.
- The state machine will be implemented to handle the different parsing contexts (prolog, content, etc.).

## 3. Integration

- The parser will use the `tokenizer` and `role_parser` modules to get tokens and their roles.
- The parser will call the user-defined handlers (e.g., `startElementHandler`, `endElementHandler`) as it encounters the corresponding XML constructs.

## 4. Unit Tests

- Create unit tests for the parser to ensure that it correctly parses well-formed XML documents.
- Test the handling of entities, attributes, and other XML features.
- Test the error handling for malformed XML.
