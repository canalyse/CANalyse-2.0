import os
import pandas as pd
import can
from can import Bus, BusState, Logger, LogReader, MessageSync
from can.io import ASCWriter, BLFWriter, TRCWriter, MF4Writer, SqliteWriter
import time
import pandasql as ps
import keyboard as kd
from typing import Dict, List, Set, Optional, Any
import logging
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn


class Canalyse:
    def __init__(self, channel: str, bustype: str) -> None:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # Validate inputs
        if not self._validate_channel(channel):
            raise ValueError(f"Invalid channel: {channel}")
        if not self._validate_bustype(bustype):
            raise ValueError(f"Invalid bustype: {bustype}")
        
        self.variables: Dict[str, Any] = {}
        self.channel: str = channel
        self.bustype: str = bustype
        self.builtin: Dict[str, List[str]] = {
            "scan": ["channel", "time"],
            "read": ["filename"],
            "save": ["dataframe", "filename"],
            "play": ["channel", "dataframe"],
            "sql": ["query"],
            "playmsg": ["channel", "message"],
            "import": ["projectpath"],
            "export": ["projectpath"],
            "run": ["projectpath"],
            "download": ["filename"],
            "fuzz": ["dataframe", "iterations"]
        }

        self.history: List[str] = []
        self.goterror: bool = False
        self.errorreason: str = ""
        self.telegram: bool = False
        self.bot: Optional[Any] = None
        self.chat_id: int = 0
        self.noise: Set[str] = set()
        self.signal: Dict[str, Any] = {}
        self.pending_download: Optional[str] = None

    def _validate_channel(self, channel: str) -> bool:
        """Validate CAN channel name."""
        if not isinstance(channel, str) or not channel.strip():
            return False
        # Prevent directory traversal and allow only safe characters
        if '..' in channel or '/' in channel or '\\' in channel:
            return False
        # Allow alphanumeric, underscores, dots, and hyphens
        import re
        return bool(re.match(r'^[a-zA-Z0-9_.-]+$', channel))

    def _validate_bustype(self, bustype: str) -> bool:
        """Validate CAN bus type."""
        valid_types = ['socketcan', 'slcan', 'canalystii', 'usb2can', 'ixxat', 'pcan', 'virtual']
        return bustype.lower() in valid_types

    def _validate_filename(self, filename: str) -> bool:
        """Validate filename for security."""
        if not isinstance(filename, str) or not filename.strip():
            return False
        # Prevent directory traversal and dangerous characters
        import re
        if '..' in filename or not re.match(r'^[a-zA-Z0-9_/.-]+$', filename):
            return False
        return True

    def _validate_can_message(self, message: str) -> bool:
        """Validate CAN message format (ID#DATA)."""
        if not isinstance(message, str):
            return False
        parts = message.split('#')
        if len(parts) != 2:
            return False
        can_id, data = parts
        # Validate CAN ID (hex)
        try:
            int(can_id, 16)
        except ValueError:
            return False
        # Validate data (hex, even length)
        if len(data) % 2 != 0 or not all(c in '0123456789abcdefABCDEF' for c in data):
            return False
        return True

    def _format_hex_data(self, data: bytes) -> str:
        """Convert bytes to hex string format."""
        return "".join(f"{d:02x}" for d in data)

    def _parse_hex_data(self, hex_str: str) -> bytes:
        """Convert hex string to bytes, handling various formats."""
        # Remove spaces and convert to lowercase
        hex_str = hex_str.replace(' ', '').lower()
        if len(hex_str) % 2 != 0:
            hex_str = '0' + hex_str
        return bytes.fromhex(hex_str)

    def error(self, reason: str) -> None:
        print("ERROR: "+reason)
        self.logger.error(reason)
        if not self.goterror:
            self.history.pop()
            self.goterror = True
            self.errorreason = reason

    def scan(self, channel: str, timeline: str) -> Optional[pd.DataFrame]: #scan specified bus/channel and stores the data packets for a specified time.
        if not self._validate_channel(channel):
            self.error(f"Invalid channel: {channel}")
            return None
        try:
            timeline_int = int(timeline)
            if timeline_int < 0 or timeline_int > 3600:  # Max 1 hour
                self.error("Timeline must be between 0 and 3600 seconds")
                return None
        except ValueError:
            self.error("Timeline must be a valid integer")
            return None
        
        try:
            bus = can.Bus(
                bustype=self.bustype, channel=channel)
            cls = ["timestamp", "channel", "id", "data"]
            if timeline_int != 0:
                t_end = time.time() + timeline_int
            else:
                t_end = time.time() + 600  # max time limit is 10 Min.

            msgs = []
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
            ) as progress:
                scan_task = progress.add_task("Scanning CAN bus...", total=timeline_int if timeline_int > 0 else 600)
                
                start_time = time.time()
                while time.time() < t_end:
                    msg = bus.recv(timeout=1)
                    if msg is not None:
                        mdata = self._format_hex_data(msg.data)
                        mrow = [msg.timestamp, msg.channel, str(hex(msg.arbitration_id)[2:]), mdata]
                        msgs.append(dict((cls[a], mrow[a]) for a in range(4)))
                    
                    # Update progress
                    elapsed = time.time() - start_time
                    progress.update(scan_task, completed=min(elapsed, timeline_int if timeline_int > 0 else 600))
                    
            return pd.DataFrame(msgs,columns=cls)
        except Exception as e:
            self.error(str(e))
            return None

    def read(self, filename: str) -> pd.DataFrame: #reads specified file by using logreader function from can library.
        if not self._validate_filename(filename):
            self.error(f"Invalid filename: {filename}")
            return pd.DataFrame()
        
        extension = filename.split(".")[-1].lower()
        
        if extension == "csv":
            return pd.read_csv(filename)
        
        # Use appropriate reader based on file extension
        try:
            if extension == "asc":
                reader_class = can.ASCReader
            elif extension == "blf":
                reader_class = can.BLFReader
            elif extension == "trc":
                reader_class = can.TRCReader
            elif extension == "mf4":
                reader_class = can.MF4Reader
            elif extension == "db" or extension == "sqlite":
                reader_class = can.SqliteReader
            else:
                # Default to LogReader for .log and other formats
                reader_class = can.LogReader
            
            cls = ["timestamp", "channel", "id", "data"]
            row_list = []
            
            with reader_class(filename) as reader:
                for msg in reader:
                    mdata = self._format_hex_data(msg.data)
                    mrow = [msg.timestamp, msg.channel, str(hex(msg.arbitration_id)[2:]), mdata]
                    row_list.append(dict((cls[a], mrow[a]) for a in range(4)))
            
            return pd.DataFrame(row_list, columns=cls)
            
        except Exception as e:
            self.error(f"Error reading file {filename}: {str(e)}")
            return pd.DataFrame()

    def save(self, df: pd.DataFrame, filename: str) -> None: #saves the dataframes in the specified format.
        if not self._validate_filename(filename):
            self.error(f"Invalid filename: {filename}")
            return
        
        extension = filename.lower().split(".")[-1]

        if extension == "csv":
            df.to_csv(filename, index=False)
        elif extension == "log":

            col = df.columns
            for c in ["timestamp", "channel", "id", "data"]:
                if c not in col:
                    pass  # c not available to store in log file
                    self.error(f"{c} column is needed to store as log")

            with open(filename, "w+") as file:
                for i in range(df.shape[0]):
                    t = str(df.loc[i, "timestamp"])
                    if len(t) < 17:
                        t = "0" * (17 - len(t)) + t
                    t = "(" + t + ")"
                    m = [
                        t,
                        str(df.loc[i, "channel"]),
                        str(df.loc[i, "id"]) + "#" + str(df.loc[i, "data"]) + "\n",
                    ]
                    t = " ".join(m)
                    file.write(t)

            pass
        elif extension in ["asc", "blf", "trc", "mf4", "db", "sqlite", "sqlite3"]:
            # Convert DataFrame to CAN messages and use appropriate writer
            try:
                messages = []
                for _, row in df.iterrows():
                    # Convert data to bytes using helper function
                    data = self._parse_hex_data(str(row['data']))
                    
                    # Parse CAN ID, handling both hex strings and integers
                    can_id_str = str(row['id'])
                    if can_id_str.startswith('0x'):
                        arbitration_id = int(can_id_str, 16)
                    else:
                        arbitration_id = int(can_id_str)
                    
                    msg = can.Message(
                        timestamp=float(row['timestamp']),
                        arbitration_id=arbitration_id,
                        data=data,
                        channel=int(row.get('channel', 0))
                    )
                    messages.append(msg)
                
                # Use appropriate writer based on extension
                writer_map = {
                    "asc": ASCWriter,
                    "blf": BLFWriter, 
                    "trc": TRCWriter,
                    "mf4": MF4Writer,
                    "db": SqliteWriter,
                    "sqlite": SqliteWriter,
                    "sqlite3": SqliteWriter
                }
                
                writer_class = writer_map.get(extension)
                if writer_class:
                    with writer_class(filename) as writer:
                        for msg in messages:
                            writer(msg)
                            
                    self.logger.info(f"Successfully saved {len(messages)} messages to {filename}")
                else:
                    self.error(f"Unsupported writer for extension: {extension}")
                
            except Exception as e:
                self.error(f"Error saving to {extension} format: {str(e)}")
        else:
            self.error(f"Unsupported file extension: {extension}. Supported formats: csv, log, asc, blf, trc, mf4, sqlite")

    def exportvardata(self, filepath, projectname): #exports session data path to custom file format.
        projectpath = os.path.join(filepath, projectname)
        if os.path.isdir(projectpath):
            mode = "a+"
        else:
            mode = "w+"

            os.mkdir(projectpath)
            os.mkdir(os.path.join(projectpath, "logs"))
            os.mkdir(os.path.join(projectpath, "tables"))
        datafilepath = os.path.join(projectpath, projectname + ".data.clyse")
        with open(datafilepath, mode) as datafile:
            for var in self.variables:
                val = self.variables[var]
                if type(val) == pd.DataFrame:
                    col = val.columns
                    seq = True
                    for c in ["timestamp", "channel", "id", "data"]:
                        if c not in col:
                            seq = False
                            break
                    if seq:
                        f = "logs"
                        e = "log"
                    else:
                        f = "tables"
                        e = "csv"
                    filename = os.path.join(filepath, projectname, f, var + "." + e)
                    self.save(self.variables[var], filename)
                    datafile.write(f"{var} = read('{filename}')\n")
                else:
                    if type(val) == str:
                        val = '"' + val + '"'
                    datafile.write(f"{var} = {val}\n")

    def exportcodedata(self, filepath, projectname): #exports session commands to custom file format.
        projectpath = os.path.join(filepath, projectname)
        if os.path.isdir(projectpath):
            mode = "a+"
        else:
            mode = "w+"

            os.mkdir(projectpath)
        codefilepath = os.path.join(projectpath, projectname + ".action.clyse")
        with open(codefilepath, mode) as codefile:
            for code in self.history[:-1]:
                codefile.write(f"{code}\n")

    def export(self, projectpath): #exports complete session data to projectpath.
        projectname = os.path.basename(projectpath)
        filepath = os.path.dirname(projectpath)
        self.exportvardata(filepath, projectname)
        self.exportcodedata(filepath, projectname)

    def importt(self, projectpath): #import complete session data from projectpath.
        projectname = os.path.basename(projectpath)
        datafilepath = os.path.join(projectpath, projectname + ".data.clyse")
        if os.path.isfile(datafilepath):
            with open(datafilepath, "r+") as datafile:
                for line in datafile.readlines():
                    self.repl(line)

        else:
            self.error("Invalid project path")

    def run(self, projectpath): # runs an entire session (*Testing In-Progress)
        projectname = os.path.basename(projectpath)
        actionfilepath = os.path.join(projectpath, projectname + ".action.clyse")
        if os.path.isfile(actionfilepath):
            with open(actionfilepath, "r+") as datafile:
                for line in datafile.readlines():
                    self.repl(line)

    def play(self, channel, df): #plays specified pandas dataframe.
        if not self._validate_channel(channel):
            self.error(f"Invalid channel: {channel}")
            return
            
        try:
            bus = can.Bus(bustype=self.bustype, channel=channel)
            
            # Convert DataFrame to messages without temporary file
            messages = []
            for _, row in df.iterrows():
                data = self._parse_hex_data(str(row['data']))
                can_id_str = str(row['id'])
                if can_id_str.startswith('0x'):
                    arbitration_id = int(can_id_str, 16)
                else:
                    arbitration_id = int(can_id_str)
                    
                msg = can.Message(
                    arbitration_id=arbitration_id,
                    data=data,
                    is_extended_id=False
                )
                messages.append(msg)
            
            # Send all messages
            for msg in messages:
                bus.send(msg)
                time.sleep(0.01)  # Small delay between messages
                
        except Exception as e:
            self.error(f"Failed to play messages: {str(e)}")

    def playmsg(self, channel: str, canmsg: str) -> None: #option to play a particular packet.
        if not self._validate_channel(channel):
            self.error(f"Invalid channel: {channel}")
            return
        if not self._validate_can_message(canmsg):
            self.error(f"Invalid CAN message format: {canmsg}")
            return
        
        try:
            bus = can.Bus(bustype=self.bustype, channel=channel)
            t = canmsg.split("#")
            data = self._parse_hex_data(t[1])
            arbitration_id = int(t[0], 16)
            
            msg = can.Message(
                arbitration_id=arbitration_id, 
                data=data, 
                is_extended_id=False
            )
            bus.send(msg)
        except Exception as e:
            self.error(f"Failed to send CAN message: {str(e)}")

    def sql(self, query): #runs an sql query.
        try:
            df = ps.sqldf(query, self.variables)
            return df
        except Exception as e:
            self.error(e)

    def download(self,filename): #downloads files to bot operating device.
        try:
            if self.telegram:
                self.pending_download = filename
            else:
                self.error("This function can only be used in Telegram")
        except Exception as e:
            self.error(e)

    def fuzz(self, df: pd.DataFrame, iterations: int) -> pd.DataFrame: #generates fuzzed CAN messages based on input dataframe.
        if not isinstance(df, pd.DataFrame) or df.empty:
            self.error("Invalid dataframe provided for fuzzing")
            return pd.DataFrame()
            
        required_cols = ['timestamp', 'channel', 'id', 'data']
        if not all(col in df.columns for col in required_cols):
            self.error(f"DataFrame must contain columns: {required_cols}")
            return pd.DataFrame()
            
        if not isinstance(iterations, int) or iterations < 1 or iterations > 10000:
            self.error("Iterations must be an integer between 1 and 10000")
            return pd.DataFrame()
        
        import random
        
        fuzzed_rows = []
        update_interval = max(1, iterations // 100)  # Update progress at most 100 times
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
        ) as progress:
            fuzz_task = progress.add_task("Generating fuzzed messages...", total=iterations)
            
            for i in range(iterations):
                # Pick a random row from df
                row = df.sample().iloc[0]
                
                # Fuzz the data: randomly flip bits with better algorithm
                data_str = str(row['data'])
                try:
                    data_bytes = [int(data_str[i:i+2], 16) for i in range(0, len(data_str), 2)]
                except ValueError:
                    # Skip invalid data
                    continue
                    
                # More sophisticated fuzzing: multiple mutation types
                fuzzed_data = data_bytes.copy()
                mutation_type = random.choice(['bitflip', 'byteflip', 'arithmetic', 'random'])
                
                if mutation_type == 'bitflip' and fuzzed_data:
                    # Flip random bits in random bytes
                    for _ in range(random.randint(1, min(3, len(fuzzed_data)))):
                        byte_idx = random.randint(0, len(fuzzed_data) - 1)
                        bit_idx = random.randint(0, 7)
                        fuzzed_data[byte_idx] ^= (1 << bit_idx)
                        
                elif mutation_type == 'byteflip' and fuzzed_data:
                    # Flip entire random bytes
                    for _ in range(random.randint(1, min(2, len(fuzzed_data)))):
                        byte_idx = random.randint(0, len(fuzzed_data) - 1)
                        fuzzed_data[byte_idx] = random.randint(0, 255)
                        
                elif mutation_type == 'arithmetic' and fuzzed_data:
                    # Arithmetic mutations
                    for _ in range(random.randint(1, min(2, len(fuzzed_data)))):
                        byte_idx = random.randint(0, len(fuzzed_data) - 1)
                        operation = random.choice(['add', 'sub', 'mul'])
                        if operation == 'add':
                            fuzzed_data[byte_idx] = (fuzzed_data[byte_idx] + random.randint(1, 10)) % 256
                        elif operation == 'sub':
                            fuzzed_data[byte_idx] = (fuzzed_data[byte_idx] - random.randint(1, 10)) % 256
                        elif operation == 'mul':
                            fuzzed_data[byte_idx] = (fuzzed_data[byte_idx] * random.randint(2, 5)) % 256
                            
                elif mutation_type == 'random':
                    # Completely random data
                    fuzzed_data = [random.randint(0, 255) for _ in range(len(data_bytes))]
                
                fuzzed_data_str = "".join(f"{b:02x}" for b in fuzzed_data)
                
                fuzzed_row = {
                    'timestamp': row['timestamp'],
                    'channel': row['channel'],
                    'id': row['id'],
                    'data': fuzzed_data_str
                }
                fuzzed_rows.append(fuzzed_row)
                
                if (i + 1) % update_interval == 0 or i == iterations - 1:
                    progress.update(fuzz_task, advance=update_interval)
                
        return pd.DataFrame(fuzzed_rows)

    def isfloat(self, string: str): #checks inputs.
        try:
            a = float(string)
            return True
        except:
            return False

    def check_func_args(self, func, args): #checks for arg requirements.
        if len(self.builtin[func]) != len(args):
            self.error(
                f"function {func} requires {len(self.builtin[func])} arguments {len(args)} given"
            )
            return False
        return True

    def execute_func(self, func, args): #executes functions.
        if func == "scan" and self.check_func_args(func, args):
            return self.scan(self.evaluate(args[0]), self.evaluate(args[1]))
        elif func == "read" and self.check_func_args(func, args):
            return self.read(self.evaluate(args[0]))
        elif func == "sql" and self.check_func_args(func, args):
            return self.sql(self.evaluate(args[0]))
        elif func == "save" and self.check_func_args(func, args):
            return self.save(self.evaluate(args[0]), self.evaluate(args[1]))
        elif func == "play" and self.check_func_args(func, args):
            return self.play(self.evaluate(args[0]), self.evaluate(args[1]))
        elif func == "playmsg" and self.check_func_args(func, args):
            return self.playmsg(self.evaluate(args[0]), self.evaluate(args[1]))
        elif func == "import" and self.check_func_args(func, args):
            return self.importt(self.evaluate(args[0]))
        elif func == "export" and self.check_func_args(func, args):
            return self.export(self.evaluate(args[0]))
        elif func == "run" and self.check_func_args(func, args):
            return self.run(self.evaluate(args[0]))
        elif func == "download" and self.check_func_args(func, args):
            return self.download(self.evaluate(args[0]))
        elif func == "fuzz" and self.check_func_args(func, args):
            return self.fuzz(self.evaluate(args[0]), self.evaluate(args[1]))    
        else:
            self.error(f"function {func} is not defined")

    def evaluate_var(self, token):
        if token in self.builtin:
            self.error(f"function {token} requires arguments")
        elif token in self.variables:
            return self.variables[token]
        elif token.isdigit():
            return int(token)
        elif self.isfloat(token):
            return float(token)
        elif token[0] == '"' and token[-1] == '"':
            return str(token[1:-1])
        elif token[0] == "'" and token[-1] == "'":
            return str(token[1:-1])
        elif (
            "+" in token or "-" in token or "*" in token or "/" in token or "%" in token
        ):
            # SECURITY: Replaced eval with safe arithmetic evaluation
            self.error("Arithmetic expressions are not supported for security reasons")
            return None
        else:
            self.error("Variable not defined")

    def do_split(self, code, element): #splits the specified command.
        dqsk = 0
        qk = 0
        ck = 0
        result = []
        start = 0
        for i in range(len(code)):
            if code[i] == "'":
                qk += 1
                qk %= 2
            elif code[i] == '"':
                dqsk += 1
                dqsk %= 2

            elif qk == 0 and dqsk == 0 and ck == 0 and code[i] == element:
                result.append(code[start:i])
                start = i + 1
            elif code[i] == "(":
                ck += 1
            elif code[i] == ")":
                ck += 1
        result.append(code[start:])
        return result

    def evaluate(self, code): #evaluates the split output.
        code = code.strip()
        tokens = self.do_split(code, "(")
        if len(tokens) == 0:
            pass
        elif len(tokens) == 1:
            return self.evaluate_var(tokens[0])
        else:
            code = "(".join(tokens[1:])
            if code[-1] == ")":
                code = code[:-1]
            func = tokens[0]
            args = self.do_split(code, ",")
            return self.execute_func(func, args)

    def repl(self, code: str) -> Optional[Any]: #extracts passed command for executing it through different functions.
        code = code.strip()
        if code == "":
            return None

        tokens = self.do_split(code, "=")
        self.goterror = False
        self.history.append(code)
        if len(tokens) > 1:
            tokens[0] = tokens[0].strip()
            if len(tokens[0].split(" ")) > 1 or not tokens[0].isalnum():
                pass  # variable assignment error
                self.error(f"{' '.join(tokens)} not defined")
            elif not tokens[0][0].isalpha():
                self.error(f"variable should not start with special characters")
            else:
                self.variables[tokens[0]] = self.evaluate("=".join(tokens[1:]))
        else:
            return self.evaluate(code)

    def collect_noise(self, bus):
        self.show_signals()
        s = 0
        for msg in bus:
            s+=1
            msghash = f"{msg.arbitration_id}#{msg.data}"
            self.noise.add(msghash)
            if msghash in self.signal:
                del self.signal[msghash]
            if s%100 == 0:
                self.show_signals()

            if kd.is_pressed("space"):
                break
            elif kd.is_pressed("s"):
                self.stop = True
                self.savve = True
                break
            elif kd.is_pressed("p"):
                for msghash in self.signal:
                    msg = self.signal[msghash]
                    mdata = "".join(
                        [
                            str(hex(d))[2:]
                            if len(str(hex(d))) == 4
                            else "0" + str(hex(d))[2:]
                            for d in msg.data
                        ]
                    )
                    mssg = str(hex(msg.arbitration_id)[2:]) + "#" + mdata
                    self.playmsg(self.channel, mssg)
                break
            elif kd.is_pressed("q"):
                self.stop = True
                self.savve = False
                break


    def collect_signal(self, bus):
        print(f"\033cOnce you stop giving the signals press 'b'")
        signal_cahce = {}
        sigset = set()
        if self.stop:
            return
        elif self.signal == {}:
            for msg in bus:
                msghash = f"{msg.arbitration_id}#{msg.data}"
                signal_cahce[msghash] = msg
                if kd.is_pressed('b'):
                    break
        else:
            for msg in bus:
                msghash = f"{msg.arbitration_id}#{msg.data}"
                sigset.add(msghash)
                if kd.is_pressed('b'):
                    break
        if self.signal == {}:
            msghashes = list(signal_cahce.keys())
            for msghash in msghashes:
                if msghash in self.noise:
                    del signal_cahce[msghash]
                    
            self.signal = signal_cahce
        else:
            
            sigche = {}
            for msghash in sigset:
                
                if msghash not in self.signal:
                    self.noise.add(msghash)
                if msghash in self.noise and msghash in self.signal:
                    del self.signal[msghash]
                elif msghash in self.signal:
                    sigche[msghash] = self.signal[msghash]
            for msghash in self.signal:
                if msghash not in sigche:
                    self.noise.add(msghash)
            self.signal = sigche
            
        self.show_signals()
                

    def smartscan(self):
        bus = can.Bus(bustype=self.bustype,
                              channel=self.channel)  # type: ignore
        self.stop = False
        self.savve = False
        while not self.stop:
            self.collect_noise(bus)
            self.collect_signal(bus)
        if self.savve:
            self.save_signals()

    def show_signals(self):
        print(
            f"\033cPress Spacebar and start giving the signals\nPress 'S' to save\nPress 'p' to play\nPress 'q' to quit\nNumber of messages : {len(self.signal)}"
        )
        msgs = self.signal.values()
        for msg in msgs:
            mdata = "".join(
                [
                    str(hex(d))[2:] if len(str(hex(d))) == 4 else f"0{str(hex(d))[2:]}"
                    for d in msg.data
                ]
            )
            print(
                f"{hex(msg.arbitration_id)[2:]}#{mdata}", flush=True)

    def save_signals(self):
        while True:
            print("\033c", end="")
            self.show_signals()
            try:
                filepath = input("---> ")
                filepath = 's'.join(filepath.split('s')[1:])
                self.save_signals_as_file(filepath)
                break
            except:
                pass

    def save_signals_as_file(self, filepath):
        if filepath == "":
            return
        elif filepath.split('.')[-1] != 'log':
            filepath += '.log'
        with open(filepath, "w+") as file:
            for msghash in self.signal:
                msg = self.signal[msghash]
                mdata = "".join(
                    [
                        str(hex(d))[2:]
                        if len(str(hex(d))) == 4
                        else "0" + str(hex(d))[2:]
                        for d in msg.data
                    ]
                )
                timestamp = str(msg.timestamp)
                if len(timestamp) < 17:
                    timestamp = "0" * (17 - len(timestamp)) + timestamp
                timestamp = "(" + timestamp + ")"
                m = [
                    timestamp,
                    self.channel,
                    str(hex(msg.arbitration_id)[2:]) + "#" + mdata + "\n",
                ]
                message = " ".join(m)
                file.write(message)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.variables = {}
