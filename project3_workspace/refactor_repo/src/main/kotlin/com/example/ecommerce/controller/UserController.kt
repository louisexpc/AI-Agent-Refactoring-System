package com.example.ecommerce.controller

import com.example.ecommerce.model.User
import com.example.ecommerce.repository.UserRepository
import org.springframework.web.bind.annotation.*

@RestController
@RequestMapping("/users")
class UserController(private val userRepository: UserRepository) {

    @GetMapping
    fun getAllUsers(): List<User> = userRepository.findAll()

    @GetMapping("/{id}")
    fun getUserById(@PathVariable id: Long): User = userRepository.findById(id).orElseThrow { RuntimeException("User not found") }

    @PostMapping
    fun createUser(@RequestBody user: User): User = userRepository.save(user)

    @PutMapping("/{id}")
    fun updateUser(@PathVariable id: Long, @RequestBody newUser: User): User {
        val oldUser = userRepository.findById(id).orElseThrow { RuntimeException("User not found") }
        oldUser.name = newUser.name
        oldUser.email = newUser.email
        return userRepository.save(oldUser)
    }

    @DeleteMapping("/{id}")
    fun deleteUser(@PathVariable id: Long) = userRepository.deleteById(id)
}
