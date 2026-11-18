from types import SimpleNamespace

import usb.core

from qmk_toolbox import udev
from qmk_toolbox.usb import usb_backend
from qmk_toolbox.usb.usb_backend import PyUsbBackend


def handle(bus, address, port_numbers, vendor_id=0x03EB, product_id=0x2FF4):
    return SimpleNamespace(
        bus=bus,
        address=address,
        port_numbers=port_numbers,
        idVendor=vendor_id,
        idProduct=product_id,
        bcdDevice=0x0000,
    )


def test_on_linux_devices_are_reported_once_udev_has_set_them_up(monkeypatch, tmp_path):
    monkeypatch.setattr(usb_backend.sys, "platform", "linux")
    monkeypatch.setattr(udev, "UDEV_DATA_DIR", tmp_path)
    devices = [handle(1, 1, None), handle(1, 9, (2,))]
    monkeypatch.setattr(usb.core, "find", lambda find_all, backend=None: iter(devices))
    (tmp_path / "c189:0").touch()

    assert [key[:2] for key in PyUsbBackend().scan()] == [(1, 1)]
    (tmp_path / "c189:8").touch()
    assert [key[:2] for key in PyUsbBackend().scan()] == [(1, 1), (1, 9)]


def test_a_given_libusb_library_is_used(monkeypatch):
    import usb.backend.libusb1

    monkeypatch.setattr(usb_backend.sys, "platform", "win32")
    backend = object()
    requested = []

    def get_backend(find_library):
        requested.append(find_library("usb-1.0"))
        return backend

    monkeypatch.setattr(usb.backend.libusb1, "get_backend", get_backend)
    used = []
    monkeypatch.setattr(usb.core, "find", lambda find_all, backend=None: used.append(backend) or iter([]))
    scanner = PyUsbBackend("C:/toolbox/libusb-1.0.dll")
    scanner.scan()
    scanner.scan()
    assert requested == ["C:/toolbox/libusb-1.0.dll"]  # loaded once
    assert used == [backend, backend]


def test_names_are_read_from_sysfs_on_linux(monkeypatch, tmp_path):
    monkeypatch.setattr(usb_backend.sys, "platform", "linux")
    monkeypatch.setattr(usb_backend, "SYSFS_USB_DEVICES", tmp_path)
    for name, manufacturer, product in [("usb3", "Linux xhci-hcd", "xHCI Host Controller"), ("3-1.4", "ATMEL", "ATm32U4DFU")]:
        (tmp_path / name).mkdir()
        (tmp_path / name / "manufacturer").write_text(manufacturer + "\n")
        (tmp_path / name / "product").write_text(product + "\n")

    root_hub = PyUsbBackend().describe(handle(3, 1, None, 0x1D6B, 0x0002))
    assert (root_hub.manufacturer, root_hub.product) == ("Linux xhci-hcd", "xHCI Host Controller")
    device = PyUsbBackend().describe(handle(3, 5, (1, 4)))
    assert (device.manufacturer, device.product, device.location) == ("ATMEL", "ATm32U4DFU", "3-1.4")
