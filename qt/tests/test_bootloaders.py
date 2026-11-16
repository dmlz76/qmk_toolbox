from qmk_toolbox.message_type import MessageType


def test_usb_device_description(harness):
    assert str(harness.device(0xFEED, 0x6060, 0x0001)) == "Maker Board (FEED:6060:0001)"


def test_command_line_is_logged(harness):
    harness.device(0x16C0, 0x05DF).reset("atmega32a")
    assert harness.messages == [("bootloadHID -r", MessageType.COMMAND)]


def test_atmel_dfu(harness):
    device = harness.device(0x03EB, 0x2FF4)
    assert (device.name, device.eeprom_flashable, device.resettable) == ("Atmel DFU", True, True)

    device.flash("atmega32u4", "fw.hex")
    assert harness.calls == [
        ("dfu-programmer", ["atmega32u4", "erase", "--force"]),
        ("dfu-programmer", ["atmega32u4", "flash", "--force", "fw.hex"]),
        ("dfu-programmer", ["atmega32u4", "reset"]),
    ]

    harness.calls.clear()
    device.flash_eeprom("atmega32u4", "reset.eep")
    assert harness.calls == [
        ("dfu-programmer", ["atmega32u4", "erase", "--force"]),
        ("dfu-programmer", ["atmega32u4", "flash", "--force", "--suppress-validation", "--eeprom", "reset.eep"]),
    ]
    assert harness.messages_of(MessageType.BOOTLOADER) == ["Please reflash device with firmware now"]


def test_qmk_dfu_eeprom_does_not_erase(harness):
    device = harness.device(0x03EB, 0x2FF4, 0x0936)
    assert device.name == "QMK DFU"

    device.flash_eeprom("atmega32u4", "reset.eep")
    assert harness.calls == [
        ("dfu-programmer", ["atmega32u4", "flash", "--force", "--suppress-validation", "--eeprom", "reset.eep"]),
    ]
    assert harness.messages_of(MessageType.BOOTLOADER) == []


def test_caterina(harness):
    device = harness.device(0x1B4F, 0x9205)
    assert str(device) == "Maker Board (1B4F:9205:0100) [/dev/ttyACM0]"

    device.flash("atmega32u4", "fw.hex")
    device.flash_eeprom("atmega32u4", "reset.eep")
    assert harness.calls == [
        ("avrdude", ["-p", "atmega32u4", "-c", "avr109", "-U", "flash:w:fw.hex:i", "-P", "/dev/ttyACM0"]),
        ("avrdude", ["-p", "atmega32u4", "-c", "avr109", "-U", "eeprom:w:reset.eep:i", "-P", "/dev/ttyACM0"]),
    ]


def test_avrdude_config_is_passed_when_configured(harness):
    harness.context.avrdude_conf = "/data/avrdude.conf"
    harness.device(0x16C0, 0x05DC).flash("atmega32u4", "fw.hex")
    assert harness.calls == [
        ("avrdude", ["-p", "atmega32u4", "-c", "usbasp", "-U", "flash:w:fw.hex:i", "-C", "/data/avrdude.conf"]),
    ]


def test_serial_port_is_retried_until_found(harness):
    harness.serial_port = None
    device = harness.device(0x1B4F, 0x9205)
    assert str(device) == "Maker Board (1B4F:9205:0100)"

    device.flash("atmega32u4", "fw.hex")
    assert harness.calls == []
    assert harness.messages_of(MessageType.ERROR) == ["Serial port not found!"]

    harness.serial_port = "/dev/ttyACM1"
    device.flash("atmega32u4", "fw.hex")
    assert harness.calls[0][1][-2:] == ["-P", "/dev/ttyACM1"]


def test_avrisp_and_usbtiny(harness):
    harness.device(0x16C0, 0x0483).flash("atmega32u4", "fw.hex")
    harness.device(0x1781, 0x0C9F).flash_eeprom("atmega32u4", "reset.eep")
    assert harness.calls == [
        ("avrdude", ["-p", "atmega32u4", "-c", "avrisp", "-U", "flash:w:fw.hex:i", "-P", "/dev/ttyACM0"]),
        ("avrdude", ["-p", "atmega32u4", "-c", "usbtiny", "-U", "eeprom:w:reset.eep:i"]),
    ]


def test_atmel_samba(harness):
    device = harness.device(0x03EB, 0x6124)
    device.flash("", "fw.bin")
    device.reset("")
    assert harness.calls == [
        ("mdloader", ["-p", "/dev/ttyACM0", "-D", "fw.bin", "--restart"]),
        ("mdloader", ["-p", "/dev/ttyACM0", "--restart"]),
    ]


def test_stm32_dfu(harness):
    device = harness.device(0x0483, 0xDF11)
    device.flash("", "fw.BIN")
    device.reset("")
    assert harness.calls == [
        ("dfu-util", ["-a", "0", "-d", "0483:DF11", "-s", "0x08000000:leave", "-D", "fw.BIN"]),
        ("dfu-util", ["-a", "0", "-d", "0483:DF11", "-s", "0x08000000:leave"]),
    ]


def test_dfu_util_rejects_hex(harness):
    for vid, pid in [(0x0483, 0xDF11), (0x314B, 0x0106), (0x28E9, 0x0189), (0x1C11, 0xB007), (0x1EAF, 0x0003)]:
        harness.device(vid, pid).flash("", "fw.hex")
    assert harness.calls == []
    assert harness.messages_of(MessageType.ERROR) == [
        "Only firmware files in .bin format can be flashed with dfu-util!"
    ] * 5


def test_other_dfu_util_devices(harness):
    harness.device(0x314B, 0x0106).flash("", "fw.bin")
    harness.device(0x28E9, 0x0189).flash("", "fw.bin")
    kiibohd = harness.device(0x1C11, 0xB007)
    kiibohd.flash("", "fw.bin")
    kiibohd.reset("")
    stm32duino = harness.device(0x1EAF, 0x0003)
    stm32duino.flash("", "fw.bin")
    assert not stm32duino.resettable
    assert harness.calls == [
        ("dfu-util", ["-a", "0", "-d", "314B:0106", "-s", "0x08000000:leave", "-D", "fw.bin"]),
        ("dfu-util", ["-a", "0", "-d", "28E9:0189", "-s", "0x08000000:leave", "-D", "fw.bin"]),
        ("dfu-util", ["-a", "0", "-d", "1C11:B007", "-D", "fw.bin"]),
        ("dfu-util", ["-a", "0", "-d", "1C11:B007", "-e"]),
        ("dfu-util", ["-a", "2", "-d", "1EAF:0003", "-R", "-D", "fw.bin"]),
    ]


def test_halfkay_and_lufa_hid(harness):
    halfkay = harness.device(0x16C0, 0x0478)
    halfkay.flash("atmega32u4", "fw.hex")
    halfkay.reset("atmega32u4")
    lufa_hid = harness.device(0x03EB, 0x2067)
    lufa_hid.flash("atmega32u4", "fw.hex")
    assert not lufa_hid.resettable
    assert harness.device(0x03EB, 0x2067, 0x0936).name == "QMK HID"
    assert harness.calls == [
        ("teensy_loader_cli", ["-mmcu=atmega32u4", "fw.hex", "-v"]),
        ("teensy_loader_cli", ["-mmcu=atmega32u4", "-bv"]),
        ("hid_bootloader_cli", ["-mmcu=atmega32u4", "fw.hex", "-v"]),
    ]


def test_wb32_dfu(harness):
    device = harness.device(0x342D, 0xDFA0)
    device.flash("", "fw.bin")
    device.flash("", "fw.hex")
    device.reset("")
    assert harness.calls == [
        ("wb32-dfu-updater_cli", ["--toolbox-mode", "--dfuse-address", "0x08000000", "--download", "fw.bin"]),
        ("wb32-dfu-updater_cli", ["--toolbox-mode", "--download", "fw.hex"]),
        ("wb32-dfu-updater_cli", ["--reset"]),
    ]


def test_lufa_ms(harness, tmp_path):
    firmware = tmp_path / "fw.bin"
    firmware.write_bytes(b"new")
    volume = tmp_path / "volume"
    volume.mkdir()
    (volume / "FLASH.BIN").write_bytes(b"old")

    device = harness.device(0x03EB, 0x2045)
    device.flash("", str(firmware))
    assert harness.messages_of(MessageType.ERROR) == ["Mount point not found!"]

    harness.mount_point = str(volume)
    device.flash("", str(firmware))
    assert (volume / "FLASH.BIN").read_bytes() == b"new"
    assert harness.messages_of(MessageType.COMMAND)[-1] == "Done, please eject drive now."
    assert str(device).endswith(f"[{volume}]")

    device.flash("", "fw.hex")
    assert harness.messages_of(MessageType.ERROR)[-1] == (
        "Only firmware files in .bin format can be flashed with this bootloader!"
    )


def test_atmel_dfu_reset_that_never_returns_is_not_an_error(harness):
    harness.runner.hang = True
    device = harness.device(0x03EB, 0x2FF4)

    device.flash("atmega32u4", "fw.hex")
    assert [args[1] for _, args in harness.calls] == ["erase", "flash", "reset"]
    assert harness.runner.timeouts == [None, None, 5.0]
    assert harness.messages_of(MessageType.ERROR) == []
    assert harness.messages_of(MessageType.BOOTLOADER) == [
        "Reset sent, but dfu-programmer did not return within 5 s; stopped it."
    ]

    device.reset("atmega32u4")
    assert harness.runner.timeouts[-1] == 5.0
