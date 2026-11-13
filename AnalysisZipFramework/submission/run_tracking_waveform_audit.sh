#!/usr/bin/env bash
set -eo pipefail
wave_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_wave_audit.XXXXXX")
trap 'rm -rf "$wave_scratch"' EXIT
mkdir "$wave_scratch/runtime" "$wave_scratch/code"
tar -xzf code.tar.gz -C "$wave_scratch/code"
cd "$wave_scratch"
xrdcp --silent root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/software/stage201_tracking/calypso_reco_runtime.tar.gz runtime.tar.gz
tar -xzf runtime.tar.gz -C runtime
export NU_MU_SKIP_LCG=1 FASER_CALYPSO_RUN="$wave_scratch/runtime" OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
source "$wave_scratch/code/setup_env.sh"
nu_mu_calypso_setup
xrdcp --silent root://eospublic.cern.ch//eos/experiment/fasernu-data0/faser/sim/mc24/genie/200080/rdo/s0014/FaserMC-MC24_Genie_sibyll_pi-200080-00000-00009-s0014-RDO.root input-RDO.root
for entry in 383 1915; do
    mkdir "$entry"
    cd "$entry"
    ln -s ../input-RDO.root input-RDO.root
    /usr/bin/time -v -o resources.txt python "$wave_scratch/code/AnalysisZipFramework/scripts/run_tracking_waveform_audit.py" input-RDO.root --skip "$entry" > reco.log 2>&1 || { tail -n 90 reco.log; exit 1; }
    xrdcp --silent --force waveform_fit_audit.json "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/workbook/stage204_causal/waveform_fit_$entry.json"
    xrdcp --silent --force resources.txt "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/workbook/stage204_causal/waveform_fit_$entry.resources.txt"
    cd ..
done
