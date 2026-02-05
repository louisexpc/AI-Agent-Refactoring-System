package telemetry

import (
	"errors"
	"math/rand"
	"strings"
	"testing"
)

// --- Mocks and Test Helpers ---

// mockTelemetryClient provides a controllable implementation of the Client interface
// for testing TelemetryDiagnostics. It allows setting connection success behavior
// and tracks method calls.
type mockTelemetryClient struct {
	onlineStatus            bool
	connectSuccessOnAttempt int // Which attempt should succeed (1-based). 0 or less means always fail.
	connectAttempts         int
	disconnectCalls         int
	sendCalls               int
	lastSentMessage         string
	receiveCalls            int
	receiveStub             string
}

func (m *mockTelemetryClient) Connect(connectionString string) {
	m.connectAttempts++
	if m.connectSuccessOnAttempt > 0 && m.connectAttempts >= m.connectSuccessOnAttempt {
		m.onlineStatus = true
	} else {
		m.onlineStatus = false
	}
}

func (m *mockTelemetryClient) Disconnect() {
	m.disconnectCalls++
	m.onlineStatus = false
}

func (m *mockTelemetryClient) Send(message string) {
	m.sendCalls++
	m.lastSentMessage = message
}

func (m *mockTelemetryClient) Receive() string {
	m.receiveCalls++
	return m.receiveStub
}

func (m *mockTelemetryClient) OnlineStatus() bool {
	return m.onlineStatus
}

// newTestClient creates a TelemetryClient with a deterministically seeded
// random number generator for predictable test outcomes. This is used for testing
// the concrete TelemetryClient implementation.
func newTestClient(seed int64) *TelemetryClient {
	// We create a new client, but override the random generator with a seeded one.
	return &TelemetryClient{
		rand: rand.New(rand.NewSource(seed)),
	}
}

// --- Behavioral Validation Tests ---

// TestTelemetryClientBehavior validates the concrete TelemetryClient's logic.
func TestTelemetryClientBehavior(t *testing.T) {
	// Corresponds to golden output: TelemetryClient_init_initialState
	t.Run("Init_InitialState", func(t *testing.T) {
		client := NewTelemetryClient()

		if client.OnlineStatus() {
			t.Errorf("Initial onlineStatus: got %v, want %v", client.OnlineStatus(), false)
		}
		if client.diagnosticMessageJustSent {
			t.Errorf("Initial diagnosticMessageJustSent: got %v, want %v", client.diagnosticMessageJustSent, false)
		}
	})

	// Corresponds to golden output: TelemetryClient_connect_withEmptyConnectionString, TelemetryClient_connect_withNullConnectionString
	t.Run("Connect_PanicsOnEmptyString", func(t *testing.T) {
		defer func() {
			r := recover()
			if r == nil {
				t.Error("Expected panic when connecting with empty string, but did not get one")
			} else if r != "telemetryServerConnectionString is null or empty" {
				t.Errorf("Unexpected panic message: got %q, want %q", r, "telemetryServerConnectionString is null or empty")
			}
		}()
		client := NewTelemetryClient()
		client.Connect("")
	})

	// Corresponds to golden output: TelemetryClient_connect_onSuccess
	t.Run("Connect_Success", func(t *testing.T) {
		// Seed 1 gives rand.Intn(10) -> 1, which is < 2, causing success.
		client := newTestClient(1)
		client.Connect(DiagnosticChannelConnectionString)
		if !client.OnlineStatus() {
			t.Errorf("online_status: got %v, want %v", client.OnlineStatus(), true)
		}
	})

	// Corresponds to golden output: TelemetryClient_connect_onFailure
	t.Run("Connect_Failure", func(t *testing.T) {
		// Seed 2 gives rand.Intn(10) -> 7, which is not < 2, causing failure.
		client := newTestClient(2)
		client.Connect(DiagnosticChannelConnectionString)
		if client.OnlineStatus() {
			t.Errorf("online_status: got %v, want %v", client.OnlineStatus(), false)
		}
	})

	// Corresponds to golden output: TelemetryClient_disconnect_fromOnlineState
	t.Run("Disconnect_WhenOnline", func(t *testing.T) {
		client := newTestClient(1) // Connects successfully
		client.Connect(DiagnosticChannelConnectionString)
		if !client.OnlineStatus() {
			t.Fatal("Pre-condition failed: client could not connect")
		}

		client.Disconnect()

		if client.OnlineStatus() {
			t.Errorf("post_disconnect_status: got %v, want %v", client.OnlineStatus(), false)
		}
	})

	// Corresponds to golden output: TelemetryClient_disconnect_fromOfflineState
	t.Run("Disconnect_WhenOffline", func(t *testing.T) {
		client := newTestClient(2) // Fails to connect
		client.Connect(DiagnosticChannelConnectionString)
		if client.OnlineStatus() {
			t.Fatal("Pre-condition failed: client should be offline")
		}

		client.Disconnect()

		if client.OnlineStatus() {
			t.Errorf("post_disconnect_status: got %v, want %v", client.OnlineStatus(), false)
		}
	})

	// Corresponds to golden output: TelemetryClient_send_withEmptyMessage, TelemetryClient_send_withNullMessage
	t.Run("Send_PanicsOnEmptyMessage", func(t *testing.T) {
		defer func() {
			r := recover()
			if r == nil {
				t.Error("Expected panic when sending empty message, but did not get one")
			} else if r != "message is null or empty" {
				t.Errorf("Unexpected panic message: got %q, want %q", r, "message is null or empty")
			}
		}()
		client := NewTelemetryClient()
		client.Send("")
	})

	// Corresponds to golden output: TelemetryClient_send_diagnosticMessage
	t.Run("Send_DiagnosticMessage", func(t *testing.T) {
		client := NewTelemetryClient()
		client.Send(DiagnosticMessage)
		if !client.diagnosticMessageJustSent {
			t.Errorf("internal_diagnosticMessageJustSent: got %v, want %v", client.diagnosticMessageJustSent, true)
		}
	})

	// Corresponds to golden output: TelemetryClient_send_regularMessage
	t.Run("Send_NonDiagnosticMessage", func(t *testing.T) {
		client := NewTelemetryClient()
		client.diagnosticMessageJustSent = true // Set pre-condition
		client.Send("hello world")
		if client.diagnosticMessageJustSent {
			t.Errorf("internal_diagnosticMessageJustSent: got %v, want %v", client.diagnosticMessageJustSent, false)
		}
	})

	// Corresponds to golden output: TelemetryClient_receive_afterDiagnosticSend
	t.Run("Receive_AfterDiagnosticSend", func(t *testing.T) {
		client := NewTelemetryClient()
		client.diagnosticMessageJustSent = true // Set pre-condition

		// This expected message comes directly from the refactored Go source.
		// It validates the new implementation's behavior exactly.
		expectedMessage := `LAST TX rate................ 100 MBPS
HIGHEST TX rate............. 100 MBPS
LAST RX rate................ 100 MBPS
HIGHEST RX rate............. 100 MBPS
BIT RATE.................... 100000000
WORD LEN.................... 16
WORD/FRAME.................. 511
BITS/FRAME.................. 8192
MODULATION TYPE............. PCM/FM
TX Digital Los.............. 0.75
RX Digital Los.............. 0.10
BEP Test.................... -5
Local Rtrn Count............ 00
Remote Rtrn Count........... 00`

		message := client.Receive()

		if message != expectedMessage {
			t.Errorf("message mismatch.\nGot:\n%s\nWant:\n%s", message, expectedMessage)
		}

		if client.diagnosticMessageJustSent {
			t.Errorf("internal_diagnosticMessageJustSent_afterReceive: got %v, want %v", client.diagnosticMessageJustSent, false)
		}
	})

	// Corresponds to golden output: TelemetryClient_receive_withoutDiagnosticSend
	t.Run("Receive_WithoutDiagnosticSendDeterministic", func(t *testing.T) {
		const seed = 42
		client := newTestClient(seed)

		// Pre-calculate the expected string using the same deterministic logic
		// from the source code to validate the implementation.
		expectedRand := rand.New(rand.NewSource(seed))
		messageLength := expectedRand.Intn(50) + 60
		var expectedBuilder strings.Builder
		for i := 0; i < messageLength; i++ {
			expectedBuilder.WriteByte(byte(expectedRand.Intn(40) + 86))
		}
		expectedMessage := expectedBuilder.String()

		receivedMessage := client.Receive()

		if receivedMessage != expectedMessage {
			t.Errorf("message mismatch for deterministic random string.\nGot (len %d): %q\nWant (len %d): %q", len(receivedMessage), receivedMessage, len(expectedMessage), expectedMessage)
		}
	})
}

// TestTelemetryDiagnosticsBehavior validates the TelemetryDiagnostics logic using a mock client.
func TestTelemetryDiagnosticsBehavior(t *testing.T) {
	// Corresponds to golden output: TelemetryDiagnostics_init_initialState
	t.Run("Init_InitialState", func(t *testing.T) {
		mockClient := &mockTelemetryClient{}
		diagnostics := NewTelemetryDiagnostics(mockClient)
		if diagnostics.DiagnosticInfo != "" {
			t.Errorf("Initial diagnostic_info: got %q, want %q", diagnostics.DiagnosticInfo, "")
		}
	})

	// Corresponds to golden output: TelemetryDiagnostics_checkTransmission_connectionFailureAllTries
	t.Run("CheckTransmission_ConnectionFailureAllRetries", func(t *testing.T) {
		mockClient := &mockTelemetryClient{
			connectSuccessOnAttempt: 0, // Always fail
		}
		diagnostics := NewTelemetryDiagnostics(mockClient)

		err := diagnostics.CheckTransmission()

		expectedErr := errors.New("unable to connect")
		if err == nil || err.Error() != expectedErr.Error() {
			t.Errorf("Expected error: got %v, want %v", err, expectedErr)
		}
		if diagnostics.DiagnosticInfo != "" {
			t.Errorf("final_diagnostic_info was not cleared: got %q, want %q", diagnostics.DiagnosticInfo, "")
		}
		if mockClient.disconnectCalls != 1 {
			t.Errorf("disconnect_calls: got %d, want %d", mockClient.disconnectCalls, 1)
		}
		if mockClient.connectAttempts != 3 {
			t.Errorf("connect_calls: got %d, want %d", mockClient.connectAttempts, 3)
		}
		if mockClient.sendCalls != 0 {
			t.Errorf("send_calls: got %d, want %d", mockClient.sendCalls, 0)
		}
		if mockClient.receiveCalls != 0 {
			t.Errorf("receive_calls: got %d, want %d", mockClient.receiveCalls, 0)
		}
	})

	// Corresponds to golden output: TelemetryDiagnostics_checkTransmission_connectionSuccessFirstTry
	// and TelemetryDiagnostics_checkTransmission_interactionDetails
	t.Run("CheckTransmission_SuccessFirstTry", func(t *testing.T) {
		mockClient := &mockTelemetryClient{
			connectSuccessOnAttempt: 1,
			receiveStub:             "FAKE DIAGNOSTIC INFO",
		}
		diagnostics := NewTelemetryDiagnostics(mockClient)

		err := diagnostics.CheckTransmission()

		if err != nil {
			t.Fatalf("Unexpected error: %v", err)
		}

		if diagnostics.DiagnosticInfo != "FAKE DIAGNOSTIC INFO" {
			t.Errorf("diagnostic_info: got %q, want %q", diagnostics.DiagnosticInfo, "FAKE DIAGNOSTIC INFO")
		}
		if mockClient.disconnectCalls != 1 {
			t.Errorf("disconnect_calls: got %d, want %d", mockClient.disconnectCalls, 1)
		}
		if mockClient.connectAttempts != 1 {
			t.Errorf("connect_calls: got %d, want %d", mockClient.connectAttempts, 1)
		}
		if mockClient.sendCalls != 1 {
			t.Errorf("send_calls: got %d, want %d", mockClient.sendCalls, 1)
		}
		if mockClient.lastSentMessage != DiagnosticMessage {
			t.Errorf("sent_message: got %q, want %q", mockClient.lastSentMessage, DiagnosticMessage)
		}
		if mockClient.receiveCalls != 1 {
			t.Errorf("receive_calls: got %d, want %d", mockClient.receiveCalls, 1)
		}
	})

	// Corresponds to golden output: TelemetryDiagnostics_checkTransmission_connectionSuccessThirdTry
	t.Run("CheckTransmission_SuccessThirdTry", func(t *testing.T) {
		mockClient := &mockTelemetryClient{
			connectSuccessOnAttempt: 3,
			receiveStub:             "DIAGNOSTIC DATA FROM 3RD TRY",
		}
		diagnostics := NewTelemetryDiagnostics(mockClient)

		err := diagnostics.CheckTransmission()

		if err != nil {
			t.Fatalf("Unexpected error: %v", err)
		}

		if diagnostics.DiagnosticInfo != "DIAGNOSTIC DATA FROM 3RD TRY" {
			t.Errorf("diagnostic_info: got %q, want %q", diagnostics.DiagnosticInfo, "DIAGNOSTIC DATA FROM 3RD TRY")
		}
		if mockClient.disconnectCalls != 1 {
			t.Errorf("disconnect_calls: got %d, want %d", mockClient.disconnectCalls, 1)
		}
		if mockClient.connectAttempts != 3 {
			t.Errorf("connect_calls: got %d, want %d", mockClient.connectAttempts, 3)
		}
		if mockClient.sendCalls != 1 {
			t.Errorf("send_calls: got %d, want %d", mockClient.sendCalls, 1)
		}
		if mockClient.lastSentMessage != DiagnosticMessage {
			t.Errorf("sent_message: got %q, want %q", mockClient.lastSentMessage, DiagnosticMessage)
		}
		if mockClient.receiveCalls != 1 {
			t.Errorf("receive_calls: got %d, want %d", mockClient.receiveCalls, 1)
		}
	})

	// Note: The golden output key 'TelemetryDiagnostics_checkTransmission_interactionDetails' is implicitly
	// covered by the success and failure tests above, which assert the number and nature of interactions
	// with the mocked client. The `StopIteration` error in the golden output is an artifact of Python's
	// mocking framework and has no direct equivalent here; a successful test run is the goal.
}
