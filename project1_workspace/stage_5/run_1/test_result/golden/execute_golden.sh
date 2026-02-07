#!/bin/bash
set -e

# Paths
REPO_DIR="/workspace/init/0a898b56491f42f59d9949e62c60cb80/snapshot/repo"
OUTPUT_DIR="/workspace/stage_5/run_1/test_result/golden"
SCRIPT_DIR="/workspace/stage_5/run_1/test_result/golden"
SCRIPT="/workspace/stage_5/run_1/test_result/golden/main_c_script.txt"

# Include flags
INCLUDE_FLAGS="-I"$REPO_DIR/.""

# 1. Compile golden script
cd "$SCRIPT_DIR"
gcc -Wall $INCLUDE_FLAGS -o golden_runner "$SCRIPT" *.c 2>/dev/null || \
gcc -Wall $INCLUDE_FLAGS -o golden_runner "$SCRIPT"

# 2. Execute
./golden_runner
