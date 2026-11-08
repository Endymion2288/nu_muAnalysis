"""Single-thread readers in independent processes on allocated cores."""
import concurrent.futures
import json
import subprocess
import sys
from pathlib import Path
OUT=Path('workbook/stage184_energy_ml')

def run(command,name):
    with (OUT/f'{name}.log').open('w') as stream:
        result=subprocess.run(['/usr/bin/time','-v','-o',str(OUT/f'{name}_time.txt'),sys.executable,'-u',*command],stdout=stream,stderr=subprocess.STDOUT)
    print(name,'exit',result.returncode,flush=True)
    if result.returncode:
        print((OUT/f'{name}.log').read_text()[-9000:],flush=True)
        raise RuntimeError((name,result.returncode))

if __name__=='__main__':
    phase=sys.argv[1]
    if phase=='preflight':
        run(['ml/stage184_reference.py'],'reference')
        run(['ml/stage184_native.py','0',phase],'preflight_source_0')
    elif phase=='full':
        assert json.loads((OUT/'admission.json').read_text())['admitted']
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda i:run(['ml/stage184_native.py',str(i),phase],f'{phase}_source_{i}'),[0,48,113]))
    elif phase=='audit':
        run(['ml/stage184_native.py','0',phase],'audit_source_0')
        run(['ml/stage184_audit.py'],'independent_audit')
    else:raise ValueError(phase)
    (OUT/f'{phase}_summary.json').write_text(json.dumps(dict(passed=True,phase=phase),indent=2)+'\n')
