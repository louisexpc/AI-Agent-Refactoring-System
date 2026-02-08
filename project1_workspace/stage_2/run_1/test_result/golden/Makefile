# Makefile for C Characterization Test Runner

# Compiler and flags
CC = gcc
# Use -std=c99 for C99 features like mixed declarations and code
# -I. to find local headers like xmltok.h
CFLAGS = -g -Wall -Wextra -pedantic -std=c99 -I.
LDFLAGS =
SRCS = test_runner.c xmltok.c
OBJS = $(SRCS:.c=.o)
TARGET = test_runner

# Coverage specific flags and variables
COVERAGE_CFLAGS = -fprofile-arcs -ftest-coverage
COVERAGE_TARGET = test_runner_cov

# Test output files
GOLDEN_FILE = golden.json
OUTPUT_FILE = output.json

.PHONY: all clean test golden_runner update_golden coverage

# Default target: build the main executable
all: $(TARGET)

# Rule to link the main executable
$(TARGET): $(OBJS)
	$(CC) $(LDFLAGS) -o $@ $^

# Generic rule to compile C source files into object files
%.o: %.c
	$(CC) $(CFLAGS) -c -o $@ $<

# Target to run the characterization test.
# It compares the program's output against a 'golden' reference file.
# If the golden file doesn't exist, it creates it from the first run.
golden_runner: test
test: $(TARGET)
	@./$(TARGET) > $(OUTPUT_FILE)
	@if [ ! -f $(GOLDEN_FILE) ]; then \
		echo "Golden file '$(GOLDEN_FILE)' not found. Creating it from current output."; \
		mv $(OUTPUT_FILE) $(GOLDEN_FILE); \
		echo "Please review and commit the new golden file."; \
	else \
		diff -u $(GOLDEN_FILE) $(OUTPUT_FILE); \
		if [ $$? -eq 0 ]; then \
			echo "✅ Test PASSED: Output matches $(GOLDEN_FILE)."; \
			rm $(OUTPUT_FILE); \
		else \
			echo "❌ Test FAILED: Output differs from $(GOLDEN_FILE)."; \
			echo "   To update the golden file, run: make update_golden"; \
			exit 1; \
		fi \
	fi

# Target to explicitly update the golden file with the current output
update_golden: $(TARGET)
	@./$(TARGET) > $(GOLDEN_FILE)
	@echo "✅ Golden file '$(GOLDEN_FILE)' has been updated."

# Target to build and run for code coverage analysis
coverage:
	@# Clean previous coverage data and executable
	@$(MAKE) clean > /dev/null
	@echo "Building with coverage flags..."
	@# Compile all sources into a single executable with coverage flags
	$(CC) $(CFLAGS) $(COVERAGE_CFLAGS) -o $(TARGET) $(SRCS) $(LDFLAGS) $(COVERAGE_CFLAGS)
	@echo "Running tests to generate coverage data..."
	@./$(TARGET) > /dev/null
	@echo "Generating coverage report with gcov..."
	@gcov -b -c $(SRCS)
	@echo "Coverage report files (*.gcov) generated."

# Target to clean up build artifacts
clean:
	rm -f $(TARGET) $(OBJS) $(OUTPUT_FILE)
	rm -f *.gcno *.gcda *.gcov