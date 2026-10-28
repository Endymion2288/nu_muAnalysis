#!/usr/bin/env bash
# One RDO -> official reconstruction -> merge ntuple, entirely in worker scratch.
set -eo pipefail

rdo="$1"
geometry="$2"
outfile="$3"
repo_root="$4"
runtime_archive="$5"
nevents="${6:--1}"
output_endpoint="${NU_MU_OUTPUT_ENDPOINT:-root://eoshome-x.cern.ch}"
workdir=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_reco_merge.XXXXXX")
partial_out=""
cleanup() {
    rm -rf "${workdir}"
    if [[ -n "${partial_out}" ]]; then
        xrdfs "${output_endpoint}" rm "${partial_out}" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

export NU_MU_SKIP_LCG=1
export FASER_OFFICIAL_ARCHIVE="${runtime_archive}"
source "${repo_root}/setup_env.sh"
nu_mu_official_setup "${workdir}/runtime"
set -u
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OMP_NUM_THREADS}"
export MKL_NUM_THREADS="${OMP_NUM_THREADS}"
cd "${workdir}"

echo "host=$(hostname) rdo=${rdo} geometry=${geometry} nevents=${nevents}"
cat "${FASER_CALYPSO_RUN}/NU_MU_BUILD_INFO.txt"
validator="${repo_root}/AnalysisZipFramework/submission/validate_merge_ntuple.py"
if [[ -f "${outfile}" ]] && python "${validator}" --rdo "${rdo}" \
        --ntuple "${outfile}" --nevents "${nevents}"; then
    echo "valid output already exists; skipping"
    exit 0
fi

run_stage() {
    local stage="$1"
    shift
    if /usr/bin/time -f "${stage} wall_seconds=%e max_rss_kib=%M user_seconds=%U system_seconds=%S" \
            -o "${stage}.time" "$@" > "${stage}.log" 2>&1; then
        cat "${stage}.time"
    else
        cat "${stage}.time"
        tail -n 120 "${stage}.log"
        return 1
    fi
}

local_rdo="${workdir}/$(basename "${rdo}")"
run_stage stage_rdo cp "${rdo}" "${local_rdo}"
run_stage reco faser_reco.py --isMC --geom "${geometry}" --nevents "${nevents}" "${local_rdo}"
xaod="$(basename "${rdo}" -RDO.root)-xAOD.root"
run_stage ntuple faser_ntuple_maker.py --isMC --geom "${geometry}" \
    --CKFTrackType merge --nevents "${nevents}" --outfile "${workdir}/ntuple.root" "${xaod}"

python "${validator}" --rdo "${local_rdo}" --xaod "${xaod}" --ntuple "${workdir}/ntuple.root" \
    --nevents "${nevents}" --logs reco.log ntuple.log
xrdfs "${output_endpoint}" mkdir -p "$(dirname "${outfile}")"
partial_out="${outfile}.partial.$$"
xrdcp --force --silent "${workdir}/ntuple.root" "${output_endpoint}/${partial_out}"
xrdfs "${output_endpoint}" mv "${partial_out}" "${outfile}"
partial_out=""
echo "completed output=${outfile} bytes=$(stat -c '%s' "${workdir}/ntuple.root")"
