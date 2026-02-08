package com.ecommerce.features.products

import com.ecommerce.features.products.models.CreateProductRequest
import com.ecommerce.features.products.models.Product
import com.ecommerce.features.products.models.UpdateProductRequest

class ProductService(private val productRepository: ProductRepository) {

    fun createProduct(request: CreateProductRequest): Product {
        return productRepository.createProduct(request)
    }

    fun getAllProducts(): List<Product> {
        return productRepository.findAllProducts()
    }

    fun getProductById(id: Int): Product? {
        return productRepository.findProductById(id)
    }

    fun updateProduct(id: Int, request: UpdateProductRequest): Product? {
        return productRepository.updateProduct(id, request)
    }

    fun deleteProduct(id: Int): Boolean {
        return productRepository.deleteProduct(id)
    }
}
