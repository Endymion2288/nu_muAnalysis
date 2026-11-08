"""Freeze one real detector-level selected-shape package, not an energy fit."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage197_energy_ml'

if __name__ == '__main__':
    OUT.mkdir(exist_ok=True)
    assert not (OUT / 'protocol.json').exists()
    inventory = json.loads((ROOT / 'workbook/stage167_energy_ml/inventory.json').read_text())
    p = dict(stage=197, starting_commit=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(),
        question='What actual detector-level candidate support exists at pz0=50-100 GeV, and does its measured pz0/raw-charge/IFT-occupancy support intersect the existing selected-MC calibration sample?',
        research_basis='Stage187 post-readout section7.1 explicitly permits selected detector-level distributions without claiming complete normalization; electronic-only plan keeps true-energy goals separate.',
        PHYS=[r['path'] for r in inventory['PHYS']['matched']],
        selection_config='AnalysisZipFramework/config/ml_low_energy_cuts.yaml',
        definitions_config='AnalysisZipFramework/config/definitions.yaml',
        implementation_source='AnalysisZipFramework/source/Analyis.cxx',
        GRL='workbook/stage166_energy_ml/grl_input.json',
        aux_directory='/eos/user/b/bewilson/El9CalypsoForWaveForm/WaveformsCaloNuPeriod/015838',
        aux_scope='Only configured run15838 directory, one nonrecursive listing of *.root <=1024; never search other versions. Native reduced-charge branches take priority if present and no aux is used. Otherwise actual configured aux ntuple tree named tree (actual analysis.cxx addAuxFiles argument) is required to have run,event,myVetoNu0_rawCharge35,myVetoNu1_rawCharge35; use unique identity only, duplicates are ambiguous, no arbitrary overwrite.',
        pilot='First8192 entries of original first PHYS, two4096 chunks. Inspect actual branches, derive original leading via argmax pz0, exact pre-veto cutflow, retained raw/status/quality, no timing. Bounded aux headers and first8192 rows of first two files only. Pilot is not independent N, no effect-size admission.',
        data_selection='Keep original ml_low_energy_cuts DATA/ALL cuts and inherited fitted-charge threshold cuts, pz0>50 GeV, original status cleaning, original inclusive GRL; do not modify production selection. New displayed variables use raw charges/typed missing. Leading momentum only pz0, px/py only for original angle. No p0,p1,pz1 or timing.',
        reduced_semantics='Exact native reduced <30 if actually supplied; otherwise AuxLookupSuccess and original TimingOK using (status & ~512)==0 only as EXISTING selection trust flag, original 2024 zero+raw>30 invalidation and nonnegative rectified aux. No new arrival/lag/time extraction. Invalid reduced uses original raw<40 fallback. Missing/ambiguous aux remains unknown and never silently raw-only or counted as signal.',
        full='Only admitted original16 PHYS. Four independent file processes and one-thread uproot decompress each; chunk65536. Read each source once, combine pre-veto candidates in memory; read actual aux scalar columns once and keep only matching identities. No persistent pre-veto arrays or ROOT. Preserve per-file and total raw/cutflow/unknown denominators and exact pilot overlap.',
        MC='Only original ntuples/energy_ml_stage119/old_input.npz role==2, all components including allK. Use existing audited X62 pz0/raw/cluster0 fields, no truth-defined filtering, no quarantine/reserved processing or model forward. This is selected MC support, not a weighted physical prediction. No MC/data rate ratio, p-value, calibration fit or neutrino spectrum inference.',
        display='Observed candidates remain inclusive of unknown background. Fixed pz0/raw Veto10/IFT cluster0 marginal and joint count cells plus missing bins, all under/overflow; no best bins/axes/windows/model selection. MC groups remain separate, unweighted conditional shapes and support only. No assumption every observed candidate is neutrino.',
        pz_edges_GeV=[50,100,200,500,1000,2000,5000],
        raw_Veto10_edges_pC=[-10,0,10,40,100,500,2000],
        nClusters0_edges=[0,10,25,50,100,250,500,1000],
        admission='Threefold projection from complete pilot startup + slowest postfirst4096 CPU extrapolated to original14237355 entries plus bounded auxiliary header/row cost extrapolated to actual aux N; <=16000 full and used+projection+3600 audit<=20000. Kernel CPU limits and aggregate monitoring retain original total. If unsupported selection/aux, report actual pre-veto/unknown support without inventing final candidate or expanding directories.',
        audit='Independent scalar selection of actual first8192 input rows and all retained full pre-veto candidate primitives; independent final native/aux/fallback classification, exact all final identities and scalar histograms. Actual ROOT re-read final identities/fields and original pilot; MC role/component cell counts via independent scalar loops. Verify raw source and all cutflow denominators; no claim full independent interior identity read if not performed.',
        resources=dict(CPU_budget_s=20000,phase_CPU_s=dict(pilot=400,full=16000,audit=3600),request_CPUs=8,memory_MB=24000,max_live_jobs=1,file_processes=4,inner_threads=1,MaxRuntime_s=86400,final_cache_cap_B=8388608),
        preserve='Stage87/all scientific gates/roles/reserved/quarantine/allK/pz0-only first-power momentum/raw/typedNaN/legal negatives/strict-status0 timing; Stage54 original12 assets. Data distributions are no proof of true-E performance.',
        new_G4=0,new_reco=0,energy_fits=0,model_forward=0,promotion=False,overall_complete=False)
    assert len(p['PHYS']) == 16
    (OUT / 'protocol.json').write_text(json.dumps(p,indent=2)+'\n')
    print('Frozen Stage197: observed detector-level candidate support, no energy inference.')
