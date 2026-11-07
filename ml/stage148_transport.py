"""One frozen parent through the already validated Stage142 observer/runtime."""
import json
from pathlib import Path

from stage142_pilot import worker

OUT = Path('workbook/stage148_energy_ml')


def main():
    support = json.loads((OUT/'support.json').read_text())
    admission = json.loads((OUT/'transport_admission.json').read_text())
    assert admission['admitted'] and len(support['selected_indices']) == 1
    index = support['selected_indices'][0]
    assert index == admission['frame_index']
    worker(index)


if __name__ == '__main__':
    main()
