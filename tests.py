import pytest
import pandas as pd
import sys
import os

# Add the current directory to the path for imports
sys.path.insert(0, os.path.dirname(__file__))

from canalyse import Canalyse

def test_canalyse_init():
    cn = Canalyse("test", "socketcan")
    assert cn.channel == "test"
    assert cn.bustype == "socketcan"
    assert isinstance(cn.variables, dict)

def test_repl_assignment():
    cn = Canalyse("test", "socketcan")
    result = cn.repl("a = 5")
    assert result is None
    assert cn.variables["a"] == 5

def test_repl_expression():
    cn = Canalyse("test", "socketcan")
    cn.repl("a = 5")
    result = cn.repl("a")  # Just access the variable directly
    assert result == 5

def test_fuzz():
    cn = Canalyse("test", "socketcan")
    df = pd.DataFrame({
        'timestamp': [1.0, 2.0],
        'channel': ['can0', 'can0'],
        'id': ['123', '456'],
        'data': ['deadbeef', 'cafebabe']
    })
    fuzzed = cn.fuzz(df, 5)
    assert len(fuzzed) == 5
    assert list(fuzzed.columns) == ['timestamp', 'channel', 'id', 'data']

def test_validate_channel():
    cn = Canalyse("test", "socketcan")
    assert cn._validate_channel("can0")
    assert cn._validate_channel("vcan0")
    assert not cn._validate_channel("")
    assert not cn._validate_channel("../../../etc/passwd")

def test_validate_can_message():
    cn = Canalyse("test", "socketcan")
    assert cn._validate_can_message("123#deadbeef")
    assert cn._validate_can_message("1A#cafe")
    assert not cn._validate_can_message("invalid")
    assert not cn._validate_can_message("123#gggg")

def test_format_hex_data():
    cn = Canalyse("test", "socketcan")
    assert cn._format_hex_data(b'\xde\xad\xbe\xef') == "deadbeef"
    assert cn._format_hex_data(b'\x01\x02') == "0102"

def test_parse_hex_data():
    cn = Canalyse("test", "socketcan")
    assert cn._parse_hex_data("deadbeef") == b'\xde\xad\xbe\xef'
    assert cn._parse_hex_data("0102") == b'\x01\x02'
    assert cn._parse_hex_data("DE AD BE EF") == b'\xde\xad\xbe\xef'  # handles spaces

if __name__ == "__main__":
    pytest.main([__file__])