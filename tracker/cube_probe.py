"""Packet-based AION 2 entity discovery and configured cube alerts."""
import argparse
import json
import math
import subprocess
import sys
import struct
import threading
import time
import os
from pathlib import Path

ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
BACKEND = ROOT / 'bin' / 'a2k-fixed.exe'
if not BACKEND.is_file():
    BACKEND = ROOT / 'bin' / 'a2k.exe'


def available_recording_path(path):
    if not path.exists():return path
    for number in range(2,100000):
        candidate=path.with_name(f'{path.stem}-{number:03d}{path.suffix}')
        if not candidate.exists():return candidate
    raise OSError('too many recordings with this filename')


class CubeStatePublisher:
    def __init__(self,path):
        self.path=path
        self.last_write=0
        self.last_alerts=-1
        self.lock=threading.RLock()
        self.state=None

    def _write(self,state):
        temp=self.path.with_name(self.path.name+'.tmp')
        try:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            temp.write_text(json.dumps(state),encoding='utf-8')
            os.replace(temp,self.path)
        except OSError:
            pass

    def publish(self,probe,running=True,force=False):
        with self.lock:
            now=time.monotonic()
            entities=set(probe.active_cubes)
            published_entities={obj['Entity'] for obj in self.state['cubes']} if self.state else set()
            if not force and now-self.last_write<1 and probe.counts['alerts']==self.last_alerts and entities==published_entities:return
            self.state={'schema':'cube-state/v1','updated_at':time.time(),'last_message_at':time.time(),'running':running,'cubes':[{k:obj[k] for k in ('Entity','Type','X','Y','Z')} for obj in probe.active_cubes.values()] if running else []}
            self._write(self.state)
            self.last_write=now;self.last_alerts=probe.counts['alerts']

    def heartbeat(self):
        with self.lock:
            if self.state is None or not self.state['running']:return
            self.state=dict(self.state,updated_at=time.time())
            self._write(self.state)


def play_cube_sound():
    if sys.platform != 'win32':
        return
    try:
        import winsound
        winsound.PlaySound('SystemExclamation', winsound.SND_ALIAS | winsound.SND_ASYNC)
    except RuntimeError as exc:
        print(f'Windows sound could not play: {exc}',file=sys.stderr)


class WindowsVoice:
    def __init__(self):
        self.proc = None
        if sys.platform != 'win32': return
        powershell = Path(os.environ.get('SystemRoot',r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        self.proc = subprocess.Popen([str(powershell),'-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'speak.ps1')],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)

    def speak(self,text):
        if not self.proc: return
        try:
            self.proc.stdin.write(text.replace('\n',' ')+ '\n')
            self.proc.stdin.flush()
        except (OSError,ValueError):
            print('Windows voice unavailable; text alerts remain enabled.',file=sys.stderr)
            self.close()

    def close(self):
        if not self.proc: return
        proc=self.proc;self.proc=None
        try: proc.stdin.close()
        except OSError: pass
        try: proc.wait(timeout=6)
        except subprocess.TimeoutExpired:
            proc.terminate();proc.wait()


def decode_object(payload):
    data = bytes.fromhex(payload)
    entity, offset = 0, 0
    for shift in range(0,35,7):
        if offset >= len(data): raise ValueError("truncated object entity")
        b=data[offset]; offset+=1; entity|=(b&127)<<shift
        if b<128: break
    else: raise ValueError("invalid object entity")
    if len(data)<offset+18: raise ValueError("truncated object")
    flags, type_id, x, y, z=struct.unpack_from('<HIfff',data,offset)
    if not all(math.isfinite(v) and abs(v)<=10_000_000 for v in (x,y,z)):
        raise ValueError("implausible object position")
    return dict(Entity=entity, Type=type_id, Flags=flags, X=x, Y=y, Z=z)


def recover_cube_frames(message,known_ids):
    """Recover only configured cube types at validated inner frame boundaries."""
    if message.get('recovered') or message.get('type')=='34 36' or not message.get('payload'):
        return []
    try:data=bytes.fromhex(message['payload'])
    except ValueError:return []
    if len(data)<24:return []
    def var_at(start):
        n=0
        for width in range(1,6):
            if start+width>len(data):raise ValueError()
            b=data[start+width-1];n|=(b&127)<<(7*(width-1))
            if b<128:return n,width
        raise ValueError()
    families={0x36,0x37,0x38,0x39,0x56,0x8A,0x8D,0x92,0x96,0x97}
    recovered=[];offset=0
    while (i:=data.find(b'\x34\x36',offset))>=0:
        offset=i+2
        for width in (1,2,3):
            start=i-width
            if start<0:continue
            try:
                size,head=var_at(start)
                end=start+size+head-4
                if head!=width or not 24<=size<=2048 or end<=i+20:continue
                partial=end>len(data)
                if partial:
                    # Observed Spawn framing swallowed a complete cube header,
                    # but not the remaining object metadata. Restrict this case
                    # to the observed 61-byte frame and a known complete header.
                    if message.get('type')!='41 36' or message.get('name')!='Spawn' or size!=61 or len(data)-(i+2)<21:continue
                    end=len(data)
                if end<len(data):
                    following=end
                    while following<len(data) and data[following]==0:following+=1
                    if following<len(data):
                        next_size,next_head=var_at(following)
                        if not 6<=next_size<=16384 or following+next_head+2>len(data) or data[following+next_head+1] not in families:continue
                        if following+next_size+next_head-4>len(data):continue
                payload=data[i+2:end]
                obj=decode_object(payload.hex())
                if obj['Flags']!=4 or obj['Entity']==0 or obj['Type'] not in known_ids:continue
                recovered.append({'type':'34 36','payload':payload.hex(),'t':message.get('t',0),'recovered':True,'partial_header':partial,'_offset':i})
                break
            except (ValueError,IndexError):continue
    return recovered


def lifecycle_entity(opcode,data):
    def readvar(start):
        entity=0
        for i in range(5):
            if start+i>=len(data):raise ValueError()
            b=data[start+i];entity|=(b&127)<<(i*7)
            if b<128:return entity,start+i+1
        raise ValueError()
    try:
        entity,end=readvar(0)
        if entity<=0:return None
        if opcode=='35 36' and data[end:] in (b'\x04\x03\x00',b'\x01\x01\x00'):return entity
        if opcode=='3A 36':
            actor,end=readvar(end)
            if actor>0 and data[end:]==bytes.fromhex('01 00 00 00 23 c5 9a 25'):return entity
    except ValueError:pass
    return None


def recover_lifecycle_frames(message,active_entities):
    if message.get('recovered') or not active_entities or not message.get('payload'):return []
    try:data=bytes.fromhex(message['payload'])
    except ValueError:return []
    def var(start):
        n=0
        for width in range(1,6):
            if start+width>len(data):raise ValueError()
            b=data[start+width-1];n|=(b&127)<<(7*(width-1))
            if b<128:return n,width
        raise ValueError()
    frames=[]
    for marker in (b'\x35\x36',b'\x3a\x36'):
        offset=0
        while (i:=data.find(marker,offset))>=0:
            offset=i+2
            for width in (1,2,3):
                start=i-width
                if start<0:continue
                try:
                    size,head=var(start);end=start+size+head-4
                    if head!=width or not 6<=size<=64 or end>len(data) or end<=i+2:continue
                    following=end
                    while following<len(data) and data[following]==0:following+=1
                    if following<len(data):
                        n,h=var(following)
                        if n<6 or following+h+2>len(data) or data[following+h+1] not in (0x36,0x37,0x38,0x39,0x56,0x8A,0x8D,0x92,0x96,0x97) or following+n+h-4>len(data):continue
                    payload=data[i+2:end];opcode=marker.hex(' ').upper()
                    if lifecycle_entity(opcode,payload) not in active_entities:continue
                    frames.append({'type':opcode,'payload':payload.hex(),'t':message.get('t',0),'recovered':True,'_offset':i});break
                except (ValueError,IndexError):continue
    return frames


def decode_spawn(payload, mask_bytes=2):
    data = bytes.fromhex(payload)
    entity, offset = 0, 0
    for shift in range(0, 35, 7):
        if offset >= len(data):
            raise ValueError("truncated entity ID")
        value = data[offset]
        offset += 1
        entity |= (value & 127) << shift
        if not value & 128:
            break
    else:
        raise ValueError("invalid entity varint")
    if len(data) < offset + mask_bytes + 19:
        raise ValueError("truncated spawn")
    mask = int.from_bytes(data[offset:offset+mask_bytes], "little")
    offset += mask_bytes
    if data[offset] & 1:
        raise ValueError("named spawn layout is not supported")
    offset += 1
    npc = struct.unpack_from("<I", data, offset)[0]
    x, y, z = struct.unpack_from("<fff", data, offset+6)
    if not all(math.isfinite(v) and abs(v) <= 10_000_000 for v in (x,y,z)):
        raise ValueError("implausible spawn coordinates")
    return dict(Entity=entity, NPC=npc, Mask=mask, X=x, Y=y, Z=z)


def recover_position_frames(message):
    if message.get('recovered') or not message.get('payload') or (message.get('event') and not message.get('error')):return []
    try:data=bytes.fromhex(message['payload'])
    except ValueError:return []
    if len(data)<256:return []
    def var(start):
        n=0
        for width in range(1,6):
            if start+width>len(data):raise ValueError()
            b=data[start+width-1];n|=(b&127)<<(7*(width-1))
            if b<128:return n,width
        raise ValueError()
    result=[]
    for marker in (b'\x33\x36',b'\x3f\x37',b'\x2a\x38'):
        offset=0
        while (i:=data.find(marker,offset))>=0:
            offset=i+2
            for width in (1,2,3):
                start=i-width
                if start<0:continue
                try:
                    size,head=var(start);end=start+size+head-4
                    if head!=width or not 20<=size<=16384 or end>len(data) or end<=i+10:continue
                    if end<len(data):
                        following=end
                        while following<len(data) and data[following]==0:following+=1
                        if following<len(data):
                            n,h=var(following)
                            if not 6<=n<=16384 or following+h+2>len(data) or data[following+h+1] not in (0x36,0x37,0x38,0x39,0x56,0x8A,0x8D,0x92,0x96,0x97) or following+n+h-4>len(data):continue
                    payload=data[i+2:end]
                    frame={'type':marker.hex(' ').upper(),'payload':payload.hex(),'t':message.get('t',0),'recovered':True}
                    if marker==b'\x33\x36':
                        if len(payload)<64:continue
                        entity,entity_width=var(i+2)
                        flag_at=i+2+entity_width+4
                        if entity==0 or flag_at>=end or not data[flag_at]&1:continue
                        length,length_width=var(flag_at+1)
                        text_start=flag_at+1+length_width
                        if not 1<=length<=64 or text_start+length>end:continue
                        name=data[text_start:text_start+length].decode('utf-8')
                        if not name.isprintable():continue
                        frame.update(name='Self',event={'Entity':entity,'Name':name,'Self':True})
                    elif marker==b'\x3f\x37':
                        _,entity_width=var(i+2)
                        if len(payload)!=entity_width+16 or payload[-2:]!=b'\x01\x00':continue
                    elif len(payload)<42 or len(payload)>128:continue
                    frame['_offset']=i
                    result.append((i,frame));break
                except (ValueError,IndexError):continue
    return [frame for _,frame in sorted(result,key=lambda item:item[0])]


class Probe:
    def __init__(self, cube_ids, discover=False, emit=print, mask_bytes=2, object_ids=(), on_alert=None, player_entity=None, units_per_meter=100, on_voice=None, north_axis=None, east_axis=None):
        self.cube_ids = set(cube_ids)
        self.discover = discover
        self.emit = emit
        self.mask_bytes = mask_bytes
        self.object_ids = set(object_ids)
        self.on_alert = on_alert
        self.player_entity = player_entity
        self.player_name = None
        self.player_position = None
        self.position_time = None
        self.units_per_meter = units_per_meter
        self.on_voice=on_voice
        self.north_axis=north_axis
        self.east_axis=east_axis
        self.active_cubes={}
        self.voice_time=-10000
        self.voice_signature=None
        self.position_warning_spoken=False
        self.seen = {}
        self.counts = {"messages": 0, "spawns": 0, "objects": 0, "recovered_objects":0, "alerts": 0, "decode_errors": 0}

    def cube_description(self,obj,now):
        label=f"Cube found: X {obj['X']:.1f}, Y {obj['Y']:.1f}"
        if self.player_position is None or self.position_time is None or not 0 <= now-self.position_time <= 5000:
            return label+' | direction unavailable | distance unavailable (waiting for recent player position) | candidate'
        dx,dy,dz=[obj[k]-p for k,p in zip(('X','Y','Z'),self.player_position)]
        axes=[]
        if abs(dx)>1: axes.append('+X' if dx>0 else '-X')
        if abs(dy)>1: axes.append('+Y' if dy>0 else '-Y')
        distance=math.sqrt(dx*dx+dy*dy+dz*dz)/self.units_per_meter
        direction=' / '.join(axes) or 'same X/Y'
        if self.north_axis and self.east_axis:
            def component(axis):return (dx if axis[-1]=='X' else dy)*(1 if axis[0]=='+' else -1)
            angle=math.degrees(math.atan2(component(self.east_axis),component(self.north_axis)))%360
            direction=('north','northeast','east','southeast','south','southwest','west','northwest')[int((angle+22.5)//45)%8]
        return label+f" | direction {direction} | ~{distance:.0f} meters away (position age {(now-self.position_time)/1000:.1f}s) | candidate"

    def voice_guidance(self,obj,now,found=False):
        if not self.on_voice:return
        prefix='Cube found. ' if found else ''
        if self.player_position is None or self.position_time is None or not 0<=now-self.position_time<=5000:
            if found and not self.position_warning_spoken:
                self.on_voice(prefix+'Position tracking unavailable.')
                self.position_warning_spoken=True
            return
        dx,dy,dz=[obj[k]-p for k,p in zip(('X','Y','Z'),self.player_position)]
        distance=math.sqrt(dx*dx+dy*dy+dz*dz)/self.units_per_meter
        if not self.north_axis or not self.east_axis:
            if found:self.on_voice(prefix+f'About {distance:.0f} meters away. Compass calibration needed.')
            return
        def component(axis):return (dx if axis[-1]=='X' else dy)*(1 if axis[0]=='+' else -1)
        north,east=component(self.north_axis),component(self.east_axis)
        angle=math.degrees(math.atan2(east,north))%360
        direction=('north','north east','east','south east','south','south west','west','north west')[int((angle+22.5)//45)%8]
        if math.hypot(dx,dy)/self.units_per_meter<5:direction='close by'
        height=dz/self.units_per_meter
        vertical=f' {abs(height):.0f} meters {"above" if height>0 else "below"} you.' if abs(height)>=10 else ''
        signature=(obj['Entity'],direction,round(distance/10),round(height/10))
        if not found and (now-self.voice_time<8000 or signature==self.voice_signature):return
        self.voice_time=now;self.voice_signature=signature
        self.on_voice(prefix+f'{direction}. About {distance:.0f} meters away.'+vertical)

    def track_player(self,message):
        name,event=message.get('name'),message.get('event')
        now=message.get('t',0)
        if name in ('Zone','Redirect'):
            self.player_position=None
            self.position_time=None
            if name=='Redirect': self.player_entity=None
        if name=='Self' and isinstance(event,dict):
            identity=event.get('Entity');character_name=event.get('Name')
            if type(identity) is int and identity>0 and isinstance(character_name,str) and 1<=len(character_name)<=64 and character_name.isprintable():
                if self.player_entity != identity:
                    self.player_position=None; self.position_time=None
                self.player_entity=identity
                self.player_name=character_name
        pos=None
        if name=='Zone' and isinstance(event,dict):
            pos=tuple(event.get(k) for k in ('X','Y','Z'))
        elif name=='Move' and isinstance(event,dict) and self.player_entity is not None and event.get('Entity')==self.player_entity:
            pos=tuple(event.get(k) for k in ('X','Y','Z'))
        elif message.get('type')=='3F 37' and self.player_entity is not None and message.get('payload'):
            try:
                data=bytes.fromhex(message['payload'])
                n=self.player_entity;encoded=[]
                while n>=128:encoded.append((n&127)|128);n>>=7
                encoded.append(n);prefix=bytes(encoded)
                if data.startswith(prefix) and len(data)==len(prefix)+16 and data[-2:]==b'\x01\x00':
                    pos=struct.unpack_from('<fff',data,len(prefix)+2)
            except (ValueError,struct.error):pass
        elif message.get('type')=='2A 38' and self.player_entity is not None and message.get('payload'):
            try:
                data=bytes.fromhex(message['payload'])
                n=self.player_entity; encoded=[]
                while n>=128: encoded.append((n&127)|128); n>>=7
                encoded.append(n); prefix=bytes(encoded)
                if len(data)>=42 and data.startswith(prefix) and data[-12-len(prefix)-2:-12]==prefix+b'\x01\x00':
                    pos=struct.unpack_from('<fff',data,len(data)-12)
            except (ValueError,struct.error): pass
        if pos is not None and all(isinstance(v,(int,float)) and math.isfinite(v) and abs(v)<=10_000_000 for v in pos):
            if self.position_time is None or now>=self.position_time:
                self.player_position=pos; self.position_time=now
                self.position_warning_spoken=False

    def process(self, message):
        recovered = recover_position_frames(message) + recover_cube_frames(message,self.object_ids)
        entities=set(self.active_cubes)
        for frame in recovered:
            if frame['type']=='34 36':
                try:entities.add(decode_object(frame['payload'])['Entity'])
                except ValueError:pass
        recovered += recover_lifecycle_frames(message,entities)
        for frame in sorted(recovered,key=lambda frame:frame.get('_offset',0)):
            self.process(frame)
        if message.get('type') in ('3A 36','35 36') and message.get('payload'):
            try:entity=lifecycle_entity(message['type'],bytes.fromhex(message['payload']))
            except ValueError:entity=None
            if entity in self.active_cubes:
                self.active_cubes.pop(entity)
                if self.on_voice:self.on_voice('Cube no longer nearby.')
        self.track_player(message)
        now=message.get('t',0)
        if message.get('name') in ('Zone','Redirect'):
            self.active_cubes.clear();self.voice_signature=None
        elif self.active_cubes and self.player_position is not None:
            nearest=min(self.active_cubes.values(),key=lambda obj:sum((obj[k]-p)**2 for k,p in zip(('X','Y','Z'),self.player_position)))
            self.voice_guidance(nearest,now)
        self.counts["messages"] += 1
        if self.counts["messages"] == 1:
            self.emit("GAME PROTOCOL MESSAGE RECEIVED: decoder has recognized traffic.", flush=True)
        if message.get("error"):
            self.counts["decode_errors"] += 1
        name, event = message.get("name"), message.get("event")
        if message.get("type") == "34 36" and message.get("payload"):
            try:
                obj = decode_object(message['payload'])
            except ValueError:
                self.counts['decode_errors'] += 1
                return
            self.counts['objects'] += 1
            if message.get('recovered'):self.counts['recovered_objects']+=1
            key=('object',obj['Entity'])
            if self.seen.get(key)==obj['Type']: return
            self.seen[key]=obj['Type']
            details=f"type={obj['Type']} entity={obj['Entity']} xyz=({obj['X']:.1f}, {obj['Y']:.1f}, {obj['Z']:.1f})"
            if obj['Type'] in self.object_ids:
                self.active_cubes[obj['Entity']]=obj
                self.counts['alerts']+=1
                text=self.cube_description(obj,message.get('t',0))
                if message.get('recovered'):text+=(' | recovered header; metadata incomplete' if message.get('partial_header') else ' | recovered frame')
                self.emit(text,flush=True)
                if self.on_alert:
                    self.on_alert()
                self.voice_guidance(obj,now,found=True)
            elif self.discover:
                self.emit('UNCLASSIFIED OBJECT: '+details,flush=True)
            return
        if message.get('type')=='35 36' and message.get('payload'):
            # Entity ID is the leading varint in object-removal messages.
            try:
                data=bytes.fromhex(message['payload']); entity=0
                for i,b in enumerate(data[:5]):
                    entity|=(b&127)<<(7*i)
                    if b<128:
                        self.seen.pop(('object',entity),None)
                        if entity in self.active_cubes:
                            self.active_cubes.pop(entity)
                            if self.on_voice:self.on_voice('Cube no longer nearby.')
                        break
            except ValueError: pass
        if name == "Spawn" and message.get("payload"):
            try:
                event = decode_spawn(message["payload"], self.mask_bytes)
            except ValueError:
                if not message.get("error"):
                    self.counts["decode_errors"] += 1
                return
        if name in ("Zone", "Redirect"):
            self.seen.clear()
        if not isinstance(event, dict):
            return
        if name == "Death":
            self.seen.pop(event.get("Entity"), None)
        if name != "Spawn":
            return
        self.counts["spawns"] += 1
        entity, npc = event.get("Entity"), event.get("NPC")
        if not isinstance(entity, int) or not isinstance(npc, int):
            return
        coords = [event.get(k) for k in ("X", "Y", "Z")]
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in coords):
            return
        if self.seen.get(entity) == npc:
            return
        self.seen[entity] = npc
        details = f"npc={npc} entity={entity} xyz=({coords[0]:.1f}, {coords[1]:.1f}, {coords[2]:.1f})"
        if npc in self.cube_ids:
            self.counts["alerts"] += 1
            self.emit(f"HIDDEN CUBE FOUND IN CLIENT VISIBILITY RANGE: {details}", flush=True)
            if self.on_alert:
                self.on_alert()
        elif self.discover:
            self.emit(f"UNCLASSIFIED SPAWN: {details}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discover", action="store_true", help="print unclassified spawns to identify cube NPC types")
    parser.add_argument("--diagnostics", action="store_true", help="show recurring capture traffic counters")
    parser.add_argument('--mute',action='store_true',help='disable Windows cube alert sounds')
    parser.add_argument('--test-sound',action='store_true',help='play the Windows cube alert sound and exit')
    parser.add_argument('--no-voice',action='store_true',help='disable spoken cube guidance')
    parser.add_argument('--test-voice',action='store_true',help='preview spoken cube guidance and exit')
    parser.add_argument('--north-axis',choices=('+X','-X','+Y','-Y'),help='world coordinate axis pointing north')
    parser.add_argument('--east-axis',choices=('+X','-X','+Y','-Y'),help='world coordinate axis pointing east')
    parser.add_argument('--player-entity',type=int,help='override your current session entity ID if capture missed Self')
    parser.add_argument('--units-per-meter',type=float,default=100,help='distance conversion, defaults to Unreal centimeter scale (estimate)')
    parser.add_argument("--adapter", help="Npcap adapter name; defaults to the Windows default-route adapter")
    parser.add_argument("--spawn-mask-bytes", type=int, choices=(2,4), default=2, help="current observed spawn mask is 2 bytes; legacy captures use 4")
    parser.add_argument("--seconds", type=int, default=0, help="stop live capture after this many seconds; zero means Ctrl+C")
    parser.add_argument("--list-adapters", action="store_true", help="list Npcap capture adapters and exit")
    parser.add_argument("--replay", type=Path, help="replay a2k JSONL/pcap recording instead of capturing live")
    parser.add_argument("--events", type=Path, help="read decoded a2k show/watch -json output (for debugging)")
    parser.add_argument("--config", type=Path, default=ROOT / "cube_ids.json")
    parser.add_argument("--log", type=Path, default=ROOT / "session.a2log.jsonl", help="live game-message recording for investigation")
    parser.add_argument('--map-state',type=Path,default=ROOT/'cube_state.json',help='live detected-cube feed for the map overlay')
    parser.add_argument('--no-record',action='store_true',help='capture without saving game-message recordings')
    parser.add_argument('--stop-file',type=Path,help='stop capture when this file exists (launcher integration)')
    args = parser.parse_args()
    if args.test_voice:
        voice=WindowsVoice()
        voice.speak('Cube found. North east. About eighty meters away.')
        voice.close()
        return 0
    if not math.isfinite(args.units_per_meter) or args.units_per_meter<=0:
        parser.error('--units-per-meter must be positive and finite')
    if args.test_sound:
        play_cube_sound()
        time.sleep(2)
        return 0
    if args.seconds < 0:
        parser.error("--seconds must be nonnegative")
    if args.list_adapters:
        return subprocess.call([str(BACKEND), "adapters"])
    if args.replay and args.events:
        parser.error("choose --replay or --events")
    try:
        config = json.loads(args.config.read_text(encoding="utf-8-sig"))
        ids = config["cube_npc_ids"]
        object_ids = config.get('candidate_cube_object_ids',[])
        north_axis=args.north_axis or config.get('north_axis')
        east_axis=args.east_axis or config.get('east_axis')
        allowed_axes=('+X','-X','+Y','-Y')
        if (north_axis is not None and north_axis not in allowed_axes) or (east_axis is not None and east_axis not in allowed_axes):
            raise ValueError('invalid compass axes')
        if bool(north_axis)!=bool(east_axis) or (north_axis and north_axis[-1]==east_axis[-1]):
            raise ValueError('north/east axes must both be provided and perpendicular')
        if not isinstance(ids, list) or not all(type(v) is int and v > 0 for v in ids):
            raise ValueError("cube_npc_ids must be a list of positive integers")
        if not isinstance(object_ids,list) or not all(type(v) is int and v>0 for v in object_ids):
            raise ValueError('candidate_cube_object_ids must be positive integers')
    except (OSError, ValueError, KeyError) as exc:
        parser.error(f"cannot read cube configuration: {exc}")
    if not ids and not object_ids and not args.discover:
        parser.error("no verified cube IDs configured; use --discover first")
    sound = play_cube_sound if not args.mute and not args.replay and not args.events else None
    voice=None
    if not args.mute and not args.no_voice and not args.replay and not args.events:
        voice=WindowsVoice()
    probe = Probe(ids, args.discover, mask_bytes=args.spawn_mask_bytes, object_ids=object_ids, on_alert=sound,player_entity=args.player_entity,units_per_meter=args.units_per_meter,on_voice=voice.speak if voice else None,north_axis=north_axis,east_axis=east_axis)
    print("Cube probe: cube coordinates, axis direction, estimated distance. Ctrl+C stops.", flush=True)
    if config.get('trial_cube_object_ids'):
        print('Trial whitelist enabled: unconfirmed object types may produce non-cube alerts.',flush=True)
    elif object_ids:
        print('Alerts enabled for types observed during reported cube encounters; other cube variants may be missing.',flush=True)
    if not ids and args.discover:
        print("DISCOVERY MODE: no cube IDs verified. Spawns are candidates, not confirmed cubes.", flush=True)
    proc = None
    stderr_thread = None
    health_thread = None
    health_stop = threading.Event()
    stream = None
    result = 0
    live_started = False
    last_message_clock = [time.monotonic()]
    publisher = CubeStatePublisher(args.map_state) if not args.replay and not args.events else None
    try:
        if args.events:
            stream = args.events.open(encoding="utf-8-sig")
        else:
            backend = BACKEND
            if not backend.is_file():
                raise OSError(f"capture backend missing: {backend}")
            if args.replay:
                command = [str(backend), "show", "-json", str(args.replay.resolve())]
            else:
                args.log.parent.mkdir(parents=True, exist_ok=True)
                requested_log=args.log
                args.log=available_recording_path(args.log)
                if args.log!=requested_log:
                    print(f'Previous recording preserved. New recording: {args.log.resolve()}',flush=True)
                command = [str(backend), "watch", "-json", "-log", str(args.log.resolve())]
                if args.no_record:
                    command = [str(backend), 'watch', '-json']
                if args.adapter:
                    command.extend(["-adapter", args.adapter])
                if args.seconds:
                    command.extend(["-for", f"{args.seconds}s"])
                print("Live capture: raw message recording disabled." if args.no_record else f"Recording game messages to {args.log.resolve()}", flush=True)
                def watch_recording():
                    last_size = -1
                    changed_at = time.monotonic()
                    warned = False
                    while not health_stop.wait(1):
                        if args.stop_file and args.stop_file.exists():
                            if proc and proc.poll() is None:proc.terminate()
                            return
                        try:
                            # Windows directory metadata can lag behind an open writer.
                            if args.no_record:
                                size=last_message_clock[0]
                            else:
                                with args.log.open('rb') as recording:
                                    recording.seek(0,os.SEEK_END)
                                    size=recording.tell()
                        except OSError:
                            size = 0
                        if size != last_size:
                            last_size = size
                            changed_at = time.monotonic()
                            if warned:
                                print('Game-message traffic resumed.' if args.no_record else 'Recording resumed: new game messages are being saved.',file=sys.stderr,flush=True)
                                warned = False
                        elif not warned and time.monotonic()-changed_at >= 30:
                            print('CAPTURE IDLE: no recognized game messages for 30 seconds.' if args.no_record else 'RECORDING STALLED: no new game messages saved for 30 seconds. Check the game connection and that the console is not paused by text selection; stop and restart capture if needed.',file=sys.stderr,flush=True)
                            warned = True
                health_thread = threading.Thread(target=watch_recording,daemon=True)
                health_thread.start()
            proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
            live_started = not args.replay
            if publisher:
                publisher.publish(probe,force=True)
                def publish_heartbeat():
                    while not health_stop.wait(5):
                        if proc.poll() is not None:return
                        publisher.heartbeat()
                threading.Thread(target=publish_heartbeat,daemon=True).start()
            def forward_diagnostics():
                for diagnostic in proc.stderr:
                    if not args.diagnostics and diagnostic.startswith('Npcap: TCP_packets='):
                        continue
                    print(diagnostic.rstrip(),file=sys.stderr,flush=True)
            stderr_thread = threading.Thread(target=forward_diagnostics,daemon=True)
            stderr_thread.start()
            stream = proc.stdout
        for line in stream:
            try:
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError("event must be a JSON object")
                last_message_clock[0]=time.monotonic()
                probe.process(message)
                if publisher:publisher.publish(probe)
            except (ValueError, TypeError) as exc:
                print(f"Skipped invalid event: {exc}", file=sys.stderr)
        if proc:
            result = proc.wait()
    except KeyboardInterrupt:
        print("\nStopping cube probe.")
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        result = 1
    finally:
        if publisher:publisher.publish(probe,running=False,force=True)
        if voice:voice.close()
        health_stop.set()
        if health_thread:
            health_thread.join(timeout=1)
        if proc and proc.poll() is None:
            # Ctrl+C is delivered to the backend too; let it clean up pktmon first.
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.terminate()
                proc.wait()
                print("Backend forced to stop; its Npcap handle was closed by Windows.", file=sys.stderr)
        if stderr_thread:
            stderr_thread.join(timeout=2)
        if proc and proc.stderr:
            proc.stderr.close()
        if stream:
            stream.close()
        print("Summary: " + json.dumps(probe.counts))
        if live_started and probe.counts["messages"] == 0:
            print("No game messages decoded. TCP packet counts alone do not prove the game protocol is supported.", file=sys.stderr)
    if args.stop_file and args.stop_file.exists():result=0
    return result


if __name__ == "__main__":
    sys.exit(main())
