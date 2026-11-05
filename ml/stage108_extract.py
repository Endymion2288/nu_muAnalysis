"""Original frozen extraction with stage108 output and admission."""
import sys
import stage106_geometry as geometry
geometry.OUT=geometry.ROOT/'workbook/stage108_energy_ml'
geometry.CACHE=geometry.ROOT/'ntuples/energy_ml_stage108'
assert sys.argv[1] in ['train_extract','test_extract']
geometry.extract(sys.argv[1])
