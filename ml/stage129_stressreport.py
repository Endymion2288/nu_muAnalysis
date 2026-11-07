"""Complete paired stress-to-frozen-nominal comparisons, no fit or forward."""
from stage129_energy import ROOT,ART,load,evaluate
d=load(ROOT/'ntuples/energy_ml_stage119/old_input.npz')
for experiment,reference in [('saturationstress','Q'),('timingstress','T')]:
 p=load(ART/f'{experiment}_predictions.npz')
 arms=[a for a in p if a not in ['direct_cal','traditional']]
 evaluate(experiment,d,arms,extra_references=[reference])
