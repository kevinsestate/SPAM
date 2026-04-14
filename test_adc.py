#!/usr/bin/env python3
"""Quick ADC test script - reads I/Q and prints values."""

import sys
import time

# Add project to path
sys.path.insert(0, '/home/dibr4426/Desktop/SPAM')

from hardware.ad7193 import AD7193

def log(msg, level="INFO"):
    print(f"[{level}] {msg}")

def main():
    print("=" * 50)
    print("AD7193 ADC Test")
    print("=" * 50)
    print()
    
    # Initialize ADC
    try:
        adc = AD7193(spi_bus=0, spi_cs=0, speed_hz=1_000_000, log_fn=log)
        print(f"ADC initialized (sim={adc.is_simulated})")
    except Exception as e:
        print(f"Failed to init ADC: {e}")
        return
    
    # Configure
    adc.configure(gain=1, data_rate=4800)
    print(f"Configured: gain={adc._gain}, rate={adc._data_rate}Hz")
    print(f"DC offsets: I={adc._dc_i*1000:.2f}mV, Q={adc._dc_q*1000:.2f}mV")
    print()
    
    # Test single reads
    print("Single channel reads:")
    for i in range(5):
        i_raw = adc.read_channel(0)
        q_raw = adc.read_channel(1)
        print(f"  I={i_raw*1000:+.2f} mV   Q={q_raw*1000:+.2f} mV")
        time.sleep(0.1)
    
    print()
    print("Stream reads (10 samples):")
    for i in range(10):
        i_v, q_v = adc.read_iq_stream()
        print(f"  I={i_v*1000:+.2f} mV   Q={q_v*1000:+.2f} mV")
        time.sleep(0.1)
    
    print()
    print("Test complete.")

if __name__ == "__main__":
    main()
