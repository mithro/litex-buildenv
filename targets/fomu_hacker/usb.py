from migen import *

from litex.soc.cores import uart
from litex.soc.cores.uart import UARTWishboneBridge
from litex.soc.integration.soc_core import *

from targets.utils import csr_map_update
from targets.fomu_hacker.base import BaseSoC

from third_party.valentyusb.valentyusb import usbcore

from gateware import spi_flash
from gateware import firmware


class USBSoC(BaseSoC):
    csr_peripherals = (
#        "spiflash",
#        "cas",
#        "info",
        "usb",
    )
    csr_map_update(BaseSoC.csr_map, csr_peripherals)

#    mem_map = {
#        "spiflash": 0x20000000,  # (default shadow @0xa0000000)
#    }
#    mem_map.update(BaseSoC.mem_map)

    interrupt_map = {
        "usb": 3,
    }
    interrupt_map.update(BaseSoC.interrupt_map)

    def __init__(self, platform, **kwargs):
        BaseSoC.__init__(self, platform, **kwargs)

        # ValentyUSB
        usb_pads = platform.request("usb")
        usb_iobuf = usbcore.UsbIoBuf(usb_pads.d_p, usb_pads.d_n, usb_pads.pullup)
        self.submodules.usb = usbcore.UsbSimpleFifo(usb_iobuf)

        # Arachne-pnr is unsupported- it has trouble routing this design
        # on this particular board reliably. That said, annotate the build
        # template anyway just in case.
        # Disable final deep-sleep power down so firmware words are loaded
        # onto softcore's address bus.
        platform.toolchain.build_template[3] = "icepack -s {build_name}.txt {build_name}.bin"
        platform.toolchain.nextpnr_build_template[2] = "icepack -s {build_name}.txt {build_name}.bin"


SoC = USBSoC
