"""Text-only pre-registration of one bounded new IFT energy experiment."""
import json
import subprocess
from pathlib import Path
from stage191_summary import A_NAMES, V_NAMES, C_NAMES

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage191_energy_ml'

if __name__=='__main__':
    OUT.mkdir(exist_ok=True)
    assert not (OUT/'protocol.json').exists()
    requests=json.loads((ROOT/'workbook/stage129_energy_ml/extraction_contract.json').read_text())['requests']
    pilot=[0,48,113,254,255,257,260,129]
    counts={str(i):min(40,sum(c['role']==1 for c in requests[i]['cases'])) for i in pilot}
    p=dict(stage=191,starting_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        research='workbook/2026-11-08_stage187_electronic-only-observables-research.md §3/A',
        question='Does real unused-IFT all-candidate consistency add low-energy information beyond original X62, availability and prediction sigma, and a conditional joint-content shuffle?',
        input_manifest='workbook/stage129_energy_ml/extraction_contract.json',
        input_policy='All original280 sources and71376 active rows, original roles/allK/pz>50, no substitutions, no role0/reserved observations or predictions. Keep missing/failed leading identity as added NaN, retain original X62.',
        pilot=dict(source_indices=pilot,train_counts=counts,shortage='min40, original129 first40 too; original257 zero train retained, no replacement.'),
        groups=[list(range(i,min(i+8,280))) for i in range(0,280,8)],
        transport=json.loads((ROOT/'workbook/stage188_energy_ml/protocol.json').read_text())['transport'],
        native_collection='CKFTrackCollectionMergeWithoutIFT',
        native='Exact Stage188 full surface/covariance/field/material bridge; SDO pointer null for all parents, no truth feature. Single runtime per8sources. Original PHYS float32 pz matching unchanged; retain unmatched. No nearest hit; all candidate pulls enter fixed summaries. Geometry-only absence never a certified detector hole.',
        features=dict(A=A_NAMES,V=V_NAMES,C=C_NAMES,
            definition='Perlayer use all successful geometrically inside wafers with positive finite C00 and all candidate pulls finite. No supported wafer => sigma/content NaN. A=matched_start plus3 valid-wafer counts. V=mean(log(sqrt(C00)/1mm)). C=log1p(all candidates),log1p(count abs(pull)<=3),log1p(sum exp(-pull²/2)),sum pull*exp(-pull²/2)/(1+sum kernel). Empty candidates on valid wafer => four0. Never assert calibrated coverage or independent candidate N.'),
        arms=['X','A','V','C','S'],dimensions=[62,66,69,81,81],
        training='Original3seeds x400rounds/depth5 CPUhist, train incoming weights, one weighted cal offset;15 new fits, no scan; X exact Stage87. Independent contents only enter C. S keeps X/A/V and jointly shuffles12C within original role/component and fixed observable conditions.',
        shuffle_seed=20261108191,pz_edges_GeV=[100,200,400,800,1600],
        activity_edges=[0,2,4,6,8,10,12],
        conditioning_charge_columns=['VetoNu0_raw_charge','VetoNu1_raw_charge','Veto20_raw_charge','Veto21_raw_charge','Preshower0_raw_charge','Preshower1_raw_charge'],
        sigma_edges_mm=[.01,.03,.1,.3,1,3,10],
        shuffle_conditions='role/component,pz bin,asinh(sum signed raw charges/1pC) bin,exact A counts and finite pattern,perlayer sigma bins; no truth. Singleton rows remain; report moved fraction.',
        gates='Original8strata/3tails and all Stage87 gates; cal/test both trueE50-100/100-200 content vs X/A/V/S point<=.95 upper95<1 with tail guards<=2pp;500 incoming/component conditional bootstraps. No promotion from sigma or association improvement alone.',
        resources=dict(CPU_budget_s=60000,pilot_cap_s=3000,review_cap_s=1000,production_cap_s=48000,fit_cap_s=3000,audit_cap_s=5000,
            requested_CPUs=8,memory_MB=24000,max_live_jobs=4,final_cache_models_cap_B=100663296),
        admission='Before full: all original pilot identities and typed X62 exact, source/frame residual audits pass, first source0/48/113 each>=1 matched valid layer. Projection=3*(35*complete pilot GNU+compile CPU+fullN*max measured source/global mean subsequent CPU+35*max first-source-eventCPU)<=48000; used+1000+projection+8000<=60000;8*1.25*peakRSS<=24000MB. Production groups divided into5fixed families of7groups, each9600CPU seconds; max4 live. No budget enlargement if fail.',
        persistence='Only compact perparent15+4 scalar summary; full native measurement retained only first2active/source for independent audit, all pilot records for exact overlap. No new ROOT/xAOD.',
        promotion=False,overall_complete=False)
    (OUT/'protocol.json').write_text(json.dumps(p,indent=2)+'\n')
    for name in ['build_spec.json','pinned_source_evidence.json']:
        (OUT/name).write_bytes((ROOT/'workbook/stage188_energy_ml'/name).read_bytes())
    print('FROZEN',counts,'60000 CPU s, fixed5arms; full conditional on measured pilot')
