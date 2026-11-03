"""Stage81 direct compatible PHYS extraction; no reconstruction or model calls."""
import argparse
import json
import resource
from pathlib import Path
from audited_features import REPO
from extract_alternative_support import extract


def main():
    p=argparse.ArgumentParser();p.add_argument('--index',type=int,required=True);p.add_argument('--qa-input',type=Path)
    a=p.parse_args();plan=json.loads((REPO/'workbook/stage81_energy_ml/protocol.json').read_text())
    assert a.index in plan['compatible_source_indices']
    source=plan['sources'][a.index]
    if a.qa_input:
        output=REPO/f'ntuples/energy_ml_stage81/package_qa{a.index}.npz';path=a.qa_input
    else:
        resource.setrlimit(resource.RLIMIT_CPU,(3300,3350))
        output=REPO/f'ntuples/energy_ml_stage81/source{a.index}.npz';path=Path(source['input'])
    extract(a.index,path,output,qa=bool(a.qa_input),source=source)


if __name__=='__main__':main()
