import synnax as sy

from lmp import LMPMessage, TelemetryMessage, ValveStateMessage

from .limewire_utils import get_write_time_channel_name


class SynnaxFramer:
    def __init__(self, channels: dict[str, list[str]]):
        self.channels = channels

    def build_synnax_frame(self, msg: LMPMessage) -> dict[str, float] | None:
        if isinstance(msg, TelemetryMessage):
            try:
                frame = self._build_telemetry_frame(msg)
            except KeyError as err:
                raise err
        elif isinstance(msg, ValveStateMessage):
            frame = self._build_valve_state_frame(msg)
        else:
            raise ValueError("Unrecognized message type for Synnax framer")

        return frame

    def _build_telemetry_frame(self, msg: TelemetryMessage):
        # Check if index channel is loaded
        if msg.index_channel not in self.channels:
            raise KeyError(
                f"Channel {msg.index_channel} not active! Is LIMEWIRE_DEV_SYNNAX enabled?"
            )

        data_channels = self.channels[msg.index_channel].copy()
        limewire_write_time_channel = get_write_time_channel_name(
            msg.index_channel
        )
        data_channels.remove(limewire_write_time_channel)
        frame = {
            channel: value for channel, value in zip(data_channels, msg.values)
        }
        frame[msg.index_channel] = msg.timestamp
        frame[limewire_write_time_channel] = sy.TimeStamp.now()

        return frame

    def _build_valve_state_frame(self, msg: ValveStateMessage):
        """Construct a frame to write to Synnax from a valve state message."""
        frame: dict[str, float] = {}
        frame[msg.valve.state_channel_index] = msg.timestamp
        frame[msg.valve.state_channel] = int(msg.state)
        limewire_write_time_channel = get_write_time_channel_name(
            msg.valve.state_channel_index
        )
        frame[limewire_write_time_channel] = sy.TimeStamp.now()
        return frame
