"""Sequential, frozen VetoNu channel controls; reuse the Stage142 runtime."""
import json
import sys
from pathlib import Path
from stage142_pilot import worker

OUT = Path('workbook/stage143_energy_ml')


def main():
    index = int(sys.argv[1])
    support = json.loads((OUT/'support.json').read_text())
    admission = json.loads((OUT/f'parent_{index}_admission.json').read_text())
    assert index in support['selected_indices'] and admission['admitted']
    assert len(support['selected_indices']) <= 2
    worker(index)


if __name__ == '__main__':
    main()
