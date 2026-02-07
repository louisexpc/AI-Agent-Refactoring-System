# Compiler and tools
CC = gcc
GCOV = gcov

# Executable name
TARGET = test_runner

# Source files
# test_runner.c is the main compilation unit.
SRCS = test_runner.c
# source.c is a dependency because it's #included. A change in it should trigger a rebuild.
DEPS = source.c

# Compiler flags
# -I. is to search for headers in the current directory.
# -g adds debug information.
# -Wall and -Wextra enable most compiler warnings.
CFLAGS_BASE = -Wall -Wextra -g -I.
CFLAGS = $(CFLAGS_BASE)

# Linker flags
LDFLAGS =

# Coverage flags
GCOV_FLAGS = -fprofile-arcs -ftest-coverage

# Phony targets do not represent files.
.PHONY: all clean run coverage golden_runner

# The 'all' target is the default, executed when you just run 'make'.
all: $(TARGET)

# Rule to build the main executable.
# $@ is the target name (test_runner).
# $< is the first prerequisite (test_runner.c).
# Using $(SRCS) is safer if there were multiple source files to compile.
$(TARGET): $(SRCS) $(DEPS)
	$(CC) $(CFLAGS) -o $@ $(SRCS) $(LDFLAGS)

# The user requested a 'golden_runner' target. We make it an alias for the default build.
golden_runner: $(TARGET)

# Target to run the executable.
run: $(TARGET)
	./$(TARGET)

# Target to generate a code coverage report.
# 1. Adds coverage flags to CFLAGS and LDFLAGS for this target only.
# 2. Cleans previous builds and reports to ensure a fresh run.
# 3. Builds the instrumented executable.
# 4. Runs the executable to generate profile data (*.gcda files).
# 5. Runs gcov to generate human-readable reports (*.gcov files).
coverage: CFLAGS += $(GCOV_FLAGS)
coverage: LDFLAGS += $(GCOV_FLAGS)
coverage: clean $(TARGET)
	@echo "Running instrumented executable to generate profile data..."
	./$(TARGET) > /dev/null
	@echo "Generating coverage report for $(SRCS) and $(DEPS)..."
	$(GCOV) -b -c $(SRCS) $(DEPS)
	@echo "Coverage report created in *.gcov files."

# Target to clean up the directory from build artifacts and reports.
clean:
	@echo "Cleaning up build artifacts and coverage data..."
	rm -f $(TARGET) *.o *.gcda *.gcno *.gcov