"""Run-3 period-aware Athena job option helper for MyWaveformTimeRangeAlg / NtupleDumperAlg.

Selects thoroughgoing-muon station localtime peak differences automatically by
run number and MC/Data era:
  - MC:                   Veto2 - VN = 27.21 ns,  Trig - VN = 32.43 ns,  PS01 - VN = 51.41 ns
  - 2024 CaloNu (15821..16924):  35.783 ns,              34.872 ns,              53.512 ns
  - 2022-2024 non-CaloNu (<18500): 33.165 ns,            34.725 ns,              53.625 ns
  - 2025-2026 (>=18500):         33.166 ns,              34.930 ns,              13.330 ns
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import NamedTuple


class StationTimeDiffs(NamedTuple):
    period: str
    veto_vetonu_ns: float
    trigger_vetonu_ns: float
    preshower_vetonu_ns: float
    disable_preshower_fallback: bool


def get_run3_time_diffs(run_number: int, is_mc: bool = False, reco_tag: str = "") -> StationTimeDiffs:
    """Return measured station localtime differences for a given Run 3 run."""
    if is_mc:
        return StationTimeDiffs("mc", 27.21, 32.43, 51.41, False)
    if 15821 <= run_number <= 16924:
        return StationTimeDiffs("2024_CaloNu", 35.783, 34.872, 53.512, False)
    if run_number >= 18500:
        broken_ps = (reco_tag == "2025/p0013") and (19413 <= run_number <= 20142)
        period = "2026" if run_number >= 21000 else "2025"
        return StationTimeDiffs(period, 33.166, 34.930, 13.330, broken_ps)
    if run_number >= 12000:
        period = "2024_postCaloNu" if run_number > 16924 else "2024_preCaloNu"
        return StationTimeDiffs(period, 33.165, 34.725, 53.625, False)
    period = "2023" if run_number >= 10000 else "2022"
    return StationTimeDiffs(period, 33.165, 34.725, 53.625, False)


if __name__ == "__main__":
    from AthenaCommon.Configurable import Configurable
    from AthenaCommon.Constants import INFO
    from AthenaCommon.Logging import log
    from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
    from CalypsoConfiguration.AllConfigFlags import initConfigFlags
    from CalypsoConfiguration.MainServicesConfig import MainServicesCfg
    from FaserGeoModel.FaserGeoModelConfig import FaserGeometryCfg
    from MyWaveforms.MyWaveformTimeRangeConfig import MyWaveformTimeRangeCfg

    start_time = time.time()
    parser = argparse.ArgumentParser(description="Run-3 period-aware MyWaveformTimeRange config")
    parser.add_argument("file_path", nargs="+")
    parser.add_argument("--run", type=int, required=True, help="Run number used to select Run-3 timing offsets")
    parser.add_argument("--reco-tag", default="", help="Optional reconstruction tag (e.g. 2025/p0013)")
    parser.add_argument("--nevents", "-n", default=-1, type=int)
    parser.add_argument("--skip", type=int, default=0)
    parser.add_argument("--isMC", action="store_true")
    parser.add_argument("--output", "-o", type=str, default="")
    args = parser.parse_args()

    diffs = get_run3_time_diffs(args.run, is_mc=args.isMC, reco_tag=args.reco_tag)
    log.setLevel(INFO)
    Configurable.configurableRun3Behavior = True

    ConfigFlags = initConfigFlags()
    ConfigFlags.Input.isMC = args.isMC
    ConfigFlags.Exec.SkipEvents = args.skip
    ConfigFlags.Input.Files = args.file_path
    ConfigFlags.IOVDb.DatabaseInstance = "OFLP200" if args.isMC else "CONDBR3"
    ConfigFlags.Input.ProjectName = "data20"
    ConfigFlags.GeoModel.Align.Dynamic = False
    ConfigFlags.TrackingGeometry.MaterialSource = "/cvmfs/faser.cern.ch/repo/sw/database/DBRelease/current/acts/material-maps.json"
    ConfigFlags.GeoModel.FaserVersion = "FASERNU-04"
    ConfigFlags.IOVDb.GlobalTag = "OFLCOND-FASER-04"
    ConfigFlags.lock()

    acc = MainServicesCfg(ConfigFlags)
    acc.merge(FaserGeometryCfg(ConfigFlags))
    acc.merge(PoolReadCfg(ConfigFlags))
    acc.merge(
        MyWaveformTimeRangeCfg(
            ConfigFlags,
            veto_vetoNu_time=diffs.veto_vetonu_ns,
            timing_vetoNu_time=diffs.trigger_vetonu_ns,
            preshower_vetoNu_time=diffs.preshower_vetonu_ns,
            suffix=f"{args.output}",
            Events=[],
        )
    )

    acc.foreach_component("*").OutputLevel = INFO
    from AthenaConfiguration.ComponentFactory import CompFactory

    eventLoop = CompFactory.AthenaEventLoopMgr()
    eventLoop.EventPrintoutInterval = 10000
    acc.addService(eventLoop)

    if not args.isMC:
        replicaSvc = acc.getService("DBReplicaSvc")
        replicaSvc.COOLSQLiteVetoPattern = ""
        replicaSvc.UseCOOLSQLite = True
        replicaSvc.UseCOOLFrontier = False
        replicaSvc.UseGeomSQLite = True

    sc = acc.run(maxEvents=args.nevents)
    log.info(f"Finish execution in {time.time() - start_time:.2f} s ({diffs})")
    sys.exit(0 if sc.isSuccess() else 1)
