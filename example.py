import time
from max31856 import MAX31856

max31856 = MAX31856(0, 1, [2, 3, 0])
# This requesting sample and waiting is needed now because we want to trigger a single shot
# temperature reading
max31856.request_one_shot_sample()
time.sleep(0.2)

print(f"Cold junction temperature is: {max31856.read_cold_junction_temperature()}")
print(f"Thermocouple temperature is: {max31856.read_thermocouple_temperature()}")

