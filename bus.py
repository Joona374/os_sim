from device import Device
from tps import Address, Byte, MemoryRegion
from exceptions import BusFaultUnmappedAddress, InvalidByteValue

class Bus():
    def __init__(self) -> None:
        self.address_map: list[MemoryRegion] = []

    def register_device(self, start: Address, size: int, device: Device):
        self.address_map.append(MemoryRegion(start, size, device))

    def _find_region(self, address: Address) -> MemoryRegion:
        for region in self.address_map:
            if region.contains(address):
                return region

        raise BusFaultUnmappedAddress(address)

    def read(self, address: Address) -> Byte:
        region = self._find_region(address)
        return region.device.read(region.to_offset(address))

    def write(self, address: Address, value: Byte) -> None:
        if value > 0xFF:
            raise InvalidByteValue(value)

        region = self._find_region(address)
        region.device.write(region.to_offset(address), value)

    def tick(self) -> None:
        for region in self.address_map:
            region.device.tick()
