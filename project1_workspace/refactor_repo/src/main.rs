'''use std::io::Read;

use agent_expat::{ExpatParser, ExpatOptions};

fn main() {
    let mut content = String::new();
    std::io::stdin().read_to_string(&mut content).unwrap();

    let mut parser = ExpatParser::new(
        Some(ExpatOptions {
            encoding: Some("UTF-8"),
            ..Default::default()
        })
    );

    parser.set_start_element_handler(|name, attrs| {
        println!("Start element: {} {:?}", name, attrs);
    });

    parser.set_end_element_handler(|name| {
        println!("End element: {}", name);
    });

    parser.parse(&content, false).unwrap();
}
''