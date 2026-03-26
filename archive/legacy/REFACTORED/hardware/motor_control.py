"""
Motor control via I2C and GPIO for Raspberry Pi.
Handles motor initialization, command sending, position waiting, and GPIO interrupts.
"""
import platform
import time


class MotorController:
    """Manages motor control hardware (I2C bus + GPIO interrupts)."""

    def __init__(self, settings: dict, log=None, gui_after=None):
        """
        Args:
            settings:  connection_settings dict (i2c_bus, microcontroller_address, isr_pin …)
            log:       callable(message, level) for debug logging
            gui_after: callable(ms, fn) for scheduling GUI-safe callbacks
        """
        self.settings = settings
        self._log = log or (lambda msg, lvl="INFO": print(f"[{lvl}] {msg}"))
        self._after = gui_after  # may be None outside GUI context

        self.enabled = False
        self.bus = None
        self.gpio = None
        self.movement_ready = True     # True = idle/ready, False = moving
        self.collision_detected = False

        # Public callbacks – the GUI sets these after construction
        self.on_collision = None       # callable()
        self.on_position_reached = None  # callable()

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------
    def initialize(self):
        """Initialize I2C bus and GPIO interrupt on Raspberry Pi."""
        if platform.system() != 'Linux':
            self._log("Motor control not available on this platform – simulation mode", "INFO")
            return

        try:
            from smbus import SMBus
            import RPi.GPIO as GPIO

            i2c_bus_num = int(self.settings.get('i2c_bus', '1'))
            mcu_address = int(self.settings.get('microcontroller_address', '0x55'), 16)
            isr_pin = int(self.settings.get('isr_pin', '17'))

            self._log(f"Initializing motor control: I2C Bus={i2c_bus_num}, "
                      f"Address=0x{mcu_address:02X}, ISR Pin={isr_pin}", "INFO")

            # I2C
            self.bus = SMBus(i2c_bus_num)
            self._log(f"I2C bus {i2c_bus_num} opened successfully", "INFO")

            # Probe
            try:
                status = self.bus.read_byte_data(mcu_address, 0x00)
                self._log(f"Microcontroller detected at 0x{mcu_address:02X}, "
                          f"status=0x{status:02X}", "SUCCESS")
            except Exception as e:
                self._log(f"Could not read from microcontroller at 0x{mcu_address:02X}: {e}", "WARNING")

            # GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(isr_pin, GPIO.IN)
            self.gpio = GPIO
            self._log(f"GPIO pin {isr_pin} configured for interrupt detection", "INFO")

            # Interrupt handler
            def _handle_alert(channel):
                try:
                    status = self.bus.read_byte_data(mcu_address, 0x00)
                    if status & 0x01:
                        self.collision_detected = True
                        if self.on_collision:
                            self.on_collision()
                    if status & 0x02:
                        self.movement_ready = True
                        if self.on_position_reached:
                            self.on_position_reached()
                except Exception as e:
                    self._log(f"Error reading motor status: {e}", "ERROR")

            GPIO.add_event_detect(isr_pin, GPIO.RISING, callback=_handle_alert)
            self._log(f"GPIO interrupt handler registered on pin {isr_pin}", "INFO")

            self.enabled = True
            self._log(f"Motor control initialized successfully", "SUCCESS")

        except ImportError as e:
            self._log(f"Motor control libraries not available: {e}", "ERROR")
            self.enabled = False
        except Exception as e:
            self._log(f"Motor control initialization failed: {e}", "ERROR")
            self.enabled = False

    # ------------------------------------------------------------------
    # Send command
    # ------------------------------------------------------------------
    def send_command(self, motor_num: int, position: float, command: int = 1) -> bool:
        """
        Send motor position command via I2C.

        6-byte message: [command, motor_num, float_byte0 … float_byte3]
        Position is packed as a little-endian 4-byte float.

        Returns True on success.
        """
        if not self.enabled or self.bus is None:
            # Simulation mode
            self.movement_ready = False
            self._log(f"Motor {motor_num}: Simulated move to {position:.2f}°", "INFO")
            # Auto-complete after short delay
            if self._after:
                self._after(500, self._simulate_complete)
            else:
                self.movement_ready = True
            return True

        try:
            import struct

            mcu_address = int(self.settings.get('microcontroller_address', '0x55'), 16)

            packed_val = struct.pack('<f', position)
            message = list(packed_val)
            message.insert(0, command)
            message.insert(1, motor_num)

            msg_dec = ', '.join(str(b) for b in message)
            msg_hex = ' '.join(f'0x{b:02X}' for b in message)
            decoded = struct.unpack('<f', packed_val)[0]

            self._log(f"=== Motor Command ===", "INFO")
            self._log(f"Address: 0x{mcu_address:02X}  Command: {command}  "
                      f"Motor: {motor_num}  Position: {position:.6f}°", "INFO")
            self._log(f"Bytes (dec): [{msg_dec}]", "INFO")
            self._log(f"Bytes (hex): [{msg_hex}]", "INFO")
            self._log(f"Decoded verify: {decoded:.6f}°", "INFO")

            self.bus.write_i2c_block_data(mcu_address, 0x00, message)

            self._log(f"✓ I2C write completed  [{msg_dec}]", "SUCCESS")
            self.movement_ready = False
            return True

        except Exception as e:
            import traceback
            self._log(f"Error sending motor command: {e}", "ERROR")
            self._log(traceback.format_exc(), "ERROR")
            return False

    # ------------------------------------------------------------------
    # Wait helpers
    # ------------------------------------------------------------------
    def wait_for_position(self, timeout: float = 5.0) -> bool:
        """Block until motor reaches position, collision, or timeout."""
        if not self.enabled:
            time.sleep(0.1)
            return True
        start = time.time()
        while not self.movement_ready and (time.time() - start) < timeout:
            if self.collision_detected:
                return False
            time.sleep(0.05)
        return self.movement_ready

    def _simulate_complete(self):
        self.movement_ready = True

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def cleanup(self):
        """Release GPIO and I2C resources."""
        if self.gpio:
            try:
                self.gpio.cleanup()
            except Exception:
                pass
        if self.bus:
            try:
                self.bus.close()
            except Exception:
                pass
        self.enabled = False
