"""Advance only the measured applicability item; broader goal remains active."""
from stage173_common import *
assert json.loads((OUT/'independent_validation.json').read_text())['passed']
p=OUT/'goal_requirements.tsv';s=p.read_text().replace('run15838 subsystem applicability\tin_progress\t','run15838 subsystem applicability\tcomplete_bounded_unknowns_explicit\t')
p.write_text(s)
