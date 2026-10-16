from __future__ import annotations
from typing import TYPE_CHECKING
from dataclasses import dataclass
from enum import IntEnum

if TYPE_CHECKING:
    from device import Device

Byte = int      # 0..255
Word = int      # 0..65535
Address = int   # 0..65535

KB = 1024


type Program = list[int]


class CpuMode(IntEnum):
    KERNEL = 0
    USER = 1


@dataclass(frozen=True)
class MemoryRegion:
    start: Address
    size: int
    device: Device

    @property
    def end(self) -> int:
        return self.start + self.size

    def contains(self, address: Address) -> bool:
        return self.start <= address < self.end

    def to_offset(self, address: Address) -> Address:
        return address - self.start
