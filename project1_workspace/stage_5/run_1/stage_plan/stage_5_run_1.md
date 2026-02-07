# Stage 5: CLI Integration

The final stage is to create the command-line interface that uses the newly refactored Rust parser. This will ensure that the final product is a complete, working application.

## 1. CLI Application

- Create a new binary application within the `agent_expat` crate named `agent_expat_cli`.
- The CLI will read XML from STDIN.
- It will use the `agent_expat` library to parse the XML.
- It will print the parsing events (start/end elements) to STDOUT, in the same format as the original `expat_cli`.

## 2. Integration

- The CLI will call the `XML_ParserCreate`, `XML_SetElementHandler`, `XML_Parse`, and `XML_ParserFree` functions from the `agent_expat` library.

## 3. Manual Testing

- Since automated testing is not working, we will rely on manual testing for this stage.
- We will compile the `agent_expat_cli` binary and run it with some sample XML to verify that it produces the correct output.
