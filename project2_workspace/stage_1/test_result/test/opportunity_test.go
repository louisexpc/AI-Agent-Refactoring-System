package models

import (
	"math/big"
	"testing"
	"time"
)

// TestOpportunityStruct verifies that the Opportunity struct can be instantiated
// and its fields can be set and retrieved correctly. As the source file only
// contains a struct definition and no exported functions or methods, there is no
// specific "golden output" to test against. This test serves as a basic
// sanity check of the data model's structure.
func TestOpportunityStruct(t *testing.T) {
	// 1. Setup test data
	fixedTime := time.Date(2023, 10, 26, 12, 0, 0, 0, time.UTC)
	closesOn := fixedTime.Add(30 * 24 * time.Hour)
	deletedAt := fixedTime.Add(60 * 24 * time.Hour)
	amount := new(big.Float).SetFloat64(5000.75)
	discount := new(big.Float).SetFloat64(500.25)

	opp := Opportunity{
		ID:             1,
		UserID:         2,
		CampaignID:     3,
		AssignedTo:     4,
		Name:           "Big Deal",
		Access:         "Public",
		Source:         "Referral",
		Stage:          "Prospecting",
		Probability:    20,
		Amount:         amount,
		Discount:       discount,
		ClosesOn:       &closesOn,
		DeletedAt:      &deletedAt,
		CreatedAt:      fixedTime,
		UpdatedAt:      fixedTime,
		BackgroundInfo: "Initial contact made.",
	}

	// 2. Assertions
	if opp.ID != 1 {
		t.Errorf("expected ID to be 1, got %d", opp.ID)
	}
	if opp.UserID != 2 {
		t.Errorf("expected UserID to be 2, got %d", opp.UserID)
	}
	if opp.CampaignID != 3 {
		t.Errorf("expected CampaignID to be 3, got %d", opp.CampaignID)
	}
	if opp.AssignedTo != 4 {
		t.Errorf("expected AssignedTo to be 4, got %d", opp.AssignedTo)
	}
	if opp.Name != "Big Deal" {
		t.Errorf("expected Name to be 'Big Deal', got '%s'", opp.Name)
	}
	if opp.Access != "Public" {
		t.Errorf("expected Access to be 'Public', got '%s'", opp.Access)
	}
	if opp.Source != "Referral" {
		t.Errorf("expected Source to be 'Referral', got '%s'", opp.Source)
	}
	if opp.Stage != "Prospecting" {
		t.Errorf("expected Stage to be 'Prospecting', got '%s'", opp.Stage)
	}
	if opp.Probability != 20 {
		t.Errorf("expected Probability to be 20, got %d", opp.Probability)
	}

	// Compare big.Float values
	if opp.Amount.Cmp(amount) != 0 {
		t.Errorf("expected Amount to be %v, got %v", amount, opp.Amount)
	}
	if opp.Discount.Cmp(discount) != 0 {
		t.Errorf("expected Discount to be %v, got %v", discount, opp.Discount)
	}

	// Compare time.Time pointer values
	if opp.ClosesOn == nil || !opp.ClosesOn.Equal(closesOn) {
		t.Errorf("expected ClosesOn to be %v, got %v", closesOn, opp.ClosesOn)
	}
	if opp.DeletedAt == nil || !opp.DeletedAt.Equal(deletedAt) {
		t.Errorf("expected DeletedAt to be %v, got %v", deletedAt, opp.DeletedAt)
	}

	// Compare time.Time values
	if !opp.CreatedAt.Equal(fixedTime) {
		t.Errorf("expected CreatedAt to be %v, got %v", fixedTime, opp.CreatedAt)
	}
	if !opp.UpdatedAt.Equal(fixedTime) {
		t.Errorf("expected UpdatedAt to be %v, got %v", fixedTime, opp.UpdatedAt)
	}

	if opp.BackgroundInfo != "Initial contact made." {
		t.Errorf("expected BackgroundInfo to be 'Initial contact made.', got '%s'", opp.BackgroundInfo)
	}
}

// TestOpportunityStructZeroValues verifies the behavior of an Opportunity struct
// when initialized without values. It checks that the fields hold their expected
// Go zero-values. The `gorm:"default:..."` tags are interpreted by the GORM
// library during database operations and do not affect Go's native struct
// initialization.
func TestOpportunityStructZeroValues(t *testing.T) {
	opp := Opportunity{}

	if opp.ID != 0 {
		t.Errorf("expected default ID to be 0, got %d", opp.ID)
	}
	if opp.Name != "" {
		t.Errorf("expected default Name to be '', got '%s'", opp.Name)
	}
	if opp.Access != "" {
		t.Errorf("expected default Access to be '', got '%s'", opp.Access)
	}
	if opp.Probability != 0 {
		t.Errorf("expected default Probability to be 0, got %d", opp.Probability)
	}
	if opp.Amount != nil {
		t.Errorf("expected default Amount to be nil, got %v", opp.Amount)
	}
	if opp.Discount != nil {
		t.Errorf("expected default Discount to be nil, got %v", opp.Discount)
	}
	if opp.ClosesOn != nil {
		t.Errorf("expected default ClosesOn to be nil, got %v", opp.ClosesOn)
	}
	if opp.DeletedAt != nil {
		t.Errorf("expected default DeletedAt to be nil, got %v", opp.DeletedAt)
	}
	if !opp.CreatedAt.IsZero() {
		t.Errorf("expected default CreatedAt to be the zero time, got %v", opp.CreatedAt)
	}
	if !opp.UpdatedAt.IsZero() {
		t.Errorf("expected default UpdatedAt to be the zero time, got %v", opp.UpdatedAt)
	}
	if opp.BackgroundInfo != "" {
		t.Errorf("expected default BackgroundInfo to be '', got %s", opp.BackgroundInfo)
	}
}