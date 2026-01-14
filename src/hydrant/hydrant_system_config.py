import ipaddress
from io import BytesIO

from loguru import logger
import pandas as pd
import synnax as sy
from synnax.hardware import ni

ICD_SHEET = "AVI Mappings 25-26"

DEFAULT_GSE_IP = ipaddress.IPv4Address("141.212.192.160")
DEFAULT_FC_IP = ipaddress.IPv4Address("141.212.192.170")
DEFAULT_BB1_IP = ipaddress.IPv4Address("141.212.192.180")
DEFAULT_BB2_IP = ipaddress.IPv4Address("141.212.192.190")
DEFAULT_BB3_IP = ipaddress.IPv4Address("141.212.192.200")
DEFAULT_FR_IP = ipaddress.IPv4Address("141.212.192.210")
DEFAULT_PT_RANGE = 1000
DEFAULT_PT_OFFSET = 0.5
DEFAULT_PT_MAX = 4.5
DEFAULT_TC_GAIN = 1
DEFAULT_VALVE_VOLTAGE = 12
DEFAULT_VALVE_ENABLED = False

NUM_FC_PTs = 5
NUM_BB_PTs = 10

NUM_FC_TCs = 3
NUM_BB_TCs = 6

NUM_FC_VLVs = 3
NUM_BB_VLVs = 5

analog_task_name: str = "Sensors"
analog_card_model: str = "PCI-6225"

digital_task_name: str = "Valves"
digital_card_model: str = "PCI-6514"

tc_calibrations = {
    "1": {"slope": 1.721453951, "offset": -7.888645383},
    "2": {"slope": 1.717979575, "offset": -7.887206187},
    "3": {"slope": 1.749114263, "offset": -8.059569538},
    "4": {"slope": 1.746326017, "offset": -7.988352324},
    "5": {"slope": 1.758960807, "offset": -8.000751167},
    "6": {"slope": 1.723974665, "offset": -7.891630334},
    "7": {"slope": 1.703447212, "offset": -7.961173615},
    "8": {"slope": 1.725947472, "offset": -7.928342723},
    "9": {"slope": 1.223907933, "offset": -3.041473799},
    "10": {"slope": 1.163575088, "offset": -3.001507707},
    "11": {"slope": 1.183121251, "offset": -2.962919485},
    "12": {"slope": 1.255762908, "offset": -2.436113303},
    "13": {"slope": 1.209157541, "offset": -3.018604306},
    "14": {"slope": 1.154169121, "offset": -2.924291025},
}


class ICD:
    def __init__(self, content: bytes, name: str):
        self.name = name
        ICD_df = pd.read_excel(
            BytesIO(content),
            header=1,
            sheet_name=ICD_SHEET,
            keep_default_na=False,
            na_values="",
        )
        try:
            ICD_df["Type"] = ICD_df["Type"].ffill(axis=0)
            ICD_df["Connection Location"] = ICD_df["Connection Location"].ffill(
                axis=0
            )
        except KeyError as err:
            raise KeyError("Missing critical column: " + str(err))
        self.ebox_channels = []
        self.fc_channels = []
        self.bb1_channels = []
        self.bb2_channels = []
        self.bb3_channels = []
        self.ips = []
        setup_thermistor = False

        for row_num, row in ICD_df.iterrows():
            try:
                if pd.isna(row["Name"]):
                    continue
                if row["Connection Location"] == "EBOX":
                    if row["Name"] == "":
                        continue
                    try:
                        if "Margin" in row["Name"]:
                            continue
                        if "Broken Channel" in row["Name"]:
                            continue
                    except Exception:
                        continue
                    channel_num = int(row["Channel"])
                    if row["Type"] == "PTs":
                        if (
                            pd.isna(row["Max Pressure"])
                            or pd.isna(row["Calibration Offset (V)"])
                            or pd.isna(row["Max Output Voltage"])
                        ):
                            raise ICDValueException(
                                "Missing value while processing ICD",
                                row.to_dict(),
                            )
                        channel = {
                            "name": row["Name"],
                            "type": "PT",
                            "channel": channel_num,
                            "port": channel_num - 1,
                            "max": int(row["Max Pressure"]),
                            "min": 0,
                            "offset": float(row["Calibration Offset (V)"]),
                            "max_voltage": float(row["Max Output Voltage"]),
                        }
                        self.ebox_channels.append(channel)
                    elif row["Type"] == "VLVs":
                        if channel_num >= 17:
                            port = 6
                        elif channel_num >= 9:
                            port = 5
                        elif channel_num >= 0:
                            port = 4
                        else:
                            raise ICDValueException(
                                "Invalid channel number in row", row.to_dict()
                            )
                        channel = {
                            "name": row["Name"],
                            "type": "VLV",
                            "channel": channel_num,
                            "port": port,
                            "line": (channel_num - 1) % 8,
                        }
                        self.ebox_channels.append(channel)
                    elif row["Type"] == "TCs":
                        if not setup_thermistor:
                            channel = {
                                "type": "Thermistor",
                                "name": "Thermistor",
                                "signal": 78,
                                "supply": 79,
                                "max": 8,
                                "min": -8,
                            }
                            setup_thermistor = True
                            self.ebox_channels.append(channel)
                        channel = {
                            "name": row["Name"],
                            "type": "TC",
                            "channel": channel_num,
                            "port": channel_num - 1 + 64,
                            "max": 8,
                            "min": -8,
                        }
                        self.ebox_channels.append(channel)
                    else:
                        raise ICDValueException(
                            "Unknown peripheral type", row.to_dict()
                        )
                elif row["Connection Location"] == "Press Bay Board":
                    if row["Name"] == "":
                        continue

                    if row["Type"] == "PTs":
                        if (
                            pd.isna(row["Max Pressure"])
                            or pd.isna(row["Calibration Offset (V)"])
                            or pd.isna(row["Max Output Voltage"])
                        ):
                            raise ICDValueException(
                                "Missing value while processing ICD",
                                row.to_dict(),
                            )
                        channel = {
                            "name": row["Name"],
                            "type": "PT",
                            "channel": int(row["Channel"]),
                            "range": int(row["Max Pressure"]),
                            "offset": float(row["Calibration Offset (V)"]),
                            "max_voltage": float(row["Max Output Voltage"]),
                        }
                        self.bb1_channels.append(channel)
                    elif row["Type"] == "TCs":
                        channel = {
                            "name": row["Name"],
                            "type": "TC",
                            "channel": int(row["Channel"]),
                            "gain": int(calculate_tc_gain(row["TC Range"])),
                        }
                        self.bb1_channels.append(channel)
                    elif row["Type"] == "VLVs":
                        if pd.isna(row["Supply Voltage (V)"]):
                            raise ICDValueException(
                                "Missing value while processing ICD",
                                row.to_dict(),
                            )
                        channel = {
                            "name": row["Name"],
                            "type": "VLV",
                            "channel": int(row["Channel"]),
                            "voltage": int(row["Supply Voltage (V)"]),
                        }
                        self.bb1_channels.append(channel)
                    else:
                        raise ICDValueException(
                            "Unknown peripheral type", row.to_dict()
                        )
                elif row["Connection Location"] == "Intertank Bay Board":
                    if row["Name"] == "":
                        continue

                    if row["Type"] == "PTs":
                        if (
                            pd.isna(row["Max Pressure"])
                            or pd.isna(row["Calibration Offset (V)"])
                            or pd.isna(row["Max Output Voltage"])
                        ):
                            raise ICDValueException(
                                "Missing value while processing ICD",
                                row.to_dict(),
                            )
                        channel = {
                            "name": row["Name"],
                            "type": "PT",
                            "channel": int(row["Channel"]),
                            "range": int(row["Max Pressure"]),
                            "offset": float(row["Calibration Offset (V)"]),
                            "max_voltage": float(row["Max Output Voltage"]),
                        }
                        self.bb2_channels.append(channel)
                    elif row["Type"] == "TCs":
                        channel = {
                            "name": row["Name"],
                            "type": "TC",
                            "channel": int(row["Channel"]),
                            "gain": int(calculate_tc_gain(row["TC Range"])),
                        }
                        self.bb2_channels.append(channel)
                    elif row["Type"] == "VLVs":
                        if pd.isna(row["Supply Voltage (V)"]):
                            raise ICDValueException(
                                "Missing value while processing ICD",
                                row.to_dict(),
                            )
                        channel = {
                            "name": row["Name"],
                            "type": "VLV",
                            "channel": int(row["Channel"]),
                            "voltage": int(row["Supply Voltage (V)"]),
                        }
                        self.bb2_channels.append(channel)
                    else:
                        raise ICDValueException(
                            "Unknown peripheral type", row.to_dict()
                        )
                elif row["Connection Location"] == "Engine Bay Board":
                    if row["Name"] == "":
                        continue

                    if row["Type"] == "PTs":
                        if (
                            pd.isna(row["Max Pressure"])
                            or pd.isna(row["Calibration Offset (V)"])
                            or pd.isna(row["Max Output Voltage"])
                        ):
                            raise ICDValueException(
                                "Missing value while processing ICD",
                                row.to_dict(),
                            )
                        channel = {
                            "name": row["Name"],
                            "type": "PT",
                            "channel": int(row["Channel"]),
                            "range": int(row["Max Pressure"]),
                            "offset": float(row["Calibration Offset (V)"]),
                            "max_voltage": float(row["Max Output Voltage"]),
                        }
                        self.bb3_channels.append(channel)
                    elif row["Type"] == "TCs":
                        channel = {
                            "name": row["Name"],
                            "type": "TC",
                            "channel": int(row["Channel"]),
                            "gain": int(calculate_tc_gain(row["TC Range"])),
                        }
                        self.bb3_channels.append(channel)
                    elif row["Type"] == "VLVs":
                        if pd.isna(row["Supply Voltage (V)"]):
                            raise ICDValueException(
                                "Missing value while processing ICD",
                                row.to_dict(),
                            )
                        channel = {
                            "name": row["Name"],
                            "type": "VLV",
                            "channel": int(row["Channel"]),
                            "voltage": int(row["Supply Voltage (V)"]),
                        }
                        self.bb3_channels.append(channel)
                    else:
                        raise ICDValueException(
                            "Unknown peripheral type", row.to_dict()
                        )
                elif row["Connection Location"] == "Flight Computer":
                    if row["Name"] == "":
                        continue

                    if row["Type"] == "PTs":
                        if (
                            str(row["Max Pressure"]) == "N/A"
                            or str(row["Supply Voltage (V)"]) == "N/A"
                        ):
                            logger.info("Skipping Flight Computer Fluctus channel")
                            continue  # Special case for Fluctus channel
                        if (
                            pd.isna(row["Max Pressure"])
                            or pd.isna(row["Calibration Offset (V)"])
                            or pd.isna(row["Max Output Voltage"])
                        ):
                            raise ICDValueException(
                                "Missing value while processing ICD",
                                row.to_dict(),
                            )
                        channel = {
                            "name": row["Name"],
                            "type": "PT",
                            "channel": int(row["Channel"]),
                            "range": int(row["Max Pressure"]),
                            "offset": float(row["Calibration Offset (V)"]),
                            "max_voltage": float(row["Max Output Voltage"]),
                        }
                        self.fc_channels.append(channel)
                    elif row["Type"] == "TCs":
                        channel = {
                            "name": row["Name"],
                            "type": "TC",
                            "channel": int(row["Channel"]),
                            "gain": int(calculate_tc_gain(row["TC Range"])),
                        }
                        self.fc_channels.append(channel)
                    elif row["Type"] == "VLVs":
                        if pd.isna(row["Supply Voltage (V)"]):
                            raise ICDValueException(
                                "Missing value while processing ICD",
                                row.to_dict(),
                            )
                        channel = {
                            "name": row["Name"],
                            "type": "VLV",
                            "channel": int(row["Channel"]),
                            "voltage": int(row["Supply Voltage (V)"]),
                        }
                        self.fc_channels.append(channel)
                    else:
                        raise ICDValueException(
                            "Unknown peripheral type", row.to_dict()
                        )
                elif row["Type"] == "IPs":
                    if pd.isna(row["Connection Location"]):
                        continue
                    addr = {
                        "device": row["Name"],
                        "ip": str(row["Connection Location"]),
                    }
                    self.ips.append(addr)
                else:
                    continue
            except ValueError:
                raise ICDException("ICD processing error", row.to_dict())
            except KeyError as err:
                raise KeyError("Missing critical column: " + str(err))


def calculate_tc_gain(range):
    return 8  # lol we only use Type-T


def configure_ebox(channels) -> tuple[bool, str]:
    try:
        synnax_client = synnax_login(
            "127.0.0.1"
        )  # this should be running on the same machine as synnax
        analog_task, digital_task, analog_card = create_tasks(synnax_client, 50)
        setup_channels(
            synnax_client, channels, analog_task, digital_task, analog_card
        )
        configure_tasks(synnax_client, analog_task, digital_task)
        return (True, "")
    except Exception as e:
        return (False, str(e))


def setup_channels(
    client: sy.Synnax, channels, analog_task, digital_task, analog_card
):
    logger.info("Creating channels in Synnax")
    # yes_to_all = False # create new synnax channels for all items in the sheet?

    for channel in channels:
        if channel["type"] == "PT":
            logger.info(f" > Creating PT: {channel['name']}")
            setup_pt(client, channel, analog_task, analog_card)
        elif channel["type"] == "VLV":
            logger.info(f" > Creating VLV: {channel['name']}")
            setup_vlv(client, channel, digital_task)
        elif channel["type"] == "TC":
            logger.info(f" > Creating TC: {channel['name']}")
            setup_tc(client, channel, analog_task, analog_card)
        elif channel["type"] == "Thermistor":
            logger.info(" > Creating Thermistor")
            setup_thermistor(client, channel, analog_task, analog_card)
        else:
            raise Exception(
                f"Sensor type {channel['type']} in channels dict not recognized (issue with the script)"
            )
    logger.info(" > Successfully created channels in Synnax")


def setup_pt(client: sy.Synnax, channel, analog_task, analog_card):
    time_channel = client.channels.create(
        name="gse_sensor_time",
        data_type=sy.DataType.TIMESTAMP,
        retrieve_if_name_exists=True,
        is_index=True,
    )

    pt_channel = client.channels.create(
        name=f"gse_pt_{channel['channel']}",
        data_type=sy.DataType.FLOAT32,
        index=time_channel.key,
        retrieve_if_name_exists=True,
    )

    analog_task.config.channels.append(
        ni.AIVoltageChan(
            channel=pt_channel.key,
            device=analog_card.key,
            port=channel["port"],
            custom_scale=ni.LinScale(
                slope=(
                    channel["max"]
                    / (
                        channel["max_voltage"] - channel["offset"]
                    )  # slope is max output in psi over output range (4 volts for our PTs)
                ),
                y_intercept=(
                    -(
                        channel["max"]
                        / (channel["max_voltage"] - channel["offset"])
                    )
                    * channel[
                        "offset"
                    ]  # y intercept is negative slope at 0.5 volts
                ),
                pre_scaled_units="Volts",
                scaled_units="PoundsPerSquareInch",
            ),
            terminal_config="RSE",
            max_val=channel["max"],
            min_val=channel["min"],
        )
    )


def setup_vlv(client: sy.Synnax, channel, digital_task):
    gse_state_time = client.channels.create(
        name="gse_state_time",
        is_index=True,
        data_type=sy.DataType.TIMESTAMP,
        retrieve_if_name_exists=True,
    )

    state_chan = client.channels.create(
        name=f"gse_state_{channel['channel']}",
        data_type=sy.DataType.UINT8,
        retrieve_if_name_exists=True,
        index=gse_state_time.key,
    )

    cmd_chan = client.channels.create(
        name=f"gse_vlv_{channel['channel']}",
        data_type=sy.DataType.UINT8,
        retrieve_if_name_exists=True,
        virtual=True,
    )

    digital_task.config.channels.append(
        ni.DOChan(
            cmd_channel=cmd_chan.key,
            state_channel=state_chan.key,
            port=channel["port"],
            line=channel["line"],
        )
    )


def setup_thermistor(client: sy.Synnax, channel, analog_task, analog_card):
    time_channel = client.channels.create(
        name="gse_sensor_time",
        data_type=sy.DataType.TIMESTAMP,
        retrieve_if_name_exists=True,
        is_index=True,
    )

    therm_supply = client.channels.create(
        name="gse_thermistor_supply",
        data_type=sy.DataType.FLOAT32,
        index=time_channel.key,
        retrieve_if_name_exists=True,
    )

    therm_signal = client.channels.create(
        name="gse_thermistor_signal",
        data_type=sy.DataType.FLOAT32,
        index=time_channel.key,
        retrieve_if_name_exists=True,
    )

    analog_task.config.channels.append(
        ni.AIVoltageChan(
            channel=therm_supply.key,
            device=analog_card.key,
            port=channel["supply"],
            min_val=channel["min"],
            max_val=channel["max"],
            terminal_config="RSE",
        ),
    )

    analog_task.config.channels.append(
        ni.AIVoltageChan(
            channel=therm_signal.key,
            device=analog_card.key,
            port=channel["signal"],
            min_val=channel["min"],
            max_val=channel["max"],
            terminal_config="RSE",
        ),
    )


def setup_tc(client: sy.Synnax, channel, analog_task, analog_card):
    time_channel = client.channels.create(
        name="gse_sensor_time",
        data_type=sy.DataType.TIMESTAMP,
        retrieve_if_name_exists=True,
        is_index=True,
    )

    tc_channel = client.channels.create(
        name=f"gse_tc_{channel['channel']}_raw",  # TCs without any CJC, CJC happens in a seperate script in real-time
        data_type=sy.DataType.FLOAT32,
        index=time_channel.key,
        retrieve_if_name_exists=True,
    )

    analog_task.config.channels.append(
        ni.AIVoltageChan(
            channel=tc_channel.key,
            device=analog_card.key,
            port=channel["port"],
            custom_scale=ni.LinScale(
                slope=tc_calibrations[str(channel["channel"])]["slope"],
                y_intercept=tc_calibrations[str(channel["channel"])]["offset"],
                pre_scaled_units="Volts",
                scaled_units="Volts",
            ),
            terminal_config="RSE",
            max_val=channel["max"],
        )
    )


def synnax_login(cluster: str) -> sy.Synnax:
    try:
        client = sy.Synnax(
            host=cluster,
            port=9090,
            username="synnax",
            password="seldon",
        )
    except Exception as e:
        raise Exception(
            f"Could not connect to Synnax at {cluster}, check to make sure Synnax is running. Original error: {str(e)}"
        )
    return client


def create_tasks(client: sy.Synnax, frequency: int):
    logger.info("Creating tasks...")
    logger.info(" > Scanning for cards...")
    try:
        analog_card = client.hardware.devices.retrieve(model=analog_card_model)
        logger.info(
            " > Analog card '"
            + analog_card.make
            + " "
            + analog_card.model
            + "' found!"
        )
    except Exception:
        raise Exception(
            "Analog card '"
            + analog_card_model
            + "' not found, are you sure it's connected? Maybe try re-enabling the NI Device Scanner."
        )

    try:
        digital_card = client.hardware.devices.retrieve(
            model=digital_card_model
        )
        logger.info(
            " > Digital card '"
            + digital_card.make
            + " "
            + digital_card.model
            + "' found!"
        )
    except Exception:
        raise Exception(
            "Digital card '"
            + digital_card_model
            + "' not found, are you sure it's connected? Maybe try re-enabling the NI Device Scanner."
        )

    analog_task = ni.AnalogReadTask(
        name=analog_task_name,
        sample_rate=sy.Rate.HZ * frequency,
        stream_rate=sy.Rate.HZ * frequency / 2,
        data_saving=True,
        channels=[],
    )

    digital_task = ni.DigitalWriteTask(
        name=digital_task_name,
        device=digital_card.key,
        state_rate=sy.Rate.HZ * frequency,
        data_saving=True,
        channels=[],
    )

    return analog_task, digital_task, analog_card


def configure_tasks(client: sy.Synnax, analog_task, digital_task):
    logger.info("Configuring tasks... (this may take a while)")

    if (
        analog_task.config.channels != []
    ):  # only configure if there are channels
        logger.info(" > Attempting to configure analog task")
        client.hardware.tasks.configure(
            task=analog_task, timeout=6000
        )  # long timeout cause our NI hardware is dumb
        logger.info(" > Successfully configured analog task!")
    if digital_task.config.channels != []:
        logger.info(" > Attempting to configure digital task")
        client.hardware.tasks.configure(task=digital_task, timeout=500)
        logger.info(" > Successfully configured digital task!")
    logger.info(" > All tasks have been successfully created!")


class ICDException(Exception):
    def __init__(self, *args):
        super().__init__(*args)
        self.type = args[0]
        self.row = args[1]
        for k, v in self.row.items():
            if pd.isna(v):
                self.row[k] = "-"


class ICDValueException(ICDException):
    pass
