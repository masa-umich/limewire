from pytest import approx

from packets import TelemetryMessage


def test_telemetry_deserialize() -> None:
    """Test the TelemetryMessage.deserialize_bytes() method."""
    bytes_recv = (
        b"\x00\x11\x11\x11\x11\x11\x11\x11\x11\x23\x45\x67\x89\x34\x56\x78\x9a"
    )
    msg = TelemetryMessage(bytes_recv=bytes_recv)

    assert msg.board_id == 0x00
    assert msg.timestamp == 0x1111111111111111

    # I used https://www.scadacore.com/tools/programming-calculators/online-hex-converter/
    # to convert the chunks of 4 bytes corresponding to the data values to float32s.
    # Make sure to use the "Float - Big Endian (ABCD) setting"
    expected = [approx(1.07013158e-17), approx(1.99741777e-7)]
    for value, expect in zip(msg.values, expected):
        assert value.data == expect
