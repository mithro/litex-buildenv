from litex.soc.integration.soc_core import mem_decoder
from litex.soc.integration.soc_sdram import *

from liteeth.common import convert_ip
from liteeth.core import LiteEthUDPIPCore
from liteeth.frontend.etherbone import LiteEthEtherbone
from liteeth.mac import LiteEthMAC
from liteeth.phy import LiteEthPHY

from targets.utils import csr_map_update
from targets.arty.base import SoC as BaseSoC


class NetSoC(BaseSoC):
    def __init__(self, platform, *args, **kwargs):
        # Need a larger integrated ROM on or1k to fit the BIOS with TFTP support.
        if 'integrated_rom_size' not in kwargs and kwargs.get('cpu_type', 'lm32') != 'lm32':
            kwargs['integrated_rom_size'] = 0x10000

        BaseSoC.__init__(self, platform, *args, **kwargs)

        # Ethernet ---------------------------------------------------------------------------------
        # Ethernet PHY
        self.submodules.eth_phy = LiteEthPHY(
            platform.request("eth_clocks"),
            platform.request("eth"))
        self.add_csr("eth_phy")

        # timing constraints
        self.eth_phy.crg.cd_eth_rx.clk.attr.add("keep")
        self.eth_phy.crg.cd_eth_tx.clk.attr.add("keep")
        #self.platform.add_period_constraint(self.crg.cd_sys.clk, 10.0)
        self.platform.add_period_constraint(self.eth_phy.crg.cd_eth_rx.clk, 80.0)
        self.platform.add_period_constraint(self.eth_phy.crg.cd_eth_tx.clk, 80.0)
        self.platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            self.eth_phy.crg.cd_eth_rx.clk,
            self.eth_phy.crg.cd_eth_tx.clk)

        # Ethernet Core
        etherbone_mac_address = 0x10e2d5000000
        etherbone_ip_address  = "192.168.100.50"
        self.submodules.eth_core = LiteEthUDPIPCore(
            phy         = self.eth_phy,
            mac_address = etherbone_mac_address,
            ip_address  = etherbone_ip_address,
            clk_freq    = self.clk_freq)

        # Etherbone
        self.submodules.etherbone = LiteEthEtherbone(self.eth_core.udp, 1234, mode="master")
        self.add_wb_master(self.etherbone.wishbone.bus)

        # Analyzer ---------------------------------------------------------------------------------
        #analyzer_signals = [
        #    # FIXME: find interesting signals to probe
        #    self.cpu.ibus,
        #    self.cpu.dbus
        #]
        #self.submodules.analyzer = LiteScopeAnalyzer(analyzer_signals, 512)
        #self.add_csr("analyzer")

    def configure_iprange(self, iprange):
        iprange = [int(x) for x in iprange.split(".")]
        while len(iprange) < 4:
            iprange.append(0)
        # Our IP address
        self._configure_ip("LOCALIP", iprange[:-1]+[50])
        # IP address of tftp host
        self._configure_ip("REMOTEIP", iprange[:-1]+[100])

    def _configure_ip(self, ip_type, ip):
        for i, e in enumerate(ip):
            s = ip_type + str(i + 1)
            s = s.upper()
            self.add_constant(s, e)


SoC = NetSoC
