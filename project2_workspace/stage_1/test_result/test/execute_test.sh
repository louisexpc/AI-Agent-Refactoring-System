#!/bin/bash
set -e

# Copy test file to source directory (Go requires test to be with source)
cp /workspace/stage_1/test_result/test/database_test.go /workspace/refactor_repo/backend/internal/database/database_test.go
cd /workspace/refactor_repo/backend/internal/database
go test -v -cover -coverprofile=coverage.out
