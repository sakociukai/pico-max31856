import time
from max31856 import MAX31856

max31856 = MAX31856(0, 1, [2, 3, 0])

def on_temp_read(pin):
    print("DRDY gone high, ready to read temperature")
    print(f"Fault status register is {int(max31856.get_thermocouple_health_status())}")
    print(f"Cold junction temperature is: {max31856.read_cold_junction_temperature()}")
    print(f"Thermocouple temperature is: {max31856.read_thermocouple_temperature()}")

max31856.setup_drdy_interrupt(15, on_temp_read)
