# Makefile for the Expat golden characterization test

# Compiler and flags
CC := gcc
# Add -I. for local headers (expat.h)
# Add -DXML_DTD to ensure DTD-dependent features like the billion laughs test are compiled
CFLAGS_BASE := -Wall -Wextra -g -I. -DXML_DTD
LDFLAGS_BASE :=

# Coverage-specific flags
COVFLAGS := -fprofile-arcs -ftest-coverage

# Source files, object files, and the final executable name
TARGET := golden
SRCS := golden.c xmlparse.c
OBJS := $(SRCS:.c=.o)
DEPS := expat.h

# Default CFLAGS and LDFLAGS (can be overridden by specific targets)
CFLAGS := $(CFLAGS_BASE)
LDFLAGS := $(LDFLAGS_BASE)

# --- Targets ---

.PHONY: all clean coverage test_runner

# Default target: build the executable
all: $(TARGET)

# Alias for building the test executable
test_runner: all

# Rule to link the final executable
$(TARGET): $(OBJS)
	$(CC) $(LDFLAGS) -o $@ $^

# Generic rule to compile C source files into object files
# Depends on header files to ensure recompilation when headers change
%.o: %.c $(DEPS)
	$(CC) $(CFLAGS) -c $< -o $@

# Target to build with coverage, run, and generate a report
coverage:
	@echo "--- Building for coverage ---"
	@# Clean previous builds and invoke make again with coverage flags
	$(MAKE) clean
	$(MAKE) CFLAGS="$(CFLAGS_BASE) $(COVFLAGS)" LDFLAGS="$(LDFLAGS_BASE) $(COVFLAGS)" all
	@echo "--- Running program to generate coverage data (*.gcda) ---"
	./$(TARGET) > golden_output.json
	@echo "--- Generating coverage report (*.gcov) ---"
	gcov $(SRCS)
	@echo "Coverage report generated. See *.gcov files for details."

# Target to clean up all generated files
clean:
	@echo "--- Cleaning up build artifacts ---"
	rm -f $(TARGET) $(OBJS) *.gcno *.gcda *.gcov golden_output.json