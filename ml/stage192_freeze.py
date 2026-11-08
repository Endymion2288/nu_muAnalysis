"""One bounded MC truth-link control for the already measured unused-IFT cohort."""
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage192_energy_ml'
if __name__=='__main__':
    OUT.mkdir(exist_ok=True);assert not (OUT/'protocol.json').exists()
    old=json.loads((ROOT/'workbook/stage188_energy_ml/protocol.json').read_text())
    p=dict(stage=192,starting_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        research='Stage187 electronic-only routeA: distinguish shared-fit contributors from primary-muon deposits without inventing real-data truth.',
        sources=old['sources'],pilot_per_source=4,
        original_predictions='ntuples/energy_ml_stage188/full_native.json.gz',
        source_policy='Exact original Stage188 first4/source pilot16 and full160. All unsupported/unmatched muon controls retained, no additional parents, no energy fits/forward or new transport/reco/G4.',
        labels='Actual StoreGate TruthEvent exactly1; unique status1 muon directly outgoing from status4 numu with correct sign, or for no-numu gun a unique parentless-production muon. Ambiguities retained. SDO particle pointer must belong to this exact truth event; same barcode in another collection does not certify identity.',
        deposit_policy='Read every actual SDO deposit on all original candidate strips; compare barcode sets with Stage188 cache. Positive stored weights only for direct-primary labels; raw weight units not calibrated here. Candidate labels: pure direct primary, mixed direct primary, resolved no direct primary, unknown. A secondary/delta-ray label is not automatically a fake measurement.',
        review='Fixed matched-supported inside-wafer residual/pull summaries by direct-primary/mixed/non-primary/unknown, original denominators/pz50-100, and conditional abs(pull)<=1/3 counts. Correlated clusters, truth-defined conditional mechanism control; not unconditional coverage, association error rate, absolute momentum calibration or data transfer.',
        admission='Pilot actual source/run/event and all saved SDO barcode sets exact; unique primary plus linked candidate support in >=1 nu and the original mu control, if available. Triple(complete pilot incl compile +160*slowest postfirst CPU)<=600; used+projection+200<=1200;RSS*1.25<=12000MB. No budget enlargement if insufficient.',
        resources=dict(CPU_budget_s=1200,phase_CPU_s=dict(pilot=400,full=600,audit=200),request_CPUs=4,memory_MB=12000,max_live_jobs=1,final_event_bytes_cap=16777216),
        new_G4=0,new_reconstruction=0,new_energy_fits=0,new_energy_forward=0,promotion=False,overall_complete=False)
    (OUT/'protocol.json').write_text(json.dumps(p,indent=2)+'\n')
    (OUT/'pinned_source_evidence.json').write_bytes((ROOT/'workbook/stage188_energy_ml/pinned_source_evidence.json').read_bytes())
    (OUT/'build_spec.json').write_bytes((ROOT/'workbook/stage188_energy_ml/build_spec.json').read_bytes())
    print('FROZEN Stage192 actual SDO/TruthEvent pointers,16/160 parents,1200 CPU s')
