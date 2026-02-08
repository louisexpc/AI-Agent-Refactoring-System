use crate::ascii::Ascii;
use crate::internal::XmlNameMatchesAscii;
use crate::xmltok::{Encoding, XmlTok};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(i32)]
pub enum XmlRole {
    Error = -1,
    None = 0,
    XmlDecl,
    InstanceStart,
    DoctypeNone,
    DoctypeName,
    DoctypeSystemId,
    DoctypePublicId,
    DoctypeInternalSubset,
    DoctypeClose,
    GeneralEntityName,
    ParamEntityName,
    EntityNone,
    EntityValue,
    EntitySystemId,
    EntityPublicId,
    EntityComplete,
    EntityNotationName,
    NotationNone,
    NotationName,
    NotationSystemId,
    NotationNoSystemId,
    NotationPublicId,
    AttributeName,
    AttributeTypeCdata,
    AttributeTypeId,
    AttributeTypeIdref,
    AttributeTypeIdrefs,
    AttributeTypeEntity,
    AttributeTypeEntities,
    AttributeTypeNmtoken,
    AttributeTypeNmtokens,
    AttributeEnumValue,
    AttributeNotationValue,
    AttlistNone,
    AttlistElementName,
    ImpliedAttributeValue,
    RequiredAttributeValue,
    DefaultAttributeValue,
    FixedAttributeValue,
    ElementNone,
    ElementName,
    ContentAny,
    ContentEmpty,
    ContentPcdata,
    GroupOpen,
    GroupClose,
    GroupCloseRep,
    GroupCloseOpt,
    GroupClosePlus,
    GroupChoice,
    GroupSequence,
    ContentElement,
    ContentElementRep,
    ContentElementOpt,
    ContentElementPlus,
    Pi,
    Comment,
    #[cfg(feature = "DTD")]
    TextDecl,
    #[cfg(feature = "DTD")]
    IgnoreSect,
    #[cfg(feature = "DTD")]
    InnerParamEntityRef,
    ParamEntityRef,
}

type PrologHandler = fn(&mut PrologState, XmlTok, &str, &str, &Encoding) -> XmlRole;

pub struct PrologState {
    handler: PrologHandler,
    level: u32,
    role_none: XmlRole,
    #[cfg(feature = "DTD")]
    include_level: u32,
    #[cfg(feature = "DTD")]
    document_entity: bool,
    #[cfg(feature = "DTD")]
    in_entity_value: bool,
}

impl PrologState {
    pub fn new() -> Self {
        PrologState {
            handler: prolog0,
            level: 0,
            role_none: XmlRole::None,
            #[cfg(feature = "DTD")]
            document_entity: true,
            #[cfg(feature = "DTD")]
            include_level: 0,
            #[cfg(feature = "DTD")]
            in_entity_value: false,
        }
    }

    #[cfg(feature = "DTD")]
    pub fn new_external_entity() -> Self {
        PrologState {
            handler: external_subset0,
            document_entity: false,
            include_level: 1,
            ..PrologState::new()
        }
    }

    pub fn token_role(&mut self, tok: XmlTok, ptr: &str, end: &str, enc: &Encoding) -> XmlRole {
        (self.handler)(self, tok, ptr, end, enc)
    }
}

const KW_ANY: &str = "ANY";
const KW_ATTLIST: &str = "ATTLIST";
const KW_CDATA: &str = "CDATA";
const KW_DOCTYPE: &str = "DOCTYPE";
const KW_ELEMENT: &str = "ELEMENT";
const KW_EMPTY: &str = "EMPTY";
const KW_ENTITIES: &str = "ENTITIES";
const KW_ENTITY: &str = "ENTITY";
const KW_FIXED: &str = "FIXED";
const KW_ID: &str = "ID";
const KW_IDREF: &str = "IDREF";
const KW_IDREFS: &str = "IDREFS";
#[cfg(feature = "DTD")]
const KW_IGNORE: &str = "IGNORE";
const KW_IMPLIED: &str = "IMPLIED";
#[cfg(feature = "DTD")]
const KW_INCLUDE: &str = "INCLUDE";
const KW_NDATA: &str = "NDATA";
const KW_NMTOKEN: &str = "NMTOKEN";
const KW_NMTOKENS: &str = "NMTOKENS";
const KW_NOTATION: &str = "NOTATION";
const KW_PCDATA: &str = "PCDATA";
const KW_PUBLIC: &str = "PUBLIC";
const KW_REQUIRED: &str = "REQUIRED";
const KW_SYSTEM: &str = "SYSTEM";

fn prolog0(state: &mut PrologState, tok: XmlTok, ptr: &str, end: &str, enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => {
            state.handler = prolog1;
            XmlRole::None
        }
        XmlTok::XmlDecl => {
            state.handler = prolog1;
            XmlRole::XmlDecl
        }
        XmlTok::Pi => {
            state.handler = prolog1;
            XmlRole::Pi
        }
        XmlTok::Comment => {
            state.handler = prolog1;
            XmlRole::Comment
        }
        XmlTok::Bom => XmlRole::None,
        XmlTok::DeclOpen => {
            if !XmlNameMatchesAscii(
                enc,
                &ptr[2 * enc.min_bytes_per_char()..],
                end,
                KW_DOCTYPE,
            ) {
                common(state, tok)
            } else {
                state.handler = doctype0;
                XmlRole::DoctypeNone
            }
        }
        XmlTok::InstanceStart => {
            state.handler = error;
            XmlRole::InstanceStart
        }
        _ => common(state, tok),
    }
}

fn prolog1(state: &mut PrologState, tok: XmlTok, ptr: &str, end: &str, enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::None,
        XmlTok::Pi => XmlRole::Pi,
        XmlTok::Comment => XmlRole::Comment,
        XmlTok::Bom => XmlRole::None,
        XmlTok::DeclOpen => {
            if !XmlNameMatchesAscii(
                enc,
                &ptr[2 * enc.min_bytes_per_char()..],
                end,
                KW_DOCTYPE,
            ) {
                common(state, tok)
            } else {
                state.handler = doctype0;
                XmlRole::DoctypeNone
            }
        }
        XmlTok::InstanceStart => {
            state.handler = error;
            XmlRole::InstanceStart
        }
        _ => common(state, tok),
    }
}

fn prolog2(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::None,
        XmlTok::Pi => XmlRole::Pi,
        XmlTok::Comment => XmlRole::Comment,
        XmlTok::InstanceStart => {
            state.handler = error;
            XmlRole::InstanceStart
        }
        _ => common(state, tok),
    }
}

fn doctype0(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::DoctypeNone,
        XmlTok::Name | XmlTok::PrefixedName => {
            state.handler = doctype1;
            XmlRole::DoctypeName
        }
        _ => common(state, tok),
    }
}

fn doctype1(state: &mut PrologState, tok: XmlTok, ptr: &str, end: &str, enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::DoctypeNone,
        XmlTok::OpenBracket => {
            state.handler = internal_subset;
            XmlRole::DoctypeInternalSubset
        }
        XmlTok::DeclClose => {
            state.handler = prolog2;
            XmlRole::DoctypeClose
        }
        XmlTok::Name => {
            if XmlNameMatchesAscii(enc, ptr, end, KW_SYSTEM) {
                state.handler = doctype3;
                XmlRole::DoctypeNone
            } else if XmlNameMatchesAscii(enc, ptr, end, KW_PUBLIC) {
                state.handler = doctype2;
                XmlRole::DoctypeNone
            } else {
                common(state, tok)
            }
        }
        _ => common(state, tok),
    }
}

fn doctype2(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::DoctypeNone,
        XmlTok::Literal => {
            state.handler = doctype3;
            XmlRole::DoctypePublicId
        }
        _ => common(state, tok),
    }
}

fn doctype3(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::DoctypeNone,
        XmlTok::Literal => {
            state.handler = doctype4;
            XmlRole::DoctypeSystemId
        }
        _ => common(state, tok),
    }
}

fn doctype4(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::DoctypeNone,
        XmlTok::OpenBracket => {
            state.handler = internal_subset;
            XmlRole::DoctypeInternalSubset
        }
        XmlTok::DeclClose => {
            state.handler = prolog2;
            XmlRole::DoctypeClose
        }
        _ => common(state, tok),
    }
}

fn doctype5(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::DoctypeNone,
        XmlTok::DeclClose => {
            state.handler = prolog2;
            XmlRole::DoctypeClose
        }
        _ => common(state, tok),
    }
}

fn internal_subset(state: &mut PrologState, tok: XmlTok, ptr: &str, end: &str, enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::None,
        XmlTok::DeclOpen => {
            let name = &ptr[2 * enc.min_bytes_per_char()..];
            if XmlNameMatchesAscii(enc, name, end, KW_ENTITY) {
                state.handler = entity0;
                XmlRole::EntityNone
            } else if XmlNameMatchesAscii(enc, name, end, KW_ATTLIST) {
                state.handler = attlist0;
                XmlRole::AttlistNone
            } else if XmlNameMatchesAscii(enc, name, end, KW_ELEMENT) {
                state.handler = element0;
                XmlRole::ElementNone
            } else if XmlNameMatchesAscii(enc, name, end, KW_NOTATION) {
                state.handler = notation0;
                XmlRole::NotationNone
            } else {
                common(state, tok)
            }
        }
        XmlTok::Pi => XmlRole::Pi,
        XmlTok::Comment => XmlRole::Comment,
        XmlTok::ParamEntityRef => XmlRole::ParamEntityRef,
        XmlTok::CloseBracket => {
            state.handler = doctype5;
            XmlRole::DoctypeNone
        }
        XmlTok::None => XmlRole::None,
        _ => common(state, tok),
    }
}

#[cfg(feature = "DTD")]
fn external_subset0(state: &mut PrologState, tok: XmlTok, ptr: &str, end: &str, enc: &Encoding) -> XmlRole {
    state.handler = external_subset1;
    if tok == XmlTok::XmlDecl {
        XmlRole::TextDecl
    } else {
        external_subset1(state, tok, ptr, end, enc)
    }
}

#[cfg(feature = "DTD")]
fn external_subset1(state: &mut PrologState, tok: XmlTok, ptr: &str, end: &str, enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::CondSectOpen => {
            state.handler = cond_sect0;
            XmlRole::None
        }
        XmlTok::CondSectClose => {
            if state.include_level == 0 {
                common(state, tok)
            } else {
                state.include_level -= 1;
                XmlRole::None
            }
        }
        XmlTok::PrologS => XmlRole::None,
        XmlTok::CloseBracket => common(state, tok),
        XmlTok::None => {
            if state.include_level != 0 {
                common(state, tok)
            } else {
                XmlRole::None
            }
        }
        _ => internal_subset(state, tok, ptr, end, enc),
    }
}

fn entity0(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::EntityNone,
        XmlTok::Percent => {
            state.handler = entity1;
            XmlRole::EntityNone
        }
        XmlTok::Name => {
            state.handler = entity2;
            XmlRole::GeneralEntityName
        }
        _ => common(state, tok),
    }
}

fn entity1(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::EntityNone,
        XmlTok::Name => {
            state.handler = entity7;
            XmlRole::ParamEntityName
        }
        _ => common(state, tok),
    }
}

fn entity2(state: &mut PrologState, tok: XmlTok, ptr: &str, end: &str, enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::EntityNone,
        XmlTok::Name => {
            if XmlNameMatchesAscii(enc, ptr, end, KW_SYSTEM) {
                state.handler = entity4;
                XmlRole::EntityNone
            } else if XmlNameMatchesAscii(enc, ptr, end, KW_PUBLIC) {
                state.handler = entity3;
                XmlRole::EntityNone
            } else {
                common(state, tok)
            }
        }
        XmlTok::Literal => {
            state.handler = decl_close;
            state.role_none = XmlRole::EntityNone;
            XmlRole::EntityValue
        }
        _ => common(state, tok),
    }
}

fn entity3(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::EntityNone,
        XmlTok::Literal => {
            state.handler = entity4;
            XmlRole::EntityPublicId
        }
        _ => common(state, tok),
    }
}

fn entity4(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::EntityNone,
        XmlTok::Literal => {
            state.handler = entity5;
            XmlRole::EntitySystemId
        }
        _ => common(state, tok),
    }
}

fn entity5(state: &mut PrologState, tok: XmlTok, ptr: &str, end: &str, enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::EntityNone,
        XmlTok::DeclClose => {
            set_top_level(state);
            XmlRole::EntityComplete
        }
        XmlTok::Name => {
            if XmlNameMatchesAscii(enc, ptr, end, KW_NDATA) {
                state.handler = entity6;
                XmlRole::EntityNone
            } else {
                common(state, tok)
            }
        }
        _ => common(state, tok),
    }
}

fn entity6(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::EntityNone,
        XmlTok::Name => {
            state.handler = decl_close;
            state.role_none = XmlRole::EntityNone;
            XmlRole::EntityNotationName
        }
        _ => common(state, tok),
    }
}

fn entity7(state: &mut PrologState, tok: XmlTok, ptr: &str, end: &str, enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::EntityNone,
        XmlTok::Name => {
            if XmlNameMatchesAscii(enc, ptr, end, KW_SYSTEM) {
                state.handler = entity9;
                XmlRole::EntityNone
            } else if XmlNameMatchesAscii(enc, ptr, end, KW_PUBLIC) {
                state.handler = entity8;
                XmlRole::EntityNone
            } else {
                common(state, tok)
            }
        }
        XmlTok::Literal => {
            state.handler = decl_close;
            state.role_none = XmlRole::EntityNone;
            XmlRole::EntityValue
        }
        _ => common(state, tok),
    }
}

fn entity8(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::EntityNone,
        XmlTok::Literal => {
            state.handler = entity9;
            XmlRole::EntityPublicId
        }
        _ => common(state, tok),
    }
}

fn entity9(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::EntityNone,
        XmlTok::Literal => {
            state.handler = entity10;
            XmlRole::EntitySystemId
        }
        _ => common(state, tok),
    }
}

fn entity10(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::EntityNone,
        XmlTok::DeclClose => {
            set_top_level(state);
            XmlRole::EntityComplete
        }
        _ => common(state, tok),
    }
}

fn notation0(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::NotationNone,
        XmlTok::Name => {
            state.handler = notation1;
            XmlRole::NotationName
        }
        _ => common(state, tok),
    }
}

fn notation1(state: &mut PrologState, tok: XmlTok, ptr: &str, end: &str, enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::NotationNone,
        XmlTok::Name => {
            if XmlNameMatchesAscii(enc, ptr, end, KW_SYSTEM) {
                state.handler = notation3;
                XmlRole::NotationNone
            } else if XmlNameMatchesAscii(enc, ptr, end, KW_PUBLIC) {
                state.handler = notation2;
                XmlRole::NotationNone
            } else {
                common(state, tok)
            }
        }
        _ => common(state, tok),
    }
}

fn notation2(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::NotationNone,
        XmlTok::Literal => {
            state.handler = notation4;
            XmlRole::NotationPublicId
        }
        _ => common(state, tok),
    }
}

fn notation3(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::NotationNone,
        XmlTok::Literal => {
            state.handler = decl_close;
            state.role_none = XmlRole::NotationNone;
            XmlRole::NotationSystemId
        }
        _ => common(state, tok),
    }
}

fn notation4(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::NotationNone,
        XmlTok::Literal => {
            state.handler = decl_close;
            state.role_none = XmlRole::NotationNone;
            XmlRole::NotationSystemId
        }
        XmlTok::DeclClose => {
            set_top_level(state);
            XmlRole::NotationNoSystemId
        }
        _ => common(state, tok),
    }
}

fn attlist0(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::AttlistNone,
        XmlTok::Name | XmlTok::PrefixedName => {
            state.handler = attlist1;
            XmlRole::AttlistElementName
        }
        _ => common(state, tok),
    }
}

fn attlist1(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::AttlistNone,
        XmlTok::DeclClose => {
            set_top_level(state);
            XmlRole::AttlistNone
        }
        XmlTok::Name | XmlTok::PrefixedName => {
            state.handler = attlist2;
            XmlRole::AttributeName
        }
        _ => common(state, tok),
    }
}

fn attlist2(state: &mut PrologState, tok: XmlTok, ptr: &str, end: &str, enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::AttlistNone,
        XmlTok::Name => {
            const TYPES: &[&str] = &[
                KW_CDATA, KW_ID, KW_IDREF, KW_IDREFS, KW_ENTITY, KW_ENTITIES, KW_NMTOKEN,
                KW_NMTOKENS,
            ];
            for (i, &t) in TYPES.iter().enumerate() {
                if XmlNameMatchesAscii(enc, ptr, end, t) {
                    state.handler = attlist8;
                    return unsafe { std::mem::transmute(XmlRole::AttributeTypeCdata as i32 + i as i32) };
                }
            }
            if XmlNameMatchesAscii(enc, ptr, end, KW_NOTATION) {
                state.handler = attlist5;
                XmlRole::AttlistNone
            } else {
                common(state, tok)
            }
        }
        XmlTok::OpenParen => {
            state.handler = attlist3;
            XmlRole::AttlistNone
        }
        _ => common(state, tok),
    }
}

fn attlist3(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::AttlistNone,
        XmlTok::Nmtoken | XmlTok::Name | XmlTok::PrefixedName => {
            state.handler = attlist4;
            XmlRole::AttributeEnumValue
        }
        _ => common(state, tok),
    }
}

fn attlist4(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::AttlistNone,
        XmlTok::CloseParen => {
            state.handler = attlist8;
            XmlRole::AttlistNone
        }
        XmlTok::Or => {
            state.handler = attlist3;
            XmlRole::AttlistNone
        }
        _ => common(state, tok),
    }
}

fn attlist5(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::AttlistNone,
        XmlTok::OpenParen => {
            state.handler = attlist6;
            XmlRole::AttlistNone
        }
        _ => common(state, tok),
    }
}

fn attlist6(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::AttlistNone,
        XmlTok::Name => {
            state.handler = attlist7;
            XmlRole::AttributeNotationValue
        }
        _ => common(state, tok),
    }
}

fn attlist7(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::AttlistNone,
        XmlTok::CloseParen => {
            state.handler = attlist8;
            XmlRole::AttlistNone
        }
        XmlTok::Or => {
            state.handler = attlist6;
            XmlRole::AttlistNone
        }
        _ => common(state, tok),
    }
}

fn attlist8(state: &mut PrologState, tok: XmlTok, ptr: &str, end: &str, enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::AttlistNone,
        XmlTok::PoundName => {
            let name = &ptr[enc.min_bytes_per_char()..];
            if XmlNameMatchesAscii(enc, name, end, KW_IMPLIED) {
                state.handler = attlist1;
                XmlRole::ImpliedAttributeValue
            } else if XmlNameMatchesAscii(enc, name, end, KW_REQUIRED) {
                state.handler = attlist1;
                XmlRole::RequiredAttributeValue
            } else if XmlNameMatchesAscii(enc, name, end, KW_FIXED) {
                state.handler = attlist9;
                XmlRole::AttlistNone
            } else {
                common(state, tok)
            }
        }
        XmlTok::Literal => {
            state.handler = attlist1;
            XmlRole::DefaultAttributeValue
        }
        _ => common(state, tok),
    }
}

fn attlist9(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::AttlistNone,
        XmlTok::Literal => {
            state.handler = attlist1;
            XmlRole::FixedAttributeValue
        }
        _ => common(state, tok),
    }
}

fn element0(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::ElementNone,
        XmlTok::Name | XmlTok::PrefixedName => {
            state.handler = element1;
            XmlRole::ElementName
        }
        _ => common(state, tok),
    }
}

fn element1(state: &mut PrologState, tok: XmlTok, ptr: &str, end: &str, enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::ElementNone,
        XmlTok::Name => {
            if XmlNameMatchesAscii(enc, ptr, end, KW_EMPTY) {
                state.handler = decl_close;
                state.role_none = XmlRole::ElementNone;
                XmlRole::ContentEmpty
            } else if XmlNameMatchesAscii(enc, ptr, end, KW_ANY) {
                state.handler = decl_close;
                state.role_none = XmlRole::ElementNone;
                XmlRole::ContentAny
            } else {
                common(state, tok)
            }
        }
        XmlTok::OpenParen => {
            state.handler = element2;
            state.level = 1;
            XmlRole::GroupOpen
        }
        _ => common(state, tok),
    }
}

fn element2(state: &mut PrologState, tok: XmlTok, ptr: &str, end: &str, enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::ElementNone,
        XmlTok::PoundName => {
            if XmlNameMatchesAscii(
                enc,
                &ptr[enc.min_bytes_per_char()..],
                end,
                KW_PCDATA,
            ) {
                state.handler = element3;
                XmlRole::ContentPcdata
            } else {
                common(state, tok)
            }
        }
        XmlTok::OpenParen => {
            state.level = 2;
            state.handler = element6;
            XmlRole::GroupOpen
        }
        XmlTok::Name | XmlTok::PrefixedName => {
            state.handler = element7;
            XmlRole::ContentElement
        }
        XmlTok::NameQuestion => {
            state.handler = element7;
            XmlRole::ContentElementOpt
        }
        XmlTok::NameAsterisk => {
            state.handler = element7;
            XmlRole::ContentElementRep
        }
        XmlTok::NamePlus => {
            state.handler = element7;
            XmlRole::ContentElementPlus
        }
        _ => common(state, tok),
    }
}

fn element3(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::ElementNone,
        XmlTok::CloseParen => {
            state.handler = decl_close;
            state.role_none = XmlRole::ElementNone;
            XmlRole::GroupClose
        }
        XmlTok::CloseParenAsterisk => {
            state.handler = decl_close;
            state.role_none = XmlRole::ElementNone;
            XmlRole::GroupCloseRep
        }
        XmlTok::Or => {
            state.handler = element4;
            XmlRole::ElementNone
        }
        _ => common(state, tok),
    }
}

fn element4(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::ElementNone,
        XmlTok::Name | XmlTok::PrefixedName => {
            state.handler = element5;
            XmlRole::ContentElement
        }
        _ => common(state, tok),
    }
}

fn element5(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::ElementNone,
        XmlTok::CloseParenAsterisk => {
            state.handler = decl_close;
            state.role_none = XmlRole::ElementNone;
            XmlRole::GroupCloseRep
        }
        XmlTok::Or => {
            state.handler = element4;
            XmlRole::ElementNone
        }
        _ => common(state, tok),
    }
}

fn element6(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::ElementNone,
        XmlTok::OpenParen => {
            state.level += 1;
            XmlRole::GroupOpen
        }
        XmlTok::Name | XmlTok::PrefixedName => {
            state.handler = element7;
            XmlRole::ContentElement
        }
        XmlTok::NameQuestion => {
            state.handler = element7;
            XmlRole::ContentElementOpt
        }
        XmlTok::NameAsterisk => {
            state.handler = element7;
            XmlRole::ContentElementRep
        }
        XmlTok::NamePlus => {
            state.handler = element7;
            XmlRole::ContentElementPlus
        }
        _ => common(state, tok),
    }
}

fn element7(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::ElementNone,
        XmlTok::CloseParen => {
            state.level -= 1;
            if state.level == 0 {
                state.handler = decl_close;
                state.role_none = XmlRole::ElementNone;
            }
            XmlRole::GroupClose
        }
        XmlTok::CloseParenAsterisk => {
            state.level -= 1;
            if state.level == 0 {
                state.handler = decl_close;
                state.role_none = XmlRole::ElementNone;
            }
            XmlRole::GroupCloseRep
        }
        XmlTok::CloseParenQuestion => {
            state.level -= 1;
            if state.level == 0 {
                state.handler = decl_close;
                state.role_none = XmlRole::ElementNone;
            }
            XmlRole::GroupCloseOpt
        }
        XmlTok::CloseParenPlus => {
            state.level -= 1;
            if state.level == 0 {
                state.handler = decl_close;
                state.role_none = XmlRole::ElementNone;
            }
            XmlRole::GroupClosePlus
        }
        XmlTok::Comma => {
            state.handler = element6;
            XmlRole::GroupSequence
        }
        XmlTok::Or => {
            state.handler = element6;
            XmlRole::GroupChoice
        }
        _ => common(state, tok),
    }
}

#[cfg(feature = "DTD")]
fn cond_sect0(state: &mut PrologState, tok: XmlTok, ptr: &str, end: &str, enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::None,
        XmlTok::Name => {
            if XmlNameMatchesAscii(enc, ptr, end, KW_INCLUDE) {
                state.handler = cond_sect1;
                XmlRole::None
            } else if XmlNameMatchesAscii(enc, ptr, end, KW_IGNORE) {
                state.handler = cond_sect2;
                XmlRole::None
            } else {
                common(state, tok)
            }
        }
        _ => common(state, tok),
    }
}

#[cfg(feature = "DTD")]
fn cond_sect1(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::None,
        XmlTok::OpenBracket => {
            state.handler = external_subset1;
            state.include_level += 1;
            XmlRole::None
        }
        _ => common(state, tok),
    }
}

#[cfg(feature = "DTD")]
fn cond_sect2(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => XmlRole::None,
        XmlTok::OpenBracket => {
            state.handler = external_subset1;
            XmlRole::IgnoreSect
        }
        _ => common(state, tok),
    }
}

fn decl_close(state: &mut PrologState, tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    match tok {
        XmlTok::PrologS => state.role_none,
        XmlTok::DeclClose => {
            set_top_level(state);
            state.role_none
        }
        _ => common(state, tok),
    }
}

fn error(_state: &mut PrologState, _tok: XmlTok, _ptr: &str, _end: &str, _enc: &Encoding) -> XmlRole {
    XmlRole::None
}

fn common(state: &mut PrologState, tok: XmlTok) -> XmlRole {
    #[cfg(feature = "DTD")]
    if !state.document_entity && tok == XmlTok::ParamEntityRef {
        return XmlRole::InnerParamEntityRef;
    }
    state.handler = error;
    XmlRole::Error
}

#[cfg(not(feature = "DTD"))]
fn set_top_level(state: &mut PrologState) {
    state.handler = internal_subset;
}

#[cfg(feature = "DTD")]
fn set_top_level(state: &mut PrologState) {
    if state.document_entity {
        state.handler = internal_subset;
    } else {
        state.handler = external_subset1;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    #[cfg(feature = "DTD")]
    fn test_new_external_entity_include_level() {
        let state = PrologState::new_external_entity();
        assert_eq!(state.include_level, 1);
    }
}