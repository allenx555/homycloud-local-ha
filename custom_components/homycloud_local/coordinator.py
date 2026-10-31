"""DDS worker with bounded commands and feedback, outside HA's event loop."""
import asyncio
from dataclasses import dataclass
import logging
import queue
import threading
import time
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .const import NAME
from .protocol.client import DdsClient
from .protocol.state import validate_command
from .protocol.feedback import confirmed

_LOGGER = logging.getLogger(__name__)


@dataclass
class Command:
    did: str
    key: str
    value: object
    expected: object
    deadline: float
    future: asyncio.Future
    issued_at: float = 0
    baseline: dict | None = None


class HomyCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, config):
        super().__init__(hass, _LOGGER, name=NAME, config_entry=entry)
        self.config = config
        self.devices = {d['id']: d for d in config['devices']}
        self.read_only = not entry.options.get('enable_control', entry.data.get('enable_control', False))
        self._stop = threading.Event()
        self._worker = None
        self._ready = None
        self._commands = queue.Queue(maxsize=100)
        self.data = {'values': {}, 'online': []}

    async def async_start(self):
        self._ready = self.hass.loop.create_future()
        self._worker = self.hass.async_create_background_task(asyncio.to_thread(self._run), 'HomyCloud DDS worker')
        try:
            await asyncio.wait_for(asyncio.shield(self._ready), timeout=25)
        except BaseException:
            await self.async_stop()
            raise

    async def async_command(self, did, key, value):
        if self.read_only:
            raise HomeAssistantError('HomyCloud is read-only; device control is disabled')
        if self._stop.is_set() or not self._worker or self._worker.done():
            raise HomeAssistantError('HomyCloud worker is not running')
        if did not in self.data['online']:
            raise HomeAssistantError('Device is offline')
        expected = validate_command(self.devices[did], key, value)
        future = self.hass.loop.create_future()
        command = Command(did, key, value, expected, time.monotonic()+7, future)
        try:
            self._commands.put_nowait(command)
        except queue.Full as err:
            raise HomeAssistantError('Command queue is full') from err
        try:
            await asyncio.wait_for(future, timeout=8)
        except TimeoutError as err:
            raise HomeAssistantError('No matching device feedback; command was not retried') from err

    def _resolve(self, future, error=None):
        if not future.done():
            if error:
                future.set_exception(HomeAssistantError(error))
            else:
                future.set_result(None)

    def _complete(self, command, error=None):
        self.hass.loop.call_soon_threadsafe(self._resolve, command.future, error)

    def _publish(self, snapshot, completed):
        self.async_set_updated_data(snapshot)
        for command in completed:
            self._resolve(command.future)

    def _initialized(self):
        if not self._ready.done():
            self._ready.set_result(True)

    def _failed(self):
        if not self._ready.done():
            self._ready.set_exception(RuntimeError('DDS startup failed'))
        self.async_set_updated_data({'values': self.data['values'], 'online': []})

    def _drain(self, pending, error):
        for item in pending:
            self._complete(item, error)
        pending.clear()
        while True:
            try:
                self._complete(self._commands.get_nowait(), error)
            except queue.Empty:
                break

    def _run(self):
        pending = []
        while not self._stop.is_set():
            client = DdsClient(devices=list(self.devices.values()), partition=self.config['partition'],
                               xml=self.config['dds_xml'], read_only=self.read_only)
            try:
                client.start()
                self.hass.loop.call_soon_threadsafe(self._initialized)
                due = {did: time.monotonic()+2+i*.18 for i,did in enumerate(self.devices)}
                last_publish = 0
                while not self._stop.wait(.1):
                    changed = client.poll()
                    now = time.monotonic()
                    remaining = []
                    completed = []
                    for item in pending:
                        if item.future.cancelled():
                            continue
                        if confirmed(client.store.values.get(item.did,{}), item.key, item.expected, item.issued_at, item.baseline):
                            completed.append(item)
                        elif now >= item.deadline:
                            self._complete(item, 'No matching device feedback; command was not retried')
                        else:
                            remaining.append(item)
                    pending = remaining
                    while not self._commands.empty():
                        item = self._commands.get_nowait()
                        if item.future.cancelled():
                            continue
                        if now >= item.deadline:
                            self._complete(item, 'Expired command was not sent')
                            continue
                        if any(p.did == item.did and p.key == item.key for p in pending):
                            self._complete(item, 'A command for this property is already pending')
                            continue
                        if now-client.store.last_seen.get(item.did,float('-inf')) >= 95:
                            self._complete(item, 'Device is offline; command was not sent')
                            continue
                        item.baseline = dict(client.store.values.get(item.did,{}))
                        item.issued_at = time.monotonic()
                        client.command(item.did, item.key, item.value)
                        pending.append(item)
                        due[item.did] = min(due[item.did], now+.5)
                    for did in self.devices:
                        if now >= due[did]:
                            client.request(did)
                            due[did] = now+30
                    if changed or completed or now-last_publish >= 5:
                        snapshot = {'values': client.store.snapshot(),
                                    'online': [did for did,seen in client.store.last_seen.items() if now-seen < 95]}
                        self.hass.loop.call_soon_threadsafe(self._publish, snapshot, tuple(completed))
                        last_publish = now
            except Exception:
                _LOGGER.exception('DDS worker failed; commands are not replayed after reconnect')
                self._drain(pending, 'DDS connection lost; command was not retried')
                self.hass.loop.call_soon_threadsafe(self._failed)
            finally:
                client.close()
            self._stop.wait(5)
        self._drain(pending, 'Integration stopped; command was not sent again')

    async def async_stop(self):
        self._stop.set()
        if self._worker:
            await asyncio.wait_for(asyncio.shield(self._worker), timeout=15)
