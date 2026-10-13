import unittest
import tempfile
from pathlib import Path
from cube_probe import Probe, decode_spawn, decode_object, available_recording_path, recover_cube_frames, CubeStatePublisher, recover_position_frames, recover_lifecycle_frames


class ProbeTests(unittest.TestCase):
    def test_heartbeat_keeps_message_freshness_unchanged(self):
        import json
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'state.json'
            publisher=CubeStatePublisher(path)
            publisher.publish(self.probe,force=True)
            original=json.loads(path.read_text())
            publisher.heartbeat()
            current=json.loads(path.read_text())
            self.assertEqual(current['last_message_at'],original['last_message_at'])
            self.assertGreaterEqual(current['updated_at'],original['updated_at'])
            publisher.publish(self.probe,running=False,force=True)
            publisher.heartbeat()
            self.assertFalse(json.loads(path.read_text())['running'])

    def test_short_spawn_recovers_recorded_partial_cube_header(self):
        message={'type':'41 36','name':'Spawn','payload':'f4 b3 01 04 2c 00 cb 0b 20 00 00 02 12 2f b5 c7 74 96 5d 47 00 88 47 46 00 98 b2 43 00 fe 01 94 a7 07 94 a7 07 64 00 00 00 04 00 0c 02 00 00 14 00 00 04 00 1c 01 19 00 d3 00 00 00 06 00 01 00 19 00 00 00 22 4e 20 00 f1 16 fb d6 3d 32 a1 01 00 00 83 b0 1f a9 00 3d 34 36 c4 99 02 04 00 a7 4f 12 00 00 e3 bb c7 00 4f 4d 47 00 8c 55 46 3b 00 91 00 00 00 01 01','t':1000,'event':{'NPC':999}}
        recovered=recover_cube_frames(message,{1200039})
        self.assertEqual(len(recovered),1)
        self.assertTrue(recovered[0]['partial_header'])
        self.probe.object_ids={1200039}
        self.probe.process(message)
        self.assertIn(36036,self.probe.active_cubes)
        self.assertEqual(self.probe.counts['alerts'],1)
        self.assertEqual(recover_cube_frames(message,{1200040}),[])
        wrong=dict(message,payload=message['payload'].replace('3d 34 36','3e 34 36'))
        self.assertEqual(recover_cube_frames(wrong,{1200039}),[])

    def test_collection_completion_stops_guidance_immediately(self):
        spoken=[];self.probe.on_voice=spoken.append
        self.probe.active_cubes[56885]={'Entity':56885,'Type':1200039,'X':1,'Y':2,'Z':3}
        self.probe.process({'type':'3A 36','payload':'b5 bc 03 e3 51 01 00 00 00 23 c5 9a 25','t':2000})
        self.assertNotIn(56885,self.probe.active_cubes)
        self.assertEqual(spoken,['Cube no longer nearby.'])
        self.probe.process({'type':'3A 36','payload':'b5 bc 03 e3 51 01 00 00 00 23 c5 9a 25','t':2001})
        self.assertEqual(len(spoken),1)

    def test_recorded_embedded_removal_clears_only_matching_cube(self):
        message={'type':'E6 97','payload':'b3 4a 96 99 15 5b a7 45 95 a5 e1 05 22 03 d0 98 03 05 23 34 1a 20 37 d7 16 03 fd ef e1 0b 8e db 74 0d c2 c4 ce 9a c3 41 c4 0b c4 0c 38 36 a3 ab 02 c7 6a 01 0c 35 36 b5 bc 03 04 03 00 0e 00 36 f1 1b 11 33 a1 01 00 00 05 25 01 01','t':2000}
        frames=recover_lifecycle_frames(message,{56885})
        self.assertEqual(len(frames),1)
        self.probe.active_cubes[56885]={'Entity':56885,'Type':1200039,'X':1,'Y':2,'Z':3}
        self.probe.active_cubes[7]={'Entity':7,'Type':1200041,'X':1,'Y':2,'Z':3}
        self.probe.process(message)
        self.assertNotIn(56885,self.probe.active_cubes)
        self.assertIn(7,self.probe.active_cubes)
        self.assertEqual(recover_lifecycle_frames(message,{7}),[])
        bad=dict(message,payload=message['payload'].replace('0c 35 36','0d 35 36'))
        self.assertEqual(recover_lifecycle_frames(bad,{56885}),[])

    def test_other_completion_signature_does_not_clear_cube(self):
        self.probe.active_cubes[56885]={'Entity':56885,'Type':1200039,'X':1,'Y':2,'Z':3}
        self.probe.process({'type':'3A 36','payload':'b5 bc 03 e3 51 01 00 00 00 00 00 00 00','t':2000})
        self.assertIn(56885,self.probe.active_cubes)

    def test_removal_feed_is_published_without_one_second_delay(self):
        import json
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'state.json';publisher=CubeStatePublisher(path)
            self.probe.active_cubes[1]={'Entity':1,'Type':1200041,'X':1,'Y':2,'Z':3}
            publisher.publish(self.probe,force=True)
            self.probe.active_cubes.clear()
            publisher.publish(self.probe)
            self.assertEqual(json.loads(path.read_text())['cubes'],[])

    def test_direct_removal_clears_before_spoken_direction_update(self):
        spoken=[];self.probe.on_voice=spoken.append
        self.probe.player_position=(0,0,0);self.probe.position_time=2000
        self.probe.north_axis='-Y';self.probe.east_axis='+X'
        self.probe.active_cubes[56885]={'Entity':56885,'Type':1200039,'X':1000,'Y':1000,'Z':0}
        self.probe.process({'type':'35 36','payload':'b5 bc 03 04 03 00','t':2000})
        self.assertEqual(spoken,['Cube no longer nearby.'])

    def test_player_packet_recovers_cube_header_despite_damaged_following_frame(self):
        message={'type':'45 36','name':'Player','event':{'Entity':1,'Name':'TestPlayer'},'payload':'aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa 3d 34 36 e3 da 01 04 00 a7 4f 12 00 55 c3 29 c7 b0 9c 8f 47 00 7c 2e 46 3d 00 92 28 2a 43 01 01 01 4b e3 b7 7b 06 03 02 00 f4 00 48 98 95 01 07 00 00 13 3a 36 95 ba 01 9d 57 65 03 f0 13 09 6d 8d 95 ba 01 14 00 8d a1 75 01 02 03 74 98 02 00 06 c8 a9 01 00 0e 00 36 1a fa b7','t':2000}
        recovered=recover_cube_frames(message,{1200039})
        self.assertEqual(len(recovered),1)
        self.assertTrue(recovered[0]['player_header'])
        self.probe.object_ids={1200039}
        self.probe.process(message)
        self.assertIn(28003,self.probe.active_cubes)
        self.assertAlmostEqual(self.probe.active_cubes[28003]['X'],-43459.33203125)
        self.assertEqual(recover_cube_frames(message,{1200040}),[])
        wrong_parent=dict(message,type='13 96',name=None)
        self.assertEqual(recover_cube_frames(wrong_parent,{1200039}),[])
        wrong_size=dict(message,payload=message['payload'].replace('3d 34 36','3e 34 36'))
        self.assertEqual(recover_cube_frames(wrong_size,{1200039}),[])

    def test_new_cube_voice_works_without_position_and_duplicates_stay_silent(self):
        spoken=[];self.probe.on_voice=spoken.append;self.probe.object_ids={1200041}
        self.probe.process({'type':'34 36','payload':self.OBJECT_PACKET,'t':1000})
        self.probe.process({'type':'34 36','payload':self.OBJECT_PACKET,'t':2000})
        second=self.OBJECT_PACKET.replace('9d ad 02','9e ad 02',1)
        self.probe.process({'type':'34 36','payload':second,'t':3000})
        self.assertEqual(spoken,['Cube found. Position tracking unavailable.','Cube found. '])
        self.assertIsNone(self.probe.player_position)

    def test_invalid_self_never_clears_valid_character(self):
        self.probe.track_player({'name':'Self','event':{'Entity':11294,'Name':'TestPlayer','Self':True},'t':0})
        self.probe.player_position=(1,2,3);self.probe.position_time=1
        self.probe.track_player({'name':'Self','event':{'Entity':0,'Name':'','Self':True},'t':2})
        self.assertEqual(self.probe.player_entity,11294)
        self.assertEqual(self.probe.player_position,(1,2,3))

    def test_recorded_own_position_correction_and_other_player_rejection(self):
        self.probe.player_entity=11294
        raw='9e 58 00 00 b8 93 32 c7 d5 e9 74 c7 0b e4 78 46 01 00'
        self.probe.track_player({'type':'3F 37','payload':raw,'t':1000})
        self.assertIsNotNone(self.probe.player_position)
        self.assertAlmostEqual(self.probe.player_position[0],-45715.71875)
        original=self.probe.player_position
        self.probe.track_player({'type':'3F 37','payload':raw.replace('9e 58','bd 62',1),'t':2000})
        self.assertEqual(self.probe.player_position,original)
        self.assertEqual(self.probe.position_time,1000)

    def test_recovered_self_and_position_preserve_order(self):
        def framed(op,payload):
            n=len(payload)+6;length=[]
            while n>=128:length.append((n&127)|128);n>>=7
            length.append(n)
            return bytes(length)+op+payload
        own=b'\x9e\x58'+bytes(4)+b'\x01\x0aTestPlayer'+bytes(100)
        correction=bytes.fromhex('9e 58 00 00 b8 93 32 c7 d5 e9 74 c7 0b e4 78 46 01 00')
        body=b'\xaa'*300+framed(b'\x33\x36',own)+framed(b'\x3f\x37',correction)+bytes.fromhex('0e 00 36')+bytes(8)
        wrapper={'type':'13 96','payload':body.hex(),'t':1000}
        recovered=recover_position_frames(wrapper)
        self.assertEqual([r['type'] for r in recovered],['33 36','3F 37'])
        self.probe.process(wrapper)
        self.assertEqual(self.probe.player_entity,11294)
        self.assertIsNotNone(self.probe.player_position)

    def test_overlay_feed_tracks_live_cubes_and_clears_on_stop(self):
        import json
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'state.json';publisher=CubeStatePublisher(path)
            self.probe.active_cubes[1]={'Entity':1,'Type':1200041,'X':100,'Y':200,'Z':300}
            publisher.publish(self.probe,force=True)
            state=json.loads(path.read_text())
            self.assertTrue(state['running']);self.assertEqual(state['cubes'][0]['Type'],1200041)
            publisher.publish(self.probe,running=False,force=True)
            stopped=json.loads(path.read_text())
            self.assertFalse(stopped['running']);self.assertEqual(stopped['cubes'],[])

    def test_recovery_requires_known_type_and_valid_frame_boundaries(self):
        payload=bytes.fromhex(self.OBJECT_PACKET)
        size=len(payload)+6
        frame=bytes([size])+bytes.fromhex('34 36')+payload
        # A second complete tick establishes the next frame boundary.
        following=bytes.fromhex('0e 00 36')+bytes(8)
        wrapped={'type':'13 96','payload':(b'\xaa'*300+frame+following).hex(),'t':0}
        self.assertEqual(len(recover_cube_frames(wrapped,{1200041})),1)
        self.assertEqual(recover_cube_frames(wrapped,{1200039}),[])
        bad=dict(wrapped,payload=(b'\xaa'*300+bytes([255])+frame[1:]+following).hex())
        self.assertEqual(recover_cube_frames(bad,{1200041}),[])
        self.probe.object_ids={1200041}
        self.probe.process(wrapped);self.probe.process(wrapped)
        self.assertEqual(self.probe.counts['alerts'],1)

    def test_existing_recordings_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            original=Path(folder)/'hunt.jsonl';original.write_text('original')
            second=Path(folder)/'hunt-002.jsonl';second.write_text('second')
            self.assertEqual(available_recording_path(original).name,'hunt-003.jsonl')
            self.assertEqual(original.read_text(),'original')
            self.assertEqual(second.read_text(),'second')

    def test_compass_voice_and_update_throttle(self):
        spoken=[]
        self.probe.on_voice=spoken.append
        self.probe.north_axis='-Y';self.probe.east_axis='+X'
        self.probe.player_position=(0,0,0);self.probe.position_time=0
        obj={'Entity':1,'X':3000,'Y':-4000,'Z':0}
        self.probe.voice_guidance(obj,0,found=True)
        self.assertIn('north east',spoken[0])
        self.assertIn('50 meters',spoken[0])
        self.probe.voice_guidance(obj,1000)
        self.assertEqual(len(spoken),1)
        self.probe.player_position=(2000,0,0);self.probe.position_time=9000
        self.probe.voice_guidance(obj,9000)
        self.assertEqual(len(spoken),2)

    def test_voice_waits_for_position_and_compass(self):
        spoken=[];self.probe.on_voice=spoken.append
        obj={'Entity':1,'X':3000,'Y':4000,'Z':0}
        self.probe.voice_guidance(obj,0,found=True)
        self.assertIn('unavailable',spoken[-1])
        self.probe.player_position=(0,0,0);self.probe.position_time=0
        self.probe.voice_guidance(obj,0,found=True)
        self.assertIn('Compass calibration needed',spoken[-1])

    def test_distance_uses_self_position_and_three_dimensions(self):
        self.probe.track_player({'name':'Self','event':{'Entity':9,'Name':'TestPlayer','Self':True},'t':0})
        self.probe.track_player({'name':'Move','event':{'Entity':9,'X':0,'Y':0,'Z':0},'t':1000})
        text=self.probe.cube_description({'X':300,'Y':400,'Z':1200},2000)
        self.assertIn('~13 meters away',text)
        self.assertIn('+X / +Y',text)

    def test_other_player_and_stale_position_do_not_produce_distance(self):
        self.probe.player_entity=9
        self.probe.track_player({'name':'Move','event':{'Entity':10,'X':1,'Y':2,'Z':3},'t':0})
        self.assertIsNone(self.probe.player_position)
        self.probe.player_position=(0,0,0);self.probe.position_time=0
        self.assertIn('distance unavailable',self.probe.cube_description({'X':1,'Y':2,'Z':3},6000))

    def test_recorded_self_skill_position(self):
        self.probe.player_entity=3808
        raw='e0 1d 01 11 e2 03 02 e1 f5 05 ff ff ff ff ff ff ff ff 80 75 d5 2a bb 03 00 00 e0 1d 01 00 c0 f5 71 c7 f9 90 b4 47 38 6f 80 46'
        self.probe.track_player({'type':'2A 38','payload':raw,'t':529101})
        self.assertIsNotNone(self.probe.player_position)
        self.assertAlmostEqual(self.probe.player_position[0],-61941.75)

    OBJECT_PACKET='9d ad 02 04 00 a9 4f 12 00 a3 3e 82 47 53 3d f1 47 4c ab 99 46'

    def test_recorded_object_is_separate_from_npc(self):
        obj=decode_object(self.OBJECT_PACKET)
        self.assertEqual(obj['Type'],1200041)
        self.assertEqual(obj['Entity'],38557)
        self.assertAlmostEqual(obj['X'],66685.2734375)

    def test_candidate_alert_and_remove_reset(self):
        self.probe.object_ids={1200041}
        sounds=[]
        self.probe.on_alert=lambda: sounds.append(True)
        message={'type':'34 36','payload':self.OBJECT_PACKET}
        self.probe.process(message); self.probe.process(message)
        self.assertEqual(len(self.output),1)
        self.assertEqual(len(sounds),1)
        self.assertIn('candidate',self.output[0])
        self.probe.process({'type':'35 36','payload':'9d ad 02 04 03 00'})
        self.probe.process(message)
        self.assertEqual(len(self.output),2)
        self.assertEqual(len(sounds),2)

    def test_other_object_type_does_not_alert(self):
        self.probe.object_ids={1100001}
        self.probe.process({'type':'34 36','payload':self.OBJECT_PACKET})
        self.assertEqual(self.output,[])

    def test_current_captured_spawn_layout(self):
        raw = 'e9 be 02 04 2c 00 d4 0b 20 00 00 02 48 bd d5 c6 be 2d 7f 47 00 e8 27 46'
        event = decode_spawn(raw)
        self.assertEqual(event['Entity'], 40809)
        self.assertEqual(event['NPC'], 2100180)
        self.assertEqual(event['Mask'], 11268)
        self.assertAlmostEqual(event['X'], -27358.640625)

    def setUp(self):
        self.output = []
        self.probe = Probe([9001], emit=lambda text, **kw: self.output.append(text) if not text.startswith("GAME PROTOCOL") else None)

    def spawn(self, npc=9001, entity=1, **extra):
        event = dict(Entity=entity, NPC=npc, X=1.0, Y=2.0, Z=3.0)
        event.update(extra)
        self.probe.process(dict(name="Spawn", event=event))

    def test_unknown_types_never_alert(self):
        self.spawn(npc=123)
        self.assertEqual(self.output, [])

    def test_duplicate_suppression_and_death_reset(self):
        self.spawn()
        self.spawn()
        self.assertEqual(len(self.output), 1)
        self.probe.process(dict(name="Death", event={"Entity": 1}))
        self.spawn()
        self.assertEqual(len(self.output), 2)

    def test_zone_resets_entity_ids(self):
        self.spawn()
        self.probe.process(dict(name="Zone", event={"X": 0, "Y": 0, "Z": 0}))
        self.spawn()
        self.assertEqual(len(self.output), 2)

    def test_invalid_position_and_failed_decoder_do_not_alert(self):
        self.spawn(X=float("nan"))
        self.probe.process(dict(name="Spawn", error="layout failed", payload="00"))
        self.assertEqual(self.output, [])
        self.assertEqual(self.probe.counts["decode_errors"], 1)

    def test_discovery_does_not_call_candidates_cubes(self):
        self.probe.discover = True
        self.spawn(npc=123)
        self.assertTrue(self.output[0].startswith("UNCLASSIFIED SPAWN"))


if __name__ == "__main__":
    unittest.main()
