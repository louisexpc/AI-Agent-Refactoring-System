package main

import (
	"backend/internal/database"
	"fmt"
)

func main() {
	database.InitDB()
	fmt.Println("Hello, World!")
}
