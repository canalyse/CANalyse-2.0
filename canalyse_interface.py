import os
from rich.console import Console
from canalyse import Canalyse
import pyfiglet as pf
import json
import time
import asyncio
from telegram.ext import Application
from telegram.ext import MessageHandler, filters
from typing import Dict, List, Any


class Interface:
    def __init__(self, filename: str = "nav.json") -> None:
        self.filename: str = filename
        with open(self.filename) as file:
            self.menu: Dict[str, Any] = json.load(file)
        self.path: List[str] = []
        self.console: Console = Console()
        self.channel: str = self.menu["Settings"]["Communication channel"]
        self.bustype: str = self.menu["Settings"]["Communication Interface"]

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
            # Clear screen in a cross-platform way
            print("\n" * 50)  # Simple screen clearing
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
                print("\nExiting...")
                break
            except ValueError:
                print("Invalid option. Please enter a number.")
                time.sleep(1)
            except Exception as e:
                print(f"An error occurred: {e}")
                time.sleep(1)

    def execute(self, option: str) -> None:
        func = self.goto(self.path + [option])
        if func == "ide":
            self.ide()
        elif func == "telegram": 
            try:
                self.telegram()
            except Exception as e:
                print(f"Telegram error: {e}")
        elif func == "smartscan":
            self.smartscan()
        elif func == "fuzzer":
            self.fuzzer()
        elif func == "manual":
            self.manual()

        elif len(self.path) > 0:
            if self.path[-1] == "Settings":
                self.change_settings(option,func)
    
    def change_settings(self,option,func):
        print("\n" * 50)  # Clear screen
        self.header()
        print(f"{option} is set to : {func}")
        value = input(f"Change {option} to (default): ")
        if value and value != func:
            self.menu["Settings"][option] = value
            self.channel = self.menu["Settings"]["Communication channel"]
            self.bustype = self.menu["Settings"]["Communication Interface"]
            try:
                with open(self.filename, "w") as file:
                    json.dump(self.menu, file, indent=4)
                print("Settings updated successfully.")
            except Exception as e:
                print(f"Error saving settings: {e}")
        time.sleep(1)

    def manual(self):
        try:
            print("\n" * 50)  # Clear screen
            self.header()
            with open("manual.txt",'r') as file:
                print(file.read())
            input("Press Enter to continue...")
        except FileNotFoundError:
            print("Manual file not found.")
        except Exception as e:
            print(f"Error reading manual: {e}")
        time.sleep(1)
        
    def ide(self):
        print("\n" * 50)  # Clear screen
        self.header()
        with Canalyse(self.channel, self.bustype) as cn:
            history = []
            while True:
                try:
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
                        except Exception as e:
                            print(f"Error: {e}")
                except KeyboardInterrupt:
                    print("\nExiting IDE...")
                    break
                except EOFError:
                    break

    def smartscan(self):
        print("\n" * 50)  # Clear screen
        with Canalyse(self.channel, self.bustype) as cn:
            try:
                cn.smartscan()
            except Exception as e:
                print(f"Smart scan error: {e}")
        input("Press Enter to continue...")

    def fuzzer(self):
        print("\n" * 50)  # Clear screen
        self.header()
        with Canalyse(self.channel, self.bustype) as cn:
            while True:
                try:
                    code = input("Fuzzer> ")
                    if code.lower() in ["exit", "quit"]:
                        break
                    result = cn.repl(code)
                    if result is not None:
                        print(result)
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"Error: {e}")

    def telegram(self):
        print("\n" * 50)  # Clear screen
        self.header()
        apit = self.menu["Settings"]["API_Token"]
        if not apit or apit.strip() == "":
            print("Set API Token in settings first")
            time.sleep(2)
            return

        async def run_telegram():
            try:
                application = Application.builder().token(apit).build()
            except Exception as e:
                print(f"Invalid API Token: {e}")
                return

            cn = Canalyse(self.channel, self.bustype)
            cn.telegram = True
            history = []

            async def handle_message(update, context):
                code = update.message.text.lower().strip()
                chat_id = update.message.chat_id
                cn.chat_id = chat_id
                cn.bot = context.bot

                if code in ["close", "quit", "exit"]:
                    await context.bot.send_message(chat_id=chat_id, text="👋 Goodbye!")
                    await application.stop()
                    return

                print(f"Message received: {code}")
                try:
                    output = await asyncio.to_thread(cn.repl, code)
                    if cn.pending_download:
                        try:
                            await context.bot.send_document(chat_id=chat_id, document=open(cn.pending_download, "rb"))
                        except Exception as e:
                            await context.bot.send_message(chat_id=chat_id, text=f"❌ Error sending file: {e}")
                        finally:
                            cn.pending_download = None
                    if output is not None:
                        await context.bot.send_message(chat_id=chat_id, text=str(output))
                    elif cn.goterror:
                        await context.bot.send_message(chat_id=chat_id, text=f"❌ Error: {cn.errorreason}")
                    else:
                        await context.bot.send_message(chat_id=chat_id, text="✅ Done")
                    history.append(code)
                except Exception as e:
                    await context.bot.send_message(chat_id=chat_id, text=f"❌ Error: {str(e)}")

            application.add_handler(MessageHandler(filters.TEXT, handle_message))

            try:
                await application.run_polling()
            except Exception as e:
                print(f"Telegram polling error: {e}")

        try:
            asyncio.run(run_telegram())
        except KeyboardInterrupt:
            print("Telegram bot stopped")


def main():
    """Main entry point for CANalyse."""
    interface = Interface()
    interface.display()


if __name__ == "__main__":
    main()


