from smbus import SMBus
import struct
import RPi.GPIO as GPIO

address = 0x55
bus = SMBus(1)
isrPin = 17
movementStatus = True


GPIO.setmode(GPIO.BCM)
GPIO.setup(isrPin, GPIO.IN)

def handleAlert(channel):
	status = bus.read_byte_data(address, 0x00)
	if status & 0x01:
		print("COLLISION DETECTED\n>>> ")
	if status & 0x02:
		movementStatus = True
		print("POSITION REACHED\n>>> ")

GPIO.add_event_detect(isrPin, GPIO.RISING, callback=handleAlert)

try:
	while(True):
		print("enter command: ")
		command = int(input(">>> "))
		
		

		print("enter motorNum: ")

		motorNum = int(input(">>> "))

		print("input position: ")
		position = float(input(">>> "))
		
		packed_val = struct.pack('<f', position)
		#int_pos = struct.unpack('<Q', packed_val)[0]
		
		#print(hex(int_pos))
		
		#pos8 = int_pos & 0xff
		#pos7 = (int_pos >> 8) & 0xff
		#pos6 = (int_pos >> 16) & 0xff
		#pos5 = (int_pos >> 24) & 0xff
		#pos4 = (int_pos >> 32) & 0xff
		#pos3 = (int_pos >> 40) & 0xff
		#pos2 = (position >> 48) & 0xff
		#pos1 = (position >> 56) & 0xff
		

		#message = [command, motorNum, pos1, pos2, pos3, pos4, pos5, pos6, pos7, pos8]
		
		message = list(packed_val)
		message.insert(0, command)
		message.insert(1, motorNum)
		
		print(message)
		bus.write_i2c_block_data(address, 0x00, message)
		movementStatus = False
		print("MOVING")
#		while(not movementStatus):
#			pass
except KeyboardInterrupt:
	print("\n")
	GPIO.cleanup()
