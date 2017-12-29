#!/usr/bin/python3

"""
OC_Hub

This application has the ability to perform the following tasks:
Display client information, open browsers, send client emails regarding server issues, send daily uptimes of servers,
restart receiver or feeder process, connect to a screen session, play live streams and update your time sheet.
"""

import os
import sys
import datetime
import calendar
import socket
import subprocess
import collections
import functools
import itertools
import webbrowser
import base64
import multiprocessing
import asyncio
import operator
import MySQLdb
import httplib2
import paramiko
import pygsheets
from concurrent import futures
from oauth2client import tools, file
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from apiclient import errors, discovery

__author__ = "Jasmine Pate"
__date__ = "September 2017"


class Menu:

    def __call__(self):
        return self.start_menu()

    def start_menu(self):
        self.clear()
        while True:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.display_menu())
            except RuntimeError:
                continue

    @asyncio.coroutine
    def format_options(self, options):
        """
        Display menu and prompt user to make a selection.
        """
        menu_options = collections.OrderedDict()
        for lino, client in enumerate(options, start=1):
            print("{}. {}".format(lino, client))
            menu_options[lino] = client

        try:
            ans = input(">>>")
            choice = menu_options[int(ans)]
            self.clear()
            return choice

        except KeyboardInterrupt:
            sys.exit(0)
        except (KeyError, ValueError):
            print("Invalid entry. Please enter the corresponding number. \n")
            return self.format_options(options)

    @asyncio.coroutine
    def display_menu(self):
        print("********** OCHub ************")
        menu = collections.OrderedDict([("Display client information", self.display_client_info),
                                        ("Open a webpage", self.open_webpage),
                                        ("Send uptimes", Uptimes()),
                                        ("Send an error report", self.error_report),
                                        ("Play streams", self.play_streams),
                                        ("Restart receiver or feeder", self.restart),
                                        ("Start screen session", self.start_screens),
                                        ("Submit time sheet", self.time_sheet),
                                        ("Exit", sys.exit)])
        choice = yield from self.format_options(menu)
        if choice:
            self.clear()
            try:
                yield from menu[choice]()
            except TypeError:
                return None

    @classmethod
    def clear(cls):
        os.system("clear")

    def return_to_menu(self, func):
        """
        Return to main or submenu.
        """
        ans = input("Return to main menu? \n >>>")
        self.clear()
        if ans.lower() == "yes":
            return None
        else:
            asyncio.async(func())

    @asyncio.coroutine
    def display_client_info(self):
        print("Select client who information you would like to display.")
        names = GetClient(attr="Name")
        add_to_menu = {"Return to main menu": None}
        menu = itertools.chain(names, add_to_menu)
        client = yield from self.format_options(menu)

        if client in add_to_menu:
            return None

        info = GetClient(client)
        for line in info:
            print(line)
        self.return_to_menu(self.display_client_info)

    @asyncio.coroutine
    def open_webpage(self):
        print("Select the webpage you will like to open:")
        pages = collections.OrderedDict([("SL Broadcaster", "http://sl01.oneconnxt.com:4444/index.html"),
                                         ("NY Broadcaster", "http://ny01.oneconnxt.com:4444/index.html"),
                                         ("LO Broadcaster", "http://lo01.oneconnxt.com:4444/index.html"),
                                         ("TMS", "http://tms.oneconnxt.com"),
                                         ("OC Wiki", "http://sl03.oneconnxt.com/mediawiki/index.php/Main_Page"),
                                         ("Gmail", "http://www.gmail.com"),
                                         ("Return", None)])
        page = yield from self.format_options(pages)
        url = pages.get(page)
        if url:
            print("Opening page stand by..")
            webbrowser.open(url)

            self.return_to_menu(self.open_webpage)
        else:
            return None

    @asyncio.coroutine
    def error_report(self):
        print("Choose the client to send an error report to:")
        names = GetClient(attr="Name")
        add_to_menu = collections.OrderedDict([("Return to main menu", None)])
        menu = itertools.chain(names, add_to_menu)
        get_name = yield from self.format_options(menu)

        if get_name in add_to_menu:
            return None

        client = GetClient(get_name)
        system = client.Type.capitalize(), client.Code

        print("What problem are you having?")
        menu = collections.OrderedDict([("Offline", "{} {} is offline could you please make sure it is powered on "
                                                    "and connected to the network?".format(*system)),
                                        ("Dropping Packets", "{} {} is dropping a large amount of packets. Could "
                                                             "you please check the signal?".format(*system)),
                                        ("Back to previous screen", "Back")])
        error = yield from self.format_options(menu)

        if menu[error] is "Back":
            return self.error_report()
        else:
            error = menu.get(error)
            textfile = os.path.join(os.path.dirname(__file__), "error.py")
            signature = "Thank you, \nJasmine \nOneConnxt Support"

            with Emails(textfile, client.Name, uptimes=False) as mail:
                msg = "{0} \n\n{1}".format(error, signature)
                mail.write(msg)

    @asyncio.coroutine
    def play_streams(self):
        stream = GetClient(attr="Stream")
        code = GetClient(attr="Code")
        add_to_menu = collections.OrderedDict([("Start a stream that's not in the list", "url"),
                                               ("Play All", "play all"),
                                               ("Return to main menu", None)])
        menu = itertools.chain(stream, add_to_menu)
        print("Select a stream or play all:")
        play = yield from self.format_options(menu)

        if play in add_to_menu and add_to_menu[play] is None:
            return None
        elif play in stream:
            url = stream[play]
            send_code = code[play]
            PlayStream(url, send_code)()
        elif play == "Play All":
            PlayStream(stream, code)()
        else:
            PlayStream(None)()

    @asyncio.coroutine
    def restart(self):
        names = GetClient(attr="Name")
        add_to_dict = collections.OrderedDict([("Return to main menu", None)])
        menu = itertools.chain(names, add_to_dict)

        print("Restart a receiver or feeder. Select a client:")
        server = yield from self.format_options(menu)
        if server in add_to_dict:
            return None

        server = GetClient(server)
        receiver = "sudo /etc/init.d/oneconnxtreceiver restart"
        feeder = "sudo /etc/init.d/oneconnxtfeeder restart"
        restart_type = feeder if server.Type == "encoder" else receiver

        print("Restarting process stand by...")
        stdout = SshMachine(server.Ip, restart_type, server.Code)()
        if stdout is not None:
            print(str(stdout))

        self.return_to_menu(self.restart)

    @asyncio.coroutine
    def start_screens(self):
        decoders24 = itertools.takewhile("24 hour decoder", GetClient(attr="Special"))
        server = GetClient(attr="Ip")
        add_to_menu = collections.OrderedDict([("Start screen session on all 24 hour decoders", "decoders"),
                                               ("Return to main menu", None)])
        menu = itertools.chain(server, add_to_menu)
        print("Please make a selection:")
        choice = yield from self.format_options(menu)

        if choice in add_to_menu and add_to_menu[choice] is None:
            return None
        elif choice in server:
            server = GetClient(choice)
            info = [[server.Ip, server.Type]]
            Screens(info)()
        else:
            info = [[x.Ip, x.Type] for x in decoders24]
            Screens(info)()
        self.return_to_menu(self.start_screens)

    @asyncio.coroutine
    def time_sheet(self):
        print("Select the current pay period")
        payperiod = [(9, 22), (23, 8)]
        payperiod = yield from self.format_options(payperiod)
        weekdays = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
        process = collections.OrderedDict()

        for week in range(3):
            print("Enter work hours for week {}".format(week+1))
            for day in weekdays:
                time = input("{}:".format(day))
                time = time.split("-")
                try:
                    process[day].append(time)
                except KeyError:
                    process[day] = [time]
            self.clear()
        TimeSheet(payperiod, process)()


class GetClient:
    """
    Get client information from database. Use attribute access to select individual client information,
    display all client information by iterating over the object and create a dict compose of a specific attribute from
    all clients.

    >>> x = GetClient("Test2")

    >>> for i in x:
    ...     print(i)
    Name: Test2
    Server: decoder
    Code: 678
    Email: jasminepate57@gmail.com
    Phone_Number: 4047844110
    Ip_address: 34.230.3.156
    Specials: 24 hour decoder
    Stream: sl01.oneconnxt.com:7777/OC7382.flv

    >>> x.Ip
    34.230.3.156

    >>> x.Email
    jasminepate57@gmail.com

    >>> x.Phone
    4047844110

    >>> x.Name
    Test2

    >>> x.Server
    decoder

    >>> x.Special
    24 hour decoder

    >>> x.Stream
    sl01.oneconnxt.com:7777/OC7382.flv

    >>> ip = GetClient(attr="Ip")

    >>> for i in ip:
    ...     print(i)
    52.91.67.108
    34.230.3.156
    54.65.144.5

    >>> len(ip)
    3

    >>> ip
   {'Test': '54.65.144.5', 'Test2': '52.91.67.108', 'Test3': '34.230.3.156'}

    >>> ip["Test2"]
    52.91.67.108

    >>> ip.values()
    dict_values([54.65.144.5, 52.91.67.108, 34.230.3.156])
    """

    def __init__(self, client=None, attr=None):
        self._client = client
        self.data = None
        self.storage = {}

        if attr:
            self.fill_dict(attr)

    @functools.lru_cache()
    def __getattr__(self, item):
        if item:
            try:
                return getattr(self.get_info(), item)
            except AttributeError as err:
                print("That attribute does not exist", err)

    def __iter__(self):
        if self.storage:
            return iter(self.storage)
        return self.category()

    def __getitem__(self, item):
        return self.storage[item]

    def __setitem__(self, **kwargs):
        for key, value in kwargs:
            self.storage[key] = value

    def __len__(self):
        return len(self.storage)

    def values(self):
        return self.storage.values()

    def from_database(self, read):
        db = MySQLdb.connect("localhost", "root", "Kasmin200", "OneConnxt")
        cursor = db.cursor()
        cursor.execute(read)
        results = cursor.fetchall()
        return results

    def get_info(self):
        """
        :return: Data fetched the MySQL database is returned in a named tuple.
        """
        organize = collections.namedtuple("organize", "Name Type Code Email Phone Ip Special Stream")
        read = "select * from Clients where Name='{}';".format(self._client)

        try:
            results = self.from_database(read)
            data = [results[0][i] for i in range(0, len(results[0]))]
            data = organize(*data)
            return data

        except MySQLdb.Error as err:
            print("Unable to connect and fetch data from database", err)
            sys.exit()

    def fill_dict(self, attribute):
        read = "select Name from Clients;"
        results = self.from_database(read)
        data = [results[i][0] for i in range(0, len(results))]

        with futures.ThreadPoolExecutor(3) as execute:
            process = execute.map(GetClient, sorted(data))
        for i, j in zip(sorted(data), process):
            self.storage[i] = getattr(j, attribute)
        return self.storage

    def category(self):
        rows = ("Name:", "Server:", "Code:", "Email:", "Phone_Number:", "Ip_address:", "Specials:", "Stream:")
        client = self.get_info()
        information = (" ".join(i) for i in zip(rows, client))
        return information


class SshMachine:
    """
    SSH into servers and run a command.

    >>> SshMachine("54.265.21.5", "cat /proc/uptime", "1173")()
    100045.53 172430.36

    >>> SshMachine("54.265.21.5", "screen -ls")()
    No Sockets found in /var/run/screen/S-user.

    >>> SshMachine("54.265.21.5", "sudo /etc/init.d/oneconnxtfeeder restart", "1084")()
    stopping service..
    starting service..
    """

    def __init__(self, address, command, code=None):
        self.address = address
        self.command = command
        self.code = code

    def __call__(self):
        return self.ssh_into_machine()

    def ssh_into_machine(self):
        port = 22
        username = "ec2-user"
        password = ""

        try:
            ssh = paramiko.SSHClient()
            key = paramiko.RSAKey.from_private_key_file("/home/user/Downloads/OC.pem")
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy)
            ssh.connect(self.address, port, username, password, key, timeout=5)
            stdin, stdout, stderr = ssh.exec_command(self.command)
            return stdout.read().decode("ascii")
        except socket.timeout:
            print("Server {} Offline".format(self.code))


class Emails:
    """
    Context Manager used to send secure emails using Google API.

    >>> with Emails("uptimes.py", "Test") as send:
    ...     send.write("uptimes")

    >>> with Emails("error.py", "Test", uptimes=False) as send:
    ...     send.write("error")
    """

    def __init__(self, textfile, client=None, uptimes=True):
        self._client = GetClient(client)
        self._textfile = os.path.join(os.path.dirname(__file__), textfile)
        self._uptimes = uptimes

    def __enter__(self):
        self.open_file = open(self._textfile, "w+")
        return self.open_file

    def get_credentials(self):
        """
        Authenticate access to Gmail API.
        """
        scopes = 'https://www.googleapis.com/auth/gmail.send'
        client_secret_file = 'client_secret.json'
        application_name = 'Gmail API Python Send Email'
        home_dir = os.path.expanduser('~')
        credential_dir = os.path.join(home_dir, '.credentials')

        if not os.path.exists(credential_dir):
            os.makedirs(credential_dir)
        credential_path = os.path.join(credential_dir, 'sendEmail.json')
        store = file.Storage(credential_path)
        credentials = store.get()

        if not credentials or credentials.invalid:
            flow = self._client.Name.flow_from_clientsecrets(client_secret_file, scopes)
            flow.user_agent = application_name
            credentials = tools.run_flow(flow, store)
            print('Storing credentials to ' + credential_path)
        return credentials

    def send_message(self, service):
        sender = "jpate@gmail.com"

        if self._uptimes:
            receiver = "engineering@gmail.com"
            subject = "Asset Uptimes"
        else:
            receiver = self._client.Email
            subject = "{self._client.Type} {self._client.Code}".format(**locals())

        self.open_file.seek(0)
        contents = self.open_file.read()
        print(contents, "\n\n\n", "-" * 50)
        answer = input("Do you want to send the email? \n>>>>")

        if answer.lower() == "yes":
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = sender
            msg['To'] = receiver
            msg["reply-to"] = sender
            msg.attach(MIMEText(contents))
            message = {'raw': (base64.urlsafe_b64encode(msg.as_bytes()).decode())}
        else:
            print("Email canceled by user.")
            Menu.clear()
            return None

        try:
            send_message = (service.users().messages().send(userId="me", body=message))
            return send_message
        except errors.HttpError as error:
            print('An error occurred: %s' % error)
            return "Error"

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            credentials = self.get_credentials()
            http = credentials.authorize(httplib2.Http())
            service = discovery.build('gmail', 'v1', http=http)
            self.send_message(service).execute()
            self.open_file.close()
        except Exception:
            return None
        print("Email was sent successfully")


class Uptimes:
    """
    SSH into all servers to gather uptimes.
    """
    def __init__(self):
        self.servers = GetClient(attr="Ip")
        self.codes = GetClient(attr="Code")

    def __call__(self):
        return self.compose_email()

    @asyncio.coroutine
    def get_uptimes(self, server, code):
        stdout = SshMachine(server, "cat /proc/uptime", code)()
        if stdout:
            return str(stdout)

    @asyncio.coroutine
    def process_times(self, server, code):
        """
        Format raw uptimes.
        :return: Uptime is returned, 1 day if uptime is less than 24 hours, calculated number of days otherwise.
        """
        def get_time():
            nonlocal time
            t = time.split(" ")
            time = int(functools.reduce(operator.floordiv, [float(t[0]), 60, 60, 24]))
            if time == 0:
                time = "1 day"
            else:
                time = "{0} {1} days".format(code, time)
            return time

        time = yield from self.get_uptimes(server, code)
        if time:
            uptime = get_time()
            print("Uptime gathered for {}".format(code))
            return uptime

    def compose_email(self):
        textfile = os.path.join(os.path.dirname(__file__), "uptimes.py")
        time = [self.process_times(i, j) for i, j in zip(self.servers.values(), self.codes.values())]
        print("Gathering report... Stand by")

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            process_all = asyncio.wait(time)
            results, _ = loop.run_until_complete(process_all)
            loop.close()

            with Emails(textfile) as mail:
                mail.write("I'm in the machines, OC Skype, and have caught up on emails and Skype chat. \n")
                for uptime in results:
                    if uptime.result() is not None:
                        Menu.clear()
                        mail.write("\n" + uptime.result())
        except RuntimeError:
            return None


class PlayStream:
    """
    Play live streams.
    >>> PlayStream("http://getstream.flv", "1083")()
    starting stream

    >>> streams = GetClient(attr="Stream")
    >>> ip = GetClient(attr="Ip")
    >>> PlayStream(streams, ip)()
    Plays all available streams

    >>> PlayStream("http://getstream.flv")()
    Plays a stream that's not listed in the menu.

    >>>PlayStream("http://getstream.flv")()
    Stream {} is unavailable at this time.

    >>> PlayStream("www.getstream.com")()
    Invalid stream, please enter a flash url.
    Ex. 'http://startstream.flv'
    """

    def __init__(self, stream=None, code=None):
        if stream is None:
            stream = input("Enter the flash url or 'exit' to return. \n >>>")
        self.stream = stream
        self.code = code

    def __call__(self):
        if isinstance(self.stream, GetClient):
            return self.play_all()
        else:
            return self.start_stream()

    def open_video(self, code, url):
        print("Starting stream {} stand by... \n".format(code))
        sp = subprocess.PIPE
        play_video = ["mplayer", "-really-quiet", "-title", code, url]
        subprocess.call(play_video, stdin=sp, stdout=sp, stderr=sp)

    def start_stream(self):
        if self.stream == "exit".lower():
            return None

        url = self.stream
        if url.endswith(".flv"):
            start = url.rfind("/") + 1
            end = url.find(".flv")
            basename = url[start:end]
            self.code = basename.strip(".flv")
            p = multiprocessing.Process(target=self.open_video, args=[self.code, url])
            p.start()
        else:
            Menu.clear()
            print("{} is an invalid address. Please enter a flash url."
                  "\nExample:'http://playstream.flv' ".format(self.stream))
            PlayStream(None)()

    def play_all(self):
        for code, video in zip(self.code, self.stream):
            video = self.stream[video]
            p = multiprocessing.Process(target=self.open_video, args=[code, video])
            p.start()


class Screens:
    """
    Start screen session on one or many servers.

    >>> Screens([192.8.0.12, "encoder"])()
    Connecting to screen session...

    >>> Screens([192.0.2.32, "decoder"])()
    No screen session detected.
    Starting and connecting to screen session..

    >>> Screens([192.54.12.1, "decoder"])()
    Could not connect to screen, server is offline.
    """
    def __init__(self, info):
        """
        :param info: Type list that contain the ip address and server type of the selected server(s).
        """
        self.info = info

    def __call__(self):
        return self.play_all()

    @asyncio.coroutine
    def check_status(self, ip):
        response = subprocess.run(["ping", "-c2", ip], stdout=subprocess.PIPE)
        return True if response.returncode == 0 else False

    @asyncio.coroutine
    def check_screen(self, ip, server_type):
        status = yield from self.check_status(ip)
        if status:
            script = "./encode" if server_type == "encoder" else "./decode"
            result = SshMachine(ip, command="screen -ls")
            return script, str(result)

    @asyncio.coroutine
    def start_session(self, ip, server_type):
        """
        Start bash shell and run commands to connect to screen. If a session is not running the script command will
        execute and the screen will be connected to.
        """
        try:
            script, result = yield from self.check_screen(ip, server_type)

            if result.startswith("There is a screen"):
                print("Connecting to screen session..")
                os.system("gnome-terminal -e 'bash -c \"cd /home/user/Downloads && "
                          "ssh -i OC.pem user@{} && screen -x oc; bash\" '".format(ip))
            else:
                print("No screen session detected. \nStarting and connecting to screen session..")
                os.system("gnome-terminal -e 'bash -c \"cd /home/user/Downloads && "
                          "ssh -i OC.pem ec2-user@{0} && cd /Scripts && {1}; bash\" '".format(ip, script))
        except TypeError:
            print("Could not connect to screen, server is offline.")

    def play_all(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        run = [self.start_session(x, y) for x, y in self.info]
        wait_coro = asyncio.wait(run)

        try:
            loop.run_until_complete(wait_coro)
        except RuntimeError:
            return None


class TimeSheet:
    """
    Open contractor invoice and update time sheet.

    >>>TimeSheet((9,22), [["11pm", "9am"], ["12am", "3pm"], ["5pm", "1am"]])
    Processing time sheet stand by...
    ***
    ***
    ***
    Time sheet is complete.
    """

    def __init__(self, p_period, p_times):
        self.date = datetime.datetime.today()
        self.p_period = p_period
        self.p_times = p_times

    def __call__(self):
        return self.fill_cells()

    def authorize(self):
        temp = pygsheets.authorize()
        open_temp = temp.open('Test_sheet')
        invoice = open_temp.sheet1
        return invoice, open_temp

    def pay_range(self):
        due = self.p_period
        year = self.date.year
        month = self.date.month
        end = datetime.date(year, month, due[1])
        if due[0] == 23:
            month -= 1
        start = datetime.date(year, month, due[0])
        invoice_p = self.date.strftime("%B {due[0]}-{due[1]}, %Y".format(**locals()))
        return start, end, invoice_p

    def cells(self):
        weekdays = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        wkds = collections.OrderedDict()
        col = "B"
        for day in weekdays:
            row = 8
            cells = [col + str(row)]
            for cycle in range(2):
                row = row + 6
                cells.append(col + str(row))
            col = chr(ord(col) + 2)
            wkds[day] = cells
        return wkds

    def fill_cells(self):
        wkds = self.cells()
        sheet, open_temp = self.authorize()
        start, finish, invoice_p = self.pay_range()

        print("Processing time sheet stand by...")
        sheet.update_cell('H2', invoice_p)

        while start != finish:
            start_day = calendar.day_name[start.weekday()]
            try:
                fill = wkds[start_day].pop(0)
                content = self.p_times[start_day].pop(0)
            except IndexError:
                pass

            in_time = fill[0] + str(int(fill[1:]) + 1)
            out_time = fill[0] + str(int(fill[1:]) + 2)

            try:
                if content != ['']:
                    begin, end = content
                    value = str(start.strftime("%A, %x"))
                    work_times = "{}:{}".format(fill, out_time)
                    sheet.update_cells(work_times, [[value], [begin], [end]])
                    print("***")
                else:
                    x = "{}:{}".format(in_time, out_time)
                    sheet.update_cells(x, [[''], ['']])
            except errors.HttpError as err:
                print(err)
            start = start + datetime.timedelta(days=1)
        print("Time sheet is complete.")


def main():
    x = Menu()
    x()

if __name__ == "__main__":
    main()
