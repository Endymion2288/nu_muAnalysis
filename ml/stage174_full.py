from concurrent.futures import ProcessPoolExecutor
from stage174_common import *
if __name__=='__main__':
    with ProcessPoolExecutor(max_workers=3) as pool:reports=list(pool.map(read,range(3),[4096]*3,['full']*3))
    rows=[]
    for index,r in enumerate(reports):
        if r['supported']:rows+=calibrate(index)
    write('calibrations.json',rows)
    write('full_summary.json',dict(passed=True,sources=reports,calibration_rows=len(rows),usable_rows=sum(r['usable'] for r in rows),
        real_muon_calibration_conditional=True,independent_run_transfer_certified=False,energy_fits=0,model_forward=0,overall_complete=False,promotion=False))
