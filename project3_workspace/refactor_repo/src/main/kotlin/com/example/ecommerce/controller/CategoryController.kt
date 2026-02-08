package com.example.ecommerce.controller

import com.example.ecommerce.model.Category
import com.example.ecommerce.repository.CategoryRepository
import org.springframework.web.bind.annotation.*

@RestController
@RequestMapping("/categories")
class CategoryController(private val categoryRepository: CategoryRepository) {

    @GetMapping
    fun getAllCategories(): List<Category> = categoryRepository.findAll()

    @GetMapping("/{id}")
    fun getCategoryById(@PathVariable id: Long): Category = categoryRepository.findById(id).orElseThrow { RuntimeException("Category not found") }

    @PostMapping
    fun createCategory(@RequestBody category: Category): Category = categoryRepository.save(category)

    @PutMapping("/{id}")
    fun updateCategory(@PathVariable id: Long, @RequestBody newCategory: Category): Category {
        val oldCategory = categoryRepository.findById(id).orElseThrow { RuntimeException("Category not found") }
        oldCategory.name = newCategory.name
        return categoryRepository.save(oldCategory)
    }

    @DeleteMapping("/{id}")
    fun deleteCategory(@PathVariable id: Long) = categoryRepository.deleteById(id)
}
