"""Mine local a2log captures for object types with observed cube collection signatures."""
import argparse,base64,collections,csv,datetime,json,struct
from pathlib import Path
from cube_probe import decode_object,recover_cube_frames

SIGNATURE=bytes.fromhex('23 c5 9a 25')
FAMILIES={0x36,0x37,0x38,0x39,0x56,0x8A,0x8D,0x92,0x96,0x97}

def var(data,start=0):
    value=0
    for i in range(5):
        if start+i>=len(data):raise ValueError('truncated varint')
        b=data[start+i];value|=(b&127)<<(7*i)
        if b<128:return value,start+i+1
    raise ValueError('invalid varint')

def completion(data):
    try:
        entity,end=var(data);actor,end=var(data,end)
        if entity>0 and actor>0 and data[end:]==b'\x01\x00\x00\x00'+SIGNATURE:
            return entity,actor
    except ValueError:pass
    return None

def embedded(data,marker):
    """Require complete inner frames and a plausible following frame boundary."""
    offset=0
    while (i:=data.find(marker,offset))>=0:
        offset=i+2
        for width in (1,2,3):
            start=i-width
            if start<0:continue
            try:
                size,h=var(data,start);h-=start;end=start+size+h-4
                if h!=width or not 6<=size<=2048 or end>len(data) or end<=i+2:continue
                next_at=end
                while next_at<len(data) and data[next_at]==0:next_at+=1
                if next_at<len(data):
                    nxt,head=var(data,next_at)
                    if nxt<6 or head+2>len(data) or data[head+1] not in FAMILIES or next_at+nxt+(head-next_at)-4>len(data):continue
                yield i,data[i+2:end]
                break
            except ValueError:continue

def mine(paths):
    encounters={};unresolved=[];types=collections.Counter();stats=collections.Counter()
    for path in paths:
        objects={};pending={};epoch=None
        with path.open(encoding='utf-8-sig') as stream:
            for line_number,line in enumerate(stream,1):
                try:r=json.loads(line)
                except ValueError:stats['invalid_or_partial_lines']+=1;continue
                if r.get('schema')=='a2log/v0.1':
                    try:epoch=datetime.datetime.fromisoformat(r['t0'].replace('Z','+00:00'))
                    except (KeyError,ValueError):stats['incomplete_headers']+=1;continue
                    stats['recordings']+=1;continue
                if epoch is None or not r.get('payload'):continue
                try:data=base64.b64decode(r['payload']);t=r['t'];opcode=r['opcode']
                except (ValueError,KeyError):stats['invalid_or_partial_lines']+=1;continue
                stats['messages']+=1
                connection=(r.get('src'),r.get('dst'))
                if opcode in ('23 36','0F 39'):
                    objects={k:v for k,v in objects.items() if k[:2]!=connection}
                    pending={k:v for k,v in pending.items() if k[:2]!=connection}
                events=[]
                if opcode in ('34 36','3A 36','35 36'):events.append((-1,opcode,data,'direct'))
                # No numeric type whitelist is assumed for offline mining.
                candidates=set();at=0
                while (i:=data.find(b'\x34\x36',at))>=0:
                    at=i+2
                    try:o=decode_object(data[at:].hex())
                    except ValueError:continue
                    if o['Flags']==4 and o['Entity']>0 and o['Type']>0:candidates.add(o['Type'])
                if candidates and opcode!='34 36':
                    message={'type':opcode,'name':'Spawn' if opcode=='41 36' else None,'payload':data.hex(),'t':t}
                    for recovered in recover_cube_frames(message,candidates):
                        payload=bytes.fromhex(recovered['payload'])
                        events.append((max(0,data.find(b'\x34\x36'+payload)),'34 36',payload,'partial_header' if recovered.get('partial_header') else 'embedded'))
                for marker,typ in ((b'\x3a\x36','3A 36'),(b'\x35\x36','35 36')):
                    for offset,payload in embedded(data,marker):
                        if typ=='3A 36' and not completion(payload):continue
                        if typ=='35 36':
                            try:_,end=var(payload)
                            except ValueError:continue
                            if payload[end:]!=b'\x04\x03\x00':continue
                        events.append((offset,typ,payload,'embedded'))
                for offset,typ,payload,method in sorted(events):
                    if typ=='34 36':
                        try:o=decode_object(payload.hex())
                        except ValueError:continue
                        if o['Entity']<=0 or o['Type']<=0 or o['Flags'] not in (1,4,12):continue
                        types[o['Type']]+=1
                        key=connection+(o['Entity'],)
                        objects[key]={'entity_id':o['Entity'],'type_id':o['Type'],'coordinates':[o[k] for k in ('X','Y','Z')],'appearance_t':t,'appearance_method':method}
                    elif typ=='3A 36':
                        match=completion(payload)
                        if not match:continue
                        entity,actor=match;key=connection+(entity,);obj=objects.get(key)
                        stamp=(epoch+datetime.timedelta(milliseconds=t)).isoformat()
                        record={'recording':path.name,'collection_utc':stamp,'entity_id':entity,'actor_id':actor,'type_id':obj['type_id'] if obj else None,'coordinates':obj['coordinates'] if obj else None,'appearance_method':obj['appearance_method'] if obj else None,'completion_method':method,'matching_removal':False,'t':t}
                        pending[key]=record
                        identity=(stamp,entity,actor,record['type_id'])
                        if obj:encounters[identity]=record
                        else:unresolved.append(record)
                    elif typ=='35 36':
                        try:entity,end=var(payload)
                        except ValueError:continue
                        key=connection+(entity,)
                        if payload[end:]==b'\x04\x03\x00' and key in pending and 0<=t-pending[key]['t']<=10000:
                            pending[key]['matching_removal']=True
                        objects.pop(key,None);pending.pop(key,None)
    grouped=collections.defaultdict(list)
    for r in encounters.values():grouped[r['type_id']].append(r)
    catalogue=[]
    for typ,rows in sorted(grouped.items()):
        catalogue.append({'type_id':typ,'signature_encounters':len(rows),'signature_and_removal_encounters':sum(r['matching_removal'] for r in rows),'entity_ids':sorted({r['entity_id'] for r in rows}),'recordings':sorted({r['recording'] for r in rows})})
    return {'scope':'Local recordings only; not a complete game catalogue. Signature association is observational, not a game-data name lookup.','stats':dict(stats),'object_type_count':len(types),'cube_type_evidence':catalogue,'encounters':list(encounters.values()),'unresolved_signature_encounters':unresolved,'observed_object_types':[{'type_id':k,'appearances':v} for k,v in sorted(types.items())]}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'cube-catalogue')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    paths=sorted(args.folder.glob('*.a2log*.jsonl'))
    report=mine(paths)
    (args.output/'catalogue.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    with (args.output/'encounters.csv').open('w',encoding='utf-8',newline='') as stream:
        fields=['type_id','entity_id','actor_id','collection_utc','matching_removal','appearance_method','completion_method','recording']
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(report['encounters'])
    lines=['# Cube type mining report','',report['scope'],'',f"Scanned {report['stats'].get('recordings',0)} recordings and {report['stats'].get('messages',0):,} messages; {report['object_type_count']} observed object types.",'','| Type ID | Signature encounters | Also matching removal | Entity IDs |','|---|---:|---:|---|']
    for item in report['cube_type_evidence']:
        lines.append(f"| {item['type_id']} | {item['signature_encounters']} | {item['signature_and_removal_encounters']} | {', '.join(map(str,item['entity_ids']))} |")
    lines+=['',f"Unresolved collection signatures without a mapped appearance: {len(report['unresolved_signature_encounters'])}.",'','Entity IDs are session instances. Type IDs are reusable classification keys. No live alert configuration is modified by this utility.']
    (args.output/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'stats':report['stats'],'cube_types':report['cube_type_evidence'],'unresolved':len(report['unresolved_signature_encounters'])}))
if __name__=='__main__':main()
