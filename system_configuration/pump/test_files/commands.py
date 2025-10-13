from pump_commands import PumpCommands
import time
import logging

# Configure logging to file and console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('../pump_operations.log'),
        logging.StreamHandler()  # Also print to console
    ]
)

print("="*60)
print("XLP6000 Pump Diagnostic Test Script")
print("="*60)

# Initialize pump object
pump = PumpCommands()
pump.port = 'COM9'
pump.baud_rate = 9600
pump.pump_address = 1


# Connect to pump
pump.connect()
if not pump.is_connected:
    logging.error("Failed to connect to pump. Exiting.")
    exit(1)

# Initialize pump
pump.initialize_pump()
time.sleep(10)

# pump.continuous_pump(1000000,10000,1,1)










