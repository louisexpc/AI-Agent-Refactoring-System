package models

import (
	"math/big"
	"time"
)

type Opportunity struct {
	ID             uint   `gorm:"primaryKey"`
	UserID         uint   // Foreign key for User
	CampaignID     uint   // Foreign key for Campaign
	AssignedTo     uint   // Foreign key for User
	Name           string `gorm:"size:64;not null;default:''"`
	Access         string `gorm:"size:8;default:'Public'"`
	Source         string `gorm:"size:32"`
	Stage          string `gorm:"size:32"`
	Probability    int
	Amount         *big.Float `gorm:"type:decimal(12,2)"`
	Discount       *big.Float `gorm:"type:decimal(12,2)"`
	ClosesOn       *time.Time
	DeletedAt      *time.Time
	CreatedAt      time.Time
	UpdatedAt      time.Time
	BackgroundInfo string `gorm:"size:255"`
}
