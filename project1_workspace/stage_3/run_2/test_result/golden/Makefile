#
# Makefile for xmlrole test harness
#

# Compiler and flags
CC = gcc
# CFLAGS for general builds. -DXML_DTD is included as the test harness uses it.
CFLAGS = -g -Wall -Wextra -DXML_DTD
# Coverage-specific flags
COV_FLAGS = -fprofile-arcs -ftest-coverage
LDFLAGS =
LIBS =

# Executable name
TARGET = golden_runner

# Source file. Since xmlrole.c is included directly by the test harness,
# we only need to compile the harness itself.
# IMPORTANT: This assumes the provided code is saved as 'test_xmlrole.c'
# and 'xmlrole.c' exists in the same directory.
SRCS = test_xmlrole.c

# Phony targets are not files.
.PHONY: all clean golden_runner coverage

# The default target: build the executable.
all: $(TARGET)

# Rule to link the final executable.
$(TARGET): $(SRCS)
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS) $(LIBS)

# A target to run the tests, redirecting output.
# The user prompt requested a 'golden_runner' target. This runs the executable.
golden_runner: $(TARGET)
	./$(TARGET) > output.json
	@echo "Test run complete. Output saved to output.json"

# Target to build with coverage, run tests, and generate a report.
coverage:
	# 1. Compile with coverage flags.
	$(CC) $(CFLAGS) $(COV_FLAGS) -o $(TARGET) $(SRCS) $(LDFLAGS) $(LIBS)
	# 2. Clean old profiling data if it exists.
	-rm -f *.gcda
	# 3. Run the test executable to generate new .gcda profile data.
	./$(TARGET) > /dev/null
	# 4. Run gcov to generate a text report. It will create xmlrole.c.gcov.
	gcov $(SRCS)
	@echo "Coverage report generated. See *.gcov files."

# Target to clean the directory of build artifacts.
clean:
	rm -f $(TARGET) *.o *.gcno *.gcda *.gcov output.json