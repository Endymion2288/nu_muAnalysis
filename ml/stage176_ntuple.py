"""Unchanged pinned ntuple with read-only post-merge native S0 snapshot."""
import shutil,sys
from pathlib import Path
source=Path(shutil.which('faser_ntuple_maker.py')).read_text()
needle='sc = acc.run';assert source.count(needle)==1
code='''import json
from AthenaPython import PyAthena
import ROOT
class Stage176StateSnapshot(PyAthena.Alg):
    def initialize(self):
        import StoreGateBindings.Bindings
        assert ROOT.gInterpreter.Declare(Path("STAGE176_HEADER").read_text())
        return PyAthena.StatusCode.Success
    def execute(self):
        store=PyAthena.py_svc("StoreGateSvc")
        tracks=store.retrieve("TrackCollection","CKFTrackCollectionMergeWithoutIFT")
        rows=json.loads(str(ROOT.Stage176States(tracks)))
        Path("native_S0_states.json").write_text(json.dumps(rows,indent=2)+"\\n")
        return PyAthena.StatusCode.Success
acc.addEventAlgo(Stage176StateSnapshot("Stage176NativeS0"))
'''.replace('STAGE176_HEADER',str(Path(__file__).resolve().parent/'stage176_state.hxx'))
# Path is deliberately imported in the actual executed source namespace.
code='from pathlib import Path\n'+code
source=source.replace(needle,code+needle)
sys.argv[0]='faser_ntuple_maker.py'
exec(compile(source,'stage176-pinned-ntuple-with-native-state.py','exec'),{'__name__':'__main__'})
