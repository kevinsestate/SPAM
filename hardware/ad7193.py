"""
AD7193 24-bit Sigma-Delta ADC Driver (Pmod AD5)

SPI interface to the Analog Devices AD7193 used on the Digilent Pmod AD5.
Reads two differential channels (IF-I and IF-Q) from the SPAM mixer.

On non-Linux platforms, operates in simulation mode with synthetic data.
"""

import platform
import math
import time

_SIM_MODE = False
try:
    import spidev
except ImportError:
    _SIM_MODE = True

# ---------------------------------------------------------------------------
# AD7193 register addresses
# ---------------------------------------------------------------------------
_REG_COMM   = 0x00  # Communications (write-only, starts every transaction)
_REG_STATUS = 0x00  # Status (read-only, same address as comm)
_REG_MODE   = 0x01  # Mode register (24-bit)
_REG_CONFIG = 0x02  # Configuration register (24-bit)
_REG_DATA   = 0x03  # Data register (24-bit)
_REG_ID     = 0x04  # ID register (8-bit)
_REG_GPOCON = 0x05  # GPOCON register (8-bit)
_REG_OFFSET = 0x06  # Offset register (24-bit)
_REG_FS     = 0x07  # Full-scale register (24-bit)

# Command byte bits
_COMM_READ  = 0x40  # Read operation
_COMM_WRITE = 0x00  # Write operation

# Mode register values
_MODE_SINGLE = 0x200000  # Single conversion mode
_MODE_IDLE   = 0x400000  # Idle mode
_MODE_CONT   = 0x000000  # Continuous conversion mode
_MODE_CLK_INT = 0x080000  # CLK1=1, CLK0=0 (internal 4.92 MHz clock)

# Config register bits
_CONFIG_CHOP_DIS = 0x000000  # Chop disabled
_CONFIG_REFSEL   = 0x000000  # REFIN1 reference (Pmod AD5 on-board default)
_CONFIG_PSEUDO   = 0x040000  # Pseudo-differential (0 = fully differential)
_CONFIG_BUF      = 0x000010  # Buffered mode

# Gain settings
_GAIN_MAP = {1: 0, 8: 3, 16: 4, 32: 5, 64: 6, 128: 7}

# Differential channel pairs on AD7193:
# Ch0 = AIN1+ / AIN1-  (IF-I)
# Ch1 = AIN2+ / AIN2-  (IF-Q)
_DIFF_CH = {0: 0x0100, 1: 0x0200}

# Reference voltage (Pmod AD5 uses external 2.5V reference)
_VREF = 2.5


class AD7193:
    """AD7193 24-bit ADC over SPI.

    Parameters
    ----------
    spi_bus : int
        SPI bus number (typically 0 on Raspberry Pi).
    spi_cs : int
        Chip-select line (0 or 1).
    speed_hz : int
        SPI clock speed in Hz (max 6.17 MHz for AD7193).
    log_fn : callable, optional
        Logging callback ``log_fn(message, level)``.
    """

    def __init__(self, spi_bus=0, spi_cs=0, speed_hz=1_000_000, log_fn=None):
        self._log = log_fn or (lambda m, l: None)
        self._sim = _SIM_MODE or platform.system() != 'Linux'
        self._gain = 1
        self._data_rate = 96
        self._sim_angle = 0.0  # used for simulation sweep

        if self._sim:
            self._spi = None
            self._log("AD7193: simulation mode (spidev not available)", "WARNING")
            return

        self._spi = spidev.SpiDev()
        self._spi.open(spi_bus, spi_cs)
        self._spi.max_speed_hz = speed_hz
        self._spi.mode = 3  # CPOL=1, CPHA=1 (AD7193 SPI mode 3)
        self._spi.bits_per_word = 8

        self._reset()
        self._verify_id()
        self._log(f"AD7193: initialized on SPI{spi_bus}.{spi_cs} @ {speed_hz/1e6:.1f}MHz", "SUCCESS")

    # ------------------------------------------------------------------
    # Low-level SPI helpers
    # ------------------------------------------------------------------
    def _reset(self):
        """Reset the AD7193 by sending 40+ high bits."""
        if self._sim:
            return
        self._spi.xfer2([0xFF] * 6)
        time.sleep(0.01)

    def _write_reg(self, reg, value, nbytes):
        """Write *nbytes* (1-3) to register *reg*."""
        cmd = _COMM_WRITE | (reg << 3)
        data = [cmd]
        for i in range(nbytes - 1, -1, -1):
            data.append((value >> (8 * i)) & 0xFF)
        self._spi.xfer2(data)

    def _read_reg(self, reg, nbytes):
        """Read *nbytes* (1-3) from register *reg*."""
        cmd = _COMM_READ | (reg << 3)
        result = self._spi.xfer2([cmd] + [0x00] * nbytes)
        value = 0
        for b in result[1:]:
            value = (value << 8) | b
        return value

    def _verify_id(self):
        """Read the ID register to verify communication."""
        if self._sim:
            return
        id_val = self._read_reg(_REG_ID, 1)
        # AD7193 ID reset value is 0xX2 (low nibble fixed to 0x2).
        if (id_val & 0x0F) != 0x02:
            self._log(f"AD7193: unexpected ID=0x{id_val:02X} (expected 0xX2)", "WARNING")
        else:
            self._log(f"AD7193: ID=0x{id_val:02X} verified", "INFO")

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def configure(self, gain=1, data_rate=96):
        """Configure ADC gain and output data rate.

        Parameters
        ----------
        gain : int
            Programmable gain: 1, 8, 16, 32, 64, or 128.
        data_rate : int
            Output data rate in Hz. The AD7193 filter register (FS)
            determines this: rate ~= 4.8MHz / (128 * FS).
            Common values: 96 Hz (FS=390), 50 Hz (FS=750), 10 Hz (FS=3750).
        """
        self._gain = gain
        self._data_rate = data_rate

        if self._sim:
            self._log(f"AD7193 config (sim): gain={gain}, rate={data_rate}Hz", "INFO")
            return

        gain_bits = _GAIN_MAP.get(gain, 0)

        # FS value from desired data rate (approximate)
        fs_val = max(1, min(1023, int(4_800_000 / (128 * data_rate))))

        # Mode register: single conversion, internal clock, no averaging
        mode_val = _MODE_SINGLE | _MODE_CLK_INT | (fs_val & 0x3FF)
        self._write_reg(_REG_MODE, mode_val, 3)

        # Config register: channel selection done per-read, gain, buffered, differential
        config_val = _CONFIG_REFSEL | _CONFIG_BUF | gain_bits
        self._write_reg(_REG_CONFIG, config_val, 3)

        self._log(f"AD7193 config: gain={gain}, FS={fs_val}, rate~{data_rate}Hz", "INFO")

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def read_channel(self, channel):
        """Read a single differential channel.

        Parameters
        ----------
        channel : int
            0 = AIN1+/AIN1- (IF-I), 1 = AIN2+/AIN2- (IF-Q).

        Returns
        -------
        float
            Voltage in volts.
        """
        if self._sim:
            return self._sim_voltage(channel)

        ch_bits = _DIFF_CH.get(channel, _DIFF_CH[0])
        gain_bits = _GAIN_MAP.get(self._gain, 0)

        # Write config with selected channel
        config_val = _CONFIG_REFSEL | _CONFIG_BUF | ch_bits | gain_bits
        self._write_reg(_REG_CONFIG, config_val, 3)

        # Start single conversion
        fs_val = max(1, min(1023, int(4_800_000 / (128 * self._data_rate))))
        mode_val = _MODE_SINGLE | _MODE_CLK_INT | (fs_val & 0x3FF)
        self._write_reg(_REG_MODE, mode_val, 3)

        # Wait for conversion (poll status register RDY bit)
        timeout = time.time() + 1.0
        while time.time() < timeout:
            status = self._read_reg(_REG_STATUS, 1)
            if not (status & 0x80):  # RDY bit is active-low
                break
            time.sleep(0.001)
        else:
            self._log(f"AD7193: timeout reading ch{channel}", "ERROR")
            return 0.0

        # Read 24-bit data
        raw = self._read_reg(_REG_DATA, 3)

        # Convert to voltage: bipolar, code is offset binary
        # V = ((raw / 2^23) - 1) * Vref / gain
        voltage = ((raw / 8388608.0) - 1.0) * _VREF / self._gain
        return voltage

    def read_iq(self):
        """Read both I and Q differential channels.

        Returns
        -------
        tuple of (float, float)
            (i_volts, q_volts) from channels 0 and 1.
        """
        i_v = self.read_channel(0)
        q_v = self.read_channel(1)
        return i_v, q_v

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------
    def _sim_voltage(self, channel):
        """Generate synthetic I/Q voltage for simulation mode."""
        angle_rad = math.radians(self._sim_angle)
        if channel == 0:  # IF-I
            return 0.5 * math.cos(angle_rad) * (1.0 - 0.3 * self._sim_angle / 90.0)
        else:  # IF-Q
            return 0.5 * math.sin(angle_rad) * (1.0 - 0.3 * self._sim_angle / 90.0)

    def set_sim_angle(self, angle_deg):
        """Set the current angle for simulation voltage generation."""
        self._sim_angle = angle_deg

    @property
    def is_simulated(self):
        return self._sim

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def close(self):
        """Close the SPI device."""
        if self._spi:
            try:
                self._spi.close()
            except Exception:
                pass
            self._spi = None
