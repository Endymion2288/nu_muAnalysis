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
if [[ "${1:-}" == "--official" ]]; then export NU_MU_SKIP_LCG=1; fi

# ROOT, CMake dependencies, and the FASER run-list files come from the LCG/CVMFS view.
export NU_MU_LCG_VIEW="${NU_MU_LCG_VIEW:-/cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt}"
if [[ -z "${NU_MU_SKIP_LCG:-}" && -r "${NU_MU_LCG_VIEW}/setup.sh" && -z "${NU_MU_LCG_LOADED:-}" ]]; then
    source "${NU_MU_LCG_VIEW}/setup.sh"
    export NU_MU_LCG_LOADED=1
fi

export EOS_MGM_URL="${EOS_MGM_URL:-root://eosuser.cern.ch}"
export ROOT_RDF_SNAPSHOT_INFO="${ROOT_RDF_SNAPSHOT_INFO:-0}"
export FASER_DATA_ROOT="${FASER_DATA_ROOT:-/eos/experiment/faser}"
export FASER_NU_DATA_ROOT="${FASER_NU_DATA_ROOT:-/eos/experiment/fasernu-data0/faser}"
export FASER_CALYPSO_SW="${FASER_CALYPSO_SW:-/cvmfs/faser.cern.ch/repo/sw/Calypso}"
export FASER_CALYPSO_RUN="${FASER_CALYPSO_RUN:-${NU_MU_ANALYSIS_ROOT}/../calypso/run}"
export FASER_ATHENA_SETUP="${FASER_ATHENA_SETUP:-/cvmfs/atlas.cern.ch/repo/sw/software/24.0/Athena/24.0.41/InstallArea/x86_64-el9-gcc13-opt/setup.sh}"
export FASER_GCC13_SETUP="${FASER_GCC13_SETUP:-/cvmfs/atlas.cern.ch/repo/sw/software/24.0/sw/lcg/releases/gcc/13.1.0-b3d18/x86_64-el9/setup.sh}"
export FASER_RELEASE_DATA="${FASER_RELEASE_DATA:-/cvmfs/faser.cern.ch/repo/sw/software/22.0/faser/offline/ReleaseData/v20}"
export FASER_POOLCOND="${FASER_POOLCOND:-/cvmfs/faser.cern.ch/repo/sw/database/DBRelease/current}"
export G4ENSDFSTATEDATA="${G4ENSDFSTATEDATA:-/cvmfs/geant4.cern.ch/share/data/G4ENSDFSTATE2.2}"
export FASER_OFFICIAL_COMMIT=d32b0ff3cc4a2dad4abfb1474a82422c3c25b305
export FASER_OFFICIAL_ARCHIVE="${FASER_OFFICIAL_ARCHIVE:-/eos/user/x/xcheng/FASER/nu_muAnalysis/software/calypso-master-d32b0ff3-el9-gcc13.tar.gz}"

nu_mu_official_setup() {
    local runtime="${1:-${TMPDIR:-/tmp}/nu_mu_calypso_master_d32b0ff3_${UID}}"
    if [[ -n "${Calypso_SET_UP:-}" && "${FASER_CALYPSO_RUN}" != "${runtime}" ]]; then
        echo "Load the official runtime in a fresh shell; another Calypso is already loaded." >&2
        return 1
    fi
    if [[ ! -r "${runtime}/setup.sh" ]]; then
        mkdir -p "${runtime}"
        tar -xzf "${FASER_OFFICIAL_ARCHIVE}" -C "${runtime}" || return
    fi
    export FASER_CALYPSO_RUN="${runtime}"
    nu_mu_calypso_setup || return
    export ROOT_INCLUDE_PATH="${runtime}/include:${ROOT_INCLUDE_PATH:-}"
}

nu_mu_calypso_setup() {
    if [[ -r "${FASER_ATHENA_SETUP}" && -z "${FASER_ATHENA_LOADED:-}" ]]; then
        source "${FASER_ATHENA_SETUP}"
        export FASER_ATHENA_LOADED=1
    fi
    if [[ -r "${FASER_GCC13_SETUP}" && -z "${FASER_GCC13_LOADED:-}" ]]; then
        source "${FASER_GCC13_SETUP}"
        export FASER_GCC13_LOADED=1
    fi
    export ATLAS_POOLCOND_PATH="${ATLAS_POOLCOND_PATH:-${FASER_POOLCOND}}"
    case ":${DATAPATH:-}:" in
        *":${FASER_RELEASE_DATA}:"*) ;;
        *) export DATAPATH="${FASER_RELEASE_DATA}:${DATAPATH:-}" ;;
    esac
    if [[ -r "${FASER_CALYPSO_RUN}/setup.sh" && -z "${Calypso_SET_UP:-}" ]]; then
        source "${FASER_CALYPSO_RUN}/setup.sh"
    fi
    export PATH="${FASER_CALYPSO_RUN}/bin:${PATH}"
    echo "Calypso environment loaded from ${FASER_CALYPSO_RUN}"
}

nu_mu_calypso_report() {
    echo "Calypso: ${FASER_CALYPSO_RUN}"
    echo "Athena: ${Calypso_VERSION:-unloaded} ${Calypso_PLATFORM:-unloaded}"
    echo "Pool conditions: ${ATLAS_POOLCOND_PATH:-unset}"
    echo "faser_ntuple_maker: $(command -v faser_ntuple_maker.py 2>/dev/null || echo unavailable)"
}

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
if [[ "${1:-}" == "--official" ]]; then nu_mu_official_setup || return; fi
