#!/usr/bin/env python3
"""
CAN FD 2 Click (TLE9255W) - Configuración SPI para Jetson Nano
==============================================================
Inicializa el transceiver TLE9255W en modo Normal Operation via SPI,
permitiendo convertir CAN_TX/CAN_RX (CMOS) a CAN_H/CAN_L (diferencial).

Conexión física - Jetson Nano 40-pin → CAN FD 2 Click (MikroBUS):
┌─────────────────────┬──────────────┬───────────────────┐
│  Jetson Nano Pin    │  Función     │  CAN FD 2 Click   │
├─────────────────────┼──────────────┼───────────────────┤
│  Pin 19 (SPI1_MOSI) │  MOSI        │  MOSI             │
│  Pin 21 (SPI1_MISO) │  MISO        │  MISO             │
│  Pin 23 (SPI1_SCK)  │  SCK         │  SCK              │
│  Pin 24 (SPI1_CS0)  │  CS          │  CS               │
│  Pin 29 (CAN0_TX)   │  CAN TX      │  TX (MikroBUS)    │
│  Pin 31 (CAN0_RX)   │  CAN RX      │  RX (MikroBUS)    │
│  Pin  1 (3.3V)      │  VIO         │  3.3V             │
│  Pin  2 (5V)        │  VCC/VBAT    │  5V               │
│  Pin  6 (GND)       │  GND         │  GND              │
└─────────────────────┴──────────────┴───────────────────┘

Nota: CAN_H y CAN_L salen directamente del conector del CAN FD 2 Click.

Uso:
    sudo python3 canfd2_init.py
    sudo python3 canfd2_init.py --bus 0 --device 0 --bitrate 500000
    sudo python3 canfd2_init.py --verify
"""

import spidev
import time
import argparse
import sys

# ──────────────────────────────────────────────────
#  Configuración (ajusta según tu cableado)
# ──────────────────────────────────────────────────
SPI_BUS    = 0          # /dev/spidev0.x  → SPI1 en Jetson Nano
SPI_DEVICE = 0          # /dev/spidevX.0  → CS0
SPI_SPEED  = 1_000_000  # 1 MHz
SPI_MODE   = 0          # CPOL=0, CPHA=0 (reads requieren left-shift de 1 bit)

# ──────────────────────────────────────────────────
#  Registros TLE9255W
# ──────────────────────────────────────────────────
REG_MODE_CTRL   = 0x01
REG_HW_CTRL     = 0x02
REG_TXD_TO_CTRL = 0x03
REG_SUPPLY_CTRL = 0x04
REG_SWK_CTRL_1  = 0x05
REG_SWK_CTRL_2  = 0x06
REG_TRANS_STAT  = 0x18
REG_ERR_STAT    = 0x1A

# ──────────────────────────────────────────────────
#  Valores de registro
# ──────────────────────────────────────────────────
# Modos de operación (MODE_CTRL)
MODE_SLEEP       = 0x01
MODE_STANDBY     = 0x02
MODE_REC_ONLY    = 0x04
MODE_NORMAL_OP   = 0x08

# TXD Timeout (evita que un TXD dominante permanente bloquee el bus)
TXD_TO_5_10      = 0x03   # 5/10 ms timeout
TXD_TO_DISABLE   = 0x04   # desactivado

# Selective Wake Control
SWK_CTRL_1_CFG   = 0x01
SWK_CTRL_2_1M    = 0x04   # bitrate 1 Mbps para wake
SWK_CTRL_2_EN    = 0x80   # enable SWK

# Bits de comando SPI
READ_MASK        = 0x7F   # bit7=0 → lectura
WRITE_CMD        = 0x80   # bit7=1 → escritura

# Bits de estado (TRANS_STAT)
STAT_TSD         = 0x02   # Thermal shutdown
STAT_TXD_TIMEOUT = 0x04   # TXD timeout activo
STAT_POR         = 0x80   # Power-on reset (activo tras reset)


class TLE9255W:
    """Driver SPI para el transceiver TLE9255W del CAN FD 2 Click."""

    def __init__(self, bus: int = SPI_BUS, device: int = SPI_DEVICE):
        self.spi = spidev.SpiDev()
        self.spi.open(bus, device)
        self.spi.max_speed_hz = SPI_SPEED
        self.spi.mode = SPI_MODE
        self.spi.no_cs = False
        print(f"[OK] SPI abierto: /dev/spidev{bus}.{device}  "
              f"modo={SPI_MODE}  velocidad={SPI_SPEED//1000} kHz")

    def close(self):
        self.spi.close()

    def write_reg(self, reg: int, data: int):
        """Escribe un byte en un registro del TLE9255W."""
        cmd = reg | WRITE_CMD          # bit7 = 1 → escritura
        self.spi.xfer2([cmd, data & 0xFF])

    def read_reg(self, reg: int) -> int:
        """Lee un byte de un registro del TLE9255W.

        En modo SPI 0 el chip envía MISO con un ciclo de retraso respecto
        a lo que espera el maestro, por lo que cada byte llega desplazado
        1 bit a la derecha. Se corrige con un left-shift de 1.
        """
        cmd = reg & READ_MASK          # bit7 = 0 → lectura
        result = self.spi.xfer2([cmd, 0x00])
        return (result[1] << 1) & 0xFF

    def set_normal_mode(self):
        """Pone el transceiver en modo Normal Operation (TXD→CANH/CANL activos)."""
        # Transición secuencial: STANDBY → NORMAL (requerido por TLE9255W)
        self.write_reg(REG_MODE_CTRL, MODE_STANDBY)
        time.sleep(0.05)
        self.write_reg(REG_MODE_CTRL, MODE_NORMAL_OP)
        time.sleep(0.05)

    def set_standby_mode(self):
        """Pone el transceiver en modo Standby (bajo consumo, sin transmisión)."""
        self.write_reg(REG_MODE_CTRL, MODE_STANDBY)
        time.sleep(0.01)

    def get_mode(self) -> int:
        """Devuelve el modo actual (nibble bajo del registro MODE_CTRL)."""
        return self.read_reg(REG_MODE_CTRL) & 0x0F

    def get_status(self) -> dict:
        """Lee y devuelve el estado del transceiver."""
        trans = self.read_reg(REG_TRANS_STAT)
        err   = self.read_reg(REG_ERR_STAT)
        uv    = self.read_reg(0x19)  # REG_TRANS_UV_STAT
        return {
            "trans_stat_raw": trans,
            "err_stat_raw":   err,
            "uv_stat_raw":    uv,
            "thermal_shutdown": bool(trans & STAT_TSD),
            "txd_timeout":      bool(trans & STAT_TXD_TIMEOUT),
            "power_on_reset":   bool(trans & STAT_POR),
            "cmd_error":        bool(err & 0x01),
            "com_error":        bool(err & 0x02),
            "vio_stuv":         bool(uv & 0x01),   # VIO short-time undervoltage
            "vio_ltuv":         bool(uv & 0x02),   # VIO long-time undervoltage
            "vcc_stuv":         bool(uv & 0x10),   # VCC short-time undervoltage
            "vcc_ltuv":         bool(uv & 0x20),   # VCC long-time undervoltage
            "vbat_uv":          bool(uv & 0x80),   # VBAT undervoltage
        }

    def configure_txd_timeout(self, timeout_val: int = TXD_TO_5_10):
        """
        Configura el TXD Dominant Timeout (protección contra bus bloqueado).
        timeout_val: TXD_TO_5_10 (recomendado) o TXD_TO_DISABLE
        """
        self.write_reg(REG_TXD_TO_CTRL, timeout_val)

    def init(self):
        """Secuencia completa de inicialización para operación normal."""
        print("\n[>>] Inicializando TLE9255W (CAN FD 2 Click)...")

        # Esperar estabilización de alimentación tras encendido
        time.sleep(0.1)

        # Transición secuencial: STANDBY → NORMAL
        self.set_normal_mode()
        print("[OK] Modo Normal Operation solicitado")

        # Verificar modo
        mode = self.get_mode()
        mode_names = {
            MODE_SLEEP:     "SLEEP",
            MODE_STANDBY:   "STANDBY",
            MODE_REC_ONLY:  "RECEIVE_ONLY",
            MODE_NORMAL_OP: "NORMAL_OPERATION",
        }
        mode_str = mode_names.get(mode, f"DESCONOCIDO (0x{mode:02X})")

        # Leer estado (los flags UV son latched del arranque, no bloquean)
        status = self.get_status()
        print(f"     TRANS_STAT=0x{status['trans_stat_raw']:02X}  "
              f"ERR_STAT=0x{status['err_stat_raw']:02X}  "
              f"UV_STAT=0x{status['uv_stat_raw']:02X}")
        if status["vbat_uv"] or status["vcc_ltuv"] or status["vcc_stuv"]:
            print("[--] UV flags latched (transitorios del arranque, ignorar si tensión OK)")
        if status["thermal_shutdown"]:
            print("[!!] ALERTA: Thermal shutdown activo")

        if mode == MODE_NORMAL_OP:
            print(f"[OK] Modo verificado: {mode_str}")
        else:
            print(f"[!!] ADVERTENCIA: modo inesperado → {mode_str}  (raw=0x{mode:02X})")
            print("     → Verifica cableado SPI y alimentación.")
            return False

        print("\n[OK] TLE9255W listo. CAN_TX/CAN_RX → CAN_H/CAN_L activos.\n")
        return True

    def print_all_registers(self):
        """Imprime todos los registros de configuración y estado."""
        regs = {
            "MODE_CTRL  (0x01)": REG_MODE_CTRL,
            "HW_CTRL    (0x02)": REG_HW_CTRL,
            "TXD_TO_CTRL(0x03)": REG_TXD_TO_CTRL,
            "SUPPLY_CTRL(0x04)": REG_SUPPLY_CTRL,
            "SWK_CTRL_1 (0x05)": REG_SWK_CTRL_1,
            "SWK_CTRL_2 (0x06)": REG_SWK_CTRL_2,
            "TRANS_STAT (0x18)": REG_TRANS_STAT,
            "ERR_STAT   (0x1A)": REG_ERR_STAT,
        }
        print("\n── Registros TLE9255W ──────────────────")
        for name, addr in regs.items():
            val = self.read_reg(addr)
            print(f"  {name}: 0x{val:02X}  ({val:08b}b)")
        print("────────────────────────────────────────\n")


def main():
    parser = argparse.ArgumentParser(
        description="Inicializa el TLE9255W (CAN FD 2 Click) en modo Normal via SPI")
    parser.add_argument("--bus",     type=int, default=SPI_BUS,
                        help=f"Bus SPI (default: {SPI_BUS})")
    parser.add_argument("--device",  type=int, default=SPI_DEVICE,
                        help=f"Dispositivo SPI CS (default: {SPI_DEVICE})")
    parser.add_argument("--verify",  action="store_true",
                        help="Mostrar todos los registros tras la inicialización")
    parser.add_argument("--standby", action="store_true",
                        help="Poner en modo Standby en vez de Normal")
    args = parser.parse_args()

    try:
        transceiver = TLE9255W(bus=args.bus, device=args.device)
    except FileNotFoundError:
        print(f"[ERROR] No se encontró /dev/spidev{args.bus}.{args.device}")
        print("  → Verifica que el SPI esté habilitado (ver setup_canfd2.sh)")
        sys.exit(1)
    except PermissionError:
        print("[ERROR] Permiso denegado. Ejecuta con sudo.")
        sys.exit(1)

    try:
        if args.standby:
            transceiver.set_standby_mode()
            print("[OK] TLE9255W en modo Standby")
        else:
            ok = transceiver.init()
            if not ok:
                sys.exit(1)

        if args.verify:
            transceiver.print_all_registers()
    finally:
        transceiver.close()


if __name__ == "__main__":
    main()
