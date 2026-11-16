from __future__ import annotations

from .bootloader.apm32_dfu_device import APM32DFUDevice
from .bootloader.atmel_dfu_device import AtmelDFUDevice
from .bootloader.atmel_samba_device import AtmelSAMBADevice
from .bootloader.avrisp_device import AVRISPDevice
from .bootloader.bootloader_device import BootloaderDevice, FlashContext
from .bootloader.bootloader_type import BootloaderType
from .bootloader.bootloadhid_device import BootloadHIDDevice
from .bootloader.caterina_device import CaterinaDevice
from .bootloader.gd32v_dfu_device import GD32VDFUDevice
from .bootloader.halfkay_device import HalfKayDevice
from .bootloader.kiibohd_device import KiibohdDFUDevice
from .bootloader.lufa_hid_device import LUFAHIDDevice
from .bootloader.lufa_ms_device import LUFAMSDevice
from .bootloader.stm32_dfu_device import STM32DFUDevice
from .bootloader.stm32duino_device import STM32DuinoDevice
from .bootloader.usbasp_device import USBAspDevice
from .bootloader.usbtinyisp_device import USBTinyISPDevice
from .bootloader.wb32_dfu_device import WB32DFUDevice
from .usb_device import UsbDevice

# bcdDevice reported by QMK's forks of the LUFA DFU and HID bootloaders (Unicode Ψ)
QMK_REVISION_BCD = 0x0936

# (vendor ID, product ID) -> bootloader type.
# Keep in sync with USBListener.swift (macOS) and UsbListener.cs (Windows).
_DEVICE_TYPES: dict[tuple[int, int], BootloaderType] = {
    # Atmel Corporation
    (0x03EB, 0x2045): BootloaderType.LUFA_MS,
    (0x03EB, 0x2067): BootloaderType.LUFA_HID,  # or QMK HID, by revision
    (0x03EB, 0x2FEF): BootloaderType.ATMEL_DFU,  # ATmega16U2 (these: or QMK DFU, by revision)
    (0x03EB, 0x2FF0): BootloaderType.ATMEL_DFU,  # ATmega32U2
    (0x03EB, 0x2FF3): BootloaderType.ATMEL_DFU,  # ATmega16U4
    (0x03EB, 0x2FF4): BootloaderType.ATMEL_DFU,  # ATmega32U4
    (0x03EB, 0x2FF9): BootloaderType.ATMEL_DFU,  # AT90USB64
    (0x03EB, 0x2FFA): BootloaderType.ATMEL_DFU,  # AT90USB162
    (0x03EB, 0x2FFB): BootloaderType.ATMEL_DFU,  # AT90USB128
    (0x03EB, 0x6124): BootloaderType.ATMEL_SAMBA,
    # STMicroelectronics
    (0x0483, 0xDF11): BootloaderType.STM32_DFU,
    # pid.codes
    (0x1209, 0x2302): BootloaderType.CATERINA,  # Keyboardio Atreus 2 Bootloader
    # Van Ooijen Technische Informatica
    (0x16C0, 0x0478): BootloaderType.HALFKAY,
    (0x16C0, 0x0483): BootloaderType.AVR_ISP,
    (0x16C0, 0x05DC): BootloaderType.USBASP,
    (0x16C0, 0x05DF): BootloaderType.BOOTLOADHID,
    # MECANIQUE
    (0x1781, 0x0C9F): BootloaderType.USBTINYISP,
    # Spark Fun Electronics
    (0x1B4F, 0x9203): BootloaderType.CATERINA,  # Pro Micro 3V3/8MHz
    (0x1B4F, 0x9205): BootloaderType.CATERINA,  # Pro Micro 5V/16MHz
    (0x1B4F, 0x9207): BootloaderType.CATERINA,  # LilyPad 3V3/8MHz (and some Pro Micro clones)
    # Input Club Inc.
    (0x1C11, 0xB007): BootloaderType.KIIBOHD_DFU,
    # Leaflabs
    (0x1EAF, 0x0003): BootloaderType.STM32DUINO,
    # Pololu Corporation
    (0x1FFB, 0x0101): BootloaderType.CATERINA,  # A-Star 32U4
    # Arduino SA
    (0x2341, 0x0036): BootloaderType.CATERINA,  # Leonardo
    (0x2341, 0x0037): BootloaderType.CATERINA,  # Micro
    # Adafruit
    (0x239A, 0x000C): BootloaderType.CATERINA,  # Feather 32U4
    (0x239A, 0x000D): BootloaderType.CATERINA,  # ItsyBitsy 32U4 3V3/8MHz
    (0x239A, 0x000E): BootloaderType.CATERINA,  # ItsyBitsy 32U4 5V/16MHz
    # GigaDevice
    (0x28E9, 0x0189): BootloaderType.GD32V_DFU,
    # dog hunter AG
    (0x2A03, 0x0036): BootloaderType.CATERINA,  # Leonardo
    (0x2A03, 0x0037): BootloaderType.CATERINA,  # Micro
    (0x2A03, 0x0040): BootloaderType.CATERINA,  # ETH
    # Geehy Semiconductor Co. Ltd.
    (0x314B, 0x0106): BootloaderType.APM32_DFU,
    # WestBerryTech
    (0x342D, 0xDFA0): BootloaderType.WB32_DFU,
}

_DEVICE_CLASSES: dict[BootloaderType, type[BootloaderDevice]] = {
    BootloaderType.APM32_DFU: APM32DFUDevice,
    BootloaderType.ATMEL_DFU: AtmelDFUDevice,
    BootloaderType.QMK_DFU: AtmelDFUDevice,
    BootloaderType.ATMEL_SAMBA: AtmelSAMBADevice,
    BootloaderType.AVR_ISP: AVRISPDevice,
    BootloaderType.BOOTLOADHID: BootloadHIDDevice,
    BootloaderType.CATERINA: CaterinaDevice,
    BootloaderType.GD32V_DFU: GD32VDFUDevice,
    BootloaderType.HALFKAY: HalfKayDevice,
    BootloaderType.KIIBOHD_DFU: KiibohdDFUDevice,
    BootloaderType.LUFA_HID: LUFAHIDDevice,
    BootloaderType.QMK_HID: LUFAHIDDevice,
    BootloaderType.LUFA_MS: LUFAMSDevice,
    BootloaderType.STM32_DFU: STM32DFUDevice,
    BootloaderType.STM32DUINO: STM32DuinoDevice,
    BootloaderType.USBASP: USBAspDevice,
    BootloaderType.USBTINYISP: USBTinyISPDevice,
    BootloaderType.WB32_DFU: WB32DFUDevice,
}


def device_type(vendor_id: int, product_id: int, revision_bcd: int) -> BootloaderType:
    bootloader_type = _DEVICE_TYPES.get((vendor_id, product_id), BootloaderType.NONE)
    if revision_bcd == QMK_REVISION_BCD:
        if bootloader_type is BootloaderType.ATMEL_DFU:
            return BootloaderType.QMK_DFU
        if bootloader_type is BootloaderType.LUFA_HID:
            return BootloaderType.QMK_HID
    return bootloader_type


def create_device(usb_device: UsbDevice, context: FlashContext) -> UsbDevice | BootloaderDevice:
    """Wrap a USB device in its bootloader class, or return it unchanged if it is not a bootloader."""
    bootloader_type = device_type(usb_device.vendor_id, usb_device.product_id, usb_device.revision_bcd)
    device_class = _DEVICE_CLASSES.get(bootloader_type)
    if device_class is None:
        return usb_device
    return device_class(usb_device, context)
