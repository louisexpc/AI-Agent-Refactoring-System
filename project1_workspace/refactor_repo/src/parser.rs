// Copyright 2024 The W3C XML Schema Test Suite Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

//! The main parsing logic. This is the home of the state machine that drives
//! the parsing process.

use crate::tokenizer::Tokenizer;

/// The `XML_Parser` struct holds the complete state of the parser.
pub struct XML_Parser<H> {
    /// The tokenizer is responsible for breaking the input into tokens.
    tokenizer: Tokenizer,

    /// The handler is a collection of callbacks that the user of the library
    /// can provide to be called when the parser encounters different parts of
    /// the XML document.
    handler: H,
}

impl<H> XML_Parser<H> {
    /// Creates a new `XML_Parser`.
    pub fn new(handler: H) -> Self {
        Self {
            tokenizer: Tokenizer::new(),
            handler,
        }
    }

    /// The main parsing function. This function is called with a slice of the
    /// input and a flag indicating whether this is the final slice of the
    /// input.
    ///
    /// The function returns `Ok(())` on success and `Err(&'static str)` on
    /// failure.
    pub fn parse(&mut self, input: &[u8], is_final: bool) -> Result<(), &'static str> {
        self.tokenizer.tokenize(input, is_final)
        // The tokenizer will call the appropriate handlers as it finds tokens.
    }
}
