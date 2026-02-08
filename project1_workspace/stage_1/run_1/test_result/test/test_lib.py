#[cfg(test)]
mod tests {
    use super::*;
    use libc::{c_char, c_int, c_long, c_uchar, c_ulong, c_void};
    use std::mem::size_of;
    use std::ptr::null_mut;

    #[test]
    fn test_bool_constants() {
        assert_eq!(XML_TRUE, 1, "XML_TRUE should be 1");
        assert_eq!(XML_FALSE, 0, "XML_FALSE should be 0");
    }

    #[test]
    fn test_type_alias_sizes() {
        assert_eq!(
            size_of::<XML_Char>(),
            size_of::<c_char>(),
            "Size of XML_Char should match c_char"
        );
        assert_eq!(
            size_of::<XML_LChar>(),
            size_of::<c_char>(),
            "Size of XML_LChar should match c_char"
        );
        assert_eq!(
            size_of::<XML_Bool>(),
            size_of::<c_uchar>(),
            "Size of XML_Bool should match c_uchar"
        );
        assert_eq!(
            size_of::<XML_Index>(),
            size_of::<c_long>(),
            "Size of XML_Index should match c_long"
        );
        assert_eq!(
            size_of::<XML_Size>(),
            size_of::<c_ulong>(),
            "Size of XML_Size should match c_ulong"
        );
    }

    #[test]
    fn test_parser_type_is_pointer() {
        assert_eq!(
            size_of::<XML_Parser>(),
            size_of::<*mut c_void>(),
            "XML_Parser should be a pointer type"
        );
        let p: XML_Parser = null_mut();
        assert!(p.is_null());
    }

    #[test]
    fn test_xml_status_enum_values() {
        assert_eq!(XML_Status::Error as c_int, 0);
        assert_eq!(XML_Status::Ok as c_int, 1);
        assert_eq!(XML_Status::Suspended as c_int, 2);
    }

    #[test]
    fn test_xml_error_enum_values() {
        // C enums are sequential by default. We check the first, last, and some key values.
        assert_eq!(XML_Error::None as c_int, 0);
        assert_eq!(XML_Error::NoMemory as c_int, 1);
        assert_eq!(XML_Error::Syntax as c_int, 2);
        assert_eq!(XML_Error::InvalidToken as c_int, 4);
        assert_eq!(XML_Error::JunkAfterDocElement as c_int, 9);
        assert_eq!(XML_Error::UndefinedEntity as c_int, 11);
        assert_eq!(XML_Error::UnknownEncoding as c_int, 18);
        assert_eq!(XML_Error::IncorrectEncoding as c_int, 19);
        assert_eq!(XML_Error::NotStandalone as c_int, 21);
        assert_eq!(XML_Error::IncompletePe as c_int, 29);
        assert_eq!(XML_Error::XmlDecl as c_int, 30);
        assert_eq!(XML_Error::Suspended as c_int, 32);
        assert_eq!(XML_Error::Aborted as c_int, 34);
        assert_eq!(XML_Error::Finished as c_int, 35);
        assert_eq!(XML_Error::ReservedNamespaceUri as c_int, 39);
        assert_eq!(XML_Error::AmplificationLimitBreach as c_int, 40);
        assert_eq!(XML_Error::NotStarted as c_int, 41);
    }

    #[test]
    fn test_xml_content_type_enum_values() {
        // In the C header, these are explicitly numbered starting from 1.
        assert_eq!(XML_Content_Type::Empty as c_int, 1);
        assert_eq!(XML_Content_Type::Any as c_int, 2);
        assert_eq!(XML_Content_Type::Mixed as c_int, 3);
        assert_eq!(XML_Content_Type::Name as c_int, 4);
        assert_eq!(XML_Content_Type::Choice as c_int, 5);
        assert_eq!(XML_Content_Type::Seq as c_int, 6);
    }

    #[test]
    fn test_xml_content_quant_enum_values() {
        assert_eq!(XML_Content_Quant::None as c_int, 0);
        assert_eq!(XML_Content_Quant::Opt as c_int, 1);
        assert_eq!(XML_Content_Quant::Rep as c_int, 2);
        assert_eq!(XML_Content_Quant::Plus as c_int, 3);
    }

    #[test]
    fn test_xml_parsing_enum_values() {
        assert_eq!(XML_Parsing::Initialized as c_int, 0);
        assert_eq!(XML_Parsing::Parsing as c_int, 1);
        assert_eq!(XML_Parsing::Finished as c_int, 2);
        assert_eq!(XML_Parsing::Suspended as c_int, 3);
    }

    #[test]
    fn test_xml_param_entity_parsing_enum_values() {
        assert_eq!(XML_ParamEntityParsing::Never as c_int, 0);
        assert_eq!(XML_ParamEntityParsing::UnlessStandalone as c_int, 1);
        assert_eq!(XML_ParamEntityParsing::Always as c_int, 2);
    }

    #[test]
    fn test_xml_feature_enum_values() {
        assert_eq!(XML_FeatureEnum::End as c_int, 0);
        assert_eq!(XML_FeatureEnum::Unicode as c_int, 1);
        assert_eq!(XML_FeatureEnum::UnicodeWcharT as c_int, 2);
        assert_eq!(XML_FeatureEnum::Dtd as c_int, 3);
        assert_eq!(XML_FeatureEnum::ContextBytes as c_int, 4);
        assert_eq!(XML_FeatureEnum::MinSize as c_int, 5);
        assert_eq!(XML_FeatureEnum::SizeofXmlChar as c_int, 6);
        assert_eq!(XML_FeatureEnum::SizeofXmlLchar as c_int, 7);
        assert_eq!(XML_FeatureEnum::Ns as c_int, 8);
        assert_eq!(XML_FeatureEnum::LargeSize as c_int, 9);
        assert_eq!(XML_FeatureEnum::AttrInfo as c_int, 10);
        assert_eq!(
            XML_FeatureEnum::BillionLaughsAttackProtectionMaximumAmplificationDefault as c_int,
            11
        );
        assert_eq!(
            XML_FeatureEnum::BillionLaughsAttackProtectionActivationThresholdDefault as c_int,
            12
        );
        assert_eq!(XML_FeatureEnum::Ge as c_int, 13);
        assert_eq!(XML_FeatureEnum::AllocTrackerMaximumAmplificationDefault as c_int, 14);
        assert_eq!(XML_FeatureEnum::AllocTrackerActivationThresholdDefault as c_int, 15);
    }

    // The following tests verify that #[repr(C)] structs can be created.
    // This is a basic sanity check of the definitions. It confirms they
    // compile and can be instantiated, which is the primary "behavior" of
    // FFI type definitions.

    #[test]
    fn test_can_create_xml_content() {
        let _s = XML_Content {
            type_: XML_Content_Type::Empty,
            quant: XML_Content_Quant::None,
            name: null_mut(),
            numchildren: 0,
            children: null_mut(),
        };
    }

    #[test]
    fn test_can_create_xml_memory_handling_suite() {
        let _s = XML_Memory_Handling_Suite {
            malloc_fcn: None,
            realloc_fcn: None,
            free_fcn: None,
        };
    }

    #[test]
    fn test_can_create_xml_encoding() {
        let _s = XML_Encoding {
            map: [0; 256],
            data: null_mut(),
            convert: None,
            release: None,
        };
    }

    #[test]
    fn test_can_create_xml_parsing_status() {
        let s = XML_ParsingStatus {
            parsing: XML_Parsing::Initialized,
            finalBuffer: XML_FALSE,
        };
        assert_eq!(s.parsing, XML_Parsing::Initialized);
        assert_eq!(s.finalBuffer, XML_FALSE);
    }

    #[test]
    fn test_can_create_xml_expat_version() {
        let s = XML_Expat_Version {
            major: 2,
            minor: 5,
            micro: 0,
        };
        assert_eq!(s.major, 2);
        assert_eq!(s.minor, 5);
        assert_eq!(s.micro, 0);
    }

    #[test]
    fn test_can_create_xml_feature() {
        let name_bytes = b"my-feature\0";
        let s = XML_Feature {
            feature: XML_FeatureEnum::Ns,
            name: name_bytes.as_ptr() as *const XML_LChar,
            value: 1,
        };
        assert_eq!(s.feature, XML_FeatureEnum::Ns);
        assert_eq!(s.value, 1);
        // The pointer check is mostly to ensure it's not null.
        assert!(!s.name.is_null());
    }

    #[test]
    fn test_can_create_xml_attr_info() {
        let s = XML_AttrInfo {
            nameStart: 10,
            nameEnd: 20,
            valueStart: 25,
            valueEnd: 35,
        };
        assert_eq!(s.nameStart, 10);
        assert_eq!(s.nameEnd, 20);
        assert_eq!(s.valueStart, 25);
        assert_eq!(s.valueEnd, 35);
    }
}