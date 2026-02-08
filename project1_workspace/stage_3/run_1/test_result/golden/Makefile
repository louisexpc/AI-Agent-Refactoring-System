# Compiler and flags
CC := gcc
CFLAGS := -Wall -Wextra -Wpedantic -I. -DXML_DTD=1
COVERAGE_FLAGS := -fprofile-arcs -ftest-coverage
LDFLAGS := $(COVERAGE_FLAGS)

# Source and Target
TARGET := test_runner
SRCS := test_xmlrole.c
DEPS := xmlrole.h

# Coverage tool and output files
GCOVR := gcovr
COVERAGE_REPORT_HTML := coverage.html
TEST_OUTPUT_JSON := output.json

.PHONY: all clean coverage golden_runner

all: $(TARGET)

golden_runner: $(TARGET)

$(TARGET): $(SRCS) $(DEPS)
	$(CC) $(CFLAGS) $(COVERAGE_FLAGS) $(SRCS) -o $(TARGET) $(LDFLAGS)

coverage: $(TARGET)
	./$(TARGET) > $(TEST_OUTPUT_JSON)
	@echo "--- GCOVR Text Report (xmlrole.c) ---"
	$(GCOVR) -r . --print-summary --filter "xmlrole.c"
	@echo "\n--- Generating HTML report: $(COVERAGE_REPORT_HTML) ---"
	$(GCOVR) -r . --html --html-details -o $(COVERAGE_REPORT_HTML) --filter "xmlrole.c"
	@echo "Done."

clean:
	rm -f $(TARGET) *.o *.gcda *.gcno *.gcov
	rm -f $(COVERAGE_REPORT_HTML) $(TEST_OUTPUT_JSON)