import sys
import struct
import os.path
import argparse

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.generic_platform import Pins, Subsignal, IOStandard
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *

from gateware import up5kspram
from gateware import cas
from gateware import spi_flash

from targets.utils import csr_map_update
import platforms.fomu_hacker as fomu_hacker
from targets.fomu_hacker.base import BaseSoC
from third_party.valentyusb.valentyusb import usbcore

from litex.soc.interconnect import wishbone


class RandomFirmwareROM(wishbone.SRAM):
    def __init__(self, size, seed=2373):
        import random
        # Seed the random data with a fixed number, so different bitstreams
        # can all share firmware.
        random.seed(seed)
        data = []
        for d in range(int(size / 4)):
            data.append(random.getrandbits(32))
        print("Firmware {} bytes of random data".format(size))
        wishbone.SRAM.__init__(self, size, read_only=True, init=data)


class _CRG(Module):
    def __init__(self, platform):
        clk12 = Signal()
        # "0b00" Sets 48MHz HFOSC output
        # "0b01" Sets 24MHz HFOSC output.
        # "0b10" Sets 12MHz HFOSC output.
        # "0b11" Sets 6MHz HFOSC output
        self.specials += Instance(
            "SB_HFOSC",
            i_CLKHFEN=1,
            i_CLKHFPU=1,
            o_CLKHF=clk12,
            p_CLKHF_DIV="0b10", # 12MHz
        )

        self.clock_domains.cd_sys = ClockDomain()
        self.reset = Signal()

        # FIXME: Use PLL, increase system clock to 32 MHz, pending nextpnr
        # fixes.
        self.comb += self.cd_sys.clk.eq(clk12)

        # POR reset logic- POR generated from sys clk, POR logic feeds sys clk
        # reset.
        self.clock_domains.cd_por = ClockDomain()
        reset_delay = Signal(12, reset=4095)
        self.comb += [
            self.cd_por.clk.eq(self.cd_sys.clk),
            self.cd_sys.rst.eq(reset_delay != 0)
        ]
        self.sync.por += \
            If(reset_delay != 0,
                reset_delay.eq(reset_delay - 1)
            )
        self.specials += AsyncResetSynchronizer(self.cd_por, self.reset)

        self.clock_domains.cd_usb_48 = ClockDomain()
        platform.add_period_constraint(self.cd_usb_48.clk, 1e9/48e6)
        self.comb += [
            self.cd_usb_48.clk.eq(platform.request("clk48")),
        ]


class USBNoBios(SoCCore):
    csr_peripherals = (
        "spiflash",
        "usb",
        #"cas",
    )
    csr_map_update(SoCCore.csr_map, csr_peripherals)

    mem_map = {
        "spiflash": 0x20000000,  # (default shadow @0xa0000000)
    }
    mem_map.update(SoCCore.mem_map)

    interrupt_map = {
        "usb": 3,
    }
    interrupt_map.update(BaseSoC.interrupt_map)

    def __init__(self, platform, **kwargs):
        if 'integrated_rom_size' not in kwargs:
            kwargs['integrated_rom_size']=0
        if 'integrated_sram_size' not in kwargs:
            kwargs['integrated_sram_size']=0

        # FIXME: Force either lite or minimal variants of CPUs; full is too big.
        platform.add_extension(fomu_hacker.pins_serial)

        clk_freq = int(12e6)

        kwargs['cpu_reset_address']=0
        kwargs['with_ctrl']=False
        SoCCore.__init__(self, platform, clk_freq, **kwargs)

        self.submodules.crg = _CRG(platform)
        self.platform.add_period_constraint(self.crg.cd_sys.clk, 1e9/clk_freq)

        bios_size = 0x2c00
        self.submodules.random_rom = RandomFirmwareROM(bios_size)
        self.add_constant("ROM_DISABLE", 1)
        self.register_rom(self.random_rom.bus, bios_size)

        # Control and Status
        #self.submodules.cas = cas.ControlAndStatus(platform, clk_freq)

        # SPI flash peripheral
        self.submodules.spiflash = spi_flash.SpiFlashSingle(
            platform.request("spiflash"),
            dummy=platform.spiflash_read_dummy_bits,
            div=platform.spiflash_clock_div)
        self.add_constant("SPIFLASH_PAGE_SIZE", platform.spiflash_page_size)
        self.add_constant("SPIFLASH_SECTOR_SIZE", platform.spiflash_sector_size)
        self.register_mem("spiflash", self.mem_map["spiflash"],
            self.spiflash.bus, size=platform.spiflash_total_size)

        self.flash_boot_address = self.mem_map["spiflash"] #+platform.gateware_size+bios_size

        # SPRAM- UP5K has single port RAM, might as well use it as SRAM to
        # free up scarce block RAM.
        self.submodules.spram = up5kspram.Up5kSPRAM(size=128*1024)
        self.register_mem("sram", 0x10000000, self.spram.bus, 0x20000)

        # ValentyUSB
        usb_pads = platform.request("usb")
        usb_iobuf = usbcore.UsbIoBuf(usb_pads.d_p, usb_pads.d_n, usb_pads.pullup)
        self.submodules.usb = usbcore.UsbSimpleFifo(usb_iobuf)

        # Disable final deep-sleep power down so firmware words are loaded
        # onto softcore's address bus.
        platform.toolchain.build_template[3] = "icepack -s {build_name}.txt {build_name}.bin"
        platform.toolchain.nextpnr_build_template[2] = "icepack -s {build_name}.txt {build_name}.bin"

SoC = USBNoBios
