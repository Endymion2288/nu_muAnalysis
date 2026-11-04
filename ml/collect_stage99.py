"""Collect a known Stage99 archive without overwriting frozen metadata."""
import argparse
import json
import tarfile
from pathlib import Path

R = Path(__file__).resolve().parents[1]
O = R / 'workbook/stage99_energy_ml'
DATA = {'B_collection_features.tsv', 'B_identities.tsv', 'B_classifier_predictions.tsv', 'B_QA_identities.tsv'}


def compact_native_schema(record):
    if 'schema_catalog' in record:
        return record
    catalog = {}
    for source in record['sources']:
        for kind in ['PHYS_schema', 'native_schema']:
            if kind not in source:
                continue
            schema = source.pop(kind)
            ref = next((k for k, v in catalog.items() if v == schema), None)
            if ref is None:
                ref = f'schema_{len(catalog)}'
                catalog[ref] = schema
            source[kind + '_ref'] = ref
    record['schema_catalog'] = catalog
    return record


def target(name):
    path = Path(name)
    if path.name in DATA:
        return R/'ntuples/energy_ml_stage99'/path.name
    if path.name.startswith('B_classifier_') and path.suffix == '.json':
        return R/'ml/artifacts/stage99'/path.name
    return R/path


def main(mode):
    archive = R/f'ntuples/energy_ml_stage99/result_{mode}.tar.gz'
    copied = 0
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            path = Path(member.name)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError(member.name)
            data = tar.extractfile(member).read()
            if path.name == 'native_entry_QA.json':
                data = json.dumps(compact_native_schema(json.loads(data)), indent=2).encode()
            # Correct a resource-column name: no REC event payload was read.
            if path.name in ['B_sources.tsv', 'B_QA_sources.tsv']:
                data = data.replace(b'root_payload_bytes', b'native_event_payload_bytes')
            dest = target(member.name)
            if dest.exists():
                if dest.read_bytes() != data:
                    raise RuntimeError(f'Existing evidence differs: {dest}')
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            copied += 1
    print(f'{mode}: {copied} new files, preexisting evidence preserved')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['qa', 'nativeqa', 'report', 'bqa', 'breport', 'bfinish', 'validate'])
    main(parser.parse_args().mode)
