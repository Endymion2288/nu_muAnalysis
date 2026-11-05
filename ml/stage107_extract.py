"""Reuse frozen geometry extraction with separate stage107 output paths."""
import sys
import stage106_geometry as geometry
assert sys.argv[1]=='qa_extract', 'Stage107 resource admission rejected; no full extraction'
geometry.OUT=geometry.ROOT/'workbook/stage107_energy_ml'
geometry.CACHE=geometry.ROOT/'ntuples/energy_ml_stage107'
geometry.extract(sys.argv[1])
