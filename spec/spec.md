# Refactoring Plan: Python to Go

This document outlines the plan for refactoring the Python code in the `./Racing-Car-Katas/Python` folder into Go.

## 1. Project Overview

The project consists of several small, independent modules related to a racing car system. Each module has its own source code and tests. The goal is to refactor each of these Python modules into Go, ensuring that the functionality remains the same and that the Go code is well-structured and tested.

## 2. Folder Structure

The original Python code is located in `./Racing-Car-Katas/Python`. The refactored Go code will be placed in `./refactor-golang`. The `spec` directory will contain this refactoring plan and other related documents.

### Original Python Folder Structure:
```
./Racing-Car-Katas/Python
├── Leaderboard
│   ├── leaderboard.py
│   └── test_leaderboard.py
├── TelemetrySystem
│   ├── client.py
│   ├── telemetry.py
│   └── test_telemetry.py
├── TextConverter
│   ├── html_pages.py
│   ├── test_text_converter.py
│   └── text_converter.py
├── TirePressureMonitoringSystem
│   ├── sensor.py
│   ├── test_tire_pressure_monitoring.py
│   └── tire_pressure_monitoring.py
└── TurnTicketDispenser
    ├── test_turn_ticket.py
    └── turn_ticket.py
```

### Target Go Folder Structure:
```
./refactor-golang
├── leaderboard
│   ├── leaderboard.go
│   └── leaderboard_test.go
├── telemetrysystem
│   ├── client.go
│   ├── telemetry.go
│   └── telemetry_test.go
├── textconverter
│   ├── html_pages.go
│   ├── text_converter.go
│   └── text_converter_test.go
├── tirepressuremonitoringsystem
│   ├── sensor.go
│   ├── tire_pressure_monitoring.go
│   └── tire_pressure_monitoring_test.go
└── turnticketdispenser
    ├── turn_ticket.go
    └── turn_ticket_test.go
```

## 3. To-Do List and Staging Plan

The refactoring process will be divided into stages, with each stage focusing on a single module. After each stage, the refactored code will be tested to ensure correctness.

### Stage 1: `TurnTicketDispenser`

*   [x] Refactor `TurnTicketDispenser/turn_ticket.py` to `turnticketdispenser/turn_ticket.go`.
*   [x] Refactor `TurnTicketDispenser/test_turn_ticket.py` to `turnticketdispenser/turn_ticket_test.go`.
*   [x] Run the Go tests for the `turnticketdispenser` module and ensure they pass.
*   [x] Update this to-do list.
*   [x] Record the mapping of the converted file paths in `./spec/stage_result.md`.

### Stage 2: `Leaderboard`

*   [x] Refactor `Leaderboard/leaderboard.py` to `leaderboard/leaderboard.go`.
*   [x] Refactor `Leaderboard/test_leaderboard.py` to `leaderboard/leaderboard_test.go`.
*   [x] Run the Go tests for the `leaderboard` module and ensure they pass.
*   [x] Update this to-do list.
*   [x] Record the mapping of the converted file paths in `./spec/stage_result.md`.

### Stage 3: `TirePressureMonitoringSystem`

*   [x] Refactor `TirePressureMonitoringSystem/sensor.py` to `tirepressuremonitoringsystem/sensor.go`.
*   [x] Refactor `TirePressureMonitoringSystem/tire_pressure_monitoring.py` to `tirepressuremonitoringsystem/tire_pressure_monitoring.go`.
*   [x] Refactor `TirePressureMonitoringSystem/test_tire_pressure_monitoring.py` to `tirepressuremonitoringsystem/tire_pressure_monitoring_test.go`.
*   [x] Run the Go tests for the `tirepressuremonitoringsystem` module and ensure they pass.
*   [x] Update this to-do list.
*   [x] Record the mapping of the converted file paths in `./spec/stage_result.md`.

### Stage 4: `TelemetrySystem`

*   [x] Refactor `TelemetrySystem/client.py` to `telemetrysystem/client.go`.
*   [x] Refactor `TelemetrySystem/telemetry.py` to `telemetrysystem/telemetry.go`.
*   [x] Refactor `TelemetrySystem/test_telemetry.py` to `telemetrysystem/telemetry_test.go`.
*   [x] Run the Go tests for the `telemetrysystem` module and ensure they pass.
*   [x] Update this to-do list.
*   [x] Record the mapping of the converted file paths in `./spec/stage_result.md`.

### Stage 5: `TextConverter`

*   [x] Refactor `TextConverter/html_pages.py` to `textconverter/html_pages.go`.
*   [x] Refactor `TextConverter/text_converter.py` to `textconverter/text_converter.go`.
*   [x] Refactor `TextConverter/test_text_converter.py` to `textconverter/text_converter_test.go`.
*   [x] Run the Go tests for the `textconverter` module and ensure they pass.
*   [x] Update this to-do list.
*   [x] Record the mapping of the converted file paths in `./spec/stage_result.md`.

## 4. Git Flow

Use standard Git flow for version control:
1.  Create a new branch for each stage (e.g., `feature/refactor-turnticketdispenser`).
2.  Commit the refactored code and tests to the branch.
3.  Create a pull request to merge the branch into `main` after the stage is complete and all tests pass.
4.  After merging, create a tag for the completed stage (e.g., `v1.0-turnticketdispenser`).

## 5. Validation

At the end of each refactoring phase, validate the changes by running the unit tests for the refactored Go module. Ensure that all tests pass and that there are no errors or warnings.

By following this plan, we can systematically refactor the Python project into Go, ensuring that the resulting code is high-quality, well-tested, and maintains the original functionality.
