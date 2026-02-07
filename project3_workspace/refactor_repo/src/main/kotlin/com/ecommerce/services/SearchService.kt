package com.ecommerce.services

import com.ecommerce.models.Product
import org.elasticsearch.client.RestHighLevelClient
import org.springframework.stereotype.Service
import org.elasticsearch.action.search.SearchRequest
import org.elasticsearch.index.query.QueryBuilders
import org.elasticsearch.search.builder.SearchSourceBuilder
import com.fasterxml.jackson.databind.ObjectMapper

@Service
class SearchService(private val client: RestHighLevelClient, private val objectMapper: ObjectMapper) {

    fun searchProducts(query: String): List<Product> {
        val searchRequest = SearchRequest("products")
        val searchSourceBuilder = SearchSourceBuilder()
        searchSourceBuilder.query(QueryBuilders.matchQuery("name", query))
        searchRequest.source(searchSourceBuilder)

        val searchResponse = client.search(searchRequest, org.elasticsearch.client.RequestOptions.DEFAULT)

        return searchResponse.hits.hits.map {
            objectMapper.readValue(it.sourceAsString, Product::class.java)
        }
    }
}