import asyncio
import copy
import datetime
import ipaddress
import traceback

from nicegui import run, ui

from lmp.firmware_log import FirmwareLog
from lmp.util import Board

from .eeprom_generate import (
    PT,
    TC,
    VLV,
    TCGain,
    ValveVoltage,
    configure_bb,
    configure_fc,
    configure_fr,
)
from .hydrant_error_ui import EventLogListener
from .hydrant_system_config import (
    DEFAULT_BB1_IP,
    DEFAULT_BB2_IP,
    DEFAULT_BB3_IP,
    DEFAULT_FC_IP,
    DEFAULT_FR_IP,
    DEFAULT_GSE_IP,
    DEFAULT_PT_MAX,
    DEFAULT_PT_OFFSET,
    DEFAULT_PT_RANGE,
    DEFAULT_TC_GAIN,
    DEFAULT_VALVE_ENABLED,
    DEFAULT_VALVE_VOLTAGE,
    ICD,
    ICDException,
    NUM_BB_PTs,
    NUM_BB_TCs,
    NUM_BB_VLVs,
    NUM_FC_PTs,
    NUM_FC_TCs,
    NUM_FC_VLVs,
    configure_ebox,
)

progress_lookup = {
    -1: {"name": "close", "color": "red"},
    0: {"name": "", "color": "black"},
    1: {"name": "check", "color": "green"},
}

EEPROM_RESPONSE_TIMEOUT = 1  # seconds


class IPAddressUI:
    def __init__(self, initial: ipaddress.IPv4Address, name: str):
        self.ip = initial
        with ui.row().classes("no-wrap items-end gap-1"):
            ui.label(name + ": ").classes("self-center")
            oct0 = (
                ui.input(
                    value=self.get_octet(0),
                    on_change=IPUIOctetHandle(self, 0),
                )
                .props("dense outlined")
                .classes("min-w-[4em] w-[4em]")
            )
            ui.label(".")
            oct1 = (
                ui.input(
                    value=self.get_octet(1),
                    on_change=IPUIOctetHandle(self, 1),
                )
                .props("dense outlined")
                .classes("min-w-[4em] w-[4em]")
            )
            ui.label(".")
            oct2 = (
                ui.input(
                    value=self.get_octet(2),
                    on_change=IPUIOctetHandle(self, 2),
                )
                .props("dense outlined")
                .classes("min-w-[4em] w-[4em]")
            )
            ui.label(".")
            oct3 = (
                ui.input(
                    value=self.get_octet(3),
                    on_change=IPUIOctetHandle(self, 3),
                )
                .props("dense outlined")
                .classes("min-w-[4em] w-[4em]")
            )

            self.octs = [oct0, oct1, oct2, oct3]

    def set_octet(self, octet_index: int, new_octet: int):
        if new_octet > 255 or new_octet < 0:
            raise ValueError("IP octet " + str(new_octet) + " not valid")
        ip_int = int(self.ip)
        ip_int &= ~(0xFF << (8 * (3 - octet_index)))
        ip_int |= new_octet << (8 * (3 - octet_index))
        self.ip = ipaddress.IPv4Address(ip_int)

    def get_octet(self, octet_index: int):
        ip_int = int(self.ip)
        return (ip_int >> (8 * (3 - octet_index))) & 0x000000FF

    def reset_octet(self, octet_index: int):
        self.octs[octet_index].value = self.get_octet(octet_index)

    def set_ip(self, ipaddr: ipaddress.IPv4Address):
        self.ip = ipaddr
        for x in range(4):
            self.octs[x].set_value(self.get_octet(x))


class IPUIOctetHandle:
    parent: IPAddressUI

    def __init__(self, base: IPAddressUI, octet_index: int):
        self.oct = octet_index
        self.parent = base

    def sanitize_octet(self, octet: str):
        if octet == "" or octet.isdigit():
            if int(octet) < 256 and int(octet) >= 0:
                return True
        return False

    def __call__(self, e):
        if e.value is int:
            return

        new_val = str(e.value)

        if new_val == "":
            ui.timer(0, lambda: e.sender.set_value(0), active=True, once=True)
            self.parent.set_octet(self.oct, 0)
            return
        elif new_val.isdigit():
            if int(new_val) < 256 and int(new_val) >= 0:
                self.parent.set_octet(self.oct, int(new_val))
                ui.timer(
                    0,
                    lambda: e.sender.set_value(self.parent.get_octet(self.oct)),
                    active=True,
                    once=True,
                )
                return

        ui.timer(
            0,
            lambda: e.sender.set_value(e.previous_value),
            active=True,
            once=True,
        )


class PTUI:
    def __init__(self, range: float, offset: float, max: float, name: str):
        self.range = range
        self.offset = offset
        self.max = max
        with ui.column().classes("w-full gap-1"):
            ui.label(name).classes("pb-1 pl-2")
            ui.separator()
            ui.number(label="Range", value=range).props(
                "filled dense"
            ).bind_value(self, "range")
            ui.number(label="Offset", value=offset).props(
                "filled dense"
            ).bind_value(self, "offset")
            ui.number(label="Max", value=max).props("filled dense").bind_value(
                self, "max"
            )

    def to_PT(self):
        return PT(self.range, self.offset, self.max)


class TCUI:
    def __init__(self, gain: int, name: str):
        self.gain = gain
        with ui.row().classes("w-full mx-auto no-wrap gap-1 items-center"):
            ui.label(name).classes("min-w-10")
            ui.select(
                [1, 2, 4, 8, 16, 32, 64, 128], value=gain, label="Gain"
            ).props("filled dense").classes("min-w-25").bind_value(self, "gain")

    def to_TC(self):
        return TC(TCGain.from_int(self.gain))


class ValveUI:
    def __init__(self, enabled: bool, voltage: int, name: str):
        self.voltage = voltage
        self.enabled = enabled
        with ui.column().classes("w-full gap-1"):
            ui.label(name).classes("pb-1 pl-2")
            ui.separator()
            # ui.checkbox("Enabled")
            ui.switch("Enabled", value=enabled).bind_value(self, "enabled")
            ui.select([12, 24], value=voltage, label="Voltage").props(
                "filled dense"
            ).classes("min-w-25").bind_value(self, "voltage")

    def to_VLV(self):
        if self.voltage == 12:
            return VLV(ValveVoltage.V12, self.enabled)
        elif self.voltage == 24:
            return VLV(ValveVoltage.V24, self.enabled)
        else:
            raise Exception("Voltage must be either 12v or 24v")


class FCConfigUI:
    def __init__(self):
        self.PTs: list[PTUI] = []
        self.TCs: list[TCUI] = []
        self.valves: list[ValveUI] = []
        with ui.column().classes("h-full w-full"):
            with ui.row().classes(
                "w-full mx-auto no-wrap flex items-stretch h-full"
            ):
                # PTs
                with ui.column().classes(
                    "border-1 p-2 border-gray-500 flex-1 basis-auto"
                ):
                    with ui.row().classes("w-full mx-auto no-wrap gap-3"):
                        for x in range(NUM_FC_PTs):
                            self.PTs.append(
                                PTUI(
                                    DEFAULT_PT_RANGE,
                                    DEFAULT_PT_OFFSET,
                                    DEFAULT_PT_MAX,
                                    "PT " + str(x + 1),
                                )
                            )
                # TCs
                with ui.column().classes(
                    "border-1 p-2 border-gray-500 gap-3 flex-1 basis-auto justify-center"
                ):
                    with ui.column().classes("w-full gap-3"):
                        for x in range(NUM_FC_TCs):
                            self.TCs.append(
                                TCUI(DEFAULT_TC_GAIN, "TC " + str(x + 1) + " ")
                            )
                # Valves
                with ui.column().classes(
                    "border-1 p-2 border-gray-500 flex-1 basis-auto"
                ):
                    with ui.row().classes("w-full mx-auto no-wrap gap-3"):
                        for x in range(NUM_FC_VLVs):
                            self.valves.append(
                                ValveUI(
                                    DEFAULT_VALVE_ENABLED,
                                    DEFAULT_VALVE_VOLTAGE,
                                    "Valve " + str(x + 1),
                                )
                            )
            with ui.row().classes(
                "w-full mx-auto no-wrap flex items-stretch h-full border-1 p-2 border-gray-500"
            ):
                # IP Addresses
                with ui.column().classes("w-full"):
                    with ui.column().classes("w-fit items-end"):
                        self.limewireIP = IPAddressUI(
                            DEFAULT_GSE_IP, "Limewire IP"
                        )
                        self.FCIP = IPAddressUI(
                            DEFAULT_FC_IP, "Flight Computer IP"
                        )
                with ui.column().classes("w-full"):
                    with ui.column().classes("w-fit items-end"):
                        self.BB1IP = IPAddressUI(
                            DEFAULT_BB1_IP, "Bay Board 1 IP"
                        )
                        self.BB2IP = IPAddressUI(
                            DEFAULT_BB2_IP, "Bay Board 2 IP"
                        )
                with ui.column().classes("w-full"):
                    with ui.column().classes("w-fit items-end"):
                        self.BB3IP = IPAddressUI(
                            DEFAULT_BB3_IP, "Bay Board 3 IP"
                        )
                        self.FRIP = IPAddressUI(
                            DEFAULT_FR_IP, "Flight Recorder IP"
                        )

    def restore_defaults(self):
        for x in self.PTs:
            x.range = DEFAULT_PT_RANGE
            x.offset = DEFAULT_PT_OFFSET
            x.max = DEFAULT_PT_MAX
        for x in self.TCs:
            x.gain = DEFAULT_TC_GAIN
        for x in self.valves:
            x.enabled = DEFAULT_VALVE_ENABLED
            x.voltage = DEFAULT_VALVE_VOLTAGE
        self.limewireIP.set_ip(DEFAULT_GSE_IP)
        self.FCIP.set_ip(DEFAULT_FC_IP)
        self.BB1IP.set_ip(DEFAULT_BB1_IP)
        self.BB2IP.set_ip(DEFAULT_BB2_IP)
        self.BB3IP.set_ip(DEFAULT_BB3_IP)
        self.FRIP.set_ip(DEFAULT_FR_IP)


class BBConfigUI:
    def __init__(self, num: int):
        self.bb_num = num
        self.PTs: list[PTUI] = []
        self.TCs: list[TCUI] = []
        self.valves: list[ValveUI] = []
        with ui.column().classes("h-full w-full"):
            # PTs
            with ui.row().classes(
                "w-full mx-auto no-wrap flex items-stretch h-full"
            ):
                with ui.column().classes(
                    "border-1 p-2 border-gray-500 flex-1 basis-auto"
                ):
                    with ui.row().classes("w-full mx-auto no-wrap gap-3"):
                        for x in range(NUM_BB_PTs):
                            self.PTs.append(
                                PTUI(
                                    DEFAULT_PT_RANGE,
                                    DEFAULT_PT_OFFSET,
                                    DEFAULT_PT_MAX,
                                    "PT " + str(x + 1),
                                )
                            )
            with ui.row().classes(
                "w-full mx-auto no-wrap flex items-stretch h-full"
            ):
                # TCs
                with ui.column().classes(
                    "border-1 p-2 border-gray-500 gap-3 flex-1 basis-auto justify-center"
                ):
                    with ui.row().classes("w-full mx-auto no-wrap"):
                        with ui.column().classes("w-full gap-3"):
                            for x in range(int(NUM_BB_TCs / 2)):
                                self.TCs.append(
                                    TCUI(
                                        DEFAULT_TC_GAIN,
                                        "TC " + str(x + 1) + " ",
                                    )
                                )
                        with ui.column().classes("w-full gap-3"):
                            for x in range(int(NUM_BB_TCs / 2), NUM_BB_TCs):
                                self.TCs.append(
                                    TCUI(
                                        DEFAULT_TC_GAIN,
                                        "TC " + str(x + 1) + " ",
                                    )
                                )
                # Valves
                with ui.column().classes(
                    "border-1 p-2 border-gray-500 flex-1 basis-auto"
                ):
                    with ui.row().classes("w-full mx-auto no-wrap gap-3"):
                        for x in range(NUM_BB_VLVs):
                            self.valves.append(
                                ValveUI(
                                    DEFAULT_VALVE_ENABLED,
                                    DEFAULT_VALVE_VOLTAGE,
                                    "Valve " + str(x + 1),
                                )
                            )
            with ui.row().classes(
                "w-full no-wrap justify-center h-full border-1 p-2 border-gray-500"
            ):
                # IP Addresses
                ui.space()
                if self.bb_num == 1:
                    self.BBIP = IPAddressUI(DEFAULT_BB1_IP, "Bay Board IP")
                elif self.bb_num == 2:
                    self.BBIP = IPAddressUI(DEFAULT_BB2_IP, "Bay Board IP")
                elif self.bb_num == 3:
                    self.BBIP = IPAddressUI(DEFAULT_BB3_IP, "Bay Board IP")
                ui.space()
                self.FCIP = IPAddressUI(DEFAULT_FC_IP, "Flight Computer IP")
                ui.space()

    def restore_defaults(self):
        for x in self.PTs:
            x.range = DEFAULT_PT_RANGE
            x.offset = DEFAULT_PT_OFFSET
            x.max = DEFAULT_PT_MAX
        for x in self.TCs:
            x.gain = DEFAULT_TC_GAIN
        for x in self.valves:
            x.enabled = DEFAULT_VALVE_ENABLED
            x.voltage = DEFAULT_VALVE_VOLTAGE
        self.FCIP.set_ip(DEFAULT_FC_IP)
        if self.bb_num == 1:
            self.BBIP.set_ip(DEFAULT_BB1_IP)
        elif self.bb_num == 2:
            self.BBIP.set_ip(DEFAULT_BB2_IP)
        elif self.bb_num == 3:
            self.BBIP.set_ip(DEFAULT_BB3_IP)


class FRConfigUI:
    def __init__(self):
        with ui.column().classes("h-full w-full"):
            with ui.row().classes(
                "w-full no-wrap justify-center h-full border-1 p-2 border-gray-500"
            ):
                # IP Addresses
                ui.space()
                self.FRIP = IPAddressUI(DEFAULT_FR_IP, "Flight Recorder IP")
                ui.space()
                self.FCIP = IPAddressUI(DEFAULT_FC_IP, "Flight Computer IP")
                ui.space()

    def restore_defaults(self):
        self.FCIP.set_ip(DEFAULT_FC_IP)
        self.FRIP.set_ip(DEFAULT_FR_IP)


class SystemConfigUI:
    def __init__(self, parentUI, log_listener: EventLogListener):
        self.log_listener = log_listener
        self.base = parentUI
        self.configure_ebox = False
        self.configure_fc = False
        self.configure_bb1 = False
        self.configure_bb2 = False
        self.configure_bb3 = False
        self.configure_fr = False
        self.ICD_config = None
        self.ebox_loading = False
        self.fc_loading = False
        self.bb1_loading = False
        self.bb2_loading = False
        self.bb3_loading = False
        self.fr_loading = False
        with ui.card().classes(
            "w-full bg-gray-900 border border-gray-700 p-6 h-full"
        ):
            HelpTooltip("""Configure individual devices or the entire system.<br><br>
                        Uploading the ICD will allow you to configure the EBox, and
                        modifies the board configurations parameters below.<br>
                        Regardless of whether you upload the ICD or not, you must still click the "Write Configuration" button to start the
                        configuration process.<br><br>
                        Board configuration upload IP (TFTP IP) does not get updated by
                        the ICD and must be modified appropriately for the current system.
                        """)
            with ui.row().classes("w-full mx-auto no-wrap"):
                with ui.column().classes():
                    ui.label("SYSTEM CONFIG").classes(
                        "text-xl font-bold text-white mb-4"
                    )
                    self.ICD_file = ui.upload(
                        label="Load from ICD", on_upload=self.handle_ICD
                    ).props(
                        "accept=.xlsx no-thumbnails no-icon auto__false color=lime text-color=black"
                    )
                    self.config_button = (
                        ui.button(
                            "Write Configuration",
                            color="orange",
                            on_click=self.warn_write_config,
                        )
                        .classes("text-base w-full")
                        .props("text-color=black")
                    )
                with ui.column().classes("gap-0 pl-10"):
                    self.all_select = (
                        ui.checkbox()
                        .classes("h-11")
                        .on("click", self.handle_all_check)
                    )
                    self.ebox_select = (
                        ui.checkbox("EBox")
                        .classes("h-8")
                        .on("click", self.handle_device_select)
                        .bind_value(self, "configure_ebox")
                        .bind_enabled_from(
                            self, "ICD_config", backward=self.handle_ebox_select
                        )
                    )
                    self.fc_select = (
                        ui.checkbox("Flight Computer")
                        .classes("h-8")
                        .on("click", self.handle_device_select)
                        .bind_value(self, "configure_fc")
                    )
                    self.bb1_select = (
                        ui.checkbox("Bay Board 1 (Press)")
                        .classes("h-8")
                        .on("click", self.handle_device_select)
                        .bind_value(self, "configure_bb1")
                    )
                    self.bb2_select = (
                        ui.checkbox("Bay Board 2 (Intertank)")
                        .classes("h-8")
                        .on("click", self.handle_device_select)
                        .bind_value(self, "configure_bb2")
                    )
                    self.bb3_select = (
                        ui.checkbox("Bay Board 3 (Engine)")
                        .classes("h-8")
                        .on("click", self.handle_device_select)
                        .bind_value(self, "configure_bb3")
                    )
                    self.fr_select = (
                        ui.checkbox("Flight Recorder")
                        .classes("h-8")
                        .on("click", self.handle_device_select)
                        .bind_value(self, "configure_fr")
                    )
                    self.fr_select.disable()
            ui.separator().classes("w-full h-1")
            ui.label("Progress").classes("self-center text-lg")
            with ui.row().classes(
                "w-full mx-auto no-wrap gap-0 justify-between"
            ):
                with ui.column().classes("items-center gap-0") as ebox_prog:
                    with ui.tooltip() as ebox_tooltip:
                        self.ebox_prog_tooltip = (
                            ui.html(sanitize=False)
                            .classes("text-[12px]")
                            .style(
                                """display:inline-block;width:max-content;white-space:normal;max-width:100em;"""
                            )
                        )
                        self.ebox_prog_tooltip.set_visibility(False)
                        ebox_tooltip.bind_visibility_from(
                            self.ebox_prog_tooltip, "visible"
                        )
                    self.ebox_progress_tool = ebox_prog
                    ui.label("EBox").classes("text-sm")
                    with ui.element().classes("relative w-8 h-8 mt-2"):
                        self.ebox_progress = (
                            ui.icon("", size="2em")
                            .classes("absolute inset-0 flex m-auto")
                            .bind_visibility_from(
                                self, "ebox_loading", backward=lambda v: not v
                            )
                        )
                        ui.spinner(color="white", size="2em").classes(
                            "absolute inset-0 m-auto"
                        ).bind_visibility_from(self, "ebox_loading")
                with ui.column().classes("items-center gap-0") as fc_prog:
                    with ui.tooltip() as fc_tooltip:
                        self.fc_prog_tooltip = (
                            ui.html(sanitize=False)
                            .classes("text-[12px]")
                            .style(
                                """display:inline-block;width:max-content;white-space:normal;max-width:100em;"""
                            )
                        )
                        self.fc_prog_tooltip.set_visibility(False)
                        fc_tooltip.bind_visibility_from(
                            self.fc_prog_tooltip, "visible"
                        )
                    self.fc_progress_tool = fc_prog
                    ui.label("Flight Computer").classes("text-sm")
                    with ui.element().classes("relative w-8 h-8 mt-2"):
                        self.fc_progress = (
                            ui.icon("", size="2em")
                            .classes("absolute inset-0 flex m-auto")
                            .bind_visibility_from(
                                self, "fc_loading", backward=lambda v: not v
                            )
                        )
                        ui.spinner(color="white", size="2em").classes(
                            "absolute inset-0 m-auto"
                        ).bind_visibility_from(self, "fc_loading")
                with ui.column().classes("items-center gap-0") as bb1_prog:
                    with ui.tooltip() as bb1_tooltip:
                        self.bb1_prog_tooltip = (
                            ui.html(sanitize=False)
                            .classes("text-[12px]")
                            .style(
                                """display:inline-block;width:max-content;white-space:normal;max-width:100em;"""
                            )
                        )
                        self.bb1_prog_tooltip.set_visibility(False)
                        bb1_tooltip.bind_visibility_from(
                            self.bb1_prog_tooltip, "visible"
                        )
                    self.bb1_progress_tool = bb1_prog
                    ui.label("Bay Board 1").classes("text-sm")
                    with ui.element().classes("relative w-8 h-8 mt-2"):
                        self.bb1_progress = (
                            ui.icon("", size="2em")
                            .classes("absolute inset-0 flex m-auto")
                            .bind_visibility_from(
                                self, "bb1_loading", backward=lambda v: not v
                            )
                        )
                        ui.spinner(color="white", size="2em").classes(
                            "absolute inset-0 m-auto"
                        ).bind_visibility_from(self, "bb1_loading")
                with ui.column().classes("items-center gap-0") as bb2_prog:
                    with ui.tooltip() as bb2_tooltip:
                        self.bb2_prog_tooltip = (
                            ui.html(sanitize=False)
                            .classes("text-[12px]")
                            .style(
                                """display:inline-block;width:max-content;white-space:normal;max-width:100em;"""
                            )
                        )
                        self.bb2_prog_tooltip.set_visibility(False)
                        bb2_tooltip.bind_visibility_from(
                            self.bb2_prog_tooltip, "visible"
                        )
                    self.bb2_progress_tool = bb2_prog
                    ui.label("Bay Board 2").classes("text-sm")
                    with ui.element().classes("relative w-8 h-8 mt-2"):
                        self.bb2_progress = (
                            ui.icon("", size="2em")
                            .classes("absolute inset-0 flex m-auto")
                            .bind_visibility_from(
                                self, "bb2_loading", backward=lambda v: not v
                            )
                        )
                        ui.spinner(color="white", size="2em").classes(
                            "absolute inset-0 m-auto"
                        ).bind_visibility_from(self, "bb2_loading")
                with ui.column().classes("items-center gap-0") as bb3_prog:
                    with ui.tooltip() as bb3_tooltip:
                        self.bb3_prog_tooltip = (
                            ui.html(sanitize=False)
                            .classes("text-[12px]")
                            .style(
                                """display:inline-block;width:max-content;white-space:normal;max-width:100em;"""
                            )
                        )
                        self.bb3_prog_tooltip.set_visibility(False)
                        bb3_tooltip.bind_visibility_from(
                            self.bb3_prog_tooltip, "visible"
                        )
                    self.bb3_progress_tool = bb3_prog
                    ui.label("Bay Board 3").classes("text-sm")
                    with ui.element().classes("relative w-8 h-8 mt-2"):
                        self.bb3_progress = (
                            ui.icon("", size="2em")
                            .classes("absolute inset-0 flex m-auto")
                            .bind_visibility_from(
                                self, "bb3_loading", backward=lambda v: not v
                            )
                        )
                        ui.spinner(color="white", size="2em").classes(
                            "absolute inset-0 m-auto"
                        ).bind_visibility_from(self, "bb3_loading")
                with ui.column().classes("items-center gap-0") as fr_prog:
                    with ui.tooltip() as fr_tooltip:
                        self.fr_prog_tooltip = (
                            ui.html(sanitize=False)
                            .classes("text-[12px]")
                            .style(
                                """display:inline-block;width:max-content;white-space:normal;max-width:100em;"""
                            )
                        )
                        self.fr_prog_tooltip.set_visibility(False)
                        fr_tooltip.bind_visibility_from(
                            self.fr_prog_tooltip, "visible"
                        )
                    self.fr_progress_tool = fr_prog
                    ui.label("Flight Recorder").classes("text-sm")
                    with ui.element().classes("relative w-8 h-8 mt-2"):
                        self.fr_progress = (
                            ui.icon("", size="2em")
                            .classes("absolute inset-0 flex m-auto")
                            .bind_visibility_from(
                                self, "fr_loading", backward=lambda v: not v
                            )
                        )
                        ui.spinner(color="white", size="2em").classes(
                            "absolute inset-0 m-auto"
                        ).bind_visibility_from(self, "fr_loading")

    def update_progress_icon(self, icon: ui.icon, v: int):
        icon.props(f'color="{progress_lookup[v]["color"]}"')
        icon.name = progress_lookup[v]["name"]

    def handle_all_check(self, e):
        if self.ICD_config is not None:
            self.ebox_select.set_value(e.sender.value)
        self.fc_select.set_value(e.sender.value)
        self.bb1_select.set_value(e.sender.value)
        self.bb2_select.set_value(e.sender.value)
        self.bb3_select.set_value(e.sender.value)
        # self.fr_select.set_value(e.sender.value)

    def handle_device_select(self, e):
        if (
            (self.ebox_select.value or not self.ebox_select.enabled)
            and (self.fc_select.value or not self.fc_select.enabled)
            and (self.bb1_select.value or not self.bb1_select.enabled)
            and (self.bb2_select.value or not self.bb2_select.enabled)
            and (self.bb3_select.value or not self.bb3_select.enabled)
            and (self.fr_select.value or not self.fr_select.enabled)
        ):
            self.all_select.set_value(True)
        else:
            self.all_select.set_value(False)

    async def handle_ICD(self, e):
        self.ICD_config = None
        try:
            self.ICD_config = ICD(await e.file.read(), e.file.name)
        except (ValueError, KeyError) as e:
            print("Error while processing ICD")
            traceback.print_exception(type(e), e, e.__traceback__)
            with (
                ui.dialog().props("persistent") as dialog,
                ui.card().classes(
                    "bg-[#990000] w-250 h-40 flex flex-col justify-center items-center"
                ),
            ):
                ui.button(
                    icon="close", on_click=lambda e: dialog.close()
                ).classes("absolute right-0 top-0 bg-transparent").props(
                    'flat color="white" size="lg"'
                )
                ui.label("ICD processing error:").classes("text-xl")
                ui.space().classes("h-1 w-full")
                ui.label(str(e)).classes("text-base")
                dialog.open()
            return
        except ICDException as e:
            print("Value error while processing ICD")
            traceback.print_exception(type(e), e, e.__traceback__)
            with (
                ui.dialog().props("persistent").classes("") as dialog,
                ui.card().classes(
                    "bg-[#990000] max-w-[90vw] h-60 flex flex-col justify-center items-center"
                ),
            ):
                with ui.column().classes("items-center"):
                    ui.button(
                        icon="close", on_click=lambda e: dialog.close()
                    ).classes("absolute right-0 top-0 bg-transparent").props(
                        'flat color="white" size="lg"'
                    )
                    ui.label(f"{e.type}:").classes("text-xl")
                    ui.space().classes("h-10 w-full")
                    with ui.scroll_area().classes("max-w-[80vw] w-[80vw] h-25"):
                        with ui.row().classes(
                            "w-full no-wrap overflow-x-auto overflow-scroll"
                        ):
                            for k, v in e.row.items():
                                with ui.column().classes(
                                    "whitespace-nowrap overflow-x-auto overflow-y-hidden items-center"
                                ):
                                    ui.label(str(k)).classes(
                                        "bold whitespace-nowrap overflow-x-auto overflow-y-hidden"
                                    )
                                    ui.label(str(v)).classes(
                                        "whitespace-nowrap overflow-x-auto overflow-y-hidden"
                                    )
                dialog.open()
            return
        self.process_board_channels()

    def process_board_channels(self):
        fc_board_ui: FCConfigUI = self.base.FC_config
        bb1_board_ui: BBConfigUI = self.base.BB1_config
        bb2_board_ui: BBConfigUI = self.base.BB2_config
        bb3_board_ui: BBConfigUI = self.base.BB3_config
        fr_board_ui: FRConfigUI = self.base.FR_config

        fc_vlvs_configured = []
        bb1_vlvs_configured = []
        bb2_vlvs_configured = []
        bb3_vlvs_configured = []

        for x in self.ICD_config.fc_channels:
            if x["type"] == "PT":
                fc_board_ui.PTs[x["channel"] - 1].range = x["range"]
                fc_board_ui.PTs[x["channel"] - 1].offset = x["offset"]
                fc_board_ui.PTs[x["channel"] - 1].max = x["max_voltage"]
            elif x["type"] == "TC":
                fc_board_ui.TCs[x["channel"] - 1].gain = x["gain"]
            elif x["type"] == "VLV":
                fc_board_ui.valves[x["channel"] - 1].voltage = x["voltage"]
                fc_board_ui.valves[x["channel"] - 1].enabled = True
                fc_vlvs_configured.append(x["channel"] - 1)
        for x in range(NUM_FC_VLVs):
            if x not in fc_vlvs_configured:
                fc_board_ui.valves[x].enabled = False

        for x in self.ICD_config.bb1_channels:
            if x["type"] == "PT":
                bb1_board_ui.PTs[x["channel"] - 1].range = x["range"]
                bb1_board_ui.PTs[x["channel"] - 1].offset = x["offset"]
                bb1_board_ui.PTs[x["channel"] - 1].max = x["max_voltage"]
            elif x["type"] == "TC":
                bb1_board_ui.TCs[x["channel"] - 1].gain = x["gain"]
            elif x["type"] == "VLV":
                bb1_board_ui.valves[x["channel"] - 1].voltage = x["voltage"]
                bb1_board_ui.valves[x["channel"] - 1].enabled = True
                bb1_vlvs_configured.append(x["channel"] - 1)
        for x in range(NUM_BB_VLVs):
            if x not in bb1_vlvs_configured:
                bb1_board_ui.valves[x].enabled = False

        for x in self.ICD_config.bb2_channels:
            if x["type"] == "PT":
                bb2_board_ui.PTs[x["channel"] - 1].range = x["range"]
                bb2_board_ui.PTs[x["channel"] - 1].offset = x["offset"]
                bb2_board_ui.PTs[x["channel"] - 1].max = x["max_voltage"]
            elif x["type"] == "TC":
                bb2_board_ui.TCs[x["channel"] - 1].gain = x["gain"]
            elif x["type"] == "VLV":
                bb2_board_ui.valves[x["channel"] - 1].voltage = x["voltage"]
                bb2_board_ui.valves[x["channel"] - 1].enabled = True
                bb2_vlvs_configured.append(x["channel"] - 1)
        for x in range(NUM_BB_VLVs):
            if x not in bb2_vlvs_configured:
                bb2_board_ui.valves[x].enabled = False

        for x in self.ICD_config.bb3_channels:
            if x["type"] == "PT":
                bb3_board_ui.PTs[x["channel"] - 1].range = x["range"]
                bb3_board_ui.PTs[x["channel"] - 1].offset = x["offset"]
                bb3_board_ui.PTs[x["channel"] - 1].max = x["max_voltage"]
            elif x["type"] == "TC":
                bb3_board_ui.TCs[x["channel"] - 1].gain = x["gain"]
            elif x["type"] == "VLV":
                bb3_board_ui.valves[x["channel"] - 1].voltage = x["voltage"]
                bb3_board_ui.valves[x["channel"] - 1].enabled = True
                bb3_vlvs_configured.append(x["channel"] - 1)
        for x in range(NUM_BB_VLVs):
            if x not in bb3_vlvs_configured:
                bb3_board_ui.valves[x].enabled = False

        for x in self.ICD_config.ips:
            if x["device"] == "DAQ PC":
                fc_board_ui.limewireIP.set_ip(ipaddress.IPv4Address(x["ip"]))
            elif x["device"] == "Flight Computer":
                fc_board_ui.FCIP.set_ip(ipaddress.IPv4Address(x["ip"]))
                bb1_board_ui.FCIP.set_ip(ipaddress.IPv4Address(x["ip"]))
                bb2_board_ui.FCIP.set_ip(ipaddress.IPv4Address(x["ip"]))
                bb3_board_ui.FCIP.set_ip(ipaddress.IPv4Address(x["ip"]))
                fr_board_ui.FCIP.set_ip(ipaddress.IPv4Address(x["ip"]))
            elif x["device"] == "Press Bay Board":
                fc_board_ui.BB1IP.set_ip(ipaddress.IPv4Address(x["ip"]))
                bb1_board_ui.BBIP.set_ip(ipaddress.IPv4Address(x["ip"]))
            elif x["device"] == "Intertank Bay Board":
                fc_board_ui.BB2IP.set_ip(ipaddress.IPv4Address(x["ip"]))
                bb2_board_ui.BBIP.set_ip(ipaddress.IPv4Address(x["ip"]))
            elif x["device"] == "Engine Bay Board":
                fc_board_ui.BB3IP.set_ip(ipaddress.IPv4Address(x["ip"]))
                bb3_board_ui.BBIP.set_ip(ipaddress.IPv4Address(x["ip"]))
            elif x["device"] == "Flight Recorder":
                fc_board_ui.FRIP.set_ip(ipaddress.IPv4Address(x["ip"]))
                fr_board_ui.FRIP.set_ip(ipaddress.IPv4Address(x["ip"]))

    def reset_progress_indicators(self):
        self.update_progress_icon(self.ebox_progress, 0)
        self.update_progress_icon(self.fc_progress, 0)
        self.update_progress_icon(self.bb1_progress, 0)
        self.update_progress_icon(self.bb2_progress, 0)
        self.update_progress_icon(self.bb3_progress, 0)
        self.update_progress_icon(self.fr_progress, 0)

        self.ebox_prog_tooltip.set_visibility(False)
        self.fc_prog_tooltip.set_visibility(False)
        self.bb1_prog_tooltip.set_visibility(False)
        self.bb2_prog_tooltip.set_visibility(False)
        self.bb3_prog_tooltip.set_visibility(False)
        self.fr_prog_tooltip.set_visibility(False)

    async def start_config_write(self):
        print("Starting configuration")

        # Make a copy of everything since this will take a while and we don't want things
        # changing mid configuration
        config_ebox = self.configure_ebox
        config_fc = self.configure_fc
        config_bb1 = self.configure_bb1
        config_bb2 = self.configure_bb2
        config_bb3 = self.configure_bb3
        config_fr = self.configure_fr

        gse_channels = None
        ICD_name = ""
        if self.ICD_config is not None:
            gse_channels = copy.deepcopy(self.ICD_config.ebox_channels)
            ICD_name = self.ICD_config.name

        fc_board_ui: FCConfigUI = self.base.FC_config
        bb1_board_ui: BBConfigUI = self.base.BB1_config
        bb2_board_ui: BBConfigUI = self.base.BB2_config
        bb3_board_ui: BBConfigUI = self.base.BB3_config
        fr_board_ui: FRConfigUI = self.base.FR_config

        fc_tftp = self.base.FC_TFTP_IP.ip
        bb1_tftp = self.base.BB1_TFTP_IP.ip
        bb2_tftp = self.base.BB2_TFTP_IP.ip
        bb3_tftp = self.base.BB3_TFTP_IP.ip
        fr_tftp = self.base.FR_TFTP_IP.ip

        fc_PTs = [pt.to_PT() for pt in fc_board_ui.PTs]
        fc_TCs = [tc.to_TC() for tc in fc_board_ui.TCs]
        fc_VLVs = [vlv.to_VLV() for vlv in fc_board_ui.valves]
        fc_GSEIP = fc_board_ui.limewireIP.ip
        fc_FCIP = fc_board_ui.FCIP.ip
        fc_BB1IP = fc_board_ui.BB1IP.ip
        fc_BB2IP = fc_board_ui.BB2IP.ip
        fc_BB3IP = fc_board_ui.BB3IP.ip
        fc_FRIP = fc_board_ui.FRIP.ip

        bb1_PTs = [pt.to_PT() for pt in bb1_board_ui.PTs]
        bb1_TCs = [tc.to_TC() for tc in bb1_board_ui.TCs]
        bb1_VLVs = [vlv.to_VLV() for vlv in bb1_board_ui.valves]
        bb1_BBIP = bb1_board_ui.BBIP.ip
        bb1_FCIP = bb1_board_ui.FCIP.ip

        bb2_PTs = [pt.to_PT() for pt in bb2_board_ui.PTs]
        bb2_TCs = [tc.to_TC() for tc in bb2_board_ui.TCs]
        bb2_VLVs = [vlv.to_VLV() for vlv in bb2_board_ui.valves]
        bb2_BBIP = bb2_board_ui.BBIP.ip
        bb2_FCIP = bb2_board_ui.FCIP.ip

        bb3_PTs = [pt.to_PT() for pt in bb3_board_ui.PTs]
        bb3_TCs = [tc.to_TC() for tc in bb3_board_ui.TCs]
        bb3_VLVs = [vlv.to_VLV() for vlv in bb3_board_ui.valves]
        bb3_BBIP = bb3_board_ui.BBIP.ip
        bb3_FCIP = bb3_board_ui.FCIP.ip

        fr_FCIP = fr_board_ui.FCIP.ip
        fr_FRIP = fr_board_ui.FRIP.ip

        # time to actually configure
        self.reset_progress_indicators()

        if config_ebox:
            print("Configuring EBox")
            if gse_channels is None:
                print("ICD not loaded, skipping EBox")
                self.set_progress(
                    self.ebox_progress,
                    self.ebox_prog_tooltip,
                    "ICD not loaded",
                    False,
                )
            else:
                self.ebox_loading = True
                self.set_in_progress(
                    self.ebox_prog_tooltip,
                    "Configuring, this may take a while...",
                )
                (result, msg) = await run.cpu_bound(
                    configure_ebox, gse_channels
                )
                tooltip_msg = f"Used ICD '{ICD_name}'" + (
                    f"<br><br>{msg}" if not result else ""
                )
                self.set_progress(
                    self.ebox_progress,
                    self.ebox_prog_tooltip,
                    tooltip_msg,
                    result,
                )
                self.ebox_loading = False
                print(
                    "EBox configured!"
                    if result
                    else f"Failed to configure EBox: {msg}"
                )
            print("")

        if config_fc:
            print("Configuring Flight Computer")
            self.fc_loading = True
            eeprom_future = None
            if self.log_listener is not None:
                eeprom_future = await self.log_listener.setup_future()
            self.set_board_tftp_in_progress(self.fc_prog_tooltip)
            try:
                await run.cpu_bound(
                    configure_fc,
                    fc_PTs,
                    fc_TCs,
                    fc_VLVs,
                    fc_GSEIP,
                    fc_FCIP,
                    fc_BB1IP,
                    fc_BB2IP,
                    fc_BB3IP,
                    fc_FRIP,
                    fc_tftp,
                )
                self.set_board_config_in_progress(self.fc_prog_tooltip)
                print(
                    "Flight Computer config successfully sent, waiting for response."
                )
                if eeprom_future is not None:
                    future_msg = ""
                    future_result = False
                    try:
                        log: FirmwareLog = await asyncio.wait_for(
                            eeprom_future, timeout=EEPROM_RESPONSE_TIMEOUT
                        )
                        if log.status_code % 1000 == 705:
                            future_result = True
                            future_msg = log.message
                            if log.board != Board.FC:
                                future_result = False
                                future_msg = (
                                    "A successful response came from the wrong board: "
                                    + log.board.pretty_name
                                )
                                print(
                                    "Successful eeprom came from the wrong board: "
                                    + log.board.pretty_name
                                )
                            else:
                                print(
                                    "Successful response from the Flight Computer"
                                )
                        else:
                            future_msg = log.message
                            print(
                                "Flight Computer config failed: " + log.message
                            )
                    except asyncio.CancelledError as err:
                        future_msg = (
                            "Error: configuration was started from a different source, "
                            + str(err)
                        )
                        print("EEPROM config future was cancelled")
                    except TimeoutError:
                        future_msg = "Timed out waiting for response"
                        print(
                            "Flight Computer config timed out waiting for UDP response"
                        )
                    tooltip_msg = ""
                    if gse_channels is not None:
                        tooltip_msg = f"Used ICD '{ICD_name}'<br>"
                    tooltip_msg += f"<br>{future_msg}"
                    self.set_progress(
                        self.fc_progress,
                        self.fc_prog_tooltip,
                        tooltip_msg,
                        future_result,
                    )
            except Exception as err:
                tooltip_msg = ""
                if gse_channels is not None:
                    tooltip_msg = f"Used ICD '{ICD_name}'<br>"
                tooltip_msg += f"<br>{str(err)}"
                self.set_progress(
                    self.fc_progress, self.fc_prog_tooltip, tooltip_msg, False
                )
                print(
                    f"Failed to send Flight Computer EEPROM config over TFTP: {str(err)}"
                )
            self.fc_loading = False
            print("")

        if config_bb1:
            print("Configuring Bay Board 1")
            self.bb1_loading = True
            eeprom_future = None
            if self.log_listener is not None:
                eeprom_future = await self.log_listener.setup_future()
            self.set_board_tftp_in_progress(self.bb1_prog_tooltip)
            try:
                await run.cpu_bound(
                    configure_bb,
                    1,
                    bb1_PTs,
                    bb1_TCs,
                    bb1_VLVs,
                    bb1_FCIP,
                    bb1_BBIP,
                    bb1_tftp,
                )
                self.set_board_config_in_progress(self.bb1_prog_tooltip)
                print(
                    "Bay Board 1 config successfully sent, waiting for response."
                )
                if eeprom_future is not None:
                    future_msg = ""
                    future_result = False
                    try:
                        log: FirmwareLog = await asyncio.wait_for(
                            eeprom_future, timeout=EEPROM_RESPONSE_TIMEOUT
                        )
                        if log.status_code % 1000 == 705:
                            future_result = True
                            future_msg = log.message
                            if log.board != Board.BB1:
                                future_result = False
                                future_msg = (
                                    "A successful response came from the wrong board: "
                                    + log.board.pretty_name
                                )
                                print(
                                    "Successful eeprom came from the wrong board: "
                                    + log.board.pretty_name
                                )
                            else:
                                print("Successful response from Bay Board 1")
                        else:
                            future_msg = log.message
                            print("Bay Board 1 config failed: " + log.message)
                    except asyncio.CancelledError as err:
                        future_msg = (
                            "Error: configuration was started from a different source, "
                            + str(err)
                        )
                        print("EEPROM config future was cancelled")
                    except TimeoutError:
                        future_msg = "Timed out waiting for response"
                        print(
                            "Bay Board 1 config timed out waiting for UDP response"
                        )
                    tooltip_msg = ""
                    if gse_channels is not None:
                        tooltip_msg = f"Used ICD '{ICD_name}'<br>"
                    tooltip_msg += f"<br>{future_msg}"
                    self.set_progress(
                        self.bb1_progress,
                        self.bb1_prog_tooltip,
                        tooltip_msg,
                        future_result,
                    )
            except Exception as err:
                tooltip_msg = ""
                if gse_channels is not None:
                    tooltip_msg = f"Used ICD '{ICD_name}'<br>"
                tooltip_msg += f"<br>{str(err)}"
                self.set_progress(
                    self.bb1_progress, self.bb1_prog_tooltip, tooltip_msg, False
                )
                print(
                    f"Failed to send Bay Board 1 EEPROM config over TFTP: {str(err)}"
                )
            self.bb1_loading = False
            print("")

        if config_bb2:
            print("Configuring Bay Board 2")
            self.bb2_loading = True
            eeprom_future = None
            if self.log_listener is not None:
                eeprom_future = await self.log_listener.setup_future()
            self.set_board_tftp_in_progress(self.bb2_prog_tooltip)
            try:
                await run.cpu_bound(
                    configure_bb,
                    2,
                    bb2_PTs,
                    bb2_TCs,
                    bb2_VLVs,
                    bb2_FCIP,
                    bb2_BBIP,
                    bb2_tftp,
                )
                self.set_board_config_in_progress(self.bb2_prog_tooltip)
                print(
                    "Bay Board 2 config successfully sent, waiting for response."
                )
                if eeprom_future is not None:
                    future_msg = ""
                    future_result = False
                    try:
                        log: FirmwareLog = await asyncio.wait_for(
                            eeprom_future, timeout=EEPROM_RESPONSE_TIMEOUT
                        )
                        if log.status_code % 1000 == 705:
                            future_result = True
                            future_msg = log.message
                            if log.board != Board.BB2:
                                future_result = False
                                future_msg = (
                                    "A successful response came from the wrong board: "
                                    + log.board.pretty_name
                                )
                                print(
                                    "Successful eeprom came from the wrong board: "
                                    + log.board.pretty_name
                                )
                            else:
                                print("Successful response from Bay Board 2")
                        else:
                            future_msg = log.message
                            print("Bay Board 2 config failed: " + log.message)
                    except asyncio.CancelledError as err:
                        future_msg = (
                            "Error: configuration was started from a different source, "
                            + str(err)
                        )
                        print("EEPROM config future was cancelled")
                    except TimeoutError:
                        future_msg = "Timed out waiting for response"
                        print(
                            "Bay Board 2 config timed out waiting for UDP response"
                        )
                    tooltip_msg = ""
                    if gse_channels is not None:
                        tooltip_msg = f"Used ICD '{ICD_name}'<br>"
                    tooltip_msg += f"<br>{future_msg}"
                    self.set_progress(
                        self.bb2_progress,
                        self.bb2_prog_tooltip,
                        tooltip_msg,
                        future_result,
                    )
            except Exception as err:
                tooltip_msg = ""
                if gse_channels is not None:
                    tooltip_msg = f"Used ICD '{ICD_name}'<br>"
                tooltip_msg += f"<br>{str(err)}"
                self.set_progress(
                    self.bb2_progress, self.bb2_prog_tooltip, tooltip_msg, False
                )
                print(
                    f"Failed to send Bay Board 2 EEPROM config over TFTP: {str(err)}"
                )
            self.bb2_loading = False
            print("")

        if config_bb3:
            print("Configuring Bay Board 3")
            self.bb3_loading = True
            eeprom_future = None
            if self.log_listener is not None:
                eeprom_future = await self.log_listener.setup_future()
            self.set_board_tftp_in_progress(self.bb3_prog_tooltip)
            try:
                await run.cpu_bound(
                    configure_bb,
                    3,
                    bb3_PTs,
                    bb3_TCs,
                    bb3_VLVs,
                    bb3_FCIP,
                    bb3_BBIP,
                    bb3_tftp,
                )
                self.set_board_config_in_progress(self.bb3_prog_tooltip)
                print(
                    "Bay Board 3 config successfully sent, waiting for response."
                )
                if eeprom_future is not None:
                    future_msg = ""
                    future_result = False
                    try:
                        log: FirmwareLog = await asyncio.wait_for(
                            eeprom_future, timeout=EEPROM_RESPONSE_TIMEOUT
                        )
                        if log.status_code % 1000 == 705:
                            future_result = True
                            future_msg = log.message
                            if log.board != Board.BB3:
                                future_result = False
                                future_msg = (
                                    "A successful response came from the wrong board: "
                                    + log.board.pretty_name
                                )
                                print(
                                    "Successful eeprom came from the wrong board: "
                                    + log.board.pretty_name
                                )
                            else:
                                print("Successful response from Bay Board 3")
                        else:
                            future_msg = log.message
                            print("Bay Board 3 config failed: " + log.message)
                    except asyncio.CancelledError as err:
                        future_msg = (
                            "Error: configuration was started from a different source, "
                            + str(err)
                        )
                        print("EEPROM config future was cancelled")
                    except TimeoutError:
                        future_msg = "Timed out waiting for response"
                        print(
                            "Bay Board 3 config timed out waiting for UDP response"
                        )
                    tooltip_msg = ""
                    if gse_channels is not None:
                        tooltip_msg = f"Used ICD '{ICD_name}'<br>"
                    tooltip_msg += f"<br>{future_msg}"
                    self.set_progress(
                        self.bb3_progress,
                        self.bb3_prog_tooltip,
                        tooltip_msg,
                        future_result,
                    )
            except Exception as err:
                tooltip_msg = ""
                if gse_channels is not None:
                    tooltip_msg = f"Used ICD '{ICD_name}'<br>"
                tooltip_msg += f"<br>{str(err)}"
                self.set_progress(
                    self.bb3_progress, self.bb3_prog_tooltip, tooltip_msg, False
                )
                print(
                    f"Failed to send Bay Board 3 EEPROM config over TFTP: {str(err)}"
                )
            self.bb3_loading = False
            print("")

        if config_fr:
            print("Configuring Flight Recorder")
            self.fr_loading = True
            eeprom_future = None
            if self.log_listener is not None:
                eeprom_future = await self.log_listener.setup_future()
            self.set_board_tftp_in_progress(self.fr_prog_tooltip)
            try:
                await run.cpu_bound(configure_fr, fr_FCIP, fr_FRIP, fr_tftp)
                self.set_board_config_in_progress(self.fr_prog_tooltip)
                print(
                    "Flight Recorder config successfully sent, waiting for response."
                )
                if eeprom_future is not None:
                    future_msg = ""
                    future_result = False
                    try:
                        log: FirmwareLog = await asyncio.wait_for(
                            eeprom_future, timeout=EEPROM_RESPONSE_TIMEOUT
                        )
                        if log.status_code % 1000 == 705:
                            future_result = True
                            future_msg = log.message
                            if log.board != Board.FR:
                                future_result = False
                                future_msg = (
                                    "A successful response came from the wrong board: "
                                    + log.board.pretty_name
                                )
                                print(
                                    "Successful eeprom came from the wrong board: "
                                    + log.board.pretty_name
                                )
                            else:
                                print(
                                    "Successful response from the Flight Recorder"
                                )
                        else:
                            future_msg = log.message
                            print(
                                "Flight Recorder config failed: " + log.message
                            )
                    except asyncio.CancelledError as err:
                        future_msg = (
                            "Error: configuration was started from a different source, "
                            + str(err)
                        )
                        print("EEPROM config future was cancelled")
                    except TimeoutError:
                        future_msg = "Timed out waiting for response"
                        print(
                            "Flight Recorder config timed out waiting for UDP response"
                        )
                    tooltip_msg = ""
                    if gse_channels is not None:
                        tooltip_msg = f"Used ICD '{ICD_name}'<br>"
                    tooltip_msg += f"<br>{future_msg}"
                    self.set_progress(
                        self.fr_progress,
                        self.fr_prog_tooltip,
                        tooltip_msg,
                        future_result,
                    )
            except Exception as err:
                tooltip_msg = ""
                if gse_channels is not None:
                    tooltip_msg = f"Used ICD '{ICD_name}'<br>"
                tooltip_msg += f"<br>{str(err)}"
                self.set_progress(
                    self.fr_progress, self.fr_prog_tooltip, tooltip_msg, False
                )
                print(
                    f"Failed to send Flight Recorder EEPROM config over TFTP: {str(err)}"
                )
            self.fr_loading = False
            print("")

        print("System configuration done!\n")

    def set_progress(
        self, icon: ui.icon, tooltip: ui.html, text: str, result: bool
    ):
        if result:
            self.update_progress_icon(icon, 1)
        else:
            self.update_progress_icon(icon, -1)
        now = datetime.datetime.now()
        tooltip.set_content(
            f"{now.strftime('%b %d, %Y %I:%M:%S %p')}<br>{text}"
        )
        tooltip.set_visibility(True)

    def set_board_config_in_progress(self, tooltip: ui.html):
        now = datetime.datetime.now()
        tooltip.set_content(
            f"{now.strftime('%b %d, %Y %I:%M:%S %p')}<br>Config sent, waiting for response."
        )
        tooltip.set_visibility(True)

    def set_board_tftp_in_progress(self, tooltip: ui.html):
        now = datetime.datetime.now()
        tooltip.set_content(
            f"{now.strftime('%b %d, %Y %I:%M:%S %p')}<br>Sending config..."
        )
        tooltip.set_visibility(True)

    def set_in_progress(self, tooltip: ui.html, msg: str):
        now = datetime.datetime.now()
        tooltip.set_content(f"{now.strftime('%b %d, %Y %I:%M:%S %p')}<br>{msg}")
        tooltip.set_visibility(True)

    def handle_ebox_select(self, v):
        if v is None:
            self.configure_ebox = False
        return v is not None

    def warn_write_config(self, e):
        with (
            ui.dialog() as dialog,
            ui.card().classes(
                "w-100 h-30 flex flex-col justify-center items-center"
            ),
        ):
            ui.button(icon="close", on_click=lambda e: dialog.close()).classes(
                "absolute right-0 top-0 bg-transparent"
            ).props('flat color="white" size="lg"')
            ui.label("Confirm write configuration?").classes("text-xl")
            ui.button("Confirm", on_click=lambda: self.on_config_warn(dialog))
            dialog.open()

    async def on_config_warn(self, dialog):
        dialog.close()
        self.config_button.set_enabled(False)
        await self.start_config_write()
        self.config_button.set_enabled(True)


class HelpTooltip:
    def __init__(self, content: str):
        with ui.icon("help_outline", size="20px").classes(
            "text-gray-400 absolute right-2 top-2"
        ):
            with (
                ui.tooltip()
                .classes("max-w-[50vw]")
                .style("white-space: nowrap")
            ):
                ui.html(content=content, sanitize=False).style(
                    "font-size: 12px"
                ).style("white-space: nowrap")
