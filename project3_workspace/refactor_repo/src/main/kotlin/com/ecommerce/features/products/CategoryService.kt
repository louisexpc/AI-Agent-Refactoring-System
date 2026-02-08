package com.ecommerce.features.products

import com.ecommerce.features.products.models.Category
import com.ecommerce.features.products.models.CreateCategoryRequest
import com.ecommerce.features.products.models.UpdateCategoryRequest

class CategoryService(private val categoryRepository: CategoryRepository) {

    fun createCategory(request: CreateCategoryRequest): Category {
        return categoryRepository.createCategory(request)
    }

    fun getAllCategories(): List<Category> {
        return categoryRepository.findAllCategories()
    }

    fun getCategoryById(id: Int): Category? {
        return categoryRepository.findCategoryById(id)
    }

    fun updateCategory(id: Int, request: UpdateCategoryRequest): Category? {
        return categoryRepository.updateCategory(id, request)
    }

    fun deleteCategory(id: Int): Boolean {
        return categoryRepository.deleteCategory(id)
    }
}
