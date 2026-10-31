"""Synchronous CycloneDDS adapter. Call exclusively from a dedicated worker thread.

Read-only by default: there is no ChangeAttribute writer in a read-only client.
No participants, network traffic, or native imports are created at module import.
"""
import json
import time
from pathlib import Path
from uuid import uuid4
from .state import StateStore, validate_command

TOPIC_NAMES = (
    'LanProto_ReportAttribute', 'LanProto_QueryMultiAttributes',
    'LanProto_ResponseQueryMultiAttributes', 'LanProto_ChangeAttribute',
)


class DdsClient:
    def __init__(self, *, devices: list[dict], partition: str, xml: str,
                 domain_id: int = 2031, read_only: bool = True, schema_path=None):
        self.devices = {d['id']: d for d in devices}
        if not self.devices or len(self.devices) != len(devices):
            raise ValueError('Inventory is empty or contains duplicate identifiers')
        self.partition, self.xml, self.domain_id = partition, xml, domain_id
        self.read_only = read_only
        self.schema_path = Path(schema_path) if schema_path else Path(__file__).with_name('schemas.json')
        self.store = StateStore()
        self.pending = {}
        self.types, self.topics = {}, {}
        self.domain = self.participant = None
        self.report = self.response = self.query = self.change = None
        self.leader = uuid4().hex

    def start(self):
        if self.participant is not None:
            raise RuntimeError('Client already started')
        from cyclonedds.domain import Domain, DomainParticipant
        from cyclonedds.topic import Topic
        from cyclonedds.sub import DataReader
        from cyclonedds.pub import DataWriter
        from cyclonedds.qos import Qos, Policy
        from cyclonedds.util import duration
        from cyclonedds.idl._typesupport.DDS.XTypes import TypeMapping, TypeIdentifier
        from cyclonedds.idl._xt_builder import XTInterpreter
        saved = json.loads(self.schema_path.read_text(encoding='utf-8'))['types']
        try:
            for name in TOPIC_NAMES:
                item = saved[name]
                mapping = TypeMapping.deserialize(bytes.fromhex(item['type_map']))
                tid = TypeIdentifier.deserialize(bytes.fromhex(item['type_id']))
                self.types[name], _ = XTInterpreter.xt_to_class(tid, {
                    p.type_identifier: p.type_object for p in
                    mapping.identifier_object_pair_complete + mapping.identifier_object_pair_minimal})
            # Per-domain configuration; do not change process-global CYCLONEDDS_URI.
            self.domain = Domain(self.domain_id, self.xml)
            self.participant = DomainParticipant(self.domain_id)
            self.topics = {n: Topic(self.participant, n, t) for n, t in self.types.items()
                           if not self.read_only or n != 'LanProto_ChangeAttribute'}
            part = Policy.Partition([self.partition])
            rq = Qos(part, Policy.Reliability.BestEffort, Policy.Durability.Volatile,
                     Policy.History.KeepLast(500))
            wq = Qos(part, Policy.Reliability.Reliable(duration(milliseconds=100)),
                     Policy.Durability.Volatile)
            self.report = DataReader(self.participant, self.topics[TOPIC_NAMES[0]], qos=rq)
            self.response = DataReader(self.participant, self.topics[TOPIC_NAMES[2]], qos=rq)
            self.query = DataWriter(self.participant, self.topics[TOPIC_NAMES[1]], qos=wq)
            if not self.read_only:
                self.change = DataWriter(self.participant, self.topics[TOPIC_NAMES[3]], qos=wq)
        except Exception:
            self.close()
            raise

    def request(self, did: str):
        if did not in self.devices:
            raise ValueError('Unknown device')
        mid = uuid4().hex
        keys = self.devices[did].get('query_keys', list(self.devices[did]['entities']))
        self.pending[mid] = (did, time.monotonic())
        self.query.write(self.types[TOPIC_NAMES[1]](
            deviceId=did, dpNameJsonArr=json.dumps(keys), messageId=mid, reqLeaderAddr=self.leader))

    def poll(self) -> bool:
        changed = False
        for sample in self.report.take(300):
            if sample.deviceId in self.devices:
                changed |= self.store.update(sample.deviceId, sample.dpName,
                                             sample.dpValue, sample.timeStamp)
        for sample in self.response.take(100):
            pending = self.pending.get(sample.messageId)
            if not pending or pending[0] != sample.deviceId:
                continue
            self.pending.pop(sample.messageId)
            try:
                attrs = json.loads(sample.dpResultArr)
                if not isinstance(attrs, dict):
                    continue
                for key, val in attrs.items():
                    if isinstance(val, dict) and 'value' in val:
                        changed |= self.store.update(sample.deviceId, key, val['value'], val.get('time'))
            except (ValueError, TypeError):
                continue
        now = time.monotonic()
        self.pending = {mid: item for mid, item in self.pending.items() if now-item[1] < 15}
        return changed

    def command(self, did: str, key: str, value):
        if self.read_only:
            raise PermissionError('This DDS client is read-only')
        if self.change is None:
            raise RuntimeError('Client not started')
        value = validate_command(self.devices[did], key, value)
        self.change.write(self.types[TOPIC_NAMES[3]](
            deviceId=did, command=json.dumps({key: value}, separators=(',', ':')),
            timeStamp=str(int(time.time()*1000))))
        self.request(did)

    def close(self):
        # Drop children before the participant/domain. CycloneDDS owns native finalizers.
        self.report = self.response = self.query = self.change = None
        self.topics.clear()
        self.participant = self.domain = None
        self.pending.clear()
