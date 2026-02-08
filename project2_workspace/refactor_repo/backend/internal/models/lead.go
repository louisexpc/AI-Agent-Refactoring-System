package models

import "time"

type Lead struct {
	ID             uint   `gorm:"primaryKey"`
	UserID         uint   // Foreign key for User
	CampaignID     uint   // Foreign key for Campaign
	AssignedTo     uint   // Foreign key for User
	FirstName      string `gorm:"size:64;not null;default:''"`
	LastName       string `gorm:"size:64;not null;default:''"`
	Access         string `gorm:"size:8;default:'Public'"`
	Title          string `gorm:"size:64"`
	Company        string `gorm:"size:64"`
	Source         string `gorm:"size:32"`
	Status         string `gorm:"size:32"`
	ReferredBy     string `gorm:"size:64"`
	Email          string `gorm:"size:64"`
	AltEmail       string `gorm:"size:64"`
	Phone          string `gorm:"size:32"`
	Mobile         string `gorm:"size:32"`
	Blog           string `gorm:"size:128"`
	Linkedin       string `gorm:"size:128"`
	Facebook       string `gorm:"size:128"`
	Twitter        string `gorm:"size:128"`
	Rating         int    `gorm:"not null;default:0"`
	DoNotCall      bool   `gorm:"not null;default:false"`
	DeletedAt      *time.Time
	CreatedAt      time.Time
	UpdatedAt      time.Time
	BackgroundInfo string `gorm:"size:255"`
}
