"""Bounded producer-log evidence, without scanning enormous event dumps."""
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage125_energy_ml'


def main():
    p=json.loads((OUT/'protocol.json').read_text());results=[]
    pattern=re.compile(r'physics.?list|FTF|BIC|INCLXX|JEFF|ENDF|QGSP|G4NEUTRONHPDATA|GlobalTag|FaserVersion|--phys|--geom|--evnt|EVNT.*root|UseIFT|CKFTrackType|git.*[Cc]ommit|54a9026|WAVE-Calibration|WAVE-Digitization|Calypso.*22\.|22\.0\.\d+',re.I)
    for item in p['inventory']:
        run=item['run'];base=Path(f'/eos/experiment/fasernu-data0/faser/sim/mc24/genie/{run}/log/master_dev')
        record=dict(run=run,tune=item['tune'],component=item['component'],logs=[])
        for suffix in ['HITS.sim.log','RDO.digi.log','RDO.rec.log','PHYS.ntp.log']:
            candidates=sorted(base.glob('*'+suffix))
            if not candidates:continue
            path=candidates[0];lines=[];nbytes=0
            with path.open(errors='replace') as f:
                for index,line in enumerate(f):
                    nbytes+=len(line.encode())
                    if pattern.search(line):lines.append(line.rstrip())
                    if index>=2999:break
            # Avoid the same long dump repeatedly citing one file name.
            lines=list(dict.fromkeys(lines))[:65]
            record['logs'].append(dict(path=str(path),bounded_read_bytes=nbytes,evidence=lines))
        text='\n'.join(line for log in record['logs'] for line in log['evidence'])
        evnt=re.findall(r'faser_simulate\.py (\S+)',text)
        record['first_simulation_generator_EVNT']=evnt[0] if evnt else None
        results.append(record)
    (OUT/'producer_evidence.json').write_text(json.dumps(results,indent=2)+'\n')
    for r in results:
        print(r['run'],r['tune'])
        for log in r['logs']:
            for line in log['evidence']:
                if any(k.lower() in line.lower() for k in ['EVNT.root','PhysicsList','--phys','GlobalTag','FaserVersion','WAVE-Digitization']):print(line[:500])


if __name__=='__main__':main()
