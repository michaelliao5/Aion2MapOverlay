import base64,json,struct,tempfile,unittest
from pathlib import Path
from mine_cube_ids import mine,SIGNATURE

class MiningTests(unittest.TestCase):
    def record(self,opcode,payload,src='a',t=0):
        return {'t':t,'opcode':opcode,'payload':base64.b64encode(payload).decode(),'src':src,'dst':'client'}
    def appearance(self,typ):
        return b'\x07'+struct.pack('<HIfff',4,typ,100,200,300)
    def run_mine(self,rows):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'capture.a2log.jsonl'
            p.write_text('\n'.join(json.dumps(r) for r in [{'schema':'a2log/v0.1','t0':'2026-10-12T22:00:00Z'}]+rows))
            return mine([p])
    def test_collection_maps_to_correct_connection_and_removal(self):
        result=self.run_mine([
            self.record('34 36',self.appearance(1200039),'a'),
            self.record('34 36',self.appearance(1200008),'b'),
            self.record('3A 36',b'\x07\x09\x01\x00\x00\x00'+SIGNATURE,'a',1000),
            self.record('35 36',b'\x07\x04\x03\x00','a',2000)])
        self.assertEqual([r['type_id'] for r in result['cube_type_evidence']],[1200039])
        self.assertEqual(result['cube_type_evidence'][0]['signature_and_removal_encounters'],1)
        self.assertEqual(result['encounters'][0]['entity_id'],7)
    def test_zone_reset_does_not_reuse_previous_entity_type(self):
        result=self.run_mine([
            self.record('34 36',self.appearance(1200039)),
            self.record('23 36',b'zone',t=500),
            self.record('3A 36',b'\x07\x09\x01\x00\x00\x00'+SIGNATURE,t=1000)])
        self.assertEqual(result['cube_type_evidence'],[])
        self.assertEqual(len(result['unresolved_signature_encounters']),1)
    def test_uncollected_objects_and_other_rewards_are_not_cubes(self):
        result=self.run_mine([
            self.record('34 36',self.appearance(1200008)),
            self.record('3A 36',b'\x07\x09'+bytes(8),t=1000),
            self.record('35 36',b'\x07\x01\x01\x00',t=2000)])
        self.assertEqual(result['cube_type_evidence'],[])
        self.assertEqual(result['object_type_count'],1)
if __name__=='__main__':unittest.main()
