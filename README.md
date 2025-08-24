## Introduction

Raspberry Pi Pico Micropython driver for the MAX31856 thermocouple.

Most resources about the MAX31856 feature blocking termperature reads, even though the thermocouple supports interrupt based readings. This repo is an attempt to solve that gap.

## Installation

Copy the `max31856.py` file to your pico and you should be good to go.

## Usage

In a file you're working with (like `main.py`), simply add:

```python
from max31856 import MAX31856

SPI_NUMBER = 0
CHIP_SELECT = 1
SERIAL_CLOCK_PIN = 2
MOSI_PIN = 3
MISO_PIN = 0

DRDY_PIN = 15

max31856 = MAX31856(SPI_NUMBER, CHIP_SELECT, [SERIAL_CLOCK_PIN, MOSI_PIN, MISO_PIN])

def on_temp_read(pin):
    print(f"Temperature is: {max31856.read_thermocouple_temperature()}")

max31856.setup_drdy_interrupt(DRDY_PIN, on_temp_read)
```

This will setup a DRDY interrupt on Pin 15 and you'll get the temperature readings every time the chip calculates one!
