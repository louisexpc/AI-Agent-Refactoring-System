
package com.ecommerce.features.auth

import com.ecommerce.features.auth.models.User
import com.ecommerce.features.auth.models.UserProfileUpdateRequest

class UserService(private val userRepository: UserRepository) {

    suspend fun getUserProfile(userId: Int): User? {
        return userRepository.getUserById(userId)
    }

    suspend fun updateUserProfile(userId: Int, request: UserProfileUpdateRequest): User? {
        val user = userRepository.getUserById(userId)
        if (user != null) {
            val updatedUser = user.copy(
                firstName = request.firstName ?: user.firstName,
                lastName = request.lastName ?: user.lastName,
                mobile = request.mobile ?: user.mobile
            )
            return userRepository.updateUser(userId, updatedUser)
        }
        return null
    }

    suspend fun deleteUser(userId: Int) {
        userRepository.deleteUser(userId)
    }
}
