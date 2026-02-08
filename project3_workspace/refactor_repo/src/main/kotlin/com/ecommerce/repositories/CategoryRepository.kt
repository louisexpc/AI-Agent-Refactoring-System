
package com.ecommerce.repositories

import com.ecommerce.models.Category
import org.springframework.data.mongodb.repository.MongoRepository

interface CategoryRepository : MongoRepository<Category, String>
