"""A single bounded actual fit-cluster identity control, not a replacement model."""
import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage194_energy_ml'
if __name__=='__main__':
 OUT.mkdir(exist_ok=True);assert not (OUT/'protocol.json').exists()
 old=json.loads((ROOT/'workbook/stage192_energy_ml/protocol.json').read_text())
 p=dict(stage=194,starting_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),sources=old['sources'],pilot_per_source=4,
  original_predictions=old['original_predictions'],native_collection='CKFTrackCollectionMergeWithoutIFT',
  question='Does the exact frozen fitted track have actual direct-primary deposits on its fitted strip clusters? Distinguish unweighted barcode support from positive pointers and SDO completeness, following192/193 conditional tails.',
  source_policy='Exact original16/160; same deterministic MergeTrackCfg as188 solely restores that original collection. Select cached original collection index, assert pz0/charge and every barcode count exact. No changed track choice, refit, new IFT transport/G4/energy model.',
  labels=old['labels'],deposit_policy=old['deposit_policy'],
  review='All actual fitted TSOS PRDs retained. Four original deposit classes with missing PRD/empty strips unknown. Aggregate exact conditional192 IFT pure-primary square sums by whether >=1 fitted cluster has direct-primary positive pointer. All parents retained. Perparent/class counts, missing SDO and no-positive reasons; no fitted purity/coverage or data association error certification.',
  admission='Pilot all leading indices/pz0/charge and barcode counts exact, actual pointers belong to unique original truth; at least1 nu and1 original mu parent have resolved primary fit clusters. 3*(pilot GNU including compile+160*slowest postfirst execute CPU)<=600; used+projection+200<=1200;RSS*1.25<=12000MB. Stop if fail, no budget expansion.',
  resources=old['resources'],new_G4=0,new_track_fits=0,new_energy_fits=0,new_energy_forward=0,promotion=False,overall_complete=False)
 (OUT/'protocol.json').write_text(json.dumps(p,indent=2)+'\n')
 for name in ['pinned_source_evidence.json','build_spec.json']:(OUT/name).write_bytes((ROOT/'workbook/stage192_energy_ml'/name).read_bytes())
 print('FROZEN Stage194 actual fitted-cluster links,16/160,1200CPU seconds')
