package models

import "time"

type User struct {
	ID                   uint   `gorm:"primaryKey"`
	Username             string `gorm:"size:32;not null;default:''"`
	Email                string `gorm:"size:254;not null;default:''"`
	FirstName            string `gorm:"size:32"`
	LastName             string `gorm:"size:32"`
	Title                string `gorm:"size:64"`
	Company              string `gorm:"size:64"`
	AltEmail             string `gorm:"size:64"`
	Phone                string `gorm:"size:32"`
	Mobile               string `gorm:"size:32"`
	Aim                  string `gorm:"size:32"`
	Yahoo                string `gorm:"size:32"`
	Google               string `gorm:"size:32"`
	EncryptedPassword    string `gorm:"size:255;not null;default:''"`
	PasswordSalt         string `gorm:"size:255;not null;default:''"`
	LastSignInAt         *time.Time
	CurrentSignInAt      *time.Time
	LastSignInIP         string `gorm:"size:255"`
	CurrentSignInIP      string `gorm:"size:255"`
	SignInCount          int    `gorm:"not null;default:0"`
	DeletedAt            *time.Time
	CreatedAt            time.Time
	UpdatedAt            time.Time
	Admin                bool   `gorm:"not null;default:false"`
	SuspendedAt          *time.Time
	UnconfirmedEmail     string `gorm:"size:254;not null;default:''"`
	ResetPasswordToken   string `gorm:"size:255"`
	ResetPasswordSentAt  *time.Time
	RememberToken        string `gorm:"size:255"`
	RememberCreatedAt    *time.Time
	AuthenticationToken  string `gorm:"size:255"`
	ConfirmationToken    string `gorm:"size:255"`
	ConfirmedAt          *time.Time
	ConfirmationSentAt   *time.Time
}
