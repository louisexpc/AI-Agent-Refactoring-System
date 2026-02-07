
package com.ecommerce.repositories

import com.ecommerce.models.Product
import org.springframework.data.mongodb.repository.MongoRepository

interface ProductRepository : MongoRepository<Product, String>
