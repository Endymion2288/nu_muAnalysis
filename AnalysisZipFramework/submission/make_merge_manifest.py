#!/usr/bin/env python3
"""Build the one-input-file-per-job manifest for merged CKF ntuples."""

from pathlib import Path
import re

SAMPLES = (
    (200080, "s0014", "TI12MC04"),
    (200082, "s0014", "TI12MC04"),
    (200083, "s0014", "TI12MC04"),
    (200089, "s0014", "TI12MC04"),
    (200093, "s0014", "TI12MC04"),
    (200094, "s0014", "TI12MC04"),
    (200100, "s0014", "TI12MC04"),
    (200139, "s0015", "TI12MCCaloNu"),
    (200140, "s0015", "TI12MCCaloNu"),
    (200146, "s0015", "TI12MCCaloNu"),
)

INPUT_ROOT = Path("/eos/experiment/fasernu-data0/faser/sim/mc24/genie")
OUTPUT_ROOT = Path("/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/merge_mc24")
SEGMENT = re.compile(r"-(\d{5})-(\d{5})-[^-]+-xAOD\.root$")


def main() -> None:
    rows = []
    for run, sim_tag, geometry in SAMPLES:
        input_dir = INPUT_ROOT / str(run) / "rec" / sim_tag
        files = sorted(input_dir.glob("*xAOD.root"))
        if not files:
            raise SystemExit(f"no xAOD inputs found in {input_dir}")
        for index, input_file in enumerate(files):
            match = SEGMENT.search(input_file.name)
            if match is None:
                raise SystemExit(f"cannot parse segment from {input_file}")
            first, last = match.groups()
            output = OUTPUT_ROOT / str(run) / input_file.name.replace(
                "-xAOD.root", "-merge-PHYS.root"
            )
            rows.append(
                (run, sim_tag, geometry, index, input_dir, output, first, last)
            )

    for row in rows:
        print("\t".join(map(str, row)))


if __name__ == "__main__":
    main()
