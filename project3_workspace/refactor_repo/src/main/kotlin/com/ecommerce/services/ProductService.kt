
package com.ecommerce.services

import com.ecommerce.models.Product
import com.ecommerce.repositories.ProductRepository
import org.springframework.stereotype.Service

@Service
class ProductService(private val productRepository: ProductRepository) {

    fun createProduct(product: Product): Product {
        return productRepository.save(product)
    }

    fun getAllProducts(): List<Product> {
        return productRepository.findAll()
    }

    fun getProductById(id: String): Product? {
        return productRepository.findById(id).orElse(null)
    }

    fun updateProduct(id: String, product: Product): Product? {
        return if (productRepository.existsById(id)) {
            productRepository.save(product)
        } else {
            null
        }
    }

    fun deleteProduct(id: String) {
        productRepository.deleteById(id)
    }
}
