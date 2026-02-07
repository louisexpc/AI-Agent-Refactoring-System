package models

import (
	"math/big"
	"time"
)

type Campaign struct {
	ID                uint   `gorm:"primaryKey"`
	UserID            uint   // Foreign key for User
	AssignedTo        uint   // Foreign key for User
	Name              string `gorm:"size:64;not null;default:''"`
	Access            string `gorm:"size:8;default:'Public'"`
	Status            string `gorm:"size:64"`
	Budget            *big.Float `gorm:"type:decimal(12,2)"`
	TargetLeads       int
	TargetConversion  float64
	TargetRevenue     *big.Float `gorm:"type:decimal(12,2)"`
	LeadsCount        int
	OpportunitiesCount int
	Revenue           *big.Float `gorm:"type:decimal(12,2)"`
	StartsOn          *time.Time
	EndsOn            *time.Time
	Objectives        string `gorm:"type:text"`
	DeletedAt         *time.Time
	CreatedAt         time.Time
	UpdatedAt         time.Time
	BackgroundInfo    string `gorm:"size:255"`
}
