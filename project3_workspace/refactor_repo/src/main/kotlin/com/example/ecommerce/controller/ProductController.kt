package com.example.ecommerce.controller

import com.example.ecommerce.model.Product
import com.example.ecommerce.repository.ProductRepository
import org.springframework.web.bind.annotation.*

@RestController
@RequestMapping("/products")
class ProductController(private val productRepository: ProductRepository) {

    @GetMapping
    fun getAllProducts(): List<Product> = productRepository.findAll()

    @GetMapping("/{id}")
    fun getProductById(@PathVariable id: Long): Product = productRepository.findById(id).orElseThrow { RuntimeException("Product not found") }

    @PostMapping
    fun createProduct(@RequestBody product: Product): Product = productRepository.save(product)

    @PutMapping("/{id}")
    fun updateProduct(@PathVariable id: Long, @RequestBody newProduct: Product): Product {
        val oldProduct = productRepository.findById(id).orElseThrow { RuntimeException("Product not found") }
        oldProduct.name = newProduct.name
        oldProduct.description = newProduct.description
        oldProduct.price = newProduct.price
        return productRepository.save(oldProduct)
    }

    @DeleteMapping("/{id}")
    fun deleteProduct(@PathVariable id: Long) = productRepository.deleteById(id)
}
