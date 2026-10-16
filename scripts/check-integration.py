"""Process-boundary check: real tracker publisher -> compiled overlay -> banner state."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tracker'))
from cube_probe import Probe, CubeStatePublisher

parser = argparse.ArgumentParser()
parser.add_argument('overlay', type=Path)
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='cube-integration-') as folder:
    state = Path(folder) / 'state.json'
    report = Path(folder) / 'report.json'
    publisher = CubeStatePublisher(state)
    probe = Probe(set(), object_ids={1200039}, emit=lambda *args, **kwargs: None)
    def check(label, expected_count, visible, ready=True):
        subprocess.run([str(args.overlay.resolve()), '--check-feed', '--state', str(state), '--report', str(report)], check=True, timeout=30)
        result = json.loads(report.read_text())
        assert (result['count'], result['bannerVisible'], result['ready']) == (expected_count, visible, ready), (label, result)
        print(f'PASS {label}: {result}')
    publisher.publish(probe, force=True)
    check('empty feed', 0, False)
    probe.active_cubes[56885] = {'Entity':56885, 'Type':1200039, 'X':1, 'Y':2, 'Z':3}
    publisher.publish(probe, force=True)
    check('Elyos appearance', 1, True)
    probe.process({'type':'3A 36', 'payload':'b5 bc 03 e3 51 01 00 00 00 23 c5 9a 25', 't':2000})
    publisher.publish(probe, force=True)
    check('collection clears banner', 0, False)
    probe.active_cubes[9] = {'Entity':9, 'Type':1301199, 'X':1, 'Y':2, 'Z':3}
    publisher.publish(probe, force=True)
    check('rift appearance', 1, True)
    stale = json.loads(state.read_text())
    stale['last_message_at'] = time.time()-30
    state.write_text(json.dumps(stale))
    check('idle capture hides banner', 0, False, False)
    publisher.publish(probe, running=False, force=True)
    check('stopped detector hides banner', 0, False, False)
print('Tracker/overlay integration passed.')

