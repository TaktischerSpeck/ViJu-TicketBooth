import asyncio
import shutil
from dbus_next.aio import MessageBus
from dbus_next import BusType, Variant
from dbus_next.service import ServiceInterface, method
from fastapi import HTTPException

BLUEZ = "org.bluez"


class PairingAgent(ServiceInterface):
    def __init__(self):
        super().__init__("org.bluez.Agent1")

    @method()
    def Release(self):
        pass

    @method()
    def Cancel(self):
        pass

    @method()
    def RequestConfirmation(self, device: "o", passkey: "u"):
        pass

    @method()
    def RequestAuthorization(self, device: "o"):
        pass

    @method()
    def AuthorizeService(self, device: "o", uuid: "s"):
        pass


async def _objects():
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    intro = await bus.introspect(BLUEZ, "/")
    obj = bus.get_proxy_object(BLUEZ, "/", intro)
    manager = obj.get_interface("org.freedesktop.DBus.ObjectManager")
    return bus, await manager.call_get_managed_objects()


async def status(mac):
    result = {"adapter_available": False, "device_known": False, "paired": False, "trusted": False, "connected": False}
    try:
        bus, objects = await _objects()
        for path, interfaces in objects.items():
            if "org.bluez.Adapter1" in interfaces:
                result["adapter_available"] = True
            device = interfaces.get("org.bluez.Device1")
            if device and device["Address"].value.upper() == mac:
                result.update(device_known=True, paired=device["Paired"].value, trusted=device["Trusted"].value, connected=device["Connected"].value)
        bus.disconnect()
    except Exception:
        pass
    return result


async def device_action(mac, action):
    agent_path = "/com/viju_ticketbooth/agent"
    agent_manager = None
    agent_registered = False
    try:
        bus, objects = await _objects()
        if action == "pair":
            intro = await bus.introspect(BLUEZ, "/org/bluez")
            agent_manager = bus.get_proxy_object(BLUEZ, "/org/bluez", intro).get_interface("org.bluez.AgentManager1")
            bus.export(agent_path, PairingAgent())
            await agent_manager.call_register_agent(agent_path, "NoInputNoOutput")
            agent_registered = True
        match = [(path, interfaces["org.bluez.Device1"]) for path, interfaces in objects.items()
                 if "org.bluez.Device1" in interfaces and interfaces["org.bluez.Device1"]["Address"].value.upper() == mac]
        if not match and action == "pair":
            adapters = [path for path, interfaces in objects.items() if "org.bluez.Adapter1" in interfaces]
            if adapters:
                adapter_path = adapters[0]
                intro = await bus.introspect(BLUEZ, adapter_path)
                adapter_obj = bus.get_proxy_object(BLUEZ, adapter_path, intro)
                await adapter_obj.get_interface("org.freedesktop.DBus.Properties").call_set("org.bluez.Adapter1", "Powered", Variant("b", True))
                adapter_iface = adapter_obj.get_interface("org.bluez.Adapter1")
                await adapter_iface.call_start_discovery()
                try:
                    for _ in range(15):
                        await asyncio.sleep(1)
                        probe_bus, found = await _objects()
                        match = [(path, interfaces["org.bluez.Device1"]) for path, interfaces in found.items()
                                 if "org.bluez.Device1" in interfaces and interfaces["org.bluez.Device1"]["Address"].value.upper() == mac]
                        probe_bus.disconnect()
                        if match:
                            break
                finally:
                    await adapter_iface.call_stop_discovery()
        if not match:
            raise HTTPException(404, "Configured printer was not found; wake the Sprocket and retry")
        path, _ = match[0]
        if action == "forget":
            adapter = path.rsplit("/dev_", 1)[0]
            intro = await bus.introspect(BLUEZ, adapter)
            iface = bus.get_proxy_object(BLUEZ, adapter, intro).get_interface("org.bluez.Adapter1")
            await iface.call_remove_device(path)
        else:
            intro = await bus.introspect(BLUEZ, path)
            obj = bus.get_proxy_object(BLUEZ, path, intro)
            if action == "pair":
                await obj.get_interface("org.bluez.Device1").call_pair()
            elif action == "trust":
                await obj.get_interface("org.freedesktop.DBus.Properties").call_set("org.bluez.Device1", "Trusted", Variant("b", True))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"BlueZ {action} failed: {type(exc).__name__}") from exc
    finally:
        if agent_registered:
            try:
                await agent_manager.call_unregister_agent(agent_path)
            except Exception:
                pass
        if "bus" in locals():
            bus.disconnect()
    return await status(mac)


def obex_available():
    return shutil.which("obexftp") is not None
