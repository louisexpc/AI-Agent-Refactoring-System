package telemetry

import (
	"errors"
	"math/rand"
	"strings"
	"time"
)

const (
	DiagnosticMessage = "AT#UD"
)

// Client defines the interface for a telemetry client.
type Client interface {
	Connect(connectionString string)
	Disconnect()
	Send(message string)
	Receive() string
	OnlineStatus() bool
}

// TelemetryClient is the concrete implementation of the Client interface.
type TelemetryClient struct {
	onlineStatus              bool
	diagnosticMessageJustSent bool
	rand                      *rand.Rand
}

// NewTelemetryClient creates a new TelemetryClient.
func NewTelemetryClient() *TelemetryClient {
	return &TelemetryClient{
		rand: rand.New(rand.NewSource(time.Now().UnixNano())),
	}
}

// OnlineStatus returns the online status of the client.
func (c *TelemetryClient) OnlineStatus() bool {
	return c.onlineStatus
}

// Connect establishes a connection to the telemetry server.
func (c *TelemetryClient) Connect(telemetryServerConnectionString string) {
	if telemetryServerConnectionString == "" {
		panic("telemetryServerConnectionString is null or empty")
	}

	// Fake the connection with 20% chances of success
	success := c.rand.Intn(10) < 2
	c.onlineStatus = success
}

// Disconnect closes the connection to the telemetry server.
func (c *TelemetryClient) Disconnect() {
	c.onlineStatus = false
}

// Send sends a message to the telemetry server.
func (c *TelemetryClient) Send(message string) {
	if message == "" {
		panic("message is null or empty")
	}

	if message == DiagnosticMessage {
		c.diagnosticMessageJustSent = true
	} else {
		c.diagnosticMessageJustSent = false
	}
}

// Receive receives a message from the telemetry server.
func (c *TelemetryClient) Receive() string {
	if c.diagnosticMessageJustSent {
		// Simulate the reception of the diagnostic message
		message := `LAST TX rate................ 100 MBPS
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
		c.diagnosticMessageJustSent = false
		return message
	}

	// Simulate the reception of a response message returning a random message.
	var messageBuilder strings.Builder
	messageLength := c.rand.Intn(50) + 60
	for i := 0; i < messageLength; i++ {
		messageBuilder.WriteByte(byte(c.rand.Intn(40) + 86))
	}
	return messageBuilder.String()
}

const DiagnosticChannelConnectionString = "*111#"

// TelemetryDiagnostics handles the diagnostics for the telemetry system.
type TelemetryDiagnostics struct {
	client         Client
	DiagnosticInfo string
}

// NewTelemetryDiagnostics creates a new TelemetryDiagnostics.
func NewTelemetryDiagnostics(client Client) *TelemetryDiagnostics {
	return &TelemetryDiagnostics{
		client: client,
	}
}

// CheckTransmission performs a transmission check.
func (d *TelemetryDiagnostics) CheckTransmission() error {
	d.DiagnosticInfo = ""
	d.client.Disconnect()

	retryLeft := 3
	for !d.client.OnlineStatus() && retryLeft > 0 {
		d.client.Connect(DiagnosticChannelConnectionString)
		retryLeft--
	}

	if !d.client.OnlineStatus() {
		return errors.New("unable to connect")
	}

	d.client.Send(DiagnosticMessage)
	d.DiagnosticInfo = d.client.Receive()
	return nil
}
