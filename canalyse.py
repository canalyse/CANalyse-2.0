import os
import pandas as pd
import can
from can import Bus, BusState, Logger, LogReader, MessageSync
import time
import pandasql as ps
import keyboard as kd


class Canalyse:
    def __init__(self, channel, bustype) -> None:
        self.variables = {}
        self.channel = channel
        self.bustype = bustype
        self.builtin = {
            "scan": ["channel", "time"],
            "read": ["filename"],
            "save": ["dataframe", "filename"],
            "play": ["channel", "dataframe"],
            "sql": ["query"],
            "playmsg": ["channel", "message"],
            "import": ["projectpath"],
            "export": ["projectpath"],
            "run": ["projectpath"],
            "download":["filename"]
        }

        self.history = []
        self.goterror = False
        self.errorreason = ""
        self.telegram = False
        self.bot = None
        self.chat_id = 0
        self.noise = set()
        self.signal = {}

    def error(self, reason):
        print("ERROR: "+reason)
        if not self.goterror:
            self.history.pop()
            self.goterror = True
            self.errorreason = reason
#58854
    def scan(self, channel, timeline): #scan specified bus/channel and stores the data packets for a specified time.
        try:
            bus = can.Bus(
                bustype=self.bustype, channel=channel)
            cls = ["timestamp", "channel", "id", "data"]
            if int(timeline) != 0:
                t_end = time.time() + int(timeline)
            else:
                t_end = time.time() + 600  # max time limit is 10 Min.

            msgs = []

            while time.time() < t_end:
                msg = bus.recv(timeout=1)
                if msg is not None:
                    mdata = "".join(
                        [
                            str(hex(d))[2:]
                            if len(str(hex(d))) == 4
                            else "0" + str(hex(d))[2:]
                            for d in msg.data
                        ]
                    )
                    mrow = [msg.timestamp, msg.channel, str(hex(msg.arbitration_id)[2:]), mdata]
                    msgs.append(dict((cls[a], mrow[a]) for a in range(4)))
            return pd.DataFrame(msgs,columns=cls)
        except Exception as e:
            self.error(e)

    def read(self,filename): #reads specified file by using logreader function from can library.
        if filename.split(".")[-1] == "csv":
            return pd.read_csv(filename)
        cls = ["timestamp", "channel", "id", "data"]
        row_list = []
        with can.LogReader(filename) as reader:
            for msg in reader:  # type: ignore
                mdata = "".join(
                    [
                        str(hex(d))[2:]
                        if len(str(hex(d))) == 4
                        else "0" + str(hex(d))[2:]
                        for d in msg.data
                    ]
                )
                mrow = [msg.timestamp,msg.channel,str(hex(msg.arbitration_id)[2:]),mdata]
                row_list.append(dict((cls[a], mrow[a]) for a in range(4)))
        return pd.DataFrame(row_list,columns=cls)

    def save(self, df, filename): #saves the dataframes in the specified format.
        extension = filename.split(".")[-1]

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
        else:
            pass  # file format not supported
            self.error(f"{extension} not supported")

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
        projectname = projectpath.split("/")[-1]
        filepath = "/".join(projectpath.split("/")[:-1])
        self.exportvardata(filepath, projectname)
        self.exportcodedata(filepath, projectname)

    def importt(self, projectpath): #import complete session data from projectpath.
        projectname = projectpath.split("/")[-1]
        datafilepath = os.path.join(projectpath, projectname + ".data.clyse")
        if os.path.isfile(datafilepath):
            with open(datafilepath, "r+") as datafile:
                for line in datafile.readlines():
                    self.repl(line)

        else:
            self.error("Invalid project path")

    def run(self, projectpath): # runs an entire session (*Testing In-Progress)
        projectname = projectpath.split("/")[-1]
        actionfilepath = os.path.join(projectpath, projectname + ".action.clyse")
        if os.path.isfile(actionfilepath):
            with open(actionfilepath, "r+") as datafile:
                for line in datafile.readlines():
                    self.repl(line)

    def play(self, channel, df): #plays specified pandas dataframe.
        try:
            bus = can.Bus(bustype=self.bustype, channel=channel)  # type: ignore
            self.save(df, "play_cache.log")
            reader = LogReader("play_cache.log")
            in_sync = MessageSync(reader)
            for m in in_sync:
                if m.is_error_frame:
                    continue
                bus.send(m)
        except Exception as e:
            self.error(e)

    def playmsg(self, channel, canmsg): #option to play a particular packet.
        bus = can.Bus(bustype=self.bustype, channel=channel)  # type: ignore
        t = canmsg.split("#")
        hdata = t[1]
        if len(hdata) % 2 == 1:
            hdata = "0" + hdata
        data = []
        for i in range(0, len(hdata), 2):
            data.append(int("0x" + hdata[i : i + 2], 16))
        m = can.Message(
            arbitration_id=int("0x" + t[0], 16), data=data, is_extended_id=False
        )
        bus.send(m)

    def sql(self, query): #runs an sql query.
        try:
            df = ps.sqldf(query, self.variables)
            return df
        except Exception as e:
            self.error(e)

    def download(self,filename): #downloads files to bot operating device.
        try:
            if self.telegram:
                self.bot.send_document(chat_id=self.chat_id, document=open(filename, "rb"))  # type: ignore
            else:
                self.error("This function can only be used in Telegram")
        except Exception as e:
            self.error(e)

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
            return eval(token, self.variables)
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

    def repl(self, code): #extracts passed command for executing it through different functions.
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
