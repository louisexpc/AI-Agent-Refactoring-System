# Makefile for the Expat xmlparse characterization test

# Compiler and flags
CC = gcc
# CFLAGS:
# -Wall -Wextra: Enable common warnings for better code quality.
# -g: Include debugging information.
# -I.: Add the current directory to the include path for local headers (e.g., expat.h, internal.h).
# -fprofile-arcs -ftest-coverage: Instrument code for coverage analysis with gcov.
CFLAGS = -Wall -Wextra -g -I. -fprofile-arcs -ftest-coverage

# Linker flags
# -fprofile-arcs: Needed during linking for coverage support.
LDFLAGS = -fprofile-arcs

# Libraries
# -lm: Link against the math library for functions in math.h.
LIBS = -lm

# Source files
# Assumes xmlparse.c (the module under test) is present in the same directory.
SRCS = golden.c xmlparse.c

# Object files (derived from source files)
OBJS = $(SRCS:.c=.o)

# Target executable name
TARGET = golden_runner

.PHONY: all clean coverage

# Default target: build the executable
all: $(TARGET)

# Rule to link the object files into the final executable
$(TARGET): $(OBJS)
	$(CC) $(LDFLAGS) -o $@ $^ $(LIBS)

# Explicitly define the runner target as requested
golden_runner: $(TARGET)

# Rule to generate a coverage report
# 1. Ensure the executable is built and up-to-date.
# 2. Run the executable to generate profiling data (*.gcda files).
#    Output is redirected to /dev/null as it's not needed for the report.
# 3. Run gcov on the source files to create human-readable coverage reports (*.gcov).
coverage: $(TARGET)
	./$(TARGET) > /dev/null
	gcov $(SRCS)

# Rule to clean up generated files
clean:
	rm -f $(TARGET) $(OBJS) *.gcno *.gcda *.gcov