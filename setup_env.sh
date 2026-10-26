#!/usr/bin/env bash
# Source this file from lxplus before building or running nu_muAnalysis:
#   source setup_env.sh

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "Use: source setup_env.sh" >&2
    exit 2
fi

_nu_mu_setup_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export NU_MU_ANALYSIS_ROOT="${_nu_mu_setup_dir}"
export NU_MU_ANALYSIS_SOURCE="${NU_MU_ANALYSIS_ROOT}/AnalysisZipFramework"
export NU_MU_ANALYSIS_BUILD="${NU_MU_ANALYSIS_BUILD:-${NU_MU_ANALYSIS_ROOT}/build}"

# ROOT, CMake dependencies, and the FASER run-list files come from the LCG/CVMFS view.
export NU_MU_LCG_VIEW="${NU_MU_LCG_VIEW:-/cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt}"
if [[ -r "${NU_MU_LCG_VIEW}/setup.sh" && -z "${NU_MU_LCG_LOADED:-}" ]]; then
    source "${NU_MU_LCG_VIEW}/setup.sh"
    export NU_MU_LCG_LOADED=1
fi

export EOS_MGM_URL="${EOS_MGM_URL:-root://eosuser.cern.ch}"
export ROOT_RDF_SNAPSHOT_INFO="${ROOT_RDF_SNAPSHOT_INFO:-0}"
export FASER_DATA_ROOT="${FASER_DATA_ROOT:-/eos/experiment/faser}"
export FASER_NU_DATA_ROOT="${FASER_NU_DATA_ROOT:-/eos/experiment/fasernu-data0/faser}"
export FASER_CALYPSO_SW="${FASER_CALYPSO_SW:-/cvmfs/faser.cern.ch/repo/sw/Calypso}"

# If a compatible pre-built Calypso release is selected, set FASER_CALYPSO_SETUP
# before sourcing this file. This repository itself only needs the LCG view to build.
if [[ -n "${FASER_CALYPSO_SETUP:-}" && -r "${FASER_CALYPSO_SETUP}" ]]; then
    source "${FASER_CALYPSO_SETUP}"
fi

export PATH="${NU_MU_ANALYSIS_BUILD}:${PATH}"

nu_mu_configure() {
    cmake -S "${NU_MU_ANALYSIS_SOURCE}" -B "${NU_MU_ANALYSIS_BUILD}" "$@"
}

nu_mu_build() {
    local jobs="${NU_MU_BUILD_JOBS:-}"
    if [[ -z "${jobs}" ]]; then jobs="$(nproc)"; fi
    cmake --build "${NU_MU_ANALYSIS_BUILD}" --parallel "${jobs}" "$@"
}

nu_mu_run() {
    (cd "${NU_MU_ANALYSIS_BUILD}" && ./analysis "$@")
}

nu_mu_env_report() {
    echo "host: $(hostname)"
    echo "analysis: ${NU_MU_ANALYSIS_ROOT}"
    echo "build: ${NU_MU_ANALYSIS_BUILD}"
    echo "LCG: ${NU_MU_LCG_VIEW}"
    echo "ROOT: $(root-config --version 2>/dev/null || echo unavailable)"
    if command -v nvidia-smi >/dev/null 2>&1; then
        nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
    else
        echo "GPU: nvidia-smi unavailable"
    fi
}

unset _nu_mu_setup_dir
echo "nu_muAnalysis environment loaded; use nu_mu_env_report for a summary."
