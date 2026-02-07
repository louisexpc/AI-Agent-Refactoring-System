
#[repr(C)]
pub enum Status {
    Error = 0,
    Ok = 1,
    Suspended = 2,
}

#[repr(C)]
#[derive(Debug, PartialEq, Eq, Clone, Copy)]
pub enum Error {
    None,
    NoMemory,
    Syntax,
    NoElements,
    InvalidToken,
    UnclosedToken,
    PartialChar,
    TagMismatch,
    DuplicateAttribute,
    JunkAfterDocElement,
    ParamEntityRef,
    UndefinedEntity,
    RecursiveEntityRef,
    AsyncEntity,
    BadCharRef,
    BinaryEntityRef,
    AttributeExternalEntityRef,
    MisplacedXmlPi,
    UnknownEncoding,
    IncorrectEncoding,
    UnclosedCdataSection,
    ExternalEntityHandling,
    NotStandalone,
    UnexpectedState,
    EntityDeclaredInPe,
    FeatureRequiresXmlDtd,
    CantChangeFeatureOnceParsing,
    UnboundPrefix,
    UndeclaringPrefix,
    IncompletePe,
    XmlDecl,
    TextDecl,
    Publicid,
    Suspended,
    NotSuspended,
    Aborted,
    Finished,
    SuspendPe,
    ReservedPrefixXml,
    ReservedPrefixXmlns,
    ReservedNamespaceUri,
    InvalidArgument,
    NoBuffer,
    AmplificationLimitBreach,
    NotStarted,
}

#[repr(C)]
pub enum ContentType {
    Empty = 1,
    Any,
    Mixed,
    Name,
    Choice,
    Seq,
}

#[repr(C)]
pub enum ContentQuant {
    None,
    Opt,
    Rep,
    Plus,
}

#[repr(C)]
pub enum Parsing {
    Initialized,
    Parsing,
    Finished,
    Suspended,
}

pub struct Parser;

