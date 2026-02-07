use crate::encoding::*;

#[derive(Clone, Copy, PartialEq, Debug)]
#[repr(i32)]
pub enum XmlTok {
    TrailingRsqb = -5,
    None = -4,
    TrailingCr = -3,
    PartialChar = -2,
    Partial = -1,
    Invalid = 0,
    StartTagWithAtts = 1,
    StartTagNoAtts = 2,
    EmptyElementWithAtts = 3,
    EmptyElementNoAtts = 4,
    EndTag = 5,
    DataChars = 6,
    DataNewline = 7,
    CdataSectOpen = 8,
    EntityRef = 9,
    CharRef = 10,
    Pi = 11,
    XmlDecl = 12,
    Comment = 13,
    Bom = 14,
    PrologS = 15,
    DeclOpen = 16,
    DeclClose = 17,
    Name = 18,
    Nmtoken = 19,
    PoundName = 20,
    Or = 21,
    Percent = 22,
    OpenParen = 23,
    CloseParen = 24,
    OpenBracket = 25,
    CloseBracket = 26,
    Literal = 27,
    ParamEntityRef = 28,
    InstanceStart = 29,
    NameQuestion = 30,
    NameAsterisk = 31,
    NamePlus = 32,
    CondSectOpen = 33,
    CondSectClose = 34,
    CloseParenQuestion = 35,
    CloseParenAsterisk = 36,
    CloseParenPlus = 37,
    Comma = 38,
    AttributeValueS = 39,
    CdataSectClose = 40,
    PrefixedName = 41,
    IgnoreSect = 42,
}

#[derive(Clone, Copy, Debug)]
pub struct Position {
    pub line_number: usize,
    pub column_number: usize,
}

#[derive(Debug)]
pub struct Attribute<'a> {
    pub name: &'a [u8],
    pub value: &'a [u8],
    pub normalized: bool,
}

fn byte_type(b: u8) -> u8 {
    TYPE[b as usize]
}

fn is_char_match(p: &[u8], c: u8) -> bool {
    p[0] == c
}

pub fn content_tok(ptr: &[u8]) -> (XmlTok, &[u8]) {
    if ptr.is_empty() {
        return (XmlTok::None, ptr);
    }

    let mut p = ptr;
    match byte_type(p[0]) {
        BT_LT => {
            p = &p[1..];
            scan_lt(p)
        }
        BT_AMP => {
            p = &p[1..];
            scan_ref(p)
        }
        BT_CR => {
            p = &p[1..];
            if p.is_empty() {
                return (XmlTok::TrailingCr, p);
            }
            if byte_type(p[0]) == BT_LF {
                p = &p[1..];
            }
            (XmlTok::DataNewline, p)
        }
        BT_LF => {
            p = &p[1..];
            (XmlTok::DataNewline, p)
        }
        BT_RSQB => {
            p = &p[1..];
            if p.is_empty() {
                return (XmlTok::TrailingRsqb, p);
            }
            if is_char_match(p, b']') {
                p = &p[1..];
                if p.is_empty() {
                    return (XmlTok::TrailingRsqb, p);
                }
                if is_char_match(p, b'>') {
                    return (XmlTok::Invalid, p);
                }
                p = &p[..p.len() - 1];
            }
            (XmlTok::DataChars, p)
        }
        _ => {
            loop {
                if p.is_empty() {
                    return (XmlTok::DataChars, p);
                }
                match byte_type(p[0]) {
                    BT_LT | BT_AMP | BT_CR | BT_LF | BT_RSQB => {
                        return (XmlTok::DataChars, p);
                    }
                    _ => p = &p[1..],
                }
            }
        }
    }
}

fn scan_lt(ptr: &[u8]) -> (XmlTok, &[u8]) {
    if ptr.is_empty() {
        return (XmlTok::Partial, ptr);
    }
    let mut p = ptr;
    match byte_type(p[0]) {
        BT_NMSTRT | BT_HEX => {
            p = &p[1..];
            scan_start_tag(p)
        }
        BT_SOL => {
            p = &p[1..];
            scan_end_tag(p)
        }
        BT_EXCL => {
            p = &p[1..];
            if p.is_empty() {
                return (XmlTok::Partial, p);
            }
            match byte_type(p[0]) {
                BT_MINUS => {
                    p = &p[1..];
                    scan_comment(p)
                }
                BT_LSQB => {
                    p = &p[1..];
                    scan_cdata_section(p)
                }
                _ => (XmlTok::Invalid, p),
            }
        }
        BT_QUEST => {
            p = &p[1..];
            scan_pi(p)
        }
        _ => (XmlTok::Invalid, p),
    }
}

fn scan_start_tag(ptr: &[u8]) -> (XmlTok, &[u8]) {
    let mut p = ptr;
    while !p.is_empty() {
        match byte_type(p[0]) {
            BT_S | BT_CR | BT_LF => {
                p = &p[1..];
                return scan_atts(p);
            }
            BT_GT => {
                p = &p[1..];
                return (XmlTok::StartTagNoAtts, p);
            }
            BT_SOL => {
                p = &p[1..];
                if !p.is_empty() && is_char_match(p, b'>') {
                    p = &p[1..];
                    return (XmlTok::EmptyElementNoAtts, p);
                }
                return (XmlTok::Invalid, p);
            }
            _ => p = &p[1..],
        }
    }
    (XmlTok::Partial, p)
}

fn scan_atts(ptr: &[u8]) -> (XmlTok, &[u8]) {
    let mut p = ptr;
    while !p.is_empty() {
        match byte_type(p[0]) {
            BT_S | BT_CR | BT_LF => {
                p = &p[1..];
            }
            BT_GT => {
                p = &p[1..];
                return (XmlTok::StartTagWithAtts, p);
            }
            BT_SOL => {
                p = &p[1..];
                if !p.is_empty() && is_char_match(p, b'>') {
                    p = &p[1..];
                    return (XmlTok::EmptyElementWithAtts, p);
                }
                return (XmlTok::Invalid, p);
            }
            BT_NMSTRT | BT_HEX => {
                // simplified attribute parsing
                while !p.is_empty() && byte_type(p[0]) != BT_S && byte_type(p[0]) != BT_GT {
                    p = &p[1..];
                }
            }
            _ => return (XmlTok::Invalid, p),
        }
    }
    (XmlTok::Partial, p)
}

fn scan_end_tag(ptr: &[u8]) -> (XmlTok, &[u8]) {
    let mut p = ptr;
    while !p.is_empty() {
        match byte_type(p[0]) {
            BT_S | BT_CR | BT_LF => {
                p = &p[1..];
            }
            BT_GT => {
                p = &p[1..];
                return (XmlTok::EndTag, p);
            }
            _ => p = &p[1..],
        }
    }
    (XmlTok::Partial, p)
}

fn scan_comment(ptr: &[u8]) -> (XmlTok, &[u8]) {
    let mut p = ptr;
    if !p.is_empty() && is_char_match(p, b'-') {
        p = &p[1..];
        while !p.is_empty() {
            if is_char_match(p, b'-') {
                p = &p[1..];
                if !p.is_empty() && is_char_match(p, b'-') {
                    p = &p[1..];
                    if !p.is_empty() && is_char_match(p, b'>') {
                        p = &p[1..];
                        return (XmlTok::Comment, p);
                    }
                    return (XmlTok::Invalid, p);
                }
            }
            p = &p[1..];
        }
    }
    (XmlTok::Partial, p)
}

fn scan_cdata_section(ptr: &[u8]) -> (XmlTok, &[u8]) {
    let mut p = ptr;
    let cdata = b"CDATA[";
    if p.len() < cdata.len() {
        return (XmlTok::Partial, p);
    }
    if &p[..cdata.len()] == cdata {
        p = &p[cdata.len()..];
        return (XmlTok::CdataSectOpen, p);
    }
    (XmlTok::Invalid, p)
}

fn scan_pi(ptr: &[u8]) -> (XmlTok, &[u8]) {
    let mut p = ptr;
    while !p.is_empty() {
        if is_char_match(p, b'?') {
            p = &p[1..];
            if !p.is_empty() && is_char_match(p, b'>') {
                p = &p[1..];
                return (XmlTok::Pi, p);
            }
        }
        p = &p[1..];
    }
    (XmlTok::Partial, p)
}

fn scan_ref(ptr: &[u8]) -> (XmlTok, &[u8]) {
    let mut p = ptr;
    if p.is_empty() {
        return (XmlTok::Partial, p);
    }
    match byte_type(p[0]) {
        BT_NUM => {
            p = &p[1..];
            scan_char_ref(p)
        }
        BT_NMSTRT | BT_HEX => {
            p = &p[1..];
            while !p.is_empty() {
                match byte_type(p[0]) {
                    BT_SEMI => {
                        p = &p[1..];
                        return (XmlTok::EntityRef, p);
                    }
                    _ => p = &p[1..],
                }
            }
            (XmlTok::Partial, p)
        }
        _ => (XmlTok::Invalid, p),
    }
}

fn scan_char_ref(ptr: &[u8]) -> (XmlTok, &[u8]) {
    let mut p = ptr;
    if !p.is_empty() && is_char_match(p, b'x') {
        p = &p[1..];
        return scan_hex_char_ref(p);
    }
    while !p.is_empty() {
        match byte_type(p[0]) {
            BT_DIGIT => {
                p = &p[1..];
            }
            BT_SEMI => {
                p = &p[1..];
                return (XmlTok::CharRef, p);
            }
            _ => return (XmlTok::Invalid, p),
        }
    }
    (XmlTok::Partial, p)
}

fn scan_hex_char_ref(ptr: &[u8]) -> (XmlTok, &[u8]) {
    let mut p = ptr;
    while !p.is_empty() {
        match byte_type(p[0]) {
            BT_DIGIT | BT_HEX => {
                p = &p[1..];
            }
            BT_SEMI => {
                p = &p[1..];
                return (XmlTok::CharRef, p);
            }
            _ => return (XmlTok::Invalid, p),
        }
    }
    (XmlTok::Partial, p)
}
