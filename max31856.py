from machine import SPI, Pin

CONFIG_REGISTER_0 = 0x00
CONFIG_REGISTER_1 = 0x01
COLD_JUNCTION_T_OFFSET_REGISTER = 0x09
THERMOCOUPLE_T_REGISTER = 0x0C
FAULT_STATUS_REGISTER = 0x0F


class ThermoCoupleType:
    B_Type = 0b0000
    E_Type = 0b0001
    J_Type = 0b0010
    K_Type = 0b0011
    N_Type = 0b0100
    R_Type = 0b0101
    S_Type = 0b0110
    T_Type = 0b0111


class FaultError:
    THERMOCOUPLE_OPEN_CIRCUIT = 0
    OVER_UNDER_VOLTAGE = 1
    # The following four fault by default are not achievable unless these values are set to
    # different values, they are stored from register 0x03/0x83 up to a register 0x08/0x88
    THERMOCOUPLE_LOW_FAULT = 2
    THERMOCOUPLE_HIGH_FAULT = 3
    COLD_JUNCTION_LOW_FAULT = 4
    COLD_JUNCTION_HIGH_FAULT = 5
    # Cold junction temperature should range mostly from -55 to 150 degrees Celsius with B-type
    # thermocouple being an exception (0-155 C). Thermocouple temperatures vary from one type to
    # another. Normal operation ranges can be found in MAX31856 datasheet
    THERMOCOUPLE_OUT_OF_RANGE = 6
    COLD_JUNCTION_OUT_OF_RANGE = 7


class MAX31856:
    # TODO: add FLT pin and set interrupt (and setting when to trigger fault)
    # TODO: write a fault threshold value setting function
    def __init__(
        self,
        spi_x,
        cs_pin=1,
        pins: tuple[Pin, Pin, Pin] = None,
        avgsel=2,
        tc_type=ThermoCoupleType.K_Type,
    ):
        self.chip_select = Pin(cs_pin, Pin.OUT, value=1)
        kwargs = {}
        if pins is not None:
            kwargs["sck"] = pins[0]
            kwargs["mosi"] = pins[1]
            kwargs["miso"] = pins[2]
        self.spi_handle = SPI(spi_x, baudrate=4000000, phase=1, **kwargs)
        self.set_register(
            CONFIG_REGISTER_1, self.build_config_register_1(avgsel, tc_type)
        )

    def build_config_register_0(self, one_shot=False, filter50Hz=True):
        """
        Builds a value for configuration 0 register (CR0).
        This is going to set some assumptions:
            * bit 3 (CJ) will be zero as we don't want Cold Junction sensor disabled ever
            * bit 2 (FAULT) will be zero as we'll stick to comparator mode and handle interrupt on an edge
            * bit 1 (FAULTCLR) gets irrelevant because of bit 2 always being zero

        That leaves us with:
            * bits [7:6] will deal with continuous conversion vs a single conversion
            * bits [5:4] will deal with open-circuit fault detection (TODO)
            * bit 0 will select rejection of harmonics, 60Hz vs 50Hz
        """
        cr0 = (1 << 0) if filter50Hz else 0
        if one_shot:
            cr0 |= 1 << 6
        else:
            cr0 |= 1 << 7
        return cr0

    def build_config_register_1(self, avg_sel=1, tc_type=ThermoCoupleType.K_Type):
        """
        Builds a value for configuration 1 register (CR1).
        This register is used to select the thermocouple Type (K_Type being the default), also
        average of readings per sample (avg_sel, 1 by default). Higher readings count slows the
        operation down
        """
        level = 0
        while avg_sel > 1:
            avg_sel = avg_sel / 2
            level += 1
        return tc_type | (level << 4)

    def setup_drdy_interrupt(self, drdy: Pin, on_event):
        """
        Setup an interrupt to trigger on the falling edge of DRDY.
        It sets up a drdy Pin() as an input with a pull-up resistor. The dummy register read
        is to make sure that a new temperature value is going to be presented and we won't be
        stuck because the logic level newer returning to the High logic level
        """
        drdy_pin = Pin(drdy, Pin.IN, Pin.PULL_UP)
        drdy_pin.irq(on_event, Pin.IRQ_FALLING)
        self.get_register(THERMOCOUPLE_T_REGISTER, 2)
        self.set_register(
            CONFIG_REGISTER_0, self.build_config_register_0(one_shot=False)
        )

    def request_one_shot_sample(self):
        """
        Requests One-Shot sample and puts the MAX31856 into a Normally-Off Conversion mode
        After requesting a one shot sample the user to wait 150-200 ms before reading the
        value out from a register
        """
        self.set_register(
            CONFIG_REGISTER_0, self.build_config_register_0(one_shot=True)
        )

    def set_register(self, register, value):
        """
        Writes a value to register

        The function adds 0x80 to the register value as per MAX31856 specification, where
        different register values are used for reading and writing
        """
        self.chip_select.value(0)
        self.spi_handle.write(bytes([register | 0x80, value]))
        self.chip_select.value(1)

    def get_register(self, register, nbytes):
        """
        Reads an nbytes count of values and returns them in a bytearray

        User needs to pass the first value and then can read past it
        """
        self.chip_select.value(0)
        self.spi_handle.write(bytes([register]))
        data = self.spi_handle.read(nbytes)
        self.chip_select.value(1)
        return data

    def read_cold_junction_temperature(self):
        rxdata = self.get_register(COLD_JUNCTION_T_OFFSET_REGISTER, 3)
        offset = rxdata[0]
        [junc_msb, junc_lsb] = [rxdata[1], rxdata[2]]

        temp = ((junc_msb << 8) | junc_lsb) >> 2
        temp = offset + temp

        if junc_msb & 0x80:
            temp -= 0x4000

        return temp * 0.015625

    def read_thermocouple_temperature(self):
        """
        Read linearized and cold junction compensated thermocouple temperature in degrees C
        """
        out = self.get_register(THERMOCOUPLE_T_REGISTER, 3)
        [tc_highByte, tc_middleByte, tc_lowByte] = [out[0], out[1], out[2]]
        temp = ((tc_highByte << 16) | (tc_middleByte << 8) | tc_lowByte) >> 5

        if tc_highByte & 0x80:
            temp -= 0x80000
        return temp * 0.0078125

    def get_thermocouple_health_status(self):
        """
        This function reads FAULT Status Register (0x0F) and returns a hex value
        A zero value should be expected on a normal operations. To decode the result,
        Do bit matching on FaultError struct elements, for example,
        (results & 1 << THERMOCOUPLE_OPEN_CIRCUIT) would mean Thermocouple is most probably
        not connected at all.

        This function doesn't do anything with FAULT pin. Register 02h/82h: Fault Mask Register
        is used to control that pin, and that functionality is skippped is this function, but
        this function could be used from a FAULT pin interrupt
        """
        return self.get_register(FAULT_STATUS_REGISTER, 1)[0]
