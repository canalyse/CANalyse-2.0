import os
from rich.console import Console
from canalyse import Canalyse
import pyfiglet as pf
import json
import time
from telegram import Bot


class Interface:
    def __init__(self, filename: str = "nav.json") -> None:
        self.filename = filename
        with open(self.filename) as file:
            self.menu = json.load(file)
        self.path: list[str] = []
        self.console = Console()
        self.channel = self.menu["Settings"]["Communication channel"]
        self.bustype = self.menu["Settings"]["Communication Interface"]

    def header(self) -> None:
        print("")
        result = pf.figlet_format("CANalyse", font="slant")
        print(result)
        print("")

    def footer(self) -> None:
        print("")

    def goto(self, path):
        path = path.copy()
        curr_page = self.menu
        while len(path) > 0:
            curr_page = curr_page[path[0]]
            del path[0]
        return curr_page

    def control_panel(self) -> str:
        option: int = int(input("---> "))
        options = self.goto(self.path)
        if option == len(options) + 1:
            return "back"
        return list(options.keys())[option - 1]

    def page(self) -> None:
        options = list(self.goto(self.path).keys())
        for i in range(len(options)):
            print(f"{i+1}) {options[i]}")
        back = "Back"
        if len(self.path) == 0:
            back = "Exit"
        self.console.print(f"{len(options)+1}) {back}", style="bold red")

    def display(self) -> None:
        while True:
            print("\033c", end="")
            self.header()
            self.page()
            self.footer()
            try:
                option = self.control_panel()
                if option == "back":
                    if len(self.path) > 0:
                        self.path.pop()
                    else:
                        print("Exiting...")
                        break
                elif type(self.goto(self.path + [option])) == str:
                    self.execute(option)
                else:
                    self.path.append(option)
            except KeyboardInterrupt:
                break
            except Exception:
                continue

    def execute(self, option: str) -> None:
        func = self.goto(self.path + [option])
        if func == "ide":
            self.ide()
        elif func == "telegram": 
            try:
                self.telegram()
            except:
                pass
        elif func == "smartscan":
            self.smartscan()
        elif func == "manual":
            self.manual()

        elif len(self.path) > 0:
            if self.path[-1] == "Settings":
                self.change_settings(option,func)
    
    def change_settings(self,option,func):
        print("\033c", end="")
        #print("\033c", end="")
        self.header()
        print(f"{option} is set to : {func}")
        value = input(f"Change {option} to (default): ")
        if value != func and value != None and value != "":
            self.menu["Settings"][option] = value
            self.channel = self.menu["Settings"]["Communication channel"]
            self.bustype = self.menu["Settings"]["Communication Interface"]
            j = json.dumps(self.menu,indent=4)
            with open(self.filename, "w+") as file:
                file.write(j)

    def manual(self):
        try:
            print("\033c", end="")
            #print("\033c", end="")
            self.header()
            with open("manual.txt",'r+') as file:
                input(file.read())
        except:
            pass
        
    def ide(self):
        print("\033c", end="")
        self.header()
        with Canalyse(self.channel, self.bustype) as cn:
            history = []
            while True:
                code = input("###--> ")
                code = code.lower().strip()
                if code in ["close", "quit", "exit"]:
                    break
                else:
                    try:
                        output = cn.repl(code)
                        if output is not None:
                            print(output)
                        history.append(code)
                    except KeyboardInterrupt:
                        break
                    except Exception as e:
                        print(e)

    def smartscan(self):
        print("\033c", end="")
        with Canalyse(self.channel, self.bustype) as cn:
            cn.smartscan()
        pass

    def telegram(self):
        print("\033c", end="")
        self.header()
        apit = self.menu["Settings"]["API_Token"]
        try:
            bot = Bot(token=apit)
        except:
            if apit == "":
                print("Set API Token in settings")
            else:
                print("Invalid API Token")
            time.sleep(1)
            return None

        with Canalyse(self.channel, self.bustype) as cn:
            cn.telegram = True
            history = []
            msg = self.get_new_message(bot)
            update_id = msg.update_id
            chat_id = msg.message.chat_id
            cn.bot = bot  # type: ignore
            while True:
                print("hi")
                msg = self.get_new_message(bot, update_id)
                update_id = msg.update_id
                code = msg.message.text
                chat_id = msg.message.chat_id
                cn.chat_id = chat_id
                
                code = code.lower().strip()  # type: ignore
                if code in ["close", "quit", "exit"]:
                    bot.send_message(
                        chat_id=chat_id, text="👋"
                    )
                    break
                else:
                    print("Message recieved : "+code)
                    try:
                        output = cn.repl(code)
                        if output is not None:
                            print("Output : "+str(output))
                            bot.send_message(
                                chat_id=chat_id, text=str(output)
                            )
                        elif cn.goterror:
                            print("Output : "+"👎 ERROR")
                            bot.send_message(
                                chat_id=chat_id, text="👎 ERROR: "+str(cn.errorreason)
                            )
                        else:
                            print("Output : "+"👍")
                            bot.send_message(
                                chat_id=chat_id, text="👍"
                            )

                        history.append(code)
                    except KeyboardInterrupt:
                        break
                    except Exception as e:
                        bot.send_message(
                            chat_id=chat_id, text="👎 ERROR : "+str(e)
                        )

    def get_new_message(self,bot, update_id=None):
        while True:
            msg = bot.get_updates()[-1]
            try:
                if msg.update_id != update_id:
                    return msg
            except KeyboardInterrupt:
                bot.send_message(
                    chat_id=msg.chat_id, text="Closed in terminal,bye.."
                )


if __name__ == "__main__":
    interface = Interface()
    interface.display()
