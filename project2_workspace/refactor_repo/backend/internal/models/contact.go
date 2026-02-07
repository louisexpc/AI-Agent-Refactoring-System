package models

import "time"

type Contact struct {
	ID             uint   `gorm:"primaryKey"`
	UserID         uint   // Foreign key for User
	LeadID         uint   // Foreign key for Lead
	AssignedTo     uint   // Foreign key for User
	ReportsTo      uint   // Foreign key for User
	FirstName      string `gorm:"size:64;not null;default:''"`
	LastName       string `gorm:"size:64;not null;default:''"`
	Access         string `gorm:"size:8;default:'Public'"`
	Title          string `gorm:"size:64"`
	Department     string `gorm:"size:64"`
	Source         string `gorm:"size:32"`
	Email          string `gorm:"size:64"`
	AltEmail       string `gorm:"size:64"`
	Phone          string `gorm:"size:32"`
	Mobile         string `gorm:"size:32"`
	Fax            string `gorm:"size:32"`
	Blog           string `gorm:"size:128"`
	Linkedin       string `gorm:"size:128"`
	Facebook       string `gorm:"size:128"`
	Twitter        string `gorm:"size:128"`
	BornOn         *time.Time
	DoNotCall      bool `gorm:"not null;default:false"`
	DeletedAt      *time.Time
	CreatedAt      time.Time
	UpdatedAt      time.Time
	BackgroundInfo string `gorm:"size:255"`
}
