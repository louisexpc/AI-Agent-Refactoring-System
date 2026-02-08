# Stage 3, Run 2: Role Parser Bug Fix

This run will fix a critical bug in the `PrologState` initialization for external entities. The `include_level` was incorrectly initialized to `0` instead of `1`.

## 1. Bug Fix

- In `src/role_parser.rs`, modify the `PrologState::new_external_entity` function.
- Explicitly set `include_level: 1` in the `PrologState` struct to match the original C code's behavior.

## 2. Unit Tests

- Add a unit test to verify that `PrologState::new_external_entity` correctly initializes `include_level` to `1`.
