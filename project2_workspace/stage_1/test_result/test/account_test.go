package models

import (
	"reflect"
	"testing"
	"time"
)

// TestAccountStructFields validates that the Account struct has the expected field names and types.
// The golden output for this file is empty '{}', which implies the original file was a data
// model definition (like Ruby's ActiveRecord model) with no directly testable, standalone behavior.
// Therefore, this test focuses on validating the correctness of the refactored data structure,
// ensuring the "shape" of the data (its schema) is preserved. This is a structural validation
// that serves as a baseline correctness check for the model.
func TestAccountStructFields(t *testing.T) {
	expectedFields := map[string]reflect.Type{
		"ID":             reflect.TypeOf(uint(0)),
		"UserID":         reflect.TypeOf(uint(0)),
		"AssignedTo":     reflect.TypeOf(uint(0)),
		"Name":           reflect.TypeOf(""),
		"Access":         reflect.TypeOf(""),
		"Website":        reflect.TypeOf(""),
		"TollFreePhone":  reflect.TypeOf(""),
		"Phone":          reflect.TypeOf(""),
		"Fax":            reflect.TypeOf(""),
		"DeletedAt":      reflect.TypeOf((*time.Time)(nil)),
		"CreatedAt":      reflect.TypeOf(time.Time{}),
		"UpdatedAt":      reflect.TypeOf(time.Time{}),
		"Email":          reflect.TypeOf(""),
		"BackgroundInfo": reflect.TypeOf(""),
		"Rating":         reflect.TypeOf(0),
		"Category":       reflect.TypeOf(""),
	}

	structType := reflect.TypeOf(Account{})

	// Check for the correct number of fields to catch unexpected additions.
	if structType.NumField() != len(expectedFields) {
		t.Fatalf("Account struct has %d fields, but expected %d", structType.NumField(), len(expectedFields))
	}

	for fieldName, expectedType := range expectedFields {
		field, found := structType.FieldByName(fieldName)
		if !found {
			t.Errorf("Account struct is missing expected field: '%s'", fieldName)
			continue
		}

		if field.Type != expectedType {
			t.Errorf("Field '%s' has incorrect type: got %s, want %s", fieldName, field.Type, expectedType)
		}
	}
}