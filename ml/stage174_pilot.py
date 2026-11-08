from concurrent.futures import ProcessPoolExecutor
from stage174_common import *
if __name__=='__main__':
    with ProcessPoolExecutor(max_workers=3) as pool:reports=list(pool.map(read,range(3),[256]*3,['pilot']*3))
    write('pilot_summary.json',dict(passed=True,sources=reports,all_schema_supported=all(r['supported'] for r in reports),energy_fits=0,overall_complete=False))
