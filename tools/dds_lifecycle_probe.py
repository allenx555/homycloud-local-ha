"""Repeated read-only DDS start/query/close checks using the installed runtime."""
import argparse
import gc
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from custom_components.homycloud_local.protocol.client import DdsClient
from custom_components.homycloud_local.runtime import load_runtime


def metrics():
    values={}
    for line in Path('/proc/self/status').read_text().splitlines():
        if line.startswith(('Threads:','VmRSS:')):
            key,value=line.split(':',1);values[key]=int(value.split()[0])
    return values


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory',required=True)
    parser.add_argument('--rounds',type=int,default=3)
    parser.add_argument('--seconds',type=float,default=10)
    args=parser.parse_args()
    if not 1<=args.rounds<=10 or not 8<=args.seconds<=60:parser.error('rounds 1..10, seconds 8..60')
    config=load_runtime(args.inventory);baseline=metrics();results=[]
    for index in range(args.rounds):
        client=DdsClient(devices=config['devices'],partition=config['partition'],xml=config['dds_xml'])
        try:
            client.start();assert client.change is None
            due={did:time.monotonic()+2+i*.18 for i,did in enumerate(client.devices)}
            start=time.monotonic()
            while time.monotonic()-start<args.seconds:
                client.poll();now=time.monotonic()
                for did in client.devices:
                    if now>=due[did]:client.request(did);due[did]=float('inf')
                time.sleep(.1)
            item={'round':index+1,'configured_devices':len(client.devices),
                  'responding_devices':len(client.store.values),'active':metrics()}
            assert item['responding_devices']==item['configured_devices']
        finally:
            client.close();del client;gc.collect();time.sleep(.3)
        item['closed']=metrics();results.append(item)
        print(json.dumps(item),flush=True)
        if item['closed']['Threads']>baseline['Threads']+1:
            raise RuntimeError('DDS threads did not return to baseline after close')
    print(json.dumps({'read_only':True,'baseline':baseline,'rounds_completed':len(results)}))


if __name__=='__main__':main()
