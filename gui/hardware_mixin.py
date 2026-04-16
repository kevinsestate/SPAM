"""HardwareMixin: _initialize_hardware, motor commands."""

import time
import platform

from hardware import AD7193, RFSwitch, HPS2518Servo


class HardwareMixin:
    """Provides hardware initialization and motor control methods."""

    def _initialize_hardware(self):
        # --- Motor control (Linux / Pi only) ---
        if platform.system() != 'Linux':
            self.motor_status_var.set("Not Available (Windows)")
        else:
            try:
                from smbus import SMBus
                import RPi.GPIO as GPIO
                mcu_address = int(self.connection_settings.get('microcontroller_address', '0x55'), 16)
                isr_pin = int(self.connection_settings.get('isr_pin', '17'))
                self.motor_bus = SMBus(1)
                try:
                    status = self.motor_bus.read_byte_data(mcu_address, 0x00)
                    self._log_debug(f"MCU at 0x{mcu_address:02X}, status=0x{status:02X}", "SUCCESS")
                except Exception as e:
                    self._log_debug(f"MCU read warning: {e}", "WARNING")
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(isr_pin, GPIO.IN)
                self.motor_gpio = GPIO
                def handle_alert(channel):
                    try:
                        lock = getattr(self, '_i2c_lock', None)
                        if lock:
                            lock.acquire()
                        try:
                            st = self.motor_bus.read_byte_data(mcu_address, 0x00)
                        finally:
                            if lock:
                                lock.release()
                        if st & 0x01:
                            self.motor_collision_detected = True
                            self.after(0, lambda: self._log_debug("COLLISION DETECTED", "ERROR"))
                            self.after(0, lambda: self.motor_status_var.set("COLLISION!"))
                            if self.is_measuring:
                                self.after(0, self._on_stop_measurement)
                        if st & 0x02:
                            self._motor_done_seq += 1
                            self.after(0, lambda: self.motor_status_var.set("Ready"))
                    except OSError as e:
                        self.after(0, lambda e=e: self._log_debug(f"Motor status error: {e}", "ERROR"))
                        if e.errno in (5, 121):
                            self.after(0, self._recover_i2c_bus)
                    except Exception as e:
                        self.after(0, lambda e=e: self._log_debug(f"Motor status error: {e}", "ERROR"))
                try:
                    GPIO.add_event_detect(isr_pin, GPIO.RISING, callback=handle_alert)
                    self.motor_isr_available = True
                    self._log_debug(f"GPIO edge detect on pin {isr_pin} OK", "SUCCESS")
                except RuntimeError as e:
                    self.motor_isr_available = False
                    self._log_debug(f"GPIO edge detect failed: {e} (will poll I2C instead)", "WARNING")
                self.motor_control_enabled = True
                self.motor_status_var.set("Ready")
                self._log_debug("Motor control initialized", "SUCCESS")
            except ImportError as e:
                self.motor_status_var.set("Libraries N/A")
                self._log_debug(f"Motor libs missing: {e}", "ERROR")
                self.motor_control_enabled = False

        # --- AD7193 ADC (Pmod AD5) ---
        try:
            spi_bus = int(self.connection_settings.get('spi_bus', '0'))
            spi_cs = int(self.connection_settings.get('spi_cs', '0'))
            spi_speed = int(self.connection_settings.get('spi_speed', '1000000'))
            gain = int(self.connection_settings.get('adc_gain', '1'))
            data_rate = int(self.connection_settings.get('adc_data_rate', '96'))
            self.adc = AD7193(spi_bus, spi_cs, spi_speed, log_fn=self._log_debug)
            self.adc.configure(gain=gain, data_rate=data_rate)
            if not self.adc.is_simulated:
                self.adc.start_iq_stream()
                self._log_debug("ADC stream started", "SUCCESS")
            mode_str = "SIM" if self.adc.is_simulated else "SPI"
            self._log_debug(f"ADC ready ({mode_str})", "SUCCESS")
        except Exception as e:
            self._log_debug(f"ADC init failed: {e}", "ERROR")
            self.adc = None

        # --- RF Switch (optional) ---
        self.rf_switch_enabled = str(self.connection_settings.get('enable_rf_switch', '0')).strip().lower() in ('1', 'true', 'yes', 'on')
        if not self.rf_switch_enabled:
            self.rf_switch = None
            self._log_debug("RF switch control disabled (ADC-only mode)", "INFO")
        else:
            try:
                sw_pin = int(self.connection_settings.get('switch_gpio', '22'))
                self.rf_switch = RFSwitch(gpio_pin=sw_pin, log_fn=self._log_debug)
                mode_str = "SIM" if self.rf_switch.is_simulated else "GPIO"
                self._log_debug(f"RF switch ready ({mode_str})", "SUCCESS")
            except Exception as e:
                self._log_debug(f"RF switch init failed: {e}", "ERROR")
                self.rf_switch = None

        # --- HPS-2518MG Servo (GPIO PWM) ---
        try:
            servo_pin = int(self.connection_settings.get('servo_gpio', '18'))
            self.servo = HPS2518Servo(gpio_pin=servo_pin, log_fn=self._log_debug)
            mode_str = "SIM" if self.servo.is_simulated else "GPIO"
            self._log_debug(f"Servo ready ({mode_str}) on GPIO{servo_pin}", "SUCCESS")
        except Exception as e:
            self._log_debug(f"Servo init failed: {e}", "ERROR")
            self.servo = None

    def _send_servo_command(self, angle: float, settle_s: float = 0.5) -> bool:
        """Command the HPS-2518MG servo to *angle* degrees (0-180).

        Parameters
        ----------
        angle : float
            Target angle in degrees.
        settle_s : float
            Seconds to wait for servo to reach position.

        Returns
        -------
        bool
            True on success (including simulation).
        """
        if self.servo is None:
            self._log_debug(f"Servo (sim): -> {angle:.1f}°", "INFO")
            self.servo_angle = angle
            self.current_polarization = angle
            return True
        try:
            self.servo.move_to(angle, settle_s=settle_s)
            self.servo_angle = angle
            self.current_polarization = angle
            return True
        except Exception as e:
            self._log_debug(f"Servo cmd error: {e}", "ERROR")
            return False

    def _recover_i2c_bus(self):
        """Close and reopen SMBus to clear a stuck I2C bus (EIO / EREMOTEIO)."""
        try:
            i2c_bus_num = int(self.connection_settings.get('i2c_bus', '1'))
            self.motor_bus.close()
            time.sleep(0.05)
            from smbus import SMBus
            self.motor_bus = SMBus(i2c_bus_num)
            self._log_debug("I2C bus recovered (reopened)", "WARNING")
        except Exception as e:
            self._log_debug(f"I2C recovery failed: {e}", "ERROR")

    def _send_motor_command(self, motor_num: int, position: float, command: int = 1) -> bool:
        if not self.motor_control_enabled or self.motor_bus is None:
            self.motor_movement_status = False
            self.motor_status_var.set("Moving (Sim)")
            self.after(0, lambda: self._log_debug(f"Motor {motor_num}: Sim move to {position:.2f}\u00b0", "INFO"))
            self.after(int(self.measurement_interval * 1000), self._simulate_motor_complete)
            return True
        try:
            import struct
            mcu_address = int(self.connection_settings.get('microcontroller_address', '0x55'), 16)
            packed_val = struct.pack('<f', position)
            message = list(packed_val)
            message.insert(0, command)
            message.insert(1, motor_num)
            msg_dec = ', '.join(str(b) for b in message)
            self._log_debug(f"I2C cmd: [{msg_dec}]", "INFO")
            self._motor_expect_seq = self._motor_done_seq + 1  # expect next ISR edge
            self.motor_collision_detected = False  # clear stale collision before each move
            lock = getattr(self, '_i2c_lock', None)
            if lock:
                lock.acquire()
            try:
                self.motor_bus.write_i2c_block_data(mcu_address, 0x00, message)
            finally:
                if lock:
                    lock.release()
            self.after(0, lambda: self.motor_status_var.set("Moving..."))
            self.motor_num = motor_num
            self.motor_command = command
            self.motor_position_var.set(f"{position:.1f}\u00b0")
            # 50ms settle — lets I2C transaction complete and SPI bus settle
            # before next read_channel call (which reconfigures ADC cleanly itself).
            time.sleep(0.05)
            return True
        except OSError as e:
            self._log_debug(f"Motor cmd error: {e}", "ERROR")
            self.motor_status_var.set("Error")
            if e.errno in (5, 121):  # EIO / EREMOTEIO — bus stuck, try to recover
                self._recover_i2c_bus()
            return False
        except Exception as e:
            self._log_debug(f"Motor cmd error: {e}", "ERROR")
            self.motor_status_var.set("Error")
            return False

    def _send_home_command(self) -> bool:
        """Send homing sequence to MCU (command=3). motor_num and position are ignored by firmware."""
        self._log_debug("Sending home command (cmd=3)", "INFO")
        self.motor_status_var.set("Homing...")
        return self._send_motor_command(motor_num=0, position=0.0, command=3)

    def _simulate_motor_complete(self):
        self.motor_movement_status = True
        self.motor_status_var.set("Ready (Sim)")

    def _wait_for_motor_position(self, timeout: float = 10.0) -> bool:
        if not self.motor_control_enabled:
            time.sleep(0.1)
            return True
        if self.motor_bus is not None:
            # Poll MCU status register for bit 0x02 (position reached).
            # The MCU only pulses GPIO17 for homing, not for regular moves,
            # so ISR-based waiting is unreliable for moves — always poll I2C.
            mcu_address = int(self.connection_settings.get('microcontroller_address', '0x55'), 16)
            lock = getattr(self, '_i2c_lock', None)
            start = time.time()
            # Phase 1: wait up to 2s for 0x02 to CLEAR (MCU accepted the command).
            # Also break immediately if 0x02 is already SET — motor finished instantly.
            while (time.time() - start) < 2.0:
                if self.motor_collision_detected:
                    return False
                try:
                    if lock:
                        lock.acquire()
                    try:
                        st = self.motor_bus.read_byte_data(mcu_address, 0x00)
                    finally:
                        if lock:
                            lock.release()
                    if not (st & 0x02):
                        break  # bit cleared — MCU accepted and is moving
                    if st & 0x02:
                        self.motor_movement_status = True
                        return True  # already done — fast move completed before first poll
                except Exception:
                    pass
                time.sleep(0.05)
            # Phase 2: wait for 0x02 to SET (motor reached position).
            while (time.time() - start) < timeout:
                if self.motor_collision_detected:
                    return False
                try:
                    if lock:
                        lock.acquire()
                    try:
                        st = self.motor_bus.read_byte_data(mcu_address, 0x00)
                    finally:
                        if lock:
                            lock.release()
                    if st & 0x02:
                        self.motor_movement_status = True
                        return True
                except Exception:
                    pass
                time.sleep(0.05)
            # Timeout — assume reached so sweep continues.
            self._log_debug(f"Motor timeout ({timeout:.0f}s) — continuing", "WARNING")
            self.motor_movement_status = True
            return True
        # No bus — simulation.
        time.sleep(0.1)
        return True
