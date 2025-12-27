import asyncio
from datetime import datetime, timezone
import ipaddress

from collections import deque

import pandas as pd

import os

import pathlib

import logging

from nicegui import app, ui

from lmp.util import Board, DeviceCommand
from lmp.firmware_log import FirmwareLog

from enum import Enum

EVENT_LOG_PORT = 1234

EVENT_LOG_FILE = ""

LOG_TABLE_SHEET = "Lookup Table"

class Log_Table:
    def __init__(self, table_path: pathlib.Path):
        self.table_path = table_path
        table_df = pd.read_csv(table_path)
        self.lookup_table = {}
        for _, row in table_df.iterrows():
            self.lookup_table[int(row["Number"])] = {"type": str(row["Type"]), "name": str(row["Name"]), "function": str(row["Function"]), "severity": str(row["Severity"]), "details": str(row["Note (optional)"])}
    
    def get_type(self, code: int):
        err = self.lookup_table.get(code)
        if(err != None):
            return err["type"]
        else:
            return None
        
    def get_name(self, code: int):
        err = self.lookup_table.get(code)
        if(err != None):
            return err["name"]
        else:
            return None
    
    def get_function(self, code: int):
        err = self.lookup_table.get(code)
        if(err != None):
            return err["function"]
        else:
            return None
        
    def get_severity(self, code: int):
        err = self.lookup_table.get(code)
        if(err != None):
            return err["severity"]
        else:
            return None
        
    def get_details(self, code: int):
        err = self.lookup_table.get(code)
        if(err != None):
            return err["details"]
        else:
            return None

class Event_Log_UI:
    def __init__(self, lookup_table: Log_Table = None):
        self.tables:list[ui.table] = []
        self.listener: Event_Log_Listener = None
        self.cur_id = 0
        self.lookup_table = lookup_table
    
    def display(self):
        ui.add_sass('''
                    .sticky-table
                        height: 500px
                        .q-table__top,
                        .q-table__bottom,
                        thead tr:first-child th
                            background-color: #2b2b2b
                            
                        th
                            font-size: 14px
                        thead tr th
                            position: sticky
                            z-index: 10
                        thead tr:first-child th
                            top: 0
                        tbody
                            scroll-margin-top: 48px
                    ''')
        ui.add_sass('''
                    .fullscreen
                        height: 100vw !important
                    ''')
        with ui.card().classes("w-1/2 bg-gray-900 border border-gray-700 p-6 pt-4 gap-2"): # REPLACE THE w-1/2 WITH w-full AFTER MERGING
            with ui.row().classes("w-full no-wrap"):
                ui.label("Event Log").classes("text-xl font-bold text-red-400")
                ui.space()
                ui.button("Clear", on_click=self.clear_log).props("outline").classes("self-center")
                ui.button(icon="fullscreen", on_click=lambda e: log_table.run_method("toggleFullscreen")).props("flat round dense size='20px'")
            columns = [
                {'name': 'msg', 'label': 'Message', 'field': 'msg', 'required': False, 'align': 'left', 'sortable': False, 'classes': 'max-w-70', 'headerClasses': 'max-w-70', 'style': "overflow: hidden;overflow-wrap: break-word;white-space: normal;"},
                {'name': 'board', 'label': 'Board', 'field': 'board', 'required': False, 'sortable': True, 'align': 'left'},
                {'name': 'timestamp', 'label': 'Timestamp', 'field': 'timestamp', 'required': False, 'sortable': True, 'align': 'left', 'sortOrder': 'da'},
                {'name': 'code', 'label': 'Code', 'field': 'code', 'required': False, 'sortable': True, 'align': 'left'},
                {'name': 'ip', 'label': 'IP Address', 'field': 'ip', 'required': False, 'sortable': True, 'align': 'left'},
                {'name': 'id', 'label': 'id', 'field': 'id', 'required': True, 'classes': 'hidden', 'headerClasses': 'hidden'},
                {'name': 'tooltip', 'label': 'tooltip', 'field': 'tooltip', 'required': False, 'classes': 'hidden', 'headerClasses': 'hidden'}
            ]
            log_table = ui.table(columns=columns, rows=[]).classes("w-full overflow-y-auto sticky-table").props("no-data-label hide-no-data dense table-header-class='size-xl'") # SET HEIGHT CORRECTLY IN SASS UP ABOVE AFTER MERGING
            log_table.pagination = {'sortBy': 'timestamp', 'rowsPerPage': 0, 'descending': True}
            log_table.add_slot('body-cell-msg', '''
                <q-td :props="props">
                    <q-tooltip v-if="props.row.tooltip" style="font-size: 12px;"
                    v-html="props.row.tooltip" style="max-width:75em"/>
                    {{ props.value }}
                </q-td>
            ''')
            log_table.add_slot('top-right', '''
                <q-btn
                    flat round dense
                    icon='fullscreen_exit'
                    @click="props.toggleFullscreen"
                    class="q-ml-md"
                    v-if="props.inFullscreen"
                    size="18px"
                />
            ''')
            self.tables.append(log_table)
    
    def clear_log(self, e = None):
        if(self.listener != None):
            self.listener.log_buffer.clear()
        
        for x in self.tables:
            x.rows = []
        
    def add_log(self, log: FirmwareLog, addr: ipaddress.IPv4Address = None, localtime: bool = True):
        time_str = None
        if(log.timestamp != None):
            timestamp = log.timestamp
            if(localtime):
                local_zone = datetime.now(timezone.utc).astimezone().tzinfo
                timestamp = timestamp.astimezone(local_zone)
            time_str = f"{timestamp.strftime("%b %d, %Y %I:%M:%S.")}{timestamp.microsecond // 1000} {timestamp.strftime("%p")} {timestamp.strftime("%Z")}"
            
            
        for x in self.tables:
            x.add_row({'msg': log.message, 'board': log.board.pretty_name if log.board != None else None, 'timestamp': time_str, 'code': log.status_code, 'ip': addr, 'id': self.cur_id, 'tooltip': self.generate_tooltip(log.status_code)})
        self.cur_id += 1

    def attach_listener(self, listener):
        self.listener = listener
        
    def generate_tooltip(self, code:int):
        if(code == None): return None
        if(self.lookup_table == None): return None
        error_name = self.lookup_table.get_name(code)
        error_type = self.lookup_table.get_type(code)
        error_severity = self.lookup_table.get_severity(code)
        error_details = self.lookup_table.get_details(code)
        if(error_name == None): return None
        tooltip_msg = f"Error {error_name}: Type - {error_type}, Severity - {error_severity}<br><br>{error_details}"
        return tooltip_msg

class Event_Log_Listener:
    def __init__(self):
        self.log_UIs:list[Event_Log_UI] = []
        self.transport = None
        self.log_buffer = deque(maxlen=100)
        log_setup = logging.getLogger('events')
        logdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        os.makedirs(logdir, exist_ok=True)
        log_file = os.path.join(logdir, "system-events.log") # TODO figure out logging location
        formatter = logging.Formatter('%(levelname)s: %(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p -')
        filehandler = logging.FileHandler(log_file, mode='a')
        filehandler.setFormatter(formatter)
        log_setup.setLevel(logging.INFO)
        log_setup.addHandler(filehandler)
        
    def attach_ui(self, ui: Event_Log_UI):
        self.log_UIs.append(ui)
        ui.attach_listener(self)
        for x in self.log_buffer:
            ui.add_log(x[0], x[1])
    
    async def open_listener(self):
        while True:
            try:
                loop = asyncio.get_event_loop()
                self.transport, self.handler = await loop.create_datagram_endpoint(self.create_protocol, ('0.0.0.0', EVENT_LOG_PORT), reuse_address=False, reuse_port=False)
            except Exception as err:
                print(f"Error opening log listener: {str(err)}")
                await asyncio.sleep(1)
                continue
            
            try:
                if(self.handler != None):
                    await self.handler.wait_for_close()
            except asyncio.CancelledError:
                print("Log listener cancelled.")
                break
            except Exception as e:
                print(f"Got exception: {e}")
                continue
    
    def create_protocol(self):
        return Event_Log_Protocol(self)
    
    def log_to_UIs(self, log: FirmwareLog, addr: ipaddress.IPv4Address):
        self.log_buffer.append((log, addr))
        for x in self.log_UIs:
            x.add_log(log, addr=addr, localtime=True)

class Event_Log_Protocol(asyncio.DatagramProtocol):
    def __init__(self, listener):
        super().__init__()
        self.listener: Event_Log_Listener = listener
        self.open = False
    
    def connection_made(self, transport):
        self.transport = transport
        self.open = True
        
    def datagram_received(self, data, addr):
        log = FirmwareLog.from_bytes(data)
        self.listener.log_to_UIs(log, addr[0])
        logging.getLogger("events").info(log.to_log() + f", IP: {addr[0]}")
        
    def connection_lost(self, exc):
        self.open = False
        
    async def wait_for_close(self):
        while self.open:
            await asyncio.sleep(0.5)