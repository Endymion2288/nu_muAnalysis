# Calypso `origin/master` Reduced-Charge Port

This directory contains the clean port of the `El9CalypsoForWaveForm` (`MyWaveformTimeRangeAlg`) reduced-charge fixes and Run-3 2022–2026 station time-difference measurements onto `calypso` `origin/master` (`PhysicsAnalysis/NtupleDumper/src/NtupleDumperAlg.{h,cxx}`), kept isolated from `/eos/home-x/xcheng/FASER/calypso` (`Tracking-4ST-Clean`).

## Bugs Fixed Relative to `calypso` `origin/master`
1. **Second-digitizer status bit (`512`) & `+16.0 ns` offset (`2024 CaloNu`)**:
   - `get_mean_scintillator_time` now accepts `(hit->hit_status() & ~512) == 0` instead of `hit_status() == 0`, and adds `16.0 ns` when `(hit->hit_status() & 512) != 0`.
2. **Expanded Veto2 channel list `{6, 7, 22, 23}`**:
   - Accounts for the move of Veto Station 2 readout to channels `22, 23` during the 2024 CaloNu period (`FASER_CaloScintillator.pdf`).
3. **`vetoNuContainer` index / secondary-hit bug**:
   - Filters `hit->channel()` to the two VetoNu channels (`{4, 5}`), maps `idx = (ch == ch0) ? 0 : 1` instead of indexing `m_vetonu_reduced_charge` by loop position, and skips secondary hits once the primary hit (`(hit_status & 2) == 0`) is recorded.
4. **2025–2026 Preshower PMT upgrade (`-40.3 ns` shift) & `2025/p0013` broken Preshower fallback**:
   - Following the 2025 Preshower PMT replacement, `Preshower0/1 - VetoNu` shifted from `53.625 ns` to `13.330 ns` (`Timing0..3 - VetoNu = 34.930 ns`, `Veto2 - VetoNu = 33.166 ns`).
   - Hardcoded `53.625 ns` in `2025/p0014` and `2026/p0015` shifted `expVetoNuLocalTime` `40.3 ns` too early whenever Veto2 saturated, integrating pre-pulse baseline noise (`~0 pC`).
   - In `2025/p0013` runs `19413..20142`, stale Preshower `TimingOffset` constants caused ~94% of `Preshower0/1` fits to fail and the remaining ~6% to reconstruct near `180.3 ns`; `DisablePreshowerFallback` skips Preshower and uses `TriggerWaveformHits` (`{8, 9, 10, 11}`) instead.
5. **Invalid reduced-charge sentinel `-1.0f`**:
   - Uses `-1.0f` instead of `0.0f` or copying raw charge when no valid timing reference is found or `(!isMC && run >= 12000 && q == 0 && raw_charge > 30)`.

## Applying to Calypso `master`
```bash
cd /path/to/calypso   # checked out on master
git apply /eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/calypso_port/calypso_master_reduced_charge.patch
```

For `2025/p0013` runs `19413 <= run <= 20142` (`19878` and `20012` are `p0014`), configure `NtupleDumperAlg.DisablePreshowerFallback = True`. Leaving `VetoVetoNuTimeDifference`, `TriggerVetoNuTimeDifference`, and `PreshowerVetoNuTimeDifference` at `< 0` selects the measured Run-3 period peak automatically by `run_number` and `isMC`.
