# CANalyse 2.0

CANalyse is a software tool for analyzing vehicle internal networks (CAN bus). It allows scanning, logging, replaying, and analyzing CAN messages for research purposes.

## Disclaimer

CANalyse is made available for research purposes only. Users are solely responsible for ensuring compliance with laws and obtaining proper permissions from stakeholders.

## Features

- Scan CAN bus channels and log messages
- Read and save CAN logs in multiple industry-standard formats (ASC, BLF, TRC, MF4, SQLite, CSV, LOG)
- Replay logged messages
- SQL-like queries on CAN data using pandasql
- Smart scan to identify signal vs noise messages
- Fuzzer to generate fuzzed CAN messages for testing
- Telegram bot integration for remote control
- Export/import sessions
- Comprehensive input validation and security features
- Progress bars for long-running operations

## Installation

### Option 1: Install from PyPI (Recommended)
```bash
pip install canalyse
canalyse
```

### Option 2: Install from Source
```bash
git clone https://github.com/canalyse/CANalyse-2.0.git
cd CANalyse-2.0
pip install -e .
python -m canalyse_interface
```

## Usage

- Use the interactive interface to navigate menus
- Set communication channel and interface in settings (default: vcan0, socketcan)
- For Telegram bot, set API token in settings

### REPL Commands

In the IDE or Telegram, use commands like:
- `scan("can0", "10")` - Scan CAN bus for 10 seconds
- `read("logfile.log")` - Read CAN log file
- `save(df, "output.csv")` - Save dataframe to file
- `play("can0", df)` - Replay messages
- `sql("SELECT * FROM df WHERE id = '123'")` - Query data
- `fuzz(df, 100)` - Generate 100 fuzzed messages
- `export("session")` - Export session

### Fuzzer

The fuzzer generates modified CAN messages for testing vehicle responses:
- Takes a dataframe of messages and number of iterations
- Randomly modifies data bytes to create fuzzed variants
- Useful for security testing and robustness analysis

## Requirements

- Python 3.8+
- CAN interface hardware (e.g., USBtin) or virtual CAN for testing
- For Linux testing: `sudo modprobe vcan; sudo ip link add dev vcan0 type vcan; sudo ip link set up vcan0`
- For Windows: Use compatible CAN adapters or virtual interfaces

## Testing

CANalyse includes a comprehensive test suite to ensure reliability:

- **Unit Tests**: Core functionality tests in `test_canalyse.py`
- **Coverage**: Tests initialization, REPL operations, and fuzzer functionality
- **Run Tests**: `python -m pytest test_canalyse.py -v`

All tests should pass before using the tool in production environments.

## Contributing

Contributions welcome! Please ensure tests pass and follow the existing code style.


