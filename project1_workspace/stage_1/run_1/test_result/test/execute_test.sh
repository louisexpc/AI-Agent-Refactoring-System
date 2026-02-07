#!/bin/bash
set -e

# Paths
REPO_DIR="/workspace/refactor_repo"
OUTPUT_DIR="/workspace/stage_1/run_1/test_result/test"

# 1. Change to repo directory
cd "$REPO_DIR"

# 2. Install cargo-tarpaulin if not present
if ! command -v cargo-tarpaulin &> /dev/null; then
    echo "Installing cargo-tarpaulin..."
    cargo install cargo-tarpaulin --locked || true
fi

# 3. Run tests with coverage
cargo tarpaulin --out Json --output-dir "$OUTPUT_DIR" -- --nocapture 2>/dev/null || \
cargo test -- --nocapture
