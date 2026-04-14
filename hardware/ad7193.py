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
_MODE_DAT_STA = 0x100000  # Append status byte to data reads

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
_MCLK_HZ = 4_915_200.0


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
        self._fs_val = 1
        self._mode_single_val = _MODE_SINGLE | _MODE_CLK_INT | self._fs_val
        self._base_config = _CONFIG_REFSEL | _CONFIG_BUF
        self._config_by_channel = {}
        self._streaming = False
        self._last_stream_chd = -1
        self._last_i_v = 0.0
        self._last_q_v = 0.0
        self._stream_timeout_count = 0
        self._dc_i = 0.0  # run Tare ADC after wiring to set correct offset
        self._dc_q = 0.0  # run Tare ADC after wiring to set correct offset
        self._deadband_v = 0.0

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

    def _fs_from_data_rate(self, data_rate_hz):
        # AD7193 nominal: output_rate ~= (MCLK / 1024) / FS
        rate = max(0.1, float(data_rate_hz))
        fs = int((_MCLK_HZ / 1024.0) / rate)
        return max(1, min(1023, fs))

    def _raw_to_voltage(self, raw):
        # Bipolar, offset-binary output coding.
        return ((raw / 8388608.0) - 1.0) * _VREF / self._gain

    def _wait_ready(self, timeout_s=0.5, poll_sleep_s=0.0002):
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            status = self._read_reg(_REG_STATUS, 1)
            if not (status & 0x80):  # RDY active-low
                return True
            if poll_sleep_s > 0:
                time.sleep(poll_sleep_s)
        return False

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
        self._streaming = False
        self._fs_val = self._fs_from_data_rate(data_rate)
        self._mode_single_val = _MODE_SINGLE | _MODE_CLK_INT | (self._fs_val & 0x3FF)
        self._base_config = _CONFIG_REFSEL | _CONFIG_BUF | _CONFIG_PSEUDO | gain_bits
        self._config_by_channel = {
            0: self._base_config | _DIFF_CH[0],
            1: self._base_config | _DIFF_CH[1],
        }

        # Prime ADC registers.
        self._write_reg(_REG_MODE, self._mode_single_val, 3)
        self._write_reg(_REG_CONFIG, self._base_config, 3)

        realized = (_MCLK_HZ / 1024.0) / self._fs_val
        self._log(
            f"AD7193 config: gain={gain}, FS={self._fs_val}, req_rate={data_rate}Hz "
            f"realized~{realized:.1f}Hz",
            "INFO",
        )

    def start_iq_stream(self):
        """Enable continuous conversions on both channels (throughput mode)."""
        if self._sim:
            return
        stream_cfg = self._base_config | _DIFF_CH[0] | _DIFF_CH[1]
        stream_mode = _MODE_CONT | _MODE_CLK_INT | _MODE_DAT_STA | (self._fs_val & 0x3FF)
        self._write_reg(_REG_CONFIG, stream_cfg, 3)
        self._write_reg(_REG_MODE, stream_mode, 3)
        self._streaming = True
        self._last_stream_chd = -1

    def stop_stream(self):
        """Return ADC to idle mode from streaming mode with verification."""
        if self._sim:
            return
        # Write idle mode to stop continuous conversions
        idle_mode = _MODE_IDLE | _MODE_CLK_INT | (self._fs_val & 0x3FF)
        # Retry up to 3 times to ensure mode change takes effect
        for attempt in range(3):
            self._write_reg(_REG_MODE, idle_mode, 3)
            time.sleep(0.002)  # wait for SPI transaction and ADC response
            # Verify by reading mode register back
            actual_mode = self._read_reg(_REG_MODE, 3)
            if (actual_mode & 0x1F0000) == 0:  # MODE bits [20:16] = 0 = idle
                self._streaming = False
                return
            time.sleep(0.001)
        # If we get here, mode change failed - force flag anyway
        self._log(f"AD7193: stop_stream failed to verify (mode=0x{actual_mode:06X})", "WARNING")
        self._streaming = False

    def read_iq_stream(self, timeout_s=0.1, fast_path=True):
        """Read I/Q using single conversions for reliability in pseudo-differential mode."""
        if self._sim:
            return self._sim_voltage(0), self._sim_voltage(1)
        # Use single conversions for reliability - configure and read each channel
        i_v = self.read_channel(0)
        q_v = self.read_channel(1)
        self._last_i_v = i_v
        self._last_q_v = q_v
        return self._apply_corrections(i_v, q_v)

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

        # Simple single conversion - no streaming complexity
        config_val = self._config_by_channel.get(channel, self._config_by_channel.get(0, self._base_config | _DIFF_CH[0]))
        self._write_reg(_REG_CONFIG, config_val, 3)

        # Start single conversion
        self._write_reg(_REG_MODE, self._mode_single_val, 3)
        # Brief delay to let ADC start conversion (especially after config change)
        time.sleep(0.0005)  # 500us settling

        # Wait for conversion (poll status register RDY bit)
        if not self._wait_ready(timeout_s=0.5, poll_sleep_s=0.0002):
            # Timeout - try to recover by checking status and resetting if needed
            status = self._read_reg(_REG_STATUS, 1)
            self._log(f"AD7193: timeout ch{channel} (status=0x{status:02X}), resetting...", "WARNING")
            self._reset()
            time.sleep(0.01)
            # Reconfigure after reset
            self._write_reg(_REG_CONFIG, config_val, 3)
            self._write_reg(_REG_MODE, self._mode_single_val, 3)
            # Try once more
            if not self._wait_ready(timeout_s=0.3, poll_sleep_s=0.0002):
                self._log(f"AD7193: still timeout after reset ch{channel}", "ERROR")
                return 0.0

        # Read 24-bit data
        raw = self._read_reg(_REG_DATA, 3)
        return self._raw_to_voltage(raw)

    def read_iq(self):
        """Read both I and Q differential channels.

        Returns
        -------
        tuple of (float, float)
            (i_volts, q_volts) from channels 0 and 1.
        """
        i_v = self.read_channel(0)
        q_v = self.read_channel(1)
        return self._apply_corrections(i_v, q_v)

    # ------------------------------------------------------------------
    # Signal conditioning
    # ------------------------------------------------------------------
    def _apply_corrections(self, i_v, q_v):
        """Apply DC offset subtraction and deadband clamping."""
        i_v -= self._dc_i
        q_v -= self._dc_q
        if self._deadband_v > 0.0:
            if abs(i_v) < self._deadband_v:
                i_v = 0.0
            if abs(q_v) < self._deadband_v:
                q_v = 0.0
        return i_v, q_v

    def tare(self, n=64):
        """Sample DC offset with n reads and store for subtraction on all future reads.

        Call this when nothing is connected or before a measurement to zero out
        the mixer quiescent bias.

        Parameters
        ----------
        n : int
            Number of samples to average (default 64).

        Returns
        -------
        tuple of (float, float)
            Measured (dc_i, dc_q) offset in volts.
        """
        if self._sim:
            self._dc_i = 0.0
            self._dc_q = 0.0
            self._log("ADC tare (sim): offsets reset to 0", "INFO")
            return 0.0, 0.0

        # Temporarily clear offsets so we measure raw values
        old_dc_i, old_dc_q = self._dc_i, self._dc_q
        self._dc_i = 0.0
        self._dc_q = 0.0

        i_sum = 0.0
        q_sum = 0.0
        valid = 0
        for _ in range(n):
            try:
                i_v, q_v = self.read_iq_stream(timeout_s=0.15)
                i_sum += i_v
                q_sum += q_v
                valid += 1
            except Exception:
                pass

        if valid == 0:
            self._dc_i = old_dc_i
            self._dc_q = old_dc_q
            self._log("ADC tare failed: no valid samples", "ERROR")
            return old_dc_i, old_dc_q

        self._dc_i = i_sum / valid
        self._dc_q = q_sum / valid
        self._log(
            f"ADC tare: dc_i={self._dc_i*1000:.2f}mV  dc_q={self._dc_q*1000:.2f}mV  (n={valid})",
            "SUCCESS"
        )
        return self._dc_i, self._dc_q

    def set_deadband(self, volts):
        """Set noise-floor deadband in volts. Values |v| < volts are clamped to 0."""
        self._deadband_v = max(0.0, float(volts))
        self._log(f"ADC deadband set to {self._deadband_v*1000:.2f}mV", "INFO")

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
