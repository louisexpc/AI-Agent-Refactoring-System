#!/bin/bash
set -e

# Paths
REPO_DIR="/workspace/init/3f34e3b507874b168e5505f4c160a301/snapshot/repo"
OUTPUT_DIR="/workspace/stage_1/test_result/golden"
GEMFILE="/workspace/stage_1/test_result/golden/Gemfile"
SCRIPT="/workspace/stage_1/test_result/golden/_workspace_init_3f34e3b507874b168e5505f4c160a301_snapshot_repo_db_schema_rb_script.txt"

# 1. Install dependencies
cd "$OUTPUT_DIR"
export BUNDLE_GEMFILE="$GEMFILE"
bundle install --path vendor/bundle

# 2. Set up RUBYLIB
export RUBYLIB=""$REPO_DIR//workspace/init/3f34e3b507874b168e5505f4c160a301/snapshot/repo/db"${RUBYLIB:+:$RUBYLIB}"

# 3. Execute golden script
cd "$REPO_DIR"
bundle exec ruby "$SCRIPT"
