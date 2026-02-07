package com.ecommerce.controllers

import com.ecommerce.models.Product
import com.ecommerce.services.SearchService
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController

@RestController
@RequestMapping("/search")
class SearchController(private val searchService: SearchService) {

    @PostMapping
    fun searchProducts(@RequestBody query: Map<String, String>): ResponseEntity<List<Product>> {
        val products = searchService.searchProducts(query["query"] ?: "")
        return ResponseEntity.ok(products)
    }
}