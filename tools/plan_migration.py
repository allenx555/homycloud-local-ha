"""Build an entity migration plan from snapshots. Does not connect to HA or edit registries."""
import argparse
import json
import os
from pathlib import Path


def plan_migration(devices, registry):
    if isinstance(registry, dict):
        registry = registry['data']['entities']
    old = {(e.get('domain') or e['entity_id'].split('.',1)[0],e['unique_id']):e for e in registry if e.get('platform')=='mqtt'}
    native = {(e.get('domain') or e['entity_id'].split('.',1)[0],e['unique_id']):e for e in registry if e.get('platform')=='homycloud_local'}
    plan=[]
    seen=set()
    for device in devices:
        for key,spec in device['entities'].items():
            domain=spec['component'];uid=f"homycloud_{device['id']}_{key}_{domain}"
            if (domain,uid) in seen:
                raise ValueError('Duplicate target entity')
            seen.add((domain,uid));source=old.get((domain,uid));target=native.get((domain,uid))
            status='conflict' if target else 'ready' if source else 'missing'
            item={'domain':domain,'unique_id':uid,'status':status,
                  'old_entity_id':source['entity_id'] if source else None,
                  'existing_native_entity_id':target['entity_id'] if target else None,
                  'old_config_entry_id':source.get('config_entry_id') if source else None,
                  'old_device_id':source.get('device_id') if source else None,
                  'preserve':{}}
            if source:
                item['preserve']={name:source[name] for name in
                                  ('name','icon','area_id','labels','aliases','disabled_by','hidden_by','options') if name in source}
            plan.append(item)
    summary={name:sum(item['status']==name for item in plan) for name in ('ready','missing','conflict')}
    return {'version':1,'read_only':True,'summary':summary,'entities':plan}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory',required=True)
    parser.add_argument('--entity-registry',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    inventory=json.loads(Path(args.inventory).read_text(encoding='utf-8'))
    registry=json.loads(Path(args.entity_registry).read_text(encoding='utf-8'))
    plan=plan_migration(inventory['devices'],registry)
    fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as stream:
        json.dump(plan,stream,ensure_ascii=False,indent=2)
    print(json.dumps(plan['summary']))


if __name__=='__main__':main()
