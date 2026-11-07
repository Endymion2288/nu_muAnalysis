"""Compact verified Stage129 audit products; never remove inputs or active spools."""
import gzip
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage129_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage129'


def main():
    queue_text=subprocess.check_output(['condor_q','-json','-attributes','ClusterId,ProcId,JobStatus,Iwd,Cmd,Args,TransferInput'],text=True)
    queue=json.loads(queue_text or '[]')
    assert not any('stage129' in json.dumps(r) for r in queue),'Stage129 jobs still reference inputs'
    resources=json.loads((OUT/'resource_summary.json').read_text());assert resources['terminal']==resources['unique_submitted']
    # Full generator records remain in ignored local data; summaries carry only
    # precise source/entry/seed and a reference to those complete records.
    stripped=0
    for path in OUT.rglob('fullchain_*_summary.json'):
        value=json.loads(path.read_text());case=value.get('case',{})
        if 'full_generator_record' in case:
            case.pop('full_generator_record');case['complete_record_cache']='ntuples/energy_ml_stage129/fullchain_generator_records.json';path.write_text(json.dumps(value,indent=2)+'\n');stripped+=1
    merged=[]
    for i in range(280):
        p=OUT/f'extract_{i}.json'
        if p.exists():merged.append(json.loads(p.read_text()))
    if merged:
        assert len(merged)==280
        target=OUT/'extraction_summaries.json';target.write_text(json.dumps(merged,separators=(',',':'))+'\n');assert json.loads(target.read_text())==merged
        for i in range(280):(OUT/f'extract_{i}.json').unlink()
    # Preserve one full canonical native log set for immediate review, and all
    # other native attempts in one lossless compressed text audit.
    logs=[p for p in OUT.rglob('*.log') if p.name.startswith('fullchain_') and not (p.parent==OUT and p.name.startswith('fullchain_0_'))]
    if logs:
        archive=OUT/'fullchain_native_logs.jsonl.gz'
        assert not archive.exists(),'Do not overwrite an existing lossless native archive'
        with gzip.GzipFile(filename=str(archive),mode='wb',mtime=0) as f:
            for p in logs:f.write((json.dumps(dict(path=str(p.relative_to(ROOT)),text=p.read_text()),ensure_ascii=False)+'\n').encode())
        with gzip.open(archive,'rt') as f:restored=[json.loads(line) for line in f]
        for item in restored:assert (ROOT/item['path']).read_text()==item['text']
        for p in logs:p.unlink()
    transfers=json.loads((OUT/'transfers.json').read_text());verified={(r['phase'],r['index']) for r in transfers if r['byte_roundtrip_verified']};deleted=[]
    for phase,index in sorted(verified):
        p=CACHE/f'{phase}_{index}_result.tar.gz'
        if p.exists():deleted.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,reason='collected member bytes verified on return; compact outputs and cache retained'));p.unlink()
    for p in (ROOT/'software/stage129').glob('*/*.tar.gz'):
        deleted.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,reason='all Stage129 attempts terminal; immutable package manifests retained'));p.unlink()
    for p in (ROOT/'software/stage129').glob('*'):
        if p.is_dir() and not any(p.iterdir()):p.rmdir()
    home_dirs=[]
    for root in [Path('/afs/cern.ch/user/x/xcheng'),Path('/eos/home-x/xcheng')]:
        if root.exists():home_dirs.extend(str(p) for p in root.glob('nu_mu_stage*') if p.is_dir())
    result=dict(all_stage_jobs_terminal=True,queue_reference_check=True,full_generator_payloads_removed_from_summary_count=stripped,source_summaries_merged=280,lossless_native_logs_compacted=len(logs),deleted=deleted,deleted_bytes=sum(r['bytes'] for r in deleted),event_cache_bytes=sum(p.stat().st_size for p in CACHE.rglob('*') if p.is_file()),model_cache_bytes=sum(p.stat().st_size for p in (ROOT/'ml/artifacts/stage129').rglob('*') if p.is_file()),remaining_unverified_transports=[str(p.relative_to(ROOT)) for p in CACHE.glob('*_result.tar.gz')],home_root_legacy_submission_dirs=home_dirs,home_cleanup='no matching legacy project dirs found' if not home_dirs else 'retained pending per-directory audit; no unrelated directories removed',shared_pinned_calypso_archive_retained=True,scope='byte checks from collection plus lossless audit readback; no SHA and no source data/ROOT removal')
    (OUT/'storage_cleanup.json').write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k!='deleted'})


if __name__=='__main__':main()
