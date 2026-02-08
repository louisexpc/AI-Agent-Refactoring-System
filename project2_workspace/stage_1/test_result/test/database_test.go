package database

import (
	"bytes"
	"os"
	"os/exec"
	"strings"
	"testing"
)

// TestInitDB_FailureOnNoConnection validates that InitDB calls log.Fatal
// when a database connection cannot be established.
//
// As the function under test, InitDB, has hardcoded dependencies (gorm.Open, a specific DSN)
// and a terminating side effect (log.Fatal), it cannot be unit tested in isolation.
// This test uses a standard Go pattern for testing functions that call os.Exit:
// it re-runs the test executable in a subprocess with an environment variable set.
//
// The subprocess then calls InitDB, which is expected to fail and exit in the test
// environment where no database is running. The main test process then asserts
// that the subprocess exited with a non-zero status code and that the expected
// error message was printed to stderr.
//
// Note: Testing the success path of InitDB is not possible with the current
// implementation without provisioning a live database, as the DSN is hardcoded.
// To make the success path unit-testable, InitDB could be refactored to accept a
// gorm.Dialector or a DSN string as an argument, allowing a mock or an in-memory
// database (like SQLite) to be used in tests.
func TestInitDB_FailureOnNoConnection(t *testing.T) {
	// When this env var is set, we are in the subprocess.
	// We call the function that will exit, and then we're done.
	if os.Getenv("GO_TEST_SUBPROCESS") == "1" {
		InitDB()
		return
	}

	// We are in the main test process.
	// We execute a subprocess of the test itself, setting the env var.
	cmd := exec.Command(os.Args[0], "-test.run=^"+t.Name()+"$")
	cmd.Env = append(os.Environ(), "GO_TEST_SUBPROCESS=1")

	var stderr bytes.Buffer
	cmd.Stderr = &stderr

	// The command is expected to fail because log.Fatal calls os.Exit(1).
	err := cmd.Run()

	// Assert that the command's exit code was non-zero.
	// 'err' will be of type *exec.ExitError.
	if e, ok := err.(*exec.ExitError); !ok || e.Success() {
		t.Fatalf("Expected process to exit with a non-zero status code, but it ran with err: %v", err)
	}

	// Assert that the correct error message was logged to stderr.
	output := stderr.String()
	expectedLog := "Failed to connect to database:"
	if !strings.Contains(output, expectedLog) {
		t.Errorf("Expected stderr to contain %q, but got: %q", expectedLog, output)
	}
}

// Golden output is empty (`{}`), indicating no specific return values to compare.
// The test above verifies the behavioral side-effect (logging and fatal exit on
// connection failure), which is the only scenario testable in an isolated
// environment for the given code.