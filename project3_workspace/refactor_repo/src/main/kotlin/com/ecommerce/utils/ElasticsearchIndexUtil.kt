package com.ecommerce.utils

import com.ecommerce.models.Product
import com.ecommerce.services.ProductService
import org.elasticsearch.client.RequestOptions
import org.elasticsearch.client.RestHighLevelClient
import org.elasticsearch.client.indices.CreateIndexRequest
import org.elasticsearch.client.indices.GetIndexRequest
import org.springframework.boot.CommandLineRunner
import org.springframework.stereotype.Component
import org.elasticsearch.action.index.IndexRequest
import com.fasterxml.jackson.databind.ObjectMapper

@Component
class ElasticsearchIndexUtil(
    private val client: RestHighLevelClient,
    private val productService: ProductService,
    private val objectMapper: ObjectMapper
) : CommandLineRunner {

    override fun run(vararg args: String?) {
        val indexName = "products"
        val indexExists = client.indices().exists(GetIndexRequest(indexName), RequestOptions.DEFAULT)

        if (!indexExists) {
            client.indices().create(CreateIndexRequest(indexName), RequestOptions.DEFAULT)
            indexProducts()
        }
    }

    private fun indexProducts() {
        val products = productService.findAll()
        products.forEach {
            val indexRequest = IndexRequest("products")
                .id(it.id.toString())
                .source(objectMapper.writeValueAsString(it), org.elasticsearch.common.xcontent.XContentType.JSON)
            client.index(indexRequest, RequestOptions.DEFAULT)
        }
    }
}