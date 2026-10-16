from operator import add

from bus import Bus
from exceptions import IllegalInstruction, InvalidCpuRegister, PrivilegeViolation, PrivilegedMemoryAccessViolation, PrivilegedOpertionViolation, StackPointerOutsideRam, MachineFault
from tps import Address, Byte, Word, CpuMode
from isa import Opcode, NUM_REGISTERS, PRIVLIDGED_OPERATIONS

RAM_START = 0x0400
RAM_END = 0x0800
KERNEL_ONLY_START = 0x0800


class CPU:

    def __init__(self, bus: Bus, trace_mode: bool = False, start_mode: CpuMode = CpuMode.KERNEL) -> None:
        # TRACING
        self.TRACE_MODE: bool = trace_mode
        self.bytes_for_operation: list[Byte] = []

        self.bus = bus
        self.regs: list[Byte] = [0] * NUM_REGISTERS

        self.PC: Address = 0x0000
        self.SP: Address = RAM_END
        self.halted: bool = False
        self.zero_flag: bool = False
        self.mode: CpuMode = start_mode

        self.operation_to_handler = {
            Opcode.HALT: self._process_halt,
            Opcode.LOAD: self._process_load,
            Opcode.STORE: self._process_store,
            Opcode.JUMP: self._process_jump,
            Opcode.CMP: self._process_cpm,
            Opcode.JZ: self._process_jz,
            Opcode.ADD: self._process_add,
            Opcode.SUB: self._process_sub,
            Opcode.LDR: self._process_ldr,
            Opcode.PUSH: self._process_push,
            Opcode.POP: self._process_pop,
            Opcode.CALL: self._process_call_,
            Opcode.RET: self._process_ret,
        }

    def run(self) -> None:
        while not self.halted:
            self.step()

    def step(self):
        start_pc = self.PC
        if self.TRACE_MODE:
            self.bytes_for_operation = []

        op_code = None

        try:
            byte = self._fetch_byte()
            op_code = self._get_opcpode(byte)
            if op_code in PRIVLIDGED_OPERATIONS and self.mode == CpuMode.USER:
                raise PrivilegedOpertionViolation(op_code)

            handler = self.operation_to_handler[op_code]
            handler()
        except MachineFault:
            self.PC = start_pc
            raise
        finally:
            if self.TRACE_MODE:
                self._print_trace(start_pc, op_code)

    def _print_trace(self, pc: int, op_code: Opcode | None) -> None:
        name = op_code.name if op_code else "???"
        raw = " ".join(f"{b:02X}" for b in self.bytes_for_operation)
        regs = " ".join(f"r{i}={v:02X}" for i, v in enumerate(self.regs))
        mode = "K" if self.mode == CpuMode.KERNEL else "U"
        print(f"{pc:04X}  {raw:<12} {name:<6} | {regs} Z={int(self.zero_flag) } SP={self.SP:04X} M={mode} ")

    ############# Cpu helpers #############

    def _increment_pc(self) -> None:
        self.PC += 1
        self.PC = self.PC & 0xFFFF

    def _set_pc(self, addr: Address) -> None:
        self.PC = addr

    def _set_sp(self, new_sp: Address) -> None:
        self.SP = new_sp & 0xFFFF

    def _validate_sp(self, new_sp: Address) -> Address:
        if not RAM_START <= new_sp <= RAM_END:
            raise StackPointerOutsideRam(new_sp, RAM_START, RAM_END)
        return new_sp

    def _fetch_byte(self) -> Byte:
        byte = self._bus_read(self.PC)
        self._increment_pc()

        if self.TRACE_MODE:
            self.bytes_for_operation.append(byte)

        return byte

    def _fetch_word(self) -> Word:
        hi_byte = self._fetch_byte()
        lo_byte = self._fetch_byte()
        word = (hi_byte << 8) | lo_byte

        return word

    def _get_opcpode(self, byte: Byte) -> Opcode:
        try:
            op_code = Opcode(byte)

            return op_code
        except ValueError:
            raise IllegalInstruction(byte)

    def _read_from_register(self, register: int) -> Byte:
        try:
            return self.regs[register]
        except IndexError:
            raise InvalidCpuRegister(register)

    def _write_to_register(self, register: int, value: Byte):
        try:
            self.regs[register] = value
        except IndexError:
            raise InvalidCpuRegister(register)

    def _bus_read(self, addr: Address) -> Byte:
        if addr >= KERNEL_ONLY_START and self.mode == CpuMode.USER:
            raise PrivilegedMemoryAccessViolation(addr)

        return self.bus.read(addr)

    def _bus_write(self, addr: Address, value: Byte) -> None:
        if addr >= KERNEL_ONLY_START and self.mode == CpuMode.USER:
            raise PrivilegedMemoryAccessViolation(addr)

        self.bus.write(addr, value)

    ############# OpCode processors #############

    def _process_halt(self) -> None:
        self.halted = True

    def _process_load(self) -> None:
        register = self._fetch_byte()
        value = self._fetch_byte()
        self._write_to_register(register, value)

    def _process_store(self) -> None:
        register = self._fetch_byte()
        addr = self._fetch_word()

        value_at_reg = self._read_from_register(register)

        self._bus_write(addr, value_at_reg)

    def _process_jump(self) -> None:
        addr = self._fetch_word()
        self._set_pc(addr)

    def _process_cpm(self):
        reg_a = self._fetch_byte()
        reg_b = self._fetch_byte()

        reg_a_value = self._read_from_register(reg_a)
        reg_b_value = self._read_from_register(reg_b)

        self.zero_flag = reg_a_value == reg_b_value

    def _process_jz(self):
        jump_to_addr = self._fetch_word()
        if self.zero_flag == True:
            self._set_pc(jump_to_addr)

    def _process_add(self):
        reg_a = self._fetch_byte()
        reg_b = self._fetch_byte()

        reg_a_value = self._read_from_register(reg_a)
        reg_b_value = self._read_from_register(reg_b)

        add_result = (reg_a_value + reg_b_value) & 0xFF

        self._write_to_register(reg_a, add_result)
        self.zero_flag = add_result == 0

    def _process_sub(self):
        reg_a = self._fetch_byte()
        reg_b = self._fetch_byte()

        reg_a_value = self._read_from_register(reg_a)
        reg_b_value = self._read_from_register(reg_b)

        sub_result = (reg_a_value - reg_b_value) & 0xFF

        self._write_to_register(reg_a, sub_result)
        self.zero_flag = sub_result == 0

    def _process_ldr(self):
        target_reg = self._fetch_byte()

        hi_reg = self._fetch_byte()
        lo_reg = self._fetch_byte()

        addr_hi = self._read_from_register(hi_reg)
        addr_lo = self._read_from_register(lo_reg)
        addr = (addr_hi << 8) | addr_lo

        byte = self._bus_read(addr)
        self._write_to_register(target_reg, byte)

    def _process_push(self):
        source_reg = self._fetch_byte()
        reg_value = self._read_from_register(source_reg)
        new_sp = self._validate_sp(self.SP - 1)
        self._bus_write(new_sp, reg_value)
        self._set_sp(new_sp)

    def _process_pop(self):
        target_reg = self._fetch_byte()
        new_sp = self._validate_sp(self.SP + 1)
        byte = self._bus_read(self.SP)
        self._write_to_register(target_reg, byte)
        self._set_sp(new_sp)

    def _process_call_(self):
        addr = self._fetch_word()

        ret_addr_lo = self.PC & 0xFF
        ret_addr_hi = self.PC >> 8

        new_sp = self._validate_sp(self.SP - 2)

        self._bus_write(new_sp + 1, ret_addr_lo)
        self._bus_write(new_sp, ret_addr_hi)

        self._set_sp(new_sp)
        self._set_pc(addr)

    def _process_ret(self):
        new_sp = self._validate_sp(self.SP + 2)

        ret_addr_hi = self._bus_read(self.SP)
        ret_addr_lo = self._bus_read(self.SP + 1)

        self._set_sp(new_sp)

        ret_addr = ret_addr_hi << 8 | ret_addr_lo
        self._set_pc(ret_addr)
