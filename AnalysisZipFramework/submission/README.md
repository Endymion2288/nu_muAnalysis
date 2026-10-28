# Official-master merge ntuples

Production uses unmodified Calypso master
`d32b0ff3cc4a2dad4abfb1474a82422c3c25b305`, Athena 24.0.41 and GCC 13.
The seven ordinary `TI12MC04` runs have 343 RDO files. CaloNu runs are excluded.

In a fresh shell, load the packaged runtime with:

```bash
source setup_env.sh --official
nu_mu_calypso_report
```

The software archive is stored once under `software/` on EOS and extracted to
local scratch. `FASER_OFFICIAL_ARCHIVE` can select another copy of the same build.

Regenerate the input list and submit from the repository root:

```bash
python3 AnalysisZipFramework/submission/make_merge_manifest.py > AnalysisZipFramework/submission/merge_manifest.tsv
module load lxbatch/eossubmit
mkdir -p logs
condor_submit AnalysisZipFramework/submission/ntuple_merge.sub
```

Each job stages one RDO file to local scratch, reconstructs it, then runs
`faser_ntuple_maker.py --isMC --geom TI12MC04 --CKFTrackType merge` on its new
xAOD. Both programs retain the official geometry, conditions and tracking defaults.
Athena runs serially inside each job; HTCondor supplies parallelism across files.

Only validated final ntuples are copied to
`ntuples/merge_mc24_master_d32b0ff3/<run>/` on EOS. Scratch xAOD, runtime copies,
diagnostics and temporary JSON files are removed. A retry skips an existing output
only after validating its event count and fitted-track vectors.

For a small test, invoke `run_ntuple_merge.sh` with six arguments:
`RDO geometry output repository runtime_archive nevents`; use a separate output
path so a partial test cannot be mistaken for a full production file. The RDO
scratch copy is also removed at exit.

`Track_nMeasurements` retains the official behavior of including candidates rejected
by subsequent station selection. The validator reports length mismatches. Analysis
cuts must use aligned fitted-track fields such as `Track_nDoF`; do not pair this
measurement-count field with track coordinates by index. `Track_isForward` is
validated against the fitted-track vector length.
`Track_hitSet` is filled before the same selection and has the same indexing risk.

The official reconstruction can also retain underconstrained candidates with
nonpositive `Track_nDoF`. The validator counts these without changing the output.
Apply the existing analysis requirements (`nLayers >= 7`, `nDoF >= 9`) before
interpreting chi-squared per degree of freedom. See the stage 06 workbook for
the measured example and upstream geometry diagnostics; file validation is not
a tracking-efficiency or geometry-systematics certification.
