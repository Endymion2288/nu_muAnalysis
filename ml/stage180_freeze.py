"""Bounded ordinary-Ecal dual-range support in one already known real source."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage180_energy_ml'
OUT.mkdir(parents=True,exist_ok=True);(ROOT/'ntuples/energy_ml_stage180').mkdir(parents=True,exist_ok=True)
assert not (OUT/'protocol.json').exists()
source=json.loads((ROOT/'workbook/stage159_energy_ml/protocol.json').read_text())['sources']['PHYS']
p=dict(stage=180,question='Does the actual target-period ordinary Ecal have simultaneous dual-range/high-amplitude reference support, and what relative response is supported by heldout data?',
    PHYS=source,condition_input='workbook/stage173_energy_ml/condition_records.json',
    control_input='ntuples/energy_ml_stage161/event_records.json.gz',pilot_N=8192,full='Entire single named PHYS, no additional files/run/source search.',
    pairs='Actual CableMapping calo/CaloLo vs calo2/CaloHi grouped by identical station/plate/row/module and opposite PMT; branch indices sorted by actual hardware channel. Check existing same-parent4 native raw/peak/RMS/status float32.',
    readout='Original producer raw charge/peak/RMS/status only. Historical rectified integral definition retained; no claim of signed integral, ADC waveform or absolute amplitude truth. CaloNu explicitly outside this ordinary-Ecal comparison.',
    selection='All entries denominator. Descriptive paired overlap requires both status0, finite positive rawQ, finite RMS>0, raw_peak/RMS>=10. Status/missing/signed outside this selection remain counted. No track/energy/error or amplitude re-selection.',
    relative_fit='One median log(QHi/QLo) per module on even original entries only if at least100 controls. Validate on odd entries, no fit tuning. No absolute gain, PMT linearity, covariance coverage or energy improvement certification.',
    bins_raw_peak_mV=[0,50,100,250,500,1000,1500,2000,1e300],
    uncertainty='Descriptive finite-sample quantiles only. Shared trigger/optical fluctuations and selection not modeled; no nominal1sigma or independent source claim.',
    acceptance=['actual same-module mapping supported or explicit missing', 'original native4 scalar readout exact',
        'pilot/full prefix8192 exact', 'independent audit actual prefix4 and scalar role/count/proportionality checks', 'all missing/non0status and signed retained'],
    CPU_budget_s=1200,phase_CPU_allowance_s=dict(pilot=200,full=800,audit=200),request_CPUs=4,request_memory_MB=8000,max_jobs=1,MaxRuntime_s=86400,
    admission='Pilot profiles startup and the two actual4096 chunks. Threefold(startup + N/8192 * measured two-chunk CPU) <=800; used schedulerCPU+projection+200audit <=1200. Do not enlarge budget or sources.',
    no=['new models or energy forward','new G4','ν/reserved/quarantine access','second simulated readout invented','absolute energy calibration','full-run exposure or purity claim','additional fit/bin grid'],
    preserve='Stage87/all original gates, roles/K/pz>50GeV and pz0-only/raw/typed/signed/status0 timing remain unchanged.',overall_complete=False,promotion=False)
(OUT/'protocol.json').write_text(json.dumps(p,indent=2)+'\n');print('FROZEN ordinary-Ecal dual-range support, no arrays read')
