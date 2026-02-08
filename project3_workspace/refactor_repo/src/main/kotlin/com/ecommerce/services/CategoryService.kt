
package com.ecommerce.services

import com.ecommerce.models.Category
import com.ecommerce.repositories.CategoryRepository
import org.springframework.stereotype.Service

@Service
class CategoryService(private val categoryRepository: CategoryRepository) {

    fun createCategory(category: Category): Category {
        return categoryRepository.save(category)
    }

    fun getAllCategories(): List<Category> {
        return categoryRepository.findAll()
    }

    fun getCategoryById(id: String): Category? {
        return categoryRepository.findById(id).orElse(null)
    }

    fun updateCategory(id: String, category: Category): Category? {
        return if (categoryRepository.existsById(id)) {
            categoryRepository.save(category)
        } else {
            null
        }
    }

    fun deleteCategory(id: String) {
        categoryRepository.deleteById(id)
    }
}
