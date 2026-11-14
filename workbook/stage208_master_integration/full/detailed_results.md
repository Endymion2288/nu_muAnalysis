# 最新 master 几何旋转版：实测性能明细

源码 `7fd40df8cd3b60e81b4095a4f84310c4a54700a0`。全量：3,374,987 个输入事件，383,670 个 truth-fiducial，140,132 个 truth-station-accepted proxy。未经权重修正。

old 为 d32b0ff3；strict 为前阶段已验证的 strict 材料旋转版；latest 为合入官方 7f2d1681 master、保留旋转及 isolated smoothing 的本次版本。nominal 排除 alternate run 200080。

局部 truth 参考是 SiHit 方向乘 HepMC 产生点动量模长，不能作为精确 G4 局部动量。动量残差定义为 reco/reference−1；MAD 为相对残差绝对值的中位数；宽度为 (q84−q16)/2。所有相对误差以无量纲量给出，例如 0.1 表示 10%。

## 从完整共同输入开始的 Merge cutflow

| 版本 | cut | 通过 | 原始输入分母 |
| --- | --- | --- | --- |
| old | NoCuts | 3374987 | 3374987 |
| old | Remove CaloNu PMT region (truth) | 3374987 | 3374987 |
| old | CC events only | 2559272 | 3374987 |
| old | nu_mu only | 2186815 | 3374987 |
| old | In Faser Nu Box or Lead Block | 883318 | 3374987 |
| old | Truth dec r < 100 mm | 418248 | 3374987 |
| old | Truth pz > 100 GeV | 383670 | 3374987 |
| old | At least one long track | 214310 | 3374987 |
| old | Veto20 and Veto21 charge > 40 pC | 214309 | 3374987 |
| old | Timing Station Charge > 20 pC | 214247 | 3374987 |
| old | Preshower Charge > 2.5 pC | 214089 | 3374987 |
| old | Track pz > 100 GeV | 188922 | 3374987 |
| old | Leading track has at >= 7 layers | 186740 | 3374987 |
| old | Track nDoF >= 9 | 180633 | 3374987 |
| old | Leading track has chi2/ndof < 15 | 180598 | 3374987 |
| old | Track R at max radius < 95 mm | 123895 | 3374987 |
| old | Track R at IFT < 95 mm | 122531 | 3374987 |
| old | Track rVetoNu < 120 mm | 121910 | 3374987 |
| old | Leading track theta < 25 mrad | 117752 | 3374987 |
| old | VetoNu0 reduced charge < 30 pC | 109004 | 3374987 |
| old | VetoNu1 reduced charge < 30 pC | 104930 | 3374987 |
| strict | NoCuts | 3374987 | 3374987 |
| strict | Remove CaloNu PMT region (truth) | 3374987 | 3374987 |
| strict | CC events only | 2559272 | 3374987 |
| strict | nu_mu only | 2186815 | 3374987 |
| strict | In Faser Nu Box or Lead Block | 883318 | 3374987 |
| strict | Truth dec r < 100 mm | 418248 | 3374987 |
| strict | Truth pz > 100 GeV | 383670 | 3374987 |
| strict | At least one long track | 216796 | 3374987 |
| strict | Veto20 and Veto21 charge > 40 pC | 216685 | 3374987 |
| strict | Timing Station Charge > 20 pC | 216578 | 3374987 |
| strict | Preshower Charge > 2.5 pC | 214347 | 3374987 |
| strict | Track pz > 100 GeV | 185086 | 3374987 |
| strict | Leading track has at >= 7 layers | 184046 | 3374987 |
| strict | Track nDoF >= 9 | 179798 | 3374987 |
| strict | Leading track has chi2/ndof < 15 | 179790 | 3374987 |
| strict | Track R at max radius < 95 mm | 123176 | 3374987 |
| strict | Track R at IFT < 95 mm | 121837 | 3374987 |
| strict | Track rVetoNu < 120 mm | 121217 | 3374987 |
| strict | Leading track theta < 25 mrad | 117069 | 3374987 |
| strict | VetoNu0 reduced charge < 30 pC | 108436 | 3374987 |
| strict | VetoNu1 reduced charge < 30 pC | 104425 | 3374987 |
| latest | NoCuts | 3374987 | 3374987 |
| latest | Remove CaloNu PMT region (truth) | 3374987 | 3374987 |
| latest | CC events only | 2559272 | 3374987 |
| latest | nu_mu only | 2186815 | 3374987 |
| latest | In Faser Nu Box or Lead Block | 883318 | 3374987 |
| latest | Truth dec r < 100 mm | 418248 | 3374987 |
| latest | Truth pz > 100 GeV | 383670 | 3374987 |
| latest | At least one long track | 216795 | 3374987 |
| latest | Veto20 and Veto21 charge > 40 pC | 216794 | 3374987 |
| latest | Timing Station Charge > 20 pC | 216726 | 3374987 |
| latest | Preshower Charge > 2.5 pC | 216576 | 3374987 |
| latest | Track pz > 100 GeV | 187080 | 3374987 |
| latest | Leading track has at >= 7 layers | 186032 | 3374987 |
| latest | Track nDoF >= 9 | 181731 | 3374987 |
| latest | Leading track has chi2/ndof < 15 | 181723 | 3374987 |
| latest | Track R at max radius < 95 mm | 124502 | 3374987 |
| latest | Track R at IFT < 95 mm | 123146 | 3374987 |
| latest | Track rVetoNu < 120 mm | 122516 | 3374987 |
| latest | Leading track theta < 25 mrad | 118338 | 3374987 |
| latest | VetoNu0 reduced charge < 30 pC | 109618 | 3374987 |
| latest | VetoNu1 reduced charge < 30 pC | 105554 | 3374987 |

首六项仅依赖共同 RDO truth，使用本次计数作为所有版本共享的 truth 前缀；重建选择部分分别从对应版本累计 cut bits 精确计算，latest 另与 worker 完整 cutflow 闭合。这不是对旧版重新读取全部 RDO 的计数。

## Merge 接受度及正确 primary 效率

| 版本 | 样本 | 阶段 | 分母 | 通过 | 未通过 | 效率 % | 68% 下限 % | 68% 上限 % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| old | all | any_primary_raw | 140132 | 125346 | 14786 | 89.4485 | 89.3662 | 89.5303 |
| old | all | any_primary_long | 140132 | 121143 | 18989 | 86.4492 | 86.3575 | 86.5404 |
| old | all | any_primary_quality | 140132 | 117190 | 22942 | 83.6283 | 83.5292 | 83.7269 |
| old | all | correct_leader | 140132 | 121019 | 19113 | 86.3607 | 86.2688 | 86.4521 |
| old | all | track_cuts | 140132 | 114941 | 25191 | 82.0234 | 81.9206 | 82.1257 |
| old | all | track_cuts_correct | 140132 | 114727 | 25405 | 81.8707 | 81.7675 | 81.9734 |
| old | all | final | 140132 | 102273 | 37859 | 72.9833 | 72.8645 | 73.1018 |
| old | all | final_correct | 140132 | 102066 | 38066 | 72.8356 | 72.7166 | 72.9543 |
| old | all | final_fixed_old_scintillator | 140132 | 102273 | 37859 | 72.9833 | 72.8645 | 73.1018 |
| old | nominal | any_primary_raw | 121425 | 107885 | 13540 | 88.8491 | 88.7584 | 88.9391 |
| old | nominal | any_primary_long | 121425 | 104194 | 17231 | 85.8093 | 85.7089 | 85.9092 |
| old | nominal | any_primary_quality | 121425 | 100741 | 20684 | 82.9656 | 82.8575 | 83.0732 |
| old | nominal | correct_leader | 121425 | 104079 | 17346 | 85.7146 | 85.6139 | 85.8148 |
| old | nominal | track_cuts | 121425 | 98812 | 22613 | 81.377 | 81.265 | 81.4884 |
| old | nominal | track_cuts_correct | 121425 | 98609 | 22816 | 81.2098 | 81.0974 | 81.3216 |
| old | nominal | final | 121425 | 87554 | 33871 | 72.1054 | 71.9765 | 72.2339 |
| old | nominal | final_correct | 121425 | 87358 | 34067 | 71.944 | 71.8149 | 72.0727 |
| old | nominal | final_fixed_old_scintillator | 121425 | 87554 | 33871 | 72.1054 | 71.9765 | 72.2339 |
| strict | all | any_primary_raw | 140132 | 125374 | 14758 | 89.4685 | 89.3862 | 89.5502 |
| strict | all | any_primary_long | 140132 | 120834 | 19298 | 86.2287 | 86.1364 | 86.3205 |
| strict | all | any_primary_quality | 140132 | 117619 | 22513 | 83.9344 | 83.8361 | 84.0323 |
| strict | all | correct_leader | 140132 | 120701 | 19431 | 86.1338 | 86.0412 | 86.2259 |
| strict | all | track_cuts | 140132 | 115439 | 24693 | 82.3788 | 82.2767 | 82.4803 |
| strict | all | track_cuts_correct | 140132 | 115202 | 24930 | 82.2096 | 82.1072 | 82.3116 |
| strict | all | final | 140132 | 101692 | 38440 | 72.5687 | 72.4494 | 72.6877 |
| strict | all | final_correct | 140132 | 101461 | 38671 | 72.4039 | 72.2843 | 72.5231 |
| strict | all | final_fixed_old_scintillator | 140132 | 102810 | 37322 | 73.3665 | 73.2483 | 73.4845 |
| strict | nominal | any_primary_raw | 121425 | 107904 | 13521 | 88.8647 | 88.7741 | 88.9547 |
| strict | nominal | any_primary_long | 121425 | 103954 | 17471 | 85.6117 | 85.5107 | 85.7121 |
| strict | nominal | any_primary_quality | 121425 | 101160 | 20265 | 83.3107 | 83.2034 | 83.4174 |
| strict | nominal | correct_leader | 121425 | 103833 | 17592 | 85.512 | 85.4107 | 85.6128 |
| strict | nominal | track_cuts | 121425 | 99293 | 22132 | 81.7731 | 81.6621 | 81.8836 |
| strict | nominal | track_cuts_correct | 121425 | 99072 | 22353 | 81.5911 | 81.4796 | 81.7021 |
| strict | nominal | final | 121425 | 87111 | 34314 | 71.7406 | 71.6112 | 71.8696 |
| strict | nominal | final_correct | 121425 | 86896 | 34529 | 71.5635 | 71.4339 | 71.6928 |
| strict | nominal | final_fixed_old_scintillator | 121425 | 88064 | 33361 | 72.5254 | 72.3971 | 72.6533 |
| latest | all | any_primary_raw | 140132 | 125376 | 14756 | 89.4699 | 89.3877 | 89.5516 |
| latest | all | any_primary_long | 140132 | 120834 | 19298 | 86.2287 | 86.1364 | 86.3205 |
| latest | all | any_primary_quality | 140132 | 117616 | 22516 | 83.9323 | 83.8339 | 84.0302 |
| latest | all | correct_leader | 140132 | 120701 | 19431 | 86.1338 | 86.0412 | 86.2259 |
| latest | all | track_cuts | 140132 | 115436 | 24696 | 82.3766 | 82.2746 | 82.4782 |
| latest | all | track_cuts_correct | 140132 | 115199 | 24933 | 82.2075 | 82.1051 | 82.3094 |
| latest | all | final | 140132 | 102807 | 37325 | 73.3644 | 73.2461 | 73.4823 |
| latest | all | final_correct | 140132 | 102576 | 37556 | 73.1996 | 73.0811 | 73.3177 |
| latest | all | final_fixed_old_scintillator | 140132 | 102807 | 37325 | 73.3644 | 73.2461 | 73.4823 |
| latest | nominal | any_primary_raw | 121425 | 107906 | 13519 | 88.8664 | 88.7758 | 88.9563 |
| latest | nominal | any_primary_long | 121425 | 103954 | 17471 | 85.6117 | 85.5107 | 85.7121 |
| latest | nominal | any_primary_quality | 121425 | 101157 | 20268 | 83.3082 | 83.2009 | 83.415 |
| latest | nominal | correct_leader | 121425 | 103833 | 17592 | 85.512 | 85.4107 | 85.6128 |
| latest | nominal | track_cuts | 121425 | 99290 | 22135 | 81.7706 | 81.6596 | 81.8812 |
| latest | nominal | track_cuts_correct | 121425 | 99069 | 22356 | 81.5886 | 81.4771 | 81.6996 |
| latest | nominal | final | 121425 | 88061 | 33364 | 72.523 | 72.3947 | 72.6509 |
| latest | nominal | final_correct | 121425 | 87846 | 33579 | 72.3459 | 72.2173 | 72.4741 |
| latest | nominal | final_fixed_old_scintillator | 121425 | 88061 | 33364 | 72.523 | 72.3947 | 72.6509 |

## Merge 同事件通过 / 丢失 / 新增

| 基线 | 新版 | 样本 | 阶段 | 基线通过 | 新版通过 | 丢失 | 新增 | 差值 pp | 95% 下限 pp | 95% 上限 pp | McNemar p |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| old | latest | all | track_pass | 114941 | 115436 | 1182 | 1677 | 0.353238 | 0.278474 | 0.428002 | 2.00909e-20 |
| old | latest | all | final | 102273 | 102807 | 1070 | 1604 | 0.381069 | 0.30877 | 0.453369 | 4.56673e-25 |
| old | latest | all | fixed_final | 102273 | 102807 | 1070 | 1604 | 0.381069 | 0.30877 | 0.453369 | 4.56673e-25 |
| old | latest | all | final_correct | 102066 | 102576 | 1075 | 1585 | 0.363943 | 0.29183 | 0.436055 | 4.19235e-23 |
| old | latest | all | fixed_correct | 102066 | 102576 | 1075 | 1585 | 0.363943 | 0.29183 | 0.436055 | 4.19235e-23 |
| old | latest | nominal | track_pass | 98812 | 99290 | 1028 | 1506 | 0.393659 | 0.312434 | 0.474884 | 2.02348e-21 |
| old | latest | nominal | final | 87554 | 88061 | 926 | 1433 | 0.417542 | 0.339178 | 0.495906 | 1.34244e-25 |
| old | latest | nominal | fixed_final | 87554 | 88061 | 926 | 1433 | 0.417542 | 0.339178 | 0.495906 | 1.34244e-25 |
| old | latest | nominal | final_correct | 87358 | 87846 | 932 | 1420 | 0.401894 | 0.323644 | 0.480144 | 6.92232e-24 |
| old | latest | nominal | fixed_correct | 87358 | 87846 | 932 | 1420 | 0.401894 | 0.323644 | 0.480144 | 6.92232e-24 |
| strict | latest | all | track_pass | 115439 | 115436 | 3 | 0 | -0.00214084 | -0.0045634 | 0.000281722 | 0.25 |
| strict | latest | all | final | 101692 | 102807 | 6 | 1121 | 0.795678 | 0.748909 | 0.842448 | 0 |
| strict | latest | all | fixed_final | 102810 | 102807 | 3 | 0 | -0.00214084 | -0.0045634 | 0.000281722 | 0.25 |
| strict | latest | all | final_correct | 101461 | 102576 | 6 | 1121 | 0.795678 | 0.748909 | 0.842448 | 0 |
| strict | latest | all | fixed_correct | 102579 | 102576 | 3 | 0 | -0.00214084 | -0.0045634 | 0.000281722 | 0.25 |
| strict | latest | nominal | track_pass | 99293 | 99290 | 3 | 0 | -0.00247066 | -0.00526644 | 0.000325121 | 0.25 |
| strict | latest | nominal | final | 87111 | 88061 | 6 | 956 | 0.782376 | 0.732505 | 0.832247 | 5.59546e-275 |
| strict | latest | nominal | fixed_final | 88064 | 88061 | 3 | 0 | -0.00247066 | -0.00526644 | 0.000325121 | 0.25 |
| strict | latest | nominal | final_correct | 86896 | 87846 | 6 | 956 | 0.782376 | 0.732505 | 0.832247 | 5.59546e-275 |
| strict | latest | nominal | fixed_correct | 87849 | 87846 | 3 | 0 | -0.00247066 | -0.00526644 | 0.000325121 | 0.25 |

## truth 可通过但 Merge 未通过的完整分类

| 版本 | 类别 | 事件 | truth 分母 |
| --- | --- | --- | --- |
| old | correct_leader_track_cut_failure | 6292 | 140132 |
| old | no_high_purity_primary_raw | 14660 | 140132 |
| old | primary_long_exists_wrong_leader | 46 | 140132 |
| old | primary_raw_only | 4200 | 140132 |
| old | scintillator_failure_after_track_cuts | 12661 | 140132 |
| old | selected_correct | 102066 | 140132 |
| old | selected_wrong_or_low_purity | 207 | 140132 |
| strict | correct_leader_track_cut_failure | 5499 | 140132 |
| strict | no_high_purity_primary_raw | 14618 | 140132 |
| strict | primary_long_exists_wrong_leader | 45 | 140132 |
| strict | primary_raw_only | 4537 | 140132 |
| strict | scintillator_failure_after_track_cuts | 13741 | 140132 |
| strict | selected_correct | 101461 | 140132 |
| strict | selected_wrong_or_low_purity | 231 | 140132 |
| latest | correct_leader_track_cut_failure | 5502 | 140132 |
| latest | no_high_purity_primary_raw | 14616 | 140132 |
| latest | primary_long_exists_wrong_leader | 45 | 140132 |
| latest | primary_raw_only | 4539 | 140132 |
| latest | scintillator_failure_after_track_cuts | 12623 | 140132 |
| latest | selected_correct | 102576 | 140132 |
| latest | selected_wrong_or_low_purity | 231 | 140132 |

## Merge 首个失败 cut（truth-accepted）

| 版本 | 首个失败 cut | 事件 | truth 分母 |
| --- | --- | --- | --- |
| old | At least one long track | 17360 | 140132 |
| old | Veto20 and Veto21 charge > 40 pC | 0 | 140132 |
| old | Timing Station Charge > 20 pC | 23 | 140132 |
| old | Preshower Charge > 2.5 pC | 1 | 140132 |
| old | Track pz > 100 GeV | 1774 | 140132 |
| old | Leading track has at >= 7 layers | 899 | 140132 |
| old | Track nDoF >= 9 | 3245 | 140132 |
| old | Leading track has chi2/ndof < 15 | 20 | 140132 |
| old | Track R at max radius < 95 mm | 536 | 140132 |
| old | Track R at IFT < 95 mm | 1226 | 140132 |
| old | Track rVetoNu < 120 mm | 69 | 140132 |
| old | Leading track theta < 25 mrad | 39 | 140132 |
| old | VetoNu0 reduced charge < 30 pC | 8646 | 140132 |
| old | VetoNu1 reduced charge < 30 pC | 4021 | 140132 |
| strict | At least one long track | 17064 | 140132 |
| strict | Veto20 and Veto21 charge > 40 pC | 63 | 140132 |
| strict | Timing Station Charge > 20 pC | 51 | 140132 |
| strict | Preshower Charge > 2.5 pC | 1248 | 140132 |
| strict | Track pz > 100 GeV | 2670 | 140132 |
| strict | Leading track has at >= 7 layers | 581 | 140132 |
| strict | Track nDoF >= 9 | 2413 | 140132 |
| strict | Leading track has chi2/ndof < 15 | 3 | 140132 |
| strict | Track R at max radius < 95 mm | 532 | 140132 |
| strict | Track R at IFT < 95 mm | 1218 | 140132 |
| strict | Track rVetoNu < 120 mm | 71 | 140132 |
| strict | Leading track theta < 25 mrad | 37 | 140132 |
| strict | VetoNu0 reduced charge < 30 pC | 8530 | 140132 |
| strict | VetoNu1 reduced charge < 30 pC | 3959 | 140132 |
| latest | At least one long track | 17064 | 140132 |
| latest | Veto20 and Veto21 charge > 40 pC | 0 | 140132 |
| latest | Timing Station Charge > 20 pC | 29 | 140132 |
| latest | Preshower Charge > 2.5 pC | 1 | 140132 |
| latest | Track pz > 100 GeV | 2686 | 140132 |
| latest | Leading track has at >= 7 layers | 588 | 140132 |
| latest | Track nDoF >= 9 | 2444 | 140132 |
| latest | Leading track has chi2/ndof < 15 | 3 | 140132 |
| latest | Track R at max radius < 95 mm | 538 | 140132 |
| latest | Track R at IFT < 95 mm | 1234 | 140132 |
| latest | Track rVetoNu < 120 mm | 73 | 140132 |
| latest | Leading track theta < 25 mrad | 37 | 140132 |
| latest | VetoNu0 reduced charge < 30 pC | 8616 | 140132 |
| latest | VetoNu1 reduced charge < 30 pC | 4012 | 140132 |

## Merge 正确 primary 纯度

| 版本 | 选择 | leaders | 正确 primary | 纯度 % | 68% 下限 % | 68% 上限 % |
| --- | --- | --- | --- | --- | --- | --- |
| old | all_leaders | 214310 | 194977 | 90.979 | 90.9169 | 91.0406 |
| old | track_cuts | 117753 | 115491 | 98.079 | 98.0386 | 98.1186 |
| old | final | 104930 | 102749 | 97.9215 | 97.877 | 97.9651 |
| strict | all_leaders | 216796 | 194380 | 89.6603 | 89.5948 | 89.7255 |
| strict | track_cuts | 118343 | 115949 | 97.9771 | 97.9357 | 98.0176 |
| strict | final | 104425 | 102122 | 97.7946 | 97.7487 | 97.8396 |
| latest | all_leaders | 216795 | 194380 | 89.6607 | 89.5952 | 89.7259 |
| latest | track_cuts | 118339 | 115946 | 97.9778 | 97.9365 | 98.0184 |
| latest | final | 105554 | 103243 | 97.8106 | 97.7651 | 97.8552 |

## Merge 数值异常与电荷符号错误

| 版本 | 选择 | leaders | 非有限 chi2 | ndof≤0 | 非有限 pz | 正确 primary pairs | 符号错误 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| old | leaders | 214310 | 0 | 785 | 0 | 194977 | 5324 |
| old | track_cuts | 117753 | 0 | 0 | 0 | 115491 | 1186 |
| old | final | 104930 | 0 | 0 | 0 | 102749 | 1059 |
| strict | leaders | 216796 | 0 | 117 | 0 | 194380 | 3479 |
| strict | track_cuts | 118343 | 0 | 0 | 0 | 115949 | 52 |
| strict | final | 104425 | 0 | 0 | 0 | 102122 | 45 |
| latest | leaders | 216795 | 0 | 117 | 0 | 194380 | 3480 |
| latest | track_cuts | 118339 | 0 | 0 | 0 | 115946 | 52 |
| latest | final | 105554 | 0 | 0 | 0 | 103243 | 45 |

## Merge 最终粒子组成

| 版本 | 粒子类别 | 事件 | 最终事件 |
| --- | --- | --- | --- |
| old | electron | 2 | 104930 |
| old | hadron | 2043 | 104930 |
| old | low_purity_match | 22 | 104930 |
| old | other_muon | 99 | 104930 |
| old | primary_muon_high_purity | 102749 | 104930 |
| old | primary_muon_low_purity | 8 | 104930 |
| old | unmatched | 7 | 104930 |
| strict | electron | 1 | 104425 |
| strict | hadron | 2160 | 104425 |
| strict | low_purity_match | 21 | 104425 |
| strict | other_muon | 104 | 104425 |
| strict | primary_muon_high_purity | 102122 | 104425 |
| strict | primary_muon_low_purity | 7 | 104425 |
| strict | unmatched | 10 | 104425 |
| latest | electron | 1 | 105554 |
| latest | hadron | 2169 | 105554 |
| latest | low_purity_match | 20 | 105554 |
| latest | other_muon | 104 | 105554 |
| latest | primary_muon_high_purity | 103243 | 105554 |
| latest | primary_muon_low_purity | 7 | 105554 |
| latest | unmatched | 10 | 105554 |

## 三站动量响应（Merge，正确 primary leader）

| 版本 | 站 | 选择 | 量 | pairs | 偏差中位数 | 68% 半宽 | MAD | 绝对误差 q68 | |误差|>50% |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| old | 1 | matched_leader | p_relative | 193832 | -0.0207119 | 0.148334 | 0.0760109 | 0.152047 | 20054 |
| old | 1 | matched_leader | pz_relative | 193832 | -0.0207129 | 0.148333 | 0.0760078 | 0.152048 | 20054 |
| old | 1 | matched_final_leader | p_relative | 102602 | -0.0151354 | 0.0985645 | 0.0571589 | 0.100639 | 5166 |
| old | 1 | matched_final_leader | pz_relative | 102602 | -0.0151346 | 0.0985651 | 0.0571577 | 0.100639 | 5166 |
| old | 2 | matched_leader | p_relative | 194653 | -0.0207612 | 0.151509 | 0.0771027 | 0.155184 | 20810 |
| old | 2 | matched_leader | pz_relative | 194653 | -0.0207617 | 0.151508 | 0.0771003 | 0.155182 | 20809 |
| old | 2 | matched_final_leader | p_relative | 102617 | -0.0151678 | 0.09932 | 0.0574983 | 0.101302 | 5247 |
| old | 2 | matched_final_leader | pz_relative | 102617 | -0.0151674 | 0.0993211 | 0.0574981 | 0.101302 | 5247 |
| old | 3 | matched_leader | p_relative | 193064 | -0.0208677 | 0.14831 | 0.0759332 | 0.151863 | 20080 |
| old | 3 | matched_leader | pz_relative | 193064 | -0.0208674 | 0.148311 | 0.075933 | 0.151865 | 20080 |
| old | 3 | matched_final_leader | p_relative | 102616 | -0.0152464 | 0.098576 | 0.057215 | 0.100629 | 5190 |
| old | 3 | matched_final_leader | pz_relative | 102616 | -0.0152452 | 0.0985758 | 0.0572138 | 0.100632 | 5190 |
| strict | 1 | matched_leader | p_relative | 193340 | -0.0189549 | 0.109659 | 0.0602195 | 0.112648 | 14177 |
| strict | 1 | matched_leader | pz_relative | 193340 | -0.018955 | 0.109656 | 0.0602215 | 0.112648 | 14177 |
| strict | 1 | matched_final_leader | p_relative | 101968 | -0.0139363 | 0.0703173 | 0.0444072 | 0.0724431 | 1226 |
| strict | 1 | matched_final_leader | pz_relative | 101968 | -0.0139356 | 0.0703177 | 0.0444084 | 0.0724444 | 1226 |
| strict | 2 | matched_leader | p_relative | 194075 | -0.0191345 | 0.111977 | 0.061093 | 0.115069 | 14753 |
| strict | 2 | matched_leader | pz_relative | 194075 | -0.0191328 | 0.111978 | 0.0610918 | 0.115069 | 14754 |
| strict | 2 | matched_final_leader | p_relative | 101993 | -0.0139622 | 0.0710316 | 0.0446719 | 0.0731351 | 1310 |
| strict | 2 | matched_final_leader | pz_relative | 101993 | -0.0139633 | 0.0710321 | 0.0446702 | 0.0731354 | 1310 |
| strict | 3 | matched_leader | p_relative | 192569 | -0.0192298 | 0.10956 | 0.0602364 | 0.112524 | 14192 |
| strict | 3 | matched_leader | pz_relative | 192569 | -0.0192328 | 0.109559 | 0.0602364 | 0.112531 | 14191 |
| strict | 3 | matched_final_leader | p_relative | 101985 | -0.0139922 | 0.0705238 | 0.0444941 | 0.0726821 | 1245 |
| strict | 3 | matched_final_leader | pz_relative | 101985 | -0.0139928 | 0.0705234 | 0.0444935 | 0.0726801 | 1245 |
| latest | 1 | matched_leader | p_relative | 193340 | -0.0189549 | 0.10966 | 0.0602206 | 0.11265 | 14179 |
| latest | 1 | matched_leader | pz_relative | 193340 | -0.018955 | 0.109659 | 0.0602224 | 0.11265 | 14179 |
| latest | 1 | matched_final_leader | p_relative | 103088 | -0.0139098 | 0.0702629 | 0.0443869 | 0.0723881 | 1242 |
| latest | 1 | matched_final_leader | pz_relative | 103088 | -0.0139104 | 0.0702602 | 0.0443865 | 0.0723886 | 1242 |
| latest | 2 | matched_leader | p_relative | 194075 | -0.0191345 | 0.111981 | 0.0610952 | 0.115071 | 14754 |
| latest | 2 | matched_leader | pz_relative | 194075 | -0.0191342 | 0.11198 | 0.0610968 | 0.115072 | 14755 |
| latest | 2 | matched_final_leader | p_relative | 103113 | -0.0139397 | 0.0709921 | 0.0446325 | 0.0730587 | 1326 |
| latest | 2 | matched_final_leader | pz_relative | 103113 | -0.0139394 | 0.0709921 | 0.0446321 | 0.0730635 | 1326 |
| latest | 3 | matched_leader | p_relative | 192569 | -0.0192298 | 0.109561 | 0.060237 | 0.112535 | 14194 |
| latest | 3 | matched_leader | pz_relative | 192569 | -0.0192328 | 0.109561 | 0.0602369 | 0.112538 | 14193 |
| latest | 3 | matched_final_leader | p_relative | 103105 | -0.0139762 | 0.0704833 | 0.0444731 | 0.0726225 | 1262 |
| latest | 3 | matched_final_leader | pz_relative | 103105 | -0.0139757 | 0.0704849 | 0.0444727 | 0.0726222 | 1262 |

## 三站同事件动量准确度（Merge）

| 基线 | 新版 | 站 | 量 | pairs | 基线更近 | 新版更近 | 相同 | 基线 MAD | 新版 MAD | sign p |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| old | latest | 1 | p_relative | 119205 | 46117 | 73088 | 0 | 0.0598625 | 0.0462906 | 0 |
| old | latest | 1 | pz_relative | 119205 | 46119 | 73086 | 0 | 0.0598639 | 0.0462909 | 0 |
| old | latest | 2 | p_relative | 119558 | 46328 | 73230 | 0 | 0.060514 | 0.0467058 | 0 |
| old | latest | 2 | pz_relative | 119558 | 46327 | 73230 | 1 | 0.0605129 | 0.0467076 | 0 |
| old | latest | 3 | p_relative | 119410 | 46254 | 73156 | 0 | 0.0601534 | 0.0464973 | 0 |
| old | latest | 3 | pz_relative | 119410 | 46255 | 73155 | 0 | 0.0601544 | 0.0464967 | 0 |
| strict | latest | 1 | p_relative | 120174 | 3 | 0 | 120171 | 0.0464575 | 0.0464588 | 0.25 |
| strict | latest | 1 | pz_relative | 120174 | 3 | 0 | 120171 | 0.0464563 | 0.0464573 | 0.25 |
| strict | latest | 2 | p_relative | 120518 | 3 | 0 | 120515 | 0.046901 | 0.046904 | 0.25 |
| strict | latest | 2 | pz_relative | 120518 | 3 | 0 | 120515 | 0.0469005 | 0.0469008 | 0.25 |
| strict | latest | 3 | p_relative | 120347 | 3 | 0 | 120344 | 0.0466467 | 0.0466468 | 0.25 |
| strict | latest | 3 | pz_relative | 120347 | 3 | 0 | 120344 | 0.0466436 | 0.046645 | 0.25 |

## 分动量区间的同事件准确度（Merge，truth-accepted，pz）

| 基线 | 新版 | 站 | 下限 GeV | 上限 GeV | pairs | 基线 MAD | 新版 MAD | 基线更近 | 新版更近 | 基线尾部 | 新版尾部 | sign p |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| old | latest | 1 | 0 | 100 | 0 | nan | nan | 0 | 0 | 0 | 0 | nan |
| old | latest | 1 | 100 | 300 | 30021 | 0.0286382 | 0.0253318 | 13102 | 16919 | 186 | 119 | 8.79374e-108 |
| old | latest | 1 | 300 | 1000 | 64708 | 0.0629417 | 0.048258 | 24885 | 39823 | 1831 | 407 | 0 |
| old | latest | 1 | 1000 | 3000 | 23217 | 0.190986 | 0.116782 | 7732 | 15485 | 4108 | 1086 | 0 |
| old | latest | 1 | 3000 | inf | 1259 | 0.485149 | 0.277954 | 400 | 859 | 615 | 295 | 5.83291e-39 |
| old | latest | 2 | 0 | 100 | 0 | nan | nan | 0 | 0 | 0 | 0 | nan |
| old | latest | 2 | 100 | 300 | 30098 | 0.0288477 | 0.0255005 | 13154 | 16944 | 215 | 137 | 5.11493e-106 |
| old | latest | 2 | 300 | 1000 | 64897 | 0.0635225 | 0.0485633 | 24995 | 39901 | 1994 | 538 | 0 |
| old | latest | 2 | 1000 | 3000 | 23296 | 0.192825 | 0.1179 | 7781 | 15515 | 4250 | 1181 | 0 |
| old | latest | 2 | 3000 | inf | 1267 | 0.486583 | 0.280249 | 397 | 870 | 625 | 299 | 4.55611e-41 |
| old | latest | 3 | 0 | 100 | 0 | nan | nan | 0 | 0 | 0 | 0 | nan |
| old | latest | 3 | 100 | 300 | 30057 | 0.0287076 | 0.0254399 | 13133 | 16924 | 198 | 138 | 3.24312e-106 |
| old | latest | 3 | 300 | 1000 | 64808 | 0.0631593 | 0.0483845 | 24961 | 39847 | 1921 | 473 | 0 |
| old | latest | 3 | 1000 | 3000 | 23278 | 0.192167 | 0.117282 | 7755 | 15523 | 4200 | 1140 | 0 |
| old | latest | 3 | 3000 | inf | 1267 | 0.485149 | 0.278237 | 406 | 861 | 620 | 297 | 4.68231e-38 |
| strict | latest | 1 | 0 | 100 | 0 | nan | nan | 0 | 0 | 0 | 0 | nan |
| strict | latest | 1 | 100 | 300 | 30170 | 0.025357 | 0.0253593 | 1 | 0 | 128 | 129 | 1 |
| strict | latest | 1 | 300 | 1000 | 65254 | 0.0483394 | 0.0483394 | 1 | 0 | 465 | 465 | 1 |
| strict | latest | 1 | 1000 | 3000 | 23461 | 0.117337 | 0.117337 | 1 | 0 | 1136 | 1136 | 1 |
| strict | latest | 1 | 3000 | inf | 1289 | 0.279123 | 0.279123 | 0 | 0 | 304 | 304 | nan |
| strict | latest | 2 | 0 | 100 | 0 | nan | nan | 0 | 0 | 0 | 0 | nan |
| strict | latest | 2 | 100 | 300 | 30253 | 0.0255557 | 0.0255573 | 1 | 0 | 158 | 158 | 1 |
| strict | latest | 2 | 300 | 1000 | 65425 | 0.0487019 | 0.0487019 | 1 | 0 | 612 | 612 | 1 |
| strict | latest | 2 | 1000 | 3000 | 23546 | 0.118606 | 0.118606 | 1 | 0 | 1243 | 1243 | 1 |
| strict | latest | 2 | 3000 | inf | 1294 | 0.282382 | 0.282382 | 0 | 0 | 310 | 310 | nan |
| strict | latest | 3 | 0 | 100 | 0 | nan | nan | 0 | 0 | 0 | 0 | nan |
| strict | latest | 3 | 100 | 300 | 30204 | 0.0254689 | 0.0254718 | 1 | 0 | 159 | 159 | 1 |
| strict | latest | 3 | 300 | 1000 | 65325 | 0.0484886 | 0.0484886 | 1 | 0 | 546 | 546 | 1 |
| strict | latest | 3 | 1000 | 3000 | 23525 | 0.117561 | 0.117568 | 1 | 0 | 1192 | 1193 | 1 |
| strict | latest | 3 | 3000 | inf | 1293 | 0.280041 | 0.280041 | 0 | 0 | 307 | 307 | nan |

## 三站动量 bin purity / stability / diagonal efficiency（Merge 最终样本）

| 版本 | 站 | 下限 GeV | 上限 GeV | truth 分母 | reco 分母 | bin purity % | stability % | 对角效率 % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| old | 1 | 100 | 150 | 7025 | 6680 | 82.9491 | 97.8629 | 76.2278 |
| old | 1 | 150 | 200 | 8310 | 7305 | 81.9439 | 87.9777 | 70.6739 |
| old | 1 | 200 | 300 | 18052 | 15287 | 84.3854 | 89.5212 | 70.6127 |
| old | 1 | 300 | 500 | 32117 | 25074 | 85.1918 | 87.2554 | 66.211 |
| old | 1 | 500 | 750 | 26897 | 19398 | 76.3842 | 75.8562 | 55.0247 |
| old | 1 | 750 | 1000 | 16723 | 11088 | 58.5859 | 55.7788 | 38.8268 |
| old | 1 | 1000 | 1500 | 16873 | 10231 | 59.2317 | 54.0396 | 35.8917 |
| old | 1 | 1500 | 2000 | 7333 | 3625 | 37.1034 | 29.1063 | 18.3417 |
| old | 1 | 2000 | 3000 | 5125 | 2821 | 36.051 | 31.831 | 19.8439 |
| old | 1 | 3000 | 5000 | 1591 | 1267 | 15.7853 | 21.1193 | 12.5707 |
| old | 1 | 5000 | 10000 | 86 | 600 | 1.66667 | 17.5439 | 11.6279 |
| old | 1 | 10000 | inf | 0 | 523 | 0 | nan | nan |
| old | 2 | 100 | 150 | 7025 | 6516 | 85.0522 | 97.8979 | 76.242 |
| old | 2 | 150 | 200 | 8310 | 7222 | 82.8441 | 87.9594 | 70.6619 |
| old | 2 | 200 | 300 | 18052 | 15172 | 84.9064 | 89.3838 | 70.5074 |
| old | 2 | 300 | 500 | 32117 | 25034 | 85.2521 | 87.1315 | 66.1488 |
| old | 2 | 500 | 750 | 26897 | 19376 | 76.2696 | 75.6837 | 54.8797 |
| old | 2 | 750 | 1000 | 16723 | 11076 | 58.4868 | 55.6004 | 38.7191 |
| old | 2 | 1000 | 1500 | 16873 | 10203 | 59.1885 | 53.8523 | 35.7731 |
| old | 2 | 1500 | 2000 | 7333 | 3602 | 37.035 | 28.862 | 18.1917 |
| old | 2 | 2000 | 3000 | 5125 | 2834 | 35.8151 | 31.7485 | 19.8049 |
| old | 2 | 3000 | 5000 | 1591 | 1285 | 15.9533 | 21.6017 | 12.885 |
| old | 2 | 5000 | 10000 | 86 | 615 | 1.62602 | 17.5439 | 11.6279 |
| old | 2 | 10000 | inf | 0 | 524 | 0 | nan | nan |
| old | 3 | 100 | 150 | 7025 | 6403 | 86.6469 | 97.8829 | 76.3132 |
| old | 3 | 150 | 200 | 8310 | 7171 | 83.503 | 88.0329 | 70.698 |
| old | 3 | 200 | 300 | 18052 | 15112 | 85.2898 | 89.4572 | 70.5517 |
| old | 3 | 300 | 500 | 32116 | 24998 | 85.4908 | 87.2571 | 66.2442 |
| old | 3 | 500 | 750 | 26898 | 19379 | 76.4333 | 75.8501 | 55.0078 |
| old | 3 | 750 | 1000 | 16723 | 11057 | 58.6597 | 55.6977 | 38.761 |
| old | 3 | 1000 | 1500 | 16873 | 10209 | 59.33 | 54.0273 | 35.8739 |
| old | 3 | 1500 | 2000 | 7333 | 3606 | 37.1326 | 28.9451 | 18.2599 |
| old | 3 | 2000 | 3000 | 5125 | 2832 | 35.8757 | 31.7599 | 19.8244 |
| old | 3 | 3000 | 5000 | 1591 | 1269 | 16.1545 | 21.6245 | 12.885 |
| old | 3 | 5000 | 10000 | 86 | 597 | 1.67504 | 17.5439 | 11.6279 |
| old | 3 | 10000 | inf | 0 | 526 | 0 | nan | nan |
| strict | 1 | 100 | 150 | 7025 | 6569 | 84.229 | 98.487 | 76.1423 |
| strict | 1 | 150 | 200 | 8310 | 7144 | 84.7004 | 89.8708 | 71.42 |
| strict | 1 | 200 | 300 | 18052 | 14852 | 88.1497 | 91.8093 | 71.6541 |
| strict | 1 | 300 | 500 | 32117 | 24467 | 89.8884 | 90.5957 | 68.182 |
| strict | 1 | 500 | 750 | 26897 | 19288 | 84.5344 | 83.908 | 60.5495 |
| strict | 1 | 750 | 1000 | 16723 | 11356 | 71.46 | 69.9147 | 48.508 |
| strict | 1 | 1000 | 1500 | 16873 | 10775 | 72.3155 | 69.6149 | 46.1566 |
| strict | 1 | 1500 | 2000 | 7333 | 4307 | 50.6617 | 47.2704 | 29.7286 |
| strict | 1 | 2000 | 3000 | 5125 | 3027 | 50.6772 | 48.0426 | 29.9317 |
| strict | 1 | 3000 | 5000 | 1591 | 1133 | 34.3336 | 40.3527 | 24.45 |
| strict | 1 | 5000 | 10000 | 86 | 329 | 4.86322 | 27.5862 | 18.6047 |
| strict | 1 | 10000 | inf | 0 | 106 | 0 | nan | nan |
| strict | 2 | 100 | 150 | 7025 | 6392 | 86.3423 | 98.3428 | 75.9431 |
| strict | 2 | 150 | 200 | 8310 | 7061 | 85.6111 | 89.795 | 71.3478 |
| strict | 2 | 200 | 300 | 18052 | 14745 | 88.6741 | 91.6836 | 71.5544 |
| strict | 2 | 300 | 500 | 32117 | 24424 | 89.9853 | 90.478 | 68.129 |
| strict | 2 | 500 | 750 | 26897 | 19245 | 84.5259 | 83.7167 | 60.4082 |
| strict | 2 | 750 | 1000 | 16723 | 11357 | 71.2336 | 69.6573 | 48.3585 |
| strict | 2 | 1000 | 1500 | 16873 | 10733 | 72.1793 | 69.2067 | 45.8958 |
| strict | 2 | 1500 | 2000 | 7333 | 4319 | 50.2663 | 46.9812 | 29.5786 |
| strict | 2 | 2000 | 3000 | 5125 | 3036 | 50.3294 | 47.8098 | 29.8146 |
| strict | 2 | 3000 | 5000 | 1591 | 1142 | 33.5377 | 39.6891 | 24.0729 |
| strict | 2 | 5000 | 10000 | 86 | 333 | 4.8048 | 27.5862 | 18.6047 |
| strict | 2 | 10000 | inf | 0 | 115 | 0 | nan | nan |
| strict | 3 | 100 | 150 | 7025 | 6284 | 88.0968 | 98.4353 | 76.1708 |
| strict | 3 | 150 | 200 | 8310 | 6988 | 86.5197 | 89.8232 | 71.3598 |
| strict | 3 | 200 | 300 | 18052 | 14693 | 89.0424 | 91.7654 | 71.6043 |
| strict | 3 | 300 | 500 | 32116 | 24375 | 90.24 | 90.567 | 68.1934 |
| strict | 3 | 500 | 750 | 26898 | 19225 | 84.7334 | 83.8437 | 60.4915 |
| strict | 3 | 750 | 1000 | 16723 | 11345 | 71.45 | 69.8552 | 48.4542 |
| strict | 3 | 1000 | 1500 | 16873 | 10754 | 72.3638 | 69.5256 | 46.0973 |
| strict | 3 | 1500 | 2000 | 7333 | 4308 | 50.5803 | 47.1339 | 29.6877 |
| strict | 3 | 2000 | 3000 | 5125 | 3031 | 50.5444 | 47.9049 | 29.8927 |
| strict | 3 | 3000 | 5000 | 1591 | 1136 | 34.0669 | 40.1869 | 24.3243 |
| strict | 3 | 5000 | 10000 | 86 | 327 | 4.58716 | 25.8621 | 17.4419 |
| strict | 3 | 10000 | inf | 0 | 107 | 0 | nan | nan |
| latest | 1 | 100 | 150 | 7025 | 6629 | 84.2661 | 98.4664 | 76.8683 |
| latest | 1 | 150 | 200 | 8310 | 7228 | 84.6292 | 89.8766 | 72.1901 |
| latest | 1 | 200 | 300 | 18052 | 15020 | 88.1691 | 91.8059 | 72.485 |
| latest | 1 | 300 | 500 | 32117 | 24733 | 89.9406 | 90.6036 | 68.9635 |
| latest | 1 | 500 | 750 | 26897 | 19489 | 84.5657 | 83.9283 | 61.2039 |
| latest | 1 | 750 | 1000 | 16723 | 11483 | 71.4622 | 69.9753 | 49.0522 |
| latest | 1 | 1000 | 1500 | 16873 | 10905 | 72.3796 | 69.64 | 46.7552 |
| latest | 1 | 1500 | 2000 | 7333 | 4357 | 50.6312 | 47.3289 | 30.0559 |
| latest | 1 | 2000 | 3000 | 5125 | 3055 | 50.7365 | 48.1068 | 30.2439 |
| latest | 1 | 3000 | 5000 | 1591 | 1140 | 34.386 | 40.2464 | 24.6386 |
| latest | 1 | 5000 | 10000 | 86 | 333 | 4.8048 | 27.1186 | 18.6047 |
| latest | 1 | 10000 | inf | 0 | 106 | 0 | nan | nan |
| latest | 2 | 100 | 150 | 7025 | 6452 | 86.3608 | 98.3236 | 76.669 |
| latest | 2 | 150 | 200 | 8310 | 7145 | 85.5283 | 89.8016 | 72.1179 |
| latest | 2 | 200 | 300 | 18052 | 14912 | 88.6937 | 91.6817 | 72.3853 |
| latest | 2 | 300 | 500 | 32117 | 24692 | 90.0332 | 90.4913 | 68.9137 |
| latest | 2 | 500 | 750 | 26897 | 19443 | 84.56 | 83.7331 | 61.0551 |
| latest | 2 | 750 | 1000 | 16723 | 11483 | 71.2532 | 69.7231 | 48.9087 |
| latest | 2 | 1000 | 1500 | 16873 | 10863 | 72.2452 | 69.2369 | 46.4944 |
| latest | 2 | 1500 | 2000 | 7333 | 4370 | 50.2288 | 47.0424 | 29.9059 |
| latest | 2 | 2000 | 3000 | 5125 | 3066 | 50.3588 | 47.876 | 30.1268 |
| latest | 2 | 3000 | 5000 | 1591 | 1149 | 33.5944 | 39.5897 | 24.2615 |
| latest | 2 | 5000 | 10000 | 86 | 336 | 4.7619 | 27.1186 | 18.6047 |
| latest | 2 | 10000 | inf | 0 | 115 | 0 | nan | nan |
| latest | 3 | 100 | 150 | 7025 | 6344 | 88.099 | 98.4152 | 76.8968 |
| latest | 3 | 150 | 200 | 8310 | 7073 | 86.4131 | 89.8295 | 72.13 |
| latest | 3 | 200 | 300 | 18052 | 14859 | 89.0571 | 91.7557 | 72.4296 |
| latest | 3 | 300 | 500 | 32116 | 24641 | 90.2885 | 90.5753 | 68.975 |
| latest | 3 | 500 | 750 | 26898 | 19426 | 84.7627 | 83.8647 | 61.1458 |
| latest | 3 | 750 | 1000 | 16723 | 11472 | 71.4609 | 69.9249 | 49.0044 |
| latest | 3 | 1000 | 1500 | 16873 | 10885 | 72.4208 | 69.5518 | 46.6959 |
| latest | 3 | 1500 | 2000 | 7333 | 4357 | 50.5394 | 47.1722 | 30.0014 |
| latest | 3 | 2000 | 3000 | 5125 | 3059 | 50.6048 | 47.9703 | 30.2049 |
| latest | 3 | 3000 | 5000 | 1591 | 1143 | 34.1207 | 40.0822 | 24.5129 |
| latest | 3 | 5000 | 10000 | 86 | 331 | 4.53172 | 25.4237 | 17.4419 |
| latest | 3 | 10000 | inf | 0 | 107 | 0 | nan | nan |

bin purity = 正确 primary 且 truth/reco 同 bin 的事件 / 该 reco bin 全部选中 leaders；stability 的分母是对应 truth bin 的正确匹配 selected leaders；对角效率分母是 truth-accepted 中该 truth bin 的事件。完整区间与 Wilson 误差见原始 TSV。

## duplicates：三种模式，全部 truth-accepted（purity≥0.7）

| 版本 | 方法 | 质量 | 事件分母 | 匹配 tracks | duplicate events | duplicate groups | 多余 tracks | duplicate % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| old | forward | long | 140132 | 112132 | 3 | 3 | 3 | 0.00214084 |
| old | forward | quality | 140132 | 109407 | 1 | 1 | 1 | 0.000713613 |
| old | backward | long | 140132 | 127570 | 6 | 6 | 6 | 0.00428168 |
| old | backward | quality | 140132 | 122549 | 1 | 1 | 1 | 0.000713613 |
| old | merge | long | 140132 | 128767 | 66 | 66 | 66 | 0.0470985 |
| old | merge | quality | 140132 | 124133 | 2 | 2 | 2 | 0.00142723 |
| strict | forward | long | 140132 | 109764 | 0 | 0 | 0 | 0 |
| strict | forward | quality | 140132 | 106756 | 0 | 0 | 0 | 0 |
| strict | backward | long | 140132 | 125412 | 1 | 1 | 1 | 0.000713613 |
| strict | backward | quality | 140132 | 121425 | 0 | 0 | 0 | 0 |
| strict | merge | long | 140132 | 130088 | 70 | 70 | 70 | 0.0499529 |
| strict | merge | quality | 140132 | 126335 | 0 | 0 | 0 | 0 |
| latest | forward | long | 140132 | 109761 | 0 | 0 | 0 | 0 |
| latest | forward | quality | 140132 | 106753 | 0 | 0 | 0 | 0 |
| latest | backward | long | 140132 | 125412 | 1 | 1 | 1 | 0.000713613 |
| latest | backward | quality | 140132 | 121425 | 0 | 0 | 0 | 0 |
| latest | merge | long | 140132 | 130088 | 70 | 70 | 70 | 0.0499529 |
| latest | merge | quality | 140132 | 126332 | 0 | 0 | 0 | 0 |

## primary duplicates：raw / long / quality

| 版本 | 质量 | 匹配事件 | 重复事件 | 多余 tracks | 条件重复率 % |
| --- | --- | --- | --- | --- | --- |
| old | raw | 125346 | 4136 | 4140 | 3.29967 |
| old | long | 121143 | 60 | 60 | 0.0495282 |
| old | quality | 117190 | 1 | 1 | 0.000853315 |
| strict | raw | 125374 | 7747 | 7747 | 6.17911 |
| strict | long | 120834 | 69 | 69 | 0.0571031 |
| strict | quality | 117619 | 0 | 0 | 0 |
| latest | raw | 125376 | 7747 | 7747 | 6.17901 |
| latest | long | 120834 | 69 | 69 | 0.0571031 |
| latest | quality | 117616 | 0 | 0 | 0 |

duplicate 指同一事件、同一 truth barcode 被至少两条满足 hit-purity 阈值的轨迹匹配；不是简单按轨迹数大于一计数。quality 要求 layers≥7、ndof≥9、有限 chi2 且 chi2/ndof<15，不等同于完整事例选择。完整 TSV 同时保留 purity 0.5 / 0.7 / 0.9。

## Forward / Backward / Merge 的效率

| 版本 | 方法 | 阶段 | 通过 | 分母 | 效率 % |
| --- | --- | --- | --- | --- | --- |
| old | forward | any_primary_quality | 105335 | 140132 | 75.1684 |
| old | forward | track_cuts | 103299 | 140132 | 73.7155 |
| old | forward | final | 91270 | 140132 | 65.1314 |
| old | forward | final_correct | 91163 | 140132 | 65.0551 |
| old | backward | any_primary_quality | 116148 | 140132 | 82.8847 |
| old | backward | track_cuts | 113912 | 140132 | 81.2891 |
| old | backward | final | 101356 | 140132 | 72.3289 |
| old | backward | final_correct | 101149 | 140132 | 72.1812 |
| old | merge | any_primary_quality | 117190 | 140132 | 83.6283 |
| old | merge | track_cuts | 114941 | 140132 | 82.0234 |
| old | merge | final | 102273 | 140132 | 72.9833 |
| old | merge | final_correct | 102066 | 140132 | 72.8356 |
| strict | forward | any_primary_quality | 102054 | 140132 | 72.827 |
| strict | forward | track_cuts | 100184 | 140132 | 71.4926 |
| strict | forward | final | 87566 | 140132 | 62.4882 |
| strict | forward | final_correct | 87450 | 140132 | 62.4054 |
| strict | backward | any_primary_quality | 113334 | 140132 | 80.8766 |
| strict | backward | track_cuts | 111246 | 140132 | 79.3866 |
| strict | backward | final | 98009 | 140132 | 69.9405 |
| strict | backward | final_correct | 97765 | 140132 | 69.7664 |
| strict | merge | any_primary_quality | 117619 | 140132 | 83.9344 |
| strict | merge | track_cuts | 115439 | 140132 | 82.3788 |
| strict | merge | final | 101692 | 140132 | 72.5687 |
| strict | merge | final_correct | 101461 | 140132 | 72.4039 |
| latest | forward | any_primary_quality | 102051 | 140132 | 72.8249 |
| latest | forward | track_cuts | 100181 | 140132 | 71.4905 |
| latest | forward | final | 88539 | 140132 | 63.1826 |
| latest | forward | final_correct | 88422 | 140132 | 63.0991 |
| latest | backward | any_primary_quality | 113334 | 140132 | 80.8766 |
| latest | backward | track_cuts | 111246 | 140132 | 79.3866 |
| latest | backward | final | 99084 | 140132 | 70.7076 |
| latest | backward | final_correct | 98840 | 140132 | 70.5335 |
| latest | merge | any_primary_quality | 117616 | 140132 | 83.9323 |
| latest | merge | track_cuts | 115436 | 140132 | 82.3766 |
| latest | merge | final | 102807 | 140132 | 73.3644 |
| latest | merge | final_correct | 102576 | 140132 | 73.1996 |

## 波形电荷逐值比较旧版

| 版本 | 通道 | 事件 | 逐值一致 | 非有限 | 有限负值 | 最大差 pC |
| --- | --- | --- | --- | --- | --- | --- |
| strict | Veto20 | 140132 | 19294 | 33 | 0 | 501977 |
| strict | Veto21 | 140132 | 19528 | 30 | 1 | 502282 |
| strict | Preshower0 | 140132 | 5266 | 308 | 333 | 4.91491e+07 |
| strict | Preshower1 | 140132 | 5688 | 330 | 342 | 228351 |
| strict | VetoNu0_reduced | 140132 | 139058 | 0 | 14929 | 195.708 |
| strict | VetoNu1_reduced | 140132 | 139063 | 0 | 14409 | 249.019 |
| strict | Timing0 | 140132 | 10867 | 4 | 50 | 221904 |
| strict | Timing1 | 140132 | 10844 | 5 | 48 | 213722 |
| strict | Timing2 | 140132 | 11441 | 6 | 48 | 231659 |
| strict | Timing3 | 140132 | 11490 | 4 | 42 | 254491 |
| latest | Veto20 | 140132 | 140132 | 0 | 0 | 0 |
| latest | Veto21 | 140132 | 140132 | 0 | 0 | 0 |
| latest | Preshower0 | 140132 | 140132 | 0 | 0 | 0 |
| latest | Preshower1 | 140132 | 140132 | 0 | 0 | 0 |
| latest | VetoNu0_reduced | 140132 | 140132 | 0 | 15054 | 0 |
| latest | VetoNu1_reduced | 140132 | 140132 | 0 | 14534 | 0 |
| latest | Timing0 | 140132 | 140132 | 0 | 20806 | 0 |
| latest | Timing1 | 140132 | 140132 | 0 | 20951 | 0 |
| latest | Timing2 | 140132 | 140132 | 0 | 18381 | 0 |
| latest | Timing3 | 140132 | 140132 | 0 | 18267 | 0 |

## 各 run 的 Merge 最终结果

| 版本 | run | 分母 | 通过 | 效率 % |
| --- | --- | --- | --- | --- |
| old | 200080 | 18707 | 14719 | 78.6818 |
| old | 200082 | 21502 | 17130 | 79.667 |
| old | 200083 | 35341 | 24340 | 68.8718 |
| old | 200089 | 4893 | 3216 | 65.7265 |
| old | 200093 | 20674 | 16358 | 79.1235 |
| old | 200094 | 34515 | 23481 | 68.0313 |
| old | 200100 | 4500 | 3029 | 67.3111 |
| strict | 200080 | 18707 | 14581 | 77.9441 |
| strict | 200082 | 21502 | 16972 | 78.9322 |
| strict | 200083 | 35341 | 24266 | 68.6625 |
| strict | 200089 | 4893 | 3208 | 65.563 |
| strict | 200093 | 20674 | 16200 | 78.3593 |
| strict | 200094 | 34515 | 23429 | 67.8806 |
| strict | 200100 | 4500 | 3036 | 67.4667 |
| latest | 200080 | 18707 | 14746 | 78.8261 |
| latest | 200082 | 21502 | 17162 | 79.8158 |
| latest | 200083 | 35341 | 24525 | 69.3953 |
| latest | 200089 | 4893 | 3244 | 66.2988 |
| latest | 200093 | 20674 | 16382 | 79.2396 |
| latest | 200094 | 34515 | 23682 | 68.6136 |
| latest | 200100 | 4500 | 3066 | 68.1333 |

## 保留全部有限极端值的 Merge 动量尾部审计

| 版本 | 站 | 选择 | pairs | 绝对相对误差中位数 | q95 | q99 | 算术均值 | 最大值 | |误差|>1000 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| old | 1 | truth_accepted | 120461 | 0.0601484 | 0.562637 | 2.29452 | 0.414975 | 5671.07 | 8 |
| old | 1 | final | 102602 | 0.0571577 | 0.503413 | 2.06184 | 0.362282 | 5671.07 | 4 |
| old | 2 | truth_accepted | 120821 | 0.0607962 | 0.583612 | 2.55972 | 0.640611 | 12298.2 | 10 |
| old | 2 | final | 102617 | 0.0574981 | 0.509083 | 2.10307 | 0.311236 | 1947.09 | 3 |
| old | 3 | truth_accepted | 120673 | 0.060409 | 0.576708 | 2.57708 | 57.7697 | 5.13104e+06 | 110 |
| old | 3 | final | 102616 | 0.0572138 | 0.504935 | 2.05076 | 0.317478 | 1947.57 | 4 |
| strict | 1 | truth_accepted | 120174 | 0.0464563 | 0.266364 | 0.678401 | 5.21683 | 603213 | 4 |
| strict | 1 | final | 101968 | 0.0444084 | 0.241936 | 0.550953 | 6.01254 | 603213 | 1 |
| strict | 2 | truth_accepted | 120518 | 0.0469005 | 0.279375 | 0.750656 | 4.84046 | 563976 | 3 |
| strict | 2 | final | 101993 | 0.0446702 | 0.246858 | 0.569807 | 5.64249 | 563976 | 1 |
| strict | 3 | truth_accepted | 120347 | 0.0466436 | 0.272189 | 0.726737 | 30.3266 | 1.89343e+06 | 37 |
| strict | 3 | final | 101985 | 0.0444935 | 0.242977 | 0.554473 | 5.8541 | 587072 | 1 |
| latest | 1 | truth_accepted | 120174 | 0.0464573 | 0.266379 | 0.678786 | 5.21684 | 603213 | 4 |
| latest | 1 | final | 103088 | 0.0443865 | 0.241936 | 0.550319 | 5.94801 | 603213 | 1 |
| latest | 2 | truth_accepted | 120518 | 0.0469008 | 0.279375 | 0.750656 | 4.84046 | 563976 | 3 |
| latest | 2 | final | 103113 | 0.0446321 | 0.246911 | 0.568706 | 5.58202 | 563976 | 1 |
| latest | 3 | truth_accepted | 120347 | 0.046645 | 0.272317 | 0.727209 | 30.3901 | 1.89343e+06 | 38 |
| latest | 3 | final | 103105 | 0.0444727 | 0.24293 | 0.554073 | 5.7913 | 587072 | 1 |

上述相对误差无量纲。中位数、q95/q99 与 >50% 的尾部均明显改善，但极少数巨大有限动量仍通过当前 cuts，足以恶化算术均值；不能声称所有误差指标都改善。未截断或删除这些事件，run/event 与拟合质量见 `extreme_momentum_events.tsv`。

## strict 与 latest 的少量非波形差异

全量有 9 个 fiducial 事件的 long track 或状态数组不同，合计 long tracks 差 -10；event scalar 差 147 个单元。因此 pilot 的非波形数组精确相同不能外推到全量。事件与逐轨内容见 `strict_changed_track_events.json`，标量见 `strict_changed_scalars.tsv`。

固定旧电荷后 strict / latest 的 accepted Merge final 为 102810 / 102807，丢失 3、新增 0。实际 final 为 101692 / 102807，净增加 1115；按固定电荷控制分解为恢复波形 +1118、少量轨迹差异 −3。尚未证实这 9 个事件的具体源码原因，不将静态 seed map 等候选问题写成已确认因果。

额外短片段重放（同一冻结源码及运行包，index 166、skip 2250、10 输入事件，2 个 fiducial，含 200083:652256）与 strict 全量的差异数组为 `scintillator`；与 latest 全量为 `event_cut_bits, event_individual_bits, event_scalars, raw_primary_counts, tracks, reco_station, reco_at_primary_station, matched_truth_station, nearest_state_dz_mm, station_method`。即该片段重放的非波形 science arrays 与 strict 精确一致。两个运行使用不同 worker，尚未区分事件历史、数值环境及未定义行为。不能将它直接归因为一个固定的 master 配置变更。完整证据见 `drift_replay_comparison.json`。

## 全作业资源实测（各 worker wall 相加）

| 版本 | 步骤 | 事件 | jobs | 累计 wall s | job 中位 wall s | 最大 RSS KiB | events/s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| latest | runtime_copy | 3374987 | 351 | 223.88 | 0.21 | 69376 | 15075 |
| latest | runtime_unpack | 3374987 | 351 | 732.54 | 2.12 | 6400 | 4607.24 |
| latest | input | 3374987 | 351 | 3791.05 | 4.12 | 83904 | 890.251 |
| latest | reco | 3374987 | 351 | 640059 | 1652.48 | 1367520 | 5.27293 |
| latest | forward | 3374987 | 351 | 126980 | 332.07 | 1118468 | 26.5789 |
| latest | backward | 3374987 | 351 | 127997 | 347.62 | 1076928 | 26.3677 |
| latest | merge | 3374987 | 351 | 174487 | 457.55 | 2251864 | 19.3424 |
| latest | extract | 3374987 | 351 | 24537.2 | 69.71 | 866036 | 137.546 |

## 验证与可追溯数据

共同 truth 检查：True；全量输入 ID 检查：True；分片 science arrays 回读恢复：True；全部 fiducial 波形与旧版逐值一致：True。

完整统计见本目录 TSV，逐事件迁移见 `truth_accepted_migration_events.tsv`，局部 truth-pass/reco-fail 见 `local_cut_migrations.tsv`，材料与四个 smoothing 的实际配置见 `effective_configuration.json`，源码 provenance 见 `runtime_source_provenance.json`。误差条、nominal / 分 run 及阈值变化保留在原表，稀疏高能 bin 不作过度外推。

表中 p=0 是浮点数值下溢，不能解读为真实概率严格为零。
