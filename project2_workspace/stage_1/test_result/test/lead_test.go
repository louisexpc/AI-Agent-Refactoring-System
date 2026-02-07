package models

import (
	"reflect"
	"testing"
	"time"
)

// TestLeadStructDefinition validates that the Lead struct has the expected fields, types, and GORM tags.
// This test uses reflection to ensure the data model's structure has been refactored correctly,
// which is the only behavior defined in the provided Go source file.
//
// The 'golden output' is empty ({}) because the provided 'lead.go' file only contains a type definition
// and no executable functions that produce output.
//
// Behavioral tests for methods like 'promote', complex validations depending on external settings,
// or database callbacks mentioned in the testing guidance are not applicable here, as those methods
// and logic have not been implemented in the provided Go struct definition.
func TestLeadStructDefinition(t *testing.T) {
	type fieldAssertion struct {
		Name string
		Kind reflect.Kind
		Type reflect.Type
		Tag  string
	}

	// Define expectations for each field in the Lead struct.
	expectedFields := []fieldAssertion{
		{Name: "ID", Kind: reflect.Uint, Type: reflect.TypeOf(uint(0)), Tag: `gorm:"primaryKey"`},
		{Name: "UserID", Kind: reflect.Uint, Type: reflect.TypeOf(uint(0)), Tag: ``},
		{Name: "CampaignID", Kind: reflect.Uint, Type: reflect.TypeOf(uint(0)), Tag: ``},
		{Name: "AssignedTo", Kind: reflect.Uint, Type: reflect.TypeOf(uint(0)), Tag: ``},
		{Name: "FirstName", Kind: reflect.String, Type: reflect.TypeOf(""), Tag: `gorm:"size:64;not null;default:''"`},
		{Name: "LastName", Kind: reflect.String, Type: reflect.TypeOf(""), Tag: `gorm:"size:64;not null;default:''"`},
		{Name: "Access", Kind: reflect.String, Type: reflect.TypeOf(""), Tag: `gorm:"size:8;default:'Public'"`},
		{Name: "Title", Kind: reflect.String, Type: reflect.TypeOf(""), Tag: `gorm:"size:64"`},
		{Name: "Company", Kind: reflect.String, Type: reflect.TypeOf(""), Tag: `gorm:"size:64"`},
		{Name: "Source", Kind: reflect.String, Type: reflect.TypeOf(""), Tag: `gorm:"size:32"`},
		{Name: "Status", Kind: reflect.String, Type: reflect.TypeOf(""), Tag: `gorm:"size:32"`},
		{Name: "ReferredBy", Kind: reflect.String, Type: reflect.TypeOf(""), Tag: `gorm:"size:64"`},
		{Name: "Email", Kind: reflect.String, Type: reflect.TypeOf(""), Tag: `gorm:"size:64"`},
		{Name: "AltEmail", Kind: reflect.String, Type: reflect.TypeOf(""), Tag: `gorm:"size:64"`},
		{Name: "Phone", Kind: reflect.String, Type: reflect.TypeOf(""), Tag: `gorm:"size:32"`},
		{Name: "Mobile", Kind: reflect.String, Type: reflect.TypeOf(""), Tag: `gorm:"size:32"`},
		{Name: "Blog", Kind: reflect.String, Type: reflect.TypeOf(""), Tag: `gorm:"size:128"`},
		{Name: "Linkedin", Kind: reflect.String, Type: reflect.TypeOf(""), Tag: `gorm:"size:128"`},
		{Name: "Facebook", Kind: reflect.String, Type: reflect.TypeOf(""), Tag: `gorm:"size:128"`},
		{Name: "Twitter", Kind: reflect.String, Type: reflect.TypeOf(""), Tag: `gorm:"size:128"`},
		{Name: "Rating", Kind: reflect.Int, Type: reflect.TypeOf(0), Tag: `gorm:"not null;default:0"`},
		{Name: "DoNotCall", Kind: reflect.Bool, Type: reflect.TypeOf(false), Tag: `gorm:"not null;default:false"`},
		{Name: "DeletedAt", Kind: reflect.Ptr, Type: reflect.TypeOf(&time.Time{}), Tag: ``},
		{Name: "CreatedAt", Kind: reflect.Struct, Type: reflect.TypeOf(time.Time{}), Tag: ``},
		{Name: "UpdatedAt", Kind: reflect.Struct, Type: reflect.TypeOf(time.Time{}), Tag: ``},
		{Name: "BackgroundInfo", Kind: reflect.String, Type: reflect.TypeOf(""), Tag: `gorm:"size:255"`},
	}

	leadType := reflect.TypeOf(Lead{})

	if leadType.NumField() != len(expectedFields) {
		t.Fatalf("Lead struct has %d fields, but expected %d", leadType.NumField(), len(expectedFields))
	}

	for _, expected := range expectedFields {
		t.Run(expected.Name, func(t *testing.T) {
			field, ok := leadType.FieldByName(expected.Name)
			if !ok {
				t.Fatalf("Field '%s' not found in Lead struct", expected.Name)
			}

			if field.Type.Kind() != expected.Kind {
				t.Errorf("Field '%s' has kind %s, but expected %s", expected.Name, field.Type.Kind(), expected.Kind)
			}

			if field.Type != expected.Type {
				t.Errorf("Field '%s' has type %s, but expected %s", expected.Name, field.Type, expected.Type)
			}

			gormTag := field.Tag.Get("gorm")
			if gormTag != expected.Tag {
				t.Errorf("Field '%s' has gorm tag '%s', but expected '%s'", expected.Name, gormTag, expected.Tag)
			}
		})
	}
}