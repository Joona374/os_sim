import pytest

from bus import Bus
from exceptions import BusFaultUnmappedAddress, InvalidByteValue

from conftest import CANONICAL_UNMAPPED_ADDRESS, RecordingDevice


def test_device_at_nonzero_start_receives_relative_offset() -> None:
    bus = Bus()
    device = RecordingDevice()
    bus.register_device(0x0100, 0x10, device)

    bus.write(0x0105, 0x41)
    assert device.writes == [(5, 0x41)]
    assert bus.read(0x0105) == 0x41


def test_unmapped_bus_access_raises() -> None:
    with pytest.raises(BusFaultUnmappedAddress):
        Bus().read(CANONICAL_UNMAPPED_ADDRESS)


def test_bus_rejects_values_above_one_byte() -> None:
    with pytest.raises(InvalidByteValue):
        Bus().write(0x0000, 0x100)


def test_bus_tick_reaches_every_registered_device() -> None:
    bus = Bus()
    first = RecordingDevice()
    second = RecordingDevice()
    bus.register_device(0x0000, 0x10, first)
    bus.register_device(0x0100, 0x10, second)

    bus.tick()

    assert first.ticks == 1
    assert second.ticks == 1
