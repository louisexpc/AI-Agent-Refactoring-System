package com.ecommerce.controllers

import com.ecommerce.models.User
import com.ecommerce.services.UserService
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.*

@RestController
@RequestMapping("/admin")
class AdminController(private val userService: UserService) {

    @PostMapping("/login")
    fun adminLogin(@RequestBody user: User): ResponseEntity<User> {
        val loggedInUser = userService.login(user.email, user.password)
        return if (loggedInUser != null && loggedInUser.role == "admin") {
            ResponseEntity.ok(loggedInUser)
        } else {
            ResponseEntity.status(401).build()
        }
    }

    @PostMapping("/logout")
    fun adminLogout(): ResponseEntity<Void> {
        return ResponseEntity.ok().build()
    }

    @GetMapping("/users")
    fun getAllUsers(): ResponseEntity<List<User>> {
        return ResponseEntity.ok(userService.findAll())
    }

    @GetMapping("/users/{id}")
    fun getUserById(@PathVariable id: Long): ResponseEntity<User> {
        val user = userService.findById(id)
        return if (user != null) {
            ResponseEntity.ok(user)
        } else {
            ResponseEntity.notFound().build()
        }
    }

    @DeleteMapping("/users/{id}")
    fun deleteUser(@PathVariable id: Long): ResponseEntity<Void> {
        userService.deleteById(id)
        return ResponseEntity.ok().build()
    }

    @PutMapping("/users/{id}")
    fun updateUser(@PathVariable id: Long, @RequestBody user: User): ResponseEntity<User> {
        val updatedUser = userService.updateUser(id, user)
        return if (updatedUser != null) {
            ResponseEntity.ok(updatedUser)
        } else {
            ResponseEntity.notFound().build()
        }
    }

    @PutMapping("/users/block/{id}")
    fun blockUser(@PathVariable id: Long): ResponseEntity<Void> {
        userService.blockUser(id)
        return ResponseEntity.ok().build()
    }

    @PutMapping("/users/unblock/{id}")
    fun unblockUser(@PathVariable id: Long): ResponseEntity<Void> {
        userService.unblockUser(id)
        return ResponseEntity.ok().build()
    }
}