package models

import "time"

type Account struct {
	ID             uint   `gorm:"primaryKey"`
	UserID         uint   // Foreign key for User
	AssignedTo     uint   // Foreign key for User
	Name           string `gorm:"size:64;not null;default:''"`
	Access         string `gorm:"size:8;default:'Public'"`
	Website        string `gorm:"size:64"`
	TollFreePhone  string `gorm:"size:32"`
	Phone          string `gorm:"size:32"`
	Fax            string `gorm:"size:32"`
	DeletedAt      *time.Time
	CreatedAt      time.Time
	UpdatedAt      time.Time
	Email          string `gorm:"size:64"`
	BackgroundInfo string `gorm:"size:255"`
	Rating         int    `gorm:"not null;default:0"`
	Category       string `gorm:"size:32"`
}
