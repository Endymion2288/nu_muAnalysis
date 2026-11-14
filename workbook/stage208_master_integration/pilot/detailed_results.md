# 最新 master 几何旋转版：实测性能明细

源码 `7fd40df8cd3b60e81b4095a4f84310c4a54700a0`。局部验证样本：15,343 个输入事件，1,568 个 truth-fiducial，607 个 truth-station-accepted proxy。未经权重修正。

old 为 d32b0ff3；strict 为前阶段已验证的 strict 材料旋转版；latest 为合入官方 7f2d1681 master、保留旋转及 isolated smoothing 的本次版本。nominal 排除 alternate run 200080。

局部 truth 参考是 SiHit 方向乘 HepMC 产生点动量模长，不能作为精确 G4 局部动量。动量残差定义为 reco/reference−1；MAD 为相对残差绝对值的中位数；宽度为 (q84−q16)/2。所有相对误差以无量纲量给出，例如 0.1 表示 10%。

## 从完整共同输入开始的 Merge cutflow

| 版本 | cut | 通过 | 原始输入分母 |
| --- | --- | --- | --- |
| old | NoCuts | 15343 | 15343 |
| old | Remove CaloNu PMT region (truth) | 15343 | 15343 |
| old | CC events only | 11472 | 15343 |
| old | nu_mu only | 9151 | 15343 |
| old | In Faser Nu Box or Lead Block | 3702 | 15343 |
| old | Truth dec r < 100 mm | 1683 | 15343 |
| old | Truth pz > 100 GeV | 1568 | 15343 |
| old | At least one long track | 896 | 15343 |
| old | Veto20 and Veto21 charge > 40 pC | 896 | 15343 |
| old | Timing Station Charge > 20 pC | 896 | 15343 |
| old | Preshower Charge > 2.5 pC | 895 | 15343 |
| old | Track pz > 100 GeV | 797 | 15343 |
| old | Leading track has at >= 7 layers | 789 | 15343 |
| old | Track nDoF >= 9 | 766 | 15343 |
| old | Leading track has chi2/ndof < 15 | 766 | 15343 |
| old | Track R at max radius < 95 mm | 540 | 15343 |
| old | Track R at IFT < 95 mm | 532 | 15343 |
| old | Track rVetoNu < 120 mm | 531 | 15343 |
| old | Leading track theta < 25 mrad | 520 | 15343 |
| old | VetoNu0 reduced charge < 30 pC | 470 | 15343 |
| old | VetoNu1 reduced charge < 30 pC | 449 | 15343 |
| strict | NoCuts | 15343 | 15343 |
| strict | Remove CaloNu PMT region (truth) | 15343 | 15343 |
| strict | CC events only | 11472 | 15343 |
| strict | nu_mu only | 9151 | 15343 |
| strict | In Faser Nu Box or Lead Block | 3702 | 15343 |
| strict | Truth dec r < 100 mm | 1683 | 15343 |
| strict | Truth pz > 100 GeV | 1568 | 15343 |
| strict | At least one long track | 904 | 15343 |
| strict | Veto20 and Veto21 charge > 40 pC | 903 | 15343 |
| strict | Timing Station Charge > 20 pC | 903 | 15343 |
| strict | Preshower Charge > 2.5 pC | 891 | 15343 |
| strict | Track pz > 100 GeV | 769 | 15343 |
| strict | Leading track has at >= 7 layers | 764 | 15343 |
| strict | Track nDoF >= 9 | 750 | 15343 |
| strict | Leading track has chi2/ndof < 15 | 750 | 15343 |
| strict | Track R at max radius < 95 mm | 526 | 15343 |
| strict | Track R at IFT < 95 mm | 522 | 15343 |
| strict | Track rVetoNu < 120 mm | 521 | 15343 |
| strict | Leading track theta < 25 mrad | 510 | 15343 |
| strict | VetoNu0 reduced charge < 30 pC | 460 | 15343 |
| strict | VetoNu1 reduced charge < 30 pC | 439 | 15343 |
| latest | NoCuts | 15343 | 15343 |
| latest | Remove CaloNu PMT region (truth) | 15343 | 15343 |
| latest | CC events only | 11472 | 15343 |
| latest | nu_mu only | 9151 | 15343 |
| latest | In Faser Nu Box or Lead Block | 3702 | 15343 |
| latest | Truth dec r < 100 mm | 1683 | 15343 |
| latest | Truth pz > 100 GeV | 1568 | 15343 |
| latest | At least one long track | 904 | 15343 |
| latest | Veto20 and Veto21 charge > 40 pC | 904 | 15343 |
| latest | Timing Station Charge > 20 pC | 904 | 15343 |
| latest | Preshower Charge > 2.5 pC | 904 | 15343 |
| latest | Track pz > 100 GeV | 781 | 15343 |
| latest | Leading track has at >= 7 layers | 776 | 15343 |
| latest | Track nDoF >= 9 | 761 | 15343 |
| latest | Leading track has chi2/ndof < 15 | 761 | 15343 |
| latest | Track R at max radius < 95 mm | 537 | 15343 |
| latest | Track R at IFT < 95 mm | 532 | 15343 |
| latest | Track rVetoNu < 120 mm | 531 | 15343 |
| latest | Leading track theta < 25 mrad | 520 | 15343 |
| latest | VetoNu0 reduced charge < 30 pC | 470 | 15343 |
| latest | VetoNu1 reduced charge < 30 pC | 449 | 15343 |

首六项仅依赖共同 RDO truth，使用本次计数作为所有版本共享的 truth 前缀；重建选择部分分别从对应版本累计 cut bits 精确计算，latest 另与 worker 完整 cutflow 闭合。这不是对旧版重新读取全部 RDO 的计数。

## Merge 接受度及正确 primary 效率

| 版本 | 样本 | 阶段 | 分母 | 通过 | 未通过 | 效率 % | 68% 下限 % | 68% 上限 % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| old | all | any_primary_raw | 607 | 545 | 62 | 89.7858 | 88.4905 | 90.9503 |
| old | all | any_primary_long | 607 | 527 | 80 | 86.8204 | 85.3867 | 88.1331 |
| old | all | any_primary_quality | 607 | 517 | 90 | 85.173 | 83.6728 | 86.5575 |
| old | all | correct_leader | 607 | 527 | 80 | 86.8204 | 85.3867 | 88.1331 |
| old | all | track_cuts | 607 | 508 | 99 | 83.6903 | 82.1355 | 85.1342 |
| old | all | track_cuts_correct | 607 | 508 | 99 | 83.6903 | 82.1355 | 85.1342 |
| old | all | final | 607 | 437 | 170 | 71.9934 | 70.1358 | 73.7787 |
| old | all | final_correct | 607 | 437 | 170 | 71.9934 | 70.1358 | 73.7787 |
| old | all | final_fixed_old_scintillator | 607 | 437 | 170 | 71.9934 | 70.1358 | 73.7787 |
| old | nominal | any_primary_raw | 492 | 432 | 60 | 87.8049 | 86.2524 | 89.204 |
| old | nominal | any_primary_long | 492 | 415 | 77 | 84.3496 | 82.6421 | 85.9178 |
| old | nominal | any_primary_quality | 492 | 406 | 86 | 82.5203 | 80.7426 | 84.1661 |
| old | nominal | correct_leader | 492 | 415 | 77 | 84.3496 | 82.6421 | 85.9178 |
| old | nominal | track_cuts | 492 | 398 | 94 | 80.8943 | 79.0599 | 82.6033 |
| old | nominal | track_cuts_correct | 492 | 398 | 94 | 80.8943 | 79.0599 | 82.6033 |
| old | nominal | final | 492 | 336 | 156 | 68.2927 | 66.1595 | 70.3517 |
| old | nominal | final_correct | 492 | 336 | 156 | 68.2927 | 66.1595 | 70.3517 |
| old | nominal | final_fixed_old_scintillator | 492 | 336 | 156 | 68.2927 | 66.1595 | 70.3517 |
| strict | all | any_primary_raw | 607 | 544 | 63 | 89.6211 | 88.3173 | 90.7945 |
| strict | all | any_primary_long | 607 | 523 | 84 | 86.1614 | 84.7003 | 87.5036 |
| strict | all | any_primary_quality | 607 | 512 | 95 | 84.3493 | 82.8182 | 85.7674 |
| strict | all | correct_leader | 607 | 523 | 84 | 86.1614 | 84.7003 | 87.5036 |
| strict | all | track_cuts | 607 | 506 | 101 | 83.3608 | 81.7945 | 84.8173 |
| strict | all | track_cuts_correct | 607 | 505 | 102 | 83.196 | 81.6241 | 84.6588 |
| strict | all | final | 607 | 425 | 182 | 70.0165 | 68.1251 | 71.842 |
| strict | all | final_correct | 607 | 424 | 183 | 69.8517 | 67.9577 | 71.6805 |
| strict | all | final_fixed_old_scintillator | 607 | 435 | 172 | 71.6639 | 69.8004 | 73.4562 |
| strict | nominal | any_primary_raw | 492 | 431 | 61 | 87.6016 | 86.0391 | 89.0116 |
| strict | nominal | any_primary_long | 492 | 411 | 81 | 83.5366 | 81.797 | 85.1402 |
| strict | nominal | any_primary_quality | 492 | 401 | 91 | 81.5041 | 79.6903 | 83.19 |
| strict | nominal | correct_leader | 492 | 411 | 81 | 83.5366 | 81.797 | 85.1402 |
| strict | nominal | track_cuts | 492 | 396 | 96 | 80.4878 | 78.6401 | 82.2119 |
| strict | nominal | track_cuts_correct | 492 | 395 | 97 | 80.2846 | 78.4302 | 82.016 |
| strict | nominal | final | 492 | 328 | 164 | 66.6667 | 64.5095 | 68.7562 |
| strict | nominal | final_correct | 492 | 327 | 165 | 66.4634 | 64.3034 | 68.5566 |
| strict | nominal | final_fixed_old_scintillator | 492 | 334 | 158 | 67.8862 | 65.7467 | 69.9531 |
| latest | all | any_primary_raw | 607 | 544 | 63 | 89.6211 | 88.3173 | 90.7945 |
| latest | all | any_primary_long | 607 | 523 | 84 | 86.1614 | 84.7003 | 87.5036 |
| latest | all | any_primary_quality | 607 | 512 | 95 | 84.3493 | 82.8182 | 85.7674 |
| latest | all | correct_leader | 607 | 523 | 84 | 86.1614 | 84.7003 | 87.5036 |
| latest | all | track_cuts | 607 | 506 | 101 | 83.3608 | 81.7945 | 84.8173 |
| latest | all | track_cuts_correct | 607 | 505 | 102 | 83.196 | 81.6241 | 84.6588 |
| latest | all | final | 607 | 435 | 172 | 71.6639 | 69.8004 | 73.4562 |
| latest | all | final_correct | 607 | 434 | 173 | 71.4992 | 69.6327 | 73.2949 |
| latest | all | final_fixed_old_scintillator | 607 | 435 | 172 | 71.6639 | 69.8004 | 73.4562 |
| latest | nominal | any_primary_raw | 492 | 431 | 61 | 87.6016 | 86.0391 | 89.0116 |
| latest | nominal | any_primary_long | 492 | 411 | 81 | 83.5366 | 81.797 | 85.1402 |
| latest | nominal | any_primary_quality | 492 | 401 | 91 | 81.5041 | 79.6903 | 83.19 |
| latest | nominal | correct_leader | 492 | 411 | 81 | 83.5366 | 81.797 | 85.1402 |
| latest | nominal | track_cuts | 492 | 396 | 96 | 80.4878 | 78.6401 | 82.2119 |
| latest | nominal | track_cuts_correct | 492 | 395 | 97 | 80.2846 | 78.4302 | 82.016 |
| latest | nominal | final | 492 | 334 | 158 | 67.8862 | 65.7467 | 69.9531 |
| latest | nominal | final_correct | 492 | 333 | 159 | 67.6829 | 65.5404 | 69.7537 |
| latest | nominal | final_fixed_old_scintillator | 492 | 334 | 158 | 67.8862 | 65.7467 | 69.9531 |

## Merge 同事件通过 / 丢失 / 新增

| 基线 | 新版 | 样本 | 阶段 | 基线通过 | 新版通过 | 丢失 | 新增 | 差值 pp | 95% 下限 pp | 95% 上限 pp | McNemar p |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| old | latest | all | track_pass | 508 | 506 | 6 | 4 | -0.329489 | -1.35025 | 0.691272 | 0.753906 |
| old | latest | all | final | 437 | 435 | 6 | 4 | -0.329489 | -1.35025 | 0.691272 | 0.753906 |
| old | latest | all | fixed_final | 437 | 435 | 6 | 4 | -0.329489 | -1.35025 | 0.691272 | 0.753906 |
| old | latest | all | final_correct | 437 | 434 | 7 | 4 | -0.494234 | -1.56445 | 0.575981 | 0.548828 |
| old | latest | all | fixed_correct | 437 | 434 | 7 | 4 | -0.494234 | -1.56445 | 0.575981 | 0.548828 |
| old | latest | nominal | track_pass | 398 | 396 | 6 | 4 | -0.406504 | -1.66576 | 0.852753 | 0.753906 |
| old | latest | nominal | final | 336 | 334 | 6 | 4 | -0.406504 | -1.66576 | 0.852753 | 0.753906 |
| old | latest | nominal | fixed_final | 336 | 334 | 6 | 4 | -0.406504 | -1.66576 | 0.852753 | 0.753906 |
| old | latest | nominal | final_correct | 336 | 333 | 7 | 4 | -0.609756 | -1.92991 | 0.710402 | 0.548828 |
| old | latest | nominal | fixed_correct | 336 | 333 | 7 | 4 | -0.609756 | -1.92991 | 0.710402 | 0.548828 |
| strict | latest | all | track_pass | 506 | 506 | 0 | 0 | 0 | 0 | 0 | 1 |
| strict | latest | all | final | 425 | 435 | 0 | 10 | 1.64745 | 0.634795 | 2.6601 | 0.00195312 |
| strict | latest | all | fixed_final | 435 | 435 | 0 | 0 | 0 | 0 | 0 | 1 |
| strict | latest | all | final_correct | 424 | 434 | 0 | 10 | 1.64745 | 0.634795 | 2.6601 | 0.00195312 |
| strict | latest | all | fixed_correct | 434 | 434 | 0 | 0 | 0 | 0 | 0 | 1 |
| strict | latest | nominal | track_pass | 396 | 396 | 0 | 0 | 0 | 0 | 0 | 1 |
| strict | latest | nominal | final | 328 | 334 | 0 | 6 | 1.21951 | 0.249668 | 2.18936 | 0.03125 |
| strict | latest | nominal | fixed_final | 334 | 334 | 0 | 0 | 0 | 0 | 0 | 1 |
| strict | latest | nominal | final_correct | 327 | 333 | 0 | 6 | 1.21951 | 0.249668 | 2.18936 | 0.03125 |
| strict | latest | nominal | fixed_correct | 333 | 333 | 0 | 0 | 0 | 0 | 0 | 1 |

## truth 可通过但 Merge 未通过的完整分类

| 版本 | 类别 | 事件 | truth 分母 |
| --- | --- | --- | --- |
| old | correct_leader_track_cut_failure | 19 | 607 |
| old | no_high_purity_primary_raw | 62 | 607 |
| old | primary_raw_only | 18 | 607 |
| old | scintillator_failure_after_track_cuts | 71 | 607 |
| old | selected_correct | 437 | 607 |
| strict | correct_leader_track_cut_failure | 18 | 607 |
| strict | no_high_purity_primary_raw | 63 | 607 |
| strict | primary_raw_only | 20 | 607 |
| strict | scintillator_failure_after_track_cuts | 81 | 607 |
| strict | selected_correct | 424 | 607 |
| strict | selected_wrong_or_low_purity | 1 | 607 |
| latest | correct_leader_track_cut_failure | 18 | 607 |
| latest | no_high_purity_primary_raw | 63 | 607 |
| latest | primary_raw_only | 20 | 607 |
| latest | scintillator_failure_after_track_cuts | 71 | 607 |
| latest | selected_correct | 434 | 607 |
| latest | selected_wrong_or_low_purity | 1 | 607 |

## Merge 首个失败 cut（truth-accepted）

| 版本 | 首个失败 cut | 事件 | truth 分母 |
| --- | --- | --- | --- |
| old | At least one long track | 78 | 607 |
| old | Veto20 and Veto21 charge > 40 pC | 0 | 607 |
| old | Timing Station Charge > 20 pC | 0 | 607 |
| old | Preshower Charge > 2.5 pC | 0 | 607 |
| old | Track pz > 100 GeV | 4 | 607 |
| old | Leading track has at >= 7 layers | 2 | 607 |
| old | Track nDoF >= 9 | 8 | 607 |
| old | Leading track has chi2/ndof < 15 | 0 | 607 |
| old | Track R at max radius < 95 mm | 0 | 607 |
| old | Track R at IFT < 95 mm | 7 | 607 |
| old | Track rVetoNu < 120 mm | 0 | 607 |
| old | Leading track theta < 25 mrad | 0 | 607 |
| old | VetoNu0 reduced charge < 30 pC | 50 | 607 |
| old | VetoNu1 reduced charge < 30 pC | 21 | 607 |
| strict | At least one long track | 76 | 607 |
| strict | Veto20 and Veto21 charge > 40 pC | 1 | 607 |
| strict | Timing Station Charge > 20 pC | 0 | 607 |
| strict | Preshower Charge > 2.5 pC | 11 | 607 |
| strict | Track pz > 100 GeV | 9 | 607 |
| strict | Leading track has at >= 7 layers | 2 | 607 |
| strict | Track nDoF >= 9 | 8 | 607 |
| strict | Leading track has chi2/ndof < 15 | 0 | 607 |
| strict | Track R at max radius < 95 mm | 0 | 607 |
| strict | Track R at IFT < 95 mm | 4 | 607 |
| strict | Track rVetoNu < 120 mm | 0 | 607 |
| strict | Leading track theta < 25 mrad | 0 | 607 |
| strict | VetoNu0 reduced charge < 30 pC | 50 | 607 |
| strict | VetoNu1 reduced charge < 30 pC | 21 | 607 |
| latest | At least one long track | 76 | 607 |
| latest | Veto20 and Veto21 charge > 40 pC | 0 | 607 |
| latest | Timing Station Charge > 20 pC | 0 | 607 |
| latest | Preshower Charge > 2.5 pC | 0 | 607 |
| latest | Track pz > 100 GeV | 9 | 607 |
| latest | Leading track has at >= 7 layers | 2 | 607 |
| latest | Track nDoF >= 9 | 9 | 607 |
| latest | Leading track has chi2/ndof < 15 | 0 | 607 |
| latest | Track R at max radius < 95 mm | 0 | 607 |
| latest | Track R at IFT < 95 mm | 5 | 607 |
| latest | Track rVetoNu < 120 mm | 0 | 607 |
| latest | Leading track theta < 25 mrad | 0 | 607 |
| latest | VetoNu0 reduced charge < 30 pC | 50 | 607 |
| latest | VetoNu1 reduced charge < 30 pC | 21 | 607 |

## Merge 正确 primary 纯度

| 版本 | 选择 | leaders | 正确 primary | 纯度 % | 68% 下限 % | 68% 上限 % |
| --- | --- | --- | --- | --- | --- | --- |
| old | all_leaders | 896 | 827 | 92.2991 | 91.3605 | 93.1434 |
| old | track_cuts | 520 | 511 | 98.2692 | 97.5978 | 98.7554 |
| old | final | 449 | 440 | 97.9955 | 97.2196 | 98.5581 |
| strict | all_leaders | 904 | 815 | 90.1549 | 89.1192 | 91.1018 |
| strict | track_cuts | 520 | 507 | 97.5 | 96.7188 | 98.0989 |
| strict | final | 439 | 426 | 97.0387 | 96.1166 | 97.747 |
| latest | all_leaders | 904 | 815 | 90.1549 | 89.1192 | 91.1018 |
| latest | track_cuts | 520 | 507 | 97.5 | 96.7188 | 98.0989 |
| latest | final | 449 | 436 | 97.1047 | 96.2027 | 97.7973 |

## Merge 数值异常与电荷符号错误

| 版本 | 选择 | leaders | 非有限 chi2 | ndof≤0 | 非有限 pz | 正确 primary pairs | 符号错误 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| old | leaders | 896 | 0 | 2 | 0 | 827 | 15 |
| old | track_cuts | 520 | 0 | 0 | 0 | 511 | 3 |
| old | final | 449 | 0 | 0 | 0 | 440 | 2 |
| strict | leaders | 904 | 0 | 1 | 0 | 815 | 11 |
| strict | track_cuts | 520 | 0 | 0 | 0 | 507 | 0 |
| strict | final | 439 | 0 | 0 | 0 | 426 | 0 |
| latest | leaders | 904 | 0 | 1 | 0 | 815 | 11 |
| latest | track_cuts | 520 | 0 | 0 | 0 | 507 | 0 |
| latest | final | 449 | 0 | 0 | 0 | 436 | 0 |

## Merge 最终粒子组成

| 版本 | 粒子类别 | 事件 | 最终事件 |
| --- | --- | --- | --- |
| old | hadron | 9 | 449 |
| old | primary_muon_high_purity | 440 | 449 |
| strict | hadron | 12 | 439 |
| strict | other_muon | 1 | 439 |
| strict | primary_muon_high_purity | 426 | 439 |
| latest | hadron | 12 | 449 |
| latest | other_muon | 1 | 449 |
| latest | primary_muon_high_purity | 436 | 449 |

## 三站动量响应（Merge，正确 primary leader）

| 版本 | 站 | 选择 | 量 | pairs | 偏差中位数 | 68% 半宽 | MAD | 绝对误差 q68 | |误差|>50% |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| old | 1 | matched_leader | p_relative | 822 | -0.0162342 | 0.163684 | 0.0869892 | 0.165217 | 99 |
| old | 1 | matched_leader | pz_relative | 822 | -0.0162299 | 0.163684 | 0.086989 | 0.165217 | 99 |
| old | 1 | matched_final_leader | p_relative | 440 | -0.00457733 | 0.104804 | 0.0609242 | 0.108477 | 22 |
| old | 1 | matched_final_leader | pz_relative | 440 | -0.00457622 | 0.104803 | 0.0609246 | 0.108477 | 22 |
| old | 2 | matched_leader | p_relative | 827 | -0.0159282 | 0.164453 | 0.0862277 | 0.16405 | 102 |
| old | 2 | matched_leader | pz_relative | 827 | -0.0159272 | 0.164409 | 0.0862269 | 0.164051 | 102 |
| old | 2 | matched_final_leader | p_relative | 440 | -0.0046864 | 0.104634 | 0.0603444 | 0.108464 | 23 |
| old | 2 | matched_final_leader | pz_relative | 440 | -0.00468569 | 0.104634 | 0.0603441 | 0.108464 | 23 |
| old | 3 | matched_leader | p_relative | 812 | -0.0151542 | 0.160338 | 0.0859241 | 0.162536 | 98 |
| old | 3 | matched_leader | pz_relative | 812 | -0.0151554 | 0.160337 | 0.0859246 | 0.162552 | 98 |
| old | 3 | matched_final_leader | p_relative | 435 | -0.00448879 | 0.103381 | 0.0601724 | 0.107787 | 23 |
| old | 3 | matched_final_leader | pz_relative | 435 | -0.00448721 | 0.103379 | 0.0601715 | 0.107787 | 23 |
| strict | 1 | matched_leader | p_relative | 814 | -0.0181037 | 0.124316 | 0.0672211 | 0.128041 | 68 |
| strict | 1 | matched_leader | pz_relative | 814 | -0.0181047 | 0.124317 | 0.0672221 | 0.128041 | 68 |
| strict | 1 | matched_final_leader | p_relative | 426 | -0.00695345 | 0.0805477 | 0.0512274 | 0.0815058 | 4 |
| strict | 1 | matched_final_leader | pz_relative | 426 | -0.00695497 | 0.0805485 | 0.0512258 | 0.0815061 | 4 |
| strict | 2 | matched_leader | p_relative | 812 | -0.0183926 | 0.124835 | 0.0677291 | 0.128947 | 68 |
| strict | 2 | matched_leader | pz_relative | 812 | -0.0183944 | 0.12483 | 0.0677228 | 0.128948 | 68 |
| strict | 2 | matched_final_leader | p_relative | 425 | -0.00732354 | 0.0803037 | 0.0518591 | 0.0815531 | 4 |
| strict | 2 | matched_final_leader | pz_relative | 425 | -0.00732316 | 0.0803035 | 0.0518598 | 0.0815531 | 4 |
| strict | 3 | matched_leader | p_relative | 800 | -0.0181933 | 0.12015 | 0.0659128 | 0.126189 | 63 |
| strict | 3 | matched_leader | pz_relative | 800 | -0.0181938 | 0.120149 | 0.0659097 | 0.12619 | 63 |
| strict | 3 | matched_final_leader | p_relative | 421 | -0.00775346 | 0.0800257 | 0.0501851 | 0.0811527 | 4 |
| strict | 3 | matched_final_leader | pz_relative | 421 | -0.00775361 | 0.0800258 | 0.050183 | 0.0811526 | 4 |
| latest | 1 | matched_leader | p_relative | 814 | -0.0181037 | 0.124316 | 0.0672211 | 0.128041 | 68 |
| latest | 1 | matched_leader | pz_relative | 814 | -0.0181047 | 0.124317 | 0.0672221 | 0.128041 | 68 |
| latest | 1 | matched_final_leader | p_relative | 436 | -0.00649289 | 0.0814594 | 0.05159 | 0.0823904 | 5 |
| latest | 1 | matched_final_leader | pz_relative | 436 | -0.00649426 | 0.0814619 | 0.05159 | 0.0823842 | 5 |
| latest | 2 | matched_leader | p_relative | 812 | -0.0183926 | 0.124835 | 0.0677291 | 0.128947 | 68 |
| latest | 2 | matched_leader | pz_relative | 812 | -0.0183944 | 0.12483 | 0.0677228 | 0.128948 | 68 |
| latest | 2 | matched_final_leader | p_relative | 435 | -0.00678786 | 0.0817325 | 0.0518591 | 0.0826441 | 5 |
| latest | 2 | matched_final_leader | pz_relative | 435 | -0.00679098 | 0.081734 | 0.0518598 | 0.0826376 | 5 |
| latest | 3 | matched_leader | p_relative | 800 | -0.0181933 | 0.12015 | 0.0659128 | 0.126189 | 63 |
| latest | 3 | matched_leader | pz_relative | 800 | -0.0181938 | 0.120149 | 0.0659097 | 0.12619 | 63 |
| latest | 3 | matched_final_leader | p_relative | 431 | -0.00712951 | 0.0811363 | 0.0511274 | 0.082009 | 5 |
| latest | 3 | matched_final_leader | pz_relative | 431 | -0.00712932 | 0.0811376 | 0.0511251 | 0.0820057 | 5 |

## 三站同事件动量准确度（Merge）

| 基线 | 新版 | 站 | 量 | pairs | 基线更近 | 新版更近 | 相同 | 基线 MAD | 新版 MAD | sign p |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| old | latest | 1 | p_relative | 522 | 208 | 314 | 0 | 0.0639751 | 0.0523946 | 4.01301e-06 |
| old | latest | 1 | pz_relative | 522 | 208 | 314 | 0 | 0.0639764 | 0.0523952 | 4.01301e-06 |
| old | latest | 2 | p_relative | 521 | 209 | 312 | 0 | 0.063762 | 0.0524289 | 7.37905e-06 |
| old | latest | 2 | pz_relative | 521 | 209 | 312 | 0 | 0.0637597 | 0.0524309 | 7.37905e-06 |
| old | latest | 3 | p_relative | 516 | 205 | 311 | 0 | 0.0631129 | 0.0522165 | 3.52132e-06 |
| old | latest | 3 | pz_relative | 516 | 205 | 311 | 0 | 0.0631132 | 0.0522165 | 3.52132e-06 |
| strict | latest | 1 | p_relative | 523 | 0 | 0 | 523 | 0.0523671 | 0.0523671 | nan |
| strict | latest | 1 | pz_relative | 523 | 0 | 0 | 523 | 0.0523662 | 0.0523662 | nan |
| strict | latest | 2 | p_relative | 522 | 0 | 0 | 522 | 0.0524889 | 0.0524889 | nan |
| strict | latest | 2 | pz_relative | 522 | 0 | 0 | 522 | 0.0524902 | 0.0524902 | nan |
| strict | latest | 3 | p_relative | 517 | 0 | 0 | 517 | 0.0520897 | 0.0520897 | nan |
| strict | latest | 3 | pz_relative | 517 | 0 | 0 | 517 | 0.0520903 | 0.0520903 | nan |

## 分动量区间的同事件准确度（Merge，truth-accepted，pz）

| 基线 | 新版 | 站 | 下限 GeV | 上限 GeV | pairs | 基线 MAD | 新版 MAD | 基线更近 | 新版更近 | 基线尾部 | 新版尾部 | sign p |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| old | latest | 1 | 0 | 100 | 0 | nan | nan | 0 | 0 | 0 | 0 | nan |
| old | latest | 1 | 100 | 300 | 108 | 0.0256737 | 0.0233017 | 46 | 62 | 0 | 0 | 0.148576 |
| old | latest | 1 | 300 | 1000 | 297 | 0.0687967 | 0.054962 | 119 | 178 | 10 | 2 | 0.000737115 |
| old | latest | 1 | 1000 | 3000 | 111 | 0.189076 | 0.133497 | 41 | 70 | 17 | 6 | 0.00758481 |
| old | latest | 1 | 3000 | inf | 6 | 0.374703 | 0.324233 | 2 | 4 | 3 | 1 | 0.6875 |
| old | latest | 2 | 0 | 100 | 0 | nan | nan | 0 | 0 | 0 | 0 | nan |
| old | latest | 2 | 100 | 300 | 107 | 0.0252895 | 0.022996 | 48 | 59 | 0 | 0 | 0.333705 |
| old | latest | 2 | 300 | 1000 | 297 | 0.0686243 | 0.0572267 | 119 | 178 | 10 | 2 | 0.000737115 |
| old | latest | 2 | 1000 | 3000 | 111 | 0.189075 | 0.133496 | 40 | 71 | 18 | 6 | 0.00419553 |
| old | latest | 2 | 3000 | inf | 6 | 0.374703 | 0.324234 | 2 | 4 | 3 | 1 | 0.6875 |
| old | latest | 3 | 0 | 100 | 0 | nan | nan | 0 | 0 | 0 | 0 | nan |
| old | latest | 3 | 100 | 300 | 108 | 0.0254027 | 0.0233406 | 48 | 60 | 0 | 0 | 0.289798 |
| old | latest | 3 | 300 | 1000 | 292 | 0.0685923 | 0.0551333 | 114 | 178 | 9 | 1 | 0.000215368 |
| old | latest | 3 | 1000 | 3000 | 110 | 0.185026 | 0.130419 | 41 | 69 | 18 | 6 | 0.00972219 |
| old | latest | 3 | 3000 | inf | 6 | 0.374703 | 0.324234 | 2 | 4 | 3 | 1 | 0.6875 |
| strict | latest | 1 | 0 | 100 | 0 | nan | nan | 0 | 0 | 0 | 0 | nan |
| strict | latest | 1 | 100 | 300 | 108 | 0.0233017 | 0.0233017 | 0 | 0 | 0 | 0 | nan |
| strict | latest | 1 | 300 | 1000 | 298 | 0.0549393 | 0.0549393 | 0 | 0 | 2 | 2 | nan |
| strict | latest | 1 | 1000 | 3000 | 111 | 0.133497 | 0.133497 | 0 | 0 | 6 | 6 | nan |
| strict | latest | 1 | 3000 | inf | 6 | 0.324233 | 0.324233 | 0 | 0 | 1 | 1 | nan |
| strict | latest | 2 | 0 | 100 | 0 | nan | nan | 0 | 0 | 0 | 0 | nan |
| strict | latest | 2 | 100 | 300 | 107 | 0.022996 | 0.022996 | 0 | 0 | 0 | 0 | nan |
| strict | latest | 2 | 300 | 1000 | 298 | 0.0574321 | 0.0574321 | 0 | 0 | 2 | 2 | nan |
| strict | latest | 2 | 1000 | 3000 | 111 | 0.133496 | 0.133496 | 0 | 0 | 6 | 6 | nan |
| strict | latest | 2 | 3000 | inf | 6 | 0.324234 | 0.324234 | 0 | 0 | 1 | 1 | nan |
| strict | latest | 3 | 0 | 100 | 0 | nan | nan | 0 | 0 | 0 | 0 | nan |
| strict | latest | 3 | 100 | 300 | 108 | 0.0233406 | 0.0233406 | 0 | 0 | 0 | 0 | nan |
| strict | latest | 3 | 300 | 1000 | 293 | 0.0549587 | 0.0549587 | 0 | 0 | 1 | 1 | nan |
| strict | latest | 3 | 1000 | 3000 | 110 | 0.130419 | 0.130419 | 0 | 0 | 6 | 6 | nan |
| strict | latest | 3 | 3000 | inf | 6 | 0.324234 | 0.324234 | 0 | 0 | 1 | 1 | nan |

## 三站动量 bin purity / stability / diagonal efficiency（Merge 最终样本）

| 版本 | 站 | 下限 GeV | 上限 GeV | truth 分母 | reco 分母 | bin purity % | stability % | 对角效率 % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| old | 1 | 100 | 150 | 20 | 18 | 83.3333 | 93.75 | 75 |
| old | 1 | 150 | 200 | 25 | 23 | 78.2609 | 94.7368 | 68 |
| old | 1 | 200 | 300 | 70 | 57 | 91.2281 | 88.1356 | 74.2857 |
| old | 1 | 300 | 500 | 126 | 114 | 78.9474 | 92.7835 | 70.6349 |
| old | 1 | 500 | 750 | 137 | 94 | 80.8511 | 76.7677 | 55.4745 |
| old | 1 | 750 | 1000 | 81 | 48 | 58.3333 | 50.9091 | 34.5679 |
| old | 1 | 1000 | 1500 | 78 | 47 | 55.3191 | 50.9804 | 33.3333 |
| old | 1 | 1500 | 2000 | 43 | 17 | 58.8235 | 35.7143 | 23.2558 |
| old | 1 | 2000 | 3000 | 21 | 16 | 50 | 72.7273 | 38.0952 |
| old | 1 | 3000 | 5000 | 5 | 10 | 10 | 25 | 20 |
| old | 1 | 5000 | 10000 | 1 | 2 | 0 | 0 | 0 |
| old | 1 | 10000 | inf | 0 | 0 | nan | nan | nan |
| old | 2 | 100 | 150 | 20 | 17 | 94.1176 | 100 | 80 |
| old | 2 | 150 | 200 | 25 | 23 | 78.2609 | 94.7368 | 68 |
| old | 2 | 200 | 300 | 70 | 56 | 92.8571 | 88.1356 | 74.2857 |
| old | 2 | 300 | 500 | 126 | 113 | 79.646 | 92.7835 | 70.6349 |
| old | 2 | 500 | 750 | 137 | 96 | 80.2083 | 77.7778 | 56.2044 |
| old | 2 | 750 | 1000 | 81 | 49 | 57.1429 | 50.9091 | 34.5679 |
| old | 2 | 1000 | 1500 | 78 | 42 | 57.1429 | 47.0588 | 30.7692 |
| old | 2 | 1500 | 2000 | 43 | 17 | 58.8235 | 35.7143 | 23.2558 |
| old | 2 | 2000 | 3000 | 21 | 16 | 50 | 72.7273 | 38.0952 |
| old | 2 | 3000 | 5000 | 5 | 10 | 10 | 25 | 20 |
| old | 2 | 5000 | 10000 | 1 | 3 | 0 | 0 | 0 |
| old | 2 | 10000 | inf | 0 | 0 | nan | nan | nan |
| old | 3 | 100 | 150 | 20 | 17 | 94.1176 | 100 | 80 |
| old | 3 | 150 | 200 | 25 | 22 | 81.8182 | 94.7368 | 68 |
| old | 3 | 200 | 300 | 70 | 58 | 91.3793 | 89.8305 | 75.7143 |
| old | 3 | 300 | 500 | 126 | 108 | 82.4074 | 92.7083 | 69.8413 |
| old | 3 | 500 | 750 | 137 | 94 | 80.8511 | 79.1667 | 55.4745 |
| old | 3 | 750 | 1000 | 81 | 48 | 58.3333 | 50.9091 | 34.5679 |
| old | 3 | 1000 | 1500 | 78 | 42 | 54.7619 | 46 | 29.4872 |
| old | 3 | 1500 | 2000 | 43 | 17 | 58.8235 | 35.7143 | 23.2558 |
| old | 3 | 2000 | 3000 | 21 | 16 | 50 | 72.7273 | 38.0952 |
| old | 3 | 3000 | 5000 | 5 | 10 | 10 | 25 | 20 |
| old | 3 | 5000 | 10000 | 1 | 3 | 0 | 0 | 0 |
| old | 3 | 10000 | inf | 0 | 0 | nan | nan | nan |
| strict | 1 | 100 | 150 | 20 | 18 | 83.3333 | 100 | 75 |
| strict | 1 | 150 | 200 | 25 | 20 | 90 | 100 | 68 |
| strict | 1 | 200 | 300 | 70 | 56 | 94.6429 | 91.3793 | 75.7143 |
| strict | 1 | 300 | 500 | 126 | 101 | 88.1188 | 94.6809 | 69.8413 |
| strict | 1 | 500 | 750 | 137 | 96 | 86.4583 | 86.4583 | 60.5839 |
| strict | 1 | 750 | 1000 | 81 | 51 | 70.5882 | 67.9245 | 44.4444 |
| strict | 1 | 1000 | 1500 | 78 | 47 | 70.2128 | 68.75 | 42.3077 |
| strict | 1 | 1500 | 2000 | 43 | 22 | 59.0909 | 46.4286 | 30.2326 |
| strict | 1 | 2000 | 3000 | 21 | 17 | 35.2941 | 50 | 28.5714 |
| strict | 1 | 3000 | 5000 | 5 | 7 | 14.2857 | 33.3333 | 20 |
| strict | 1 | 5000 | 10000 | 1 | 0 | nan | 0 | 0 |
| strict | 1 | 10000 | inf | 0 | 0 | nan | nan | nan |
| strict | 2 | 100 | 150 | 20 | 16 | 93.75 | 100 | 75 |
| strict | 2 | 150 | 200 | 25 | 20 | 90 | 100 | 68 |
| strict | 2 | 200 | 300 | 70 | 54 | 96.2963 | 91.2281 | 74.2857 |
| strict | 2 | 300 | 500 | 126 | 101 | 88.1188 | 94.6809 | 69.8413 |
| strict | 2 | 500 | 750 | 137 | 97 | 85.567 | 86.4583 | 60.5839 |
| strict | 2 | 750 | 1000 | 81 | 49 | 71.4286 | 66.0377 | 43.2099 |
| strict | 2 | 1000 | 1500 | 78 | 46 | 71.7391 | 68.75 | 42.3077 |
| strict | 2 | 1500 | 2000 | 43 | 22 | 59.0909 | 46.4286 | 30.2326 |
| strict | 2 | 2000 | 3000 | 21 | 17 | 35.2941 | 50 | 28.5714 |
| strict | 2 | 3000 | 5000 | 5 | 7 | 14.2857 | 33.3333 | 20 |
| strict | 2 | 5000 | 10000 | 1 | 0 | nan | 0 | 0 |
| strict | 2 | 10000 | inf | 0 | 0 | nan | nan | nan |
| strict | 3 | 100 | 150 | 20 | 16 | 93.75 | 100 | 75 |
| strict | 3 | 150 | 200 | 25 | 20 | 90 | 100 | 68 |
| strict | 3 | 200 | 300 | 70 | 55 | 96.3636 | 91.3793 | 75.7143 |
| strict | 3 | 300 | 500 | 126 | 98 | 89.7959 | 94.6237 | 69.0476 |
| strict | 3 | 500 | 750 | 137 | 94 | 86.1702 | 87.0968 | 59.1241 |
| strict | 3 | 750 | 1000 | 81 | 49 | 73.4694 | 67.9245 | 44.4444 |
| strict | 3 | 1000 | 1500 | 78 | 45 | 71.1111 | 68.0851 | 41.0256 |
| strict | 3 | 1500 | 2000 | 43 | 22 | 59.0909 | 46.4286 | 30.2326 |
| strict | 3 | 2000 | 3000 | 21 | 17 | 35.2941 | 50 | 28.5714 |
| strict | 3 | 3000 | 5000 | 5 | 7 | 14.2857 | 33.3333 | 20 |
| strict | 3 | 5000 | 10000 | 1 | 0 | nan | 0 | 0 |
| strict | 3 | 10000 | inf | 0 | 0 | nan | nan | nan |
| latest | 1 | 100 | 150 | 20 | 19 | 84.2105 | 100 | 80 |
| latest | 1 | 150 | 200 | 25 | 21 | 90.4762 | 100 | 72 |
| latest | 1 | 200 | 300 | 70 | 57 | 94.7368 | 91.5254 | 77.1429 |
| latest | 1 | 300 | 500 | 126 | 102 | 88.2353 | 94.7368 | 70.6349 |
| latest | 1 | 500 | 750 | 137 | 98 | 86.7347 | 85.8586 | 62.0438 |
| latest | 1 | 750 | 1000 | 81 | 52 | 69.2308 | 67.9245 | 44.4444 |
| latest | 1 | 1000 | 1500 | 78 | 48 | 70.8333 | 68 | 43.5897 |
| latest | 1 | 1500 | 2000 | 43 | 23 | 56.5217 | 46.4286 | 30.2326 |
| latest | 1 | 2000 | 3000 | 21 | 17 | 35.2941 | 50 | 28.5714 |
| latest | 1 | 3000 | 5000 | 5 | 7 | 14.2857 | 25 | 20 |
| latest | 1 | 5000 | 10000 | 1 | 1 | 0 | 0 | 0 |
| latest | 1 | 10000 | inf | 0 | 0 | nan | nan | nan |
| latest | 2 | 100 | 150 | 20 | 17 | 94.1176 | 100 | 80 |
| latest | 2 | 150 | 200 | 25 | 21 | 90.4762 | 100 | 72 |
| latest | 2 | 200 | 300 | 70 | 55 | 96.3636 | 91.3793 | 75.7143 |
| latest | 2 | 300 | 500 | 126 | 102 | 88.2353 | 94.7368 | 70.6349 |
| latest | 2 | 500 | 750 | 137 | 99 | 85.8586 | 85.8586 | 62.0438 |
| latest | 2 | 750 | 1000 | 81 | 50 | 70 | 66.0377 | 43.2099 |
| latest | 2 | 1000 | 1500 | 78 | 47 | 72.3404 | 68 | 43.5897 |
| latest | 2 | 1500 | 2000 | 43 | 23 | 56.5217 | 46.4286 | 30.2326 |
| latest | 2 | 2000 | 3000 | 21 | 17 | 35.2941 | 50 | 28.5714 |
| latest | 2 | 3000 | 5000 | 5 | 7 | 14.2857 | 25 | 20 |
| latest | 2 | 5000 | 10000 | 1 | 1 | 0 | 0 | 0 |
| latest | 2 | 10000 | inf | 0 | 0 | nan | nan | nan |
| latest | 3 | 100 | 150 | 20 | 17 | 94.1176 | 100 | 80 |
| latest | 3 | 150 | 200 | 25 | 21 | 90.4762 | 100 | 72 |
| latest | 3 | 200 | 300 | 70 | 56 | 96.4286 | 91.5254 | 77.1429 |
| latest | 3 | 300 | 500 | 126 | 99 | 89.899 | 94.6809 | 69.8413 |
| latest | 3 | 500 | 750 | 137 | 96 | 86.4583 | 86.4583 | 60.5839 |
| latest | 3 | 750 | 1000 | 81 | 50 | 72 | 67.9245 | 44.4444 |
| latest | 3 | 1000 | 1500 | 78 | 46 | 71.7391 | 67.3469 | 42.3077 |
| latest | 3 | 1500 | 2000 | 43 | 23 | 56.5217 | 46.4286 | 30.2326 |
| latest | 3 | 2000 | 3000 | 21 | 17 | 35.2941 | 50 | 28.5714 |
| latest | 3 | 3000 | 5000 | 5 | 7 | 14.2857 | 25 | 20 |
| latest | 3 | 5000 | 10000 | 1 | 1 | 0 | 0 | 0 |
| latest | 3 | 10000 | inf | 0 | 0 | nan | nan | nan |

bin purity = 正确 primary 且 truth/reco 同 bin 的事件 / 该 reco bin 全部选中 leaders；stability 的分母是对应 truth bin 的正确匹配 selected leaders；对角效率分母是 truth-accepted 中该 truth bin 的事件。完整区间与 Wilson 误差见原始 TSV。

## duplicates：三种模式，全部 truth-accepted（purity≥0.7）

| 版本 | 方法 | 质量 | 事件分母 | 匹配 tracks | duplicate events | duplicate groups | 多余 tracks | duplicate % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| old | forward | long | 607 | 489 | 0 | 0 | 0 | 0 |
| old | forward | quality | 607 | 480 | 0 | 0 | 0 | 0 |
| old | backward | long | 607 | 556 | 0 | 0 | 0 | 0 |
| old | backward | quality | 607 | 541 | 0 | 0 | 0 | 0 |
| old | merge | long | 607 | 561 | 0 | 0 | 0 | 0 |
| old | merge | quality | 607 | 550 | 0 | 0 | 0 | 0 |
| strict | forward | long | 607 | 482 | 0 | 0 | 0 | 0 |
| strict | forward | quality | 607 | 470 | 0 | 0 | 0 | 0 |
| strict | backward | long | 607 | 544 | 0 | 0 | 0 | 0 |
| strict | backward | quality | 607 | 530 | 0 | 0 | 0 | 0 |
| strict | merge | long | 607 | 565 | 0 | 0 | 0 | 0 |
| strict | merge | quality | 607 | 554 | 0 | 0 | 0 | 0 |
| latest | forward | long | 607 | 482 | 0 | 0 | 0 | 0 |
| latest | forward | quality | 607 | 470 | 0 | 0 | 0 | 0 |
| latest | backward | long | 607 | 544 | 0 | 0 | 0 | 0 |
| latest | backward | quality | 607 | 530 | 0 | 0 | 0 | 0 |
| latest | merge | long | 607 | 565 | 0 | 0 | 0 | 0 |
| latest | merge | quality | 607 | 554 | 0 | 0 | 0 | 0 |

## primary duplicates：raw / long / quality

| 版本 | 质量 | 匹配事件 | 重复事件 | 多余 tracks | 条件重复率 % |
| --- | --- | --- | --- | --- | --- |
| old | raw | 545 | 19 | 19 | 3.48624 |
| old | long | 527 | 0 | 0 | 0 |
| old | quality | 517 | 0 | 0 | 0 |
| strict | raw | 544 | 36 | 36 | 6.61765 |
| strict | long | 523 | 0 | 0 | 0 |
| strict | quality | 512 | 0 | 0 | 0 |
| latest | raw | 544 | 36 | 36 | 6.61765 |
| latest | long | 523 | 0 | 0 | 0 |
| latest | quality | 512 | 0 | 0 | 0 |

## Forward / Backward / Merge 的效率

| 版本 | 方法 | 阶段 | 通过 | 分母 | 效率 % |
| --- | --- | --- | --- | --- | --- |
| old | forward | any_primary_quality | 460 | 607 | 75.7825 |
| old | forward | track_cuts | 453 | 607 | 74.6293 |
| old | forward | final | 384 | 607 | 63.2619 |
| old | forward | final_correct | 384 | 607 | 63.2619 |
| old | backward | any_primary_quality | 509 | 607 | 83.855 |
| old | backward | track_cuts | 500 | 607 | 82.3723 |
| old | backward | final | 430 | 607 | 70.8402 |
| old | backward | final_correct | 430 | 607 | 70.8402 |
| old | merge | any_primary_quality | 517 | 607 | 85.173 |
| old | merge | track_cuts | 508 | 607 | 83.6903 |
| old | merge | final | 437 | 607 | 71.9934 |
| old | merge | final_correct | 437 | 607 | 71.9934 |
| strict | forward | any_primary_quality | 447 | 607 | 73.6409 |
| strict | forward | track_cuts | 441 | 607 | 72.6524 |
| strict | forward | final | 363 | 607 | 59.8023 |
| strict | forward | final_correct | 363 | 607 | 59.8023 |
| strict | backward | any_primary_quality | 491 | 607 | 80.8896 |
| strict | backward | track_cuts | 485 | 607 | 79.9012 |
| strict | backward | final | 409 | 607 | 67.3806 |
| strict | backward | final_correct | 408 | 607 | 67.2158 |
| strict | merge | any_primary_quality | 512 | 607 | 84.3493 |
| strict | merge | track_cuts | 506 | 607 | 83.3608 |
| strict | merge | final | 425 | 607 | 70.0165 |
| strict | merge | final_correct | 424 | 607 | 69.8517 |
| latest | forward | any_primary_quality | 447 | 607 | 73.6409 |
| latest | forward | track_cuts | 441 | 607 | 72.6524 |
| latest | forward | final | 373 | 607 | 61.4498 |
| latest | forward | final_correct | 373 | 607 | 61.4498 |
| latest | backward | any_primary_quality | 491 | 607 | 80.8896 |
| latest | backward | track_cuts | 485 | 607 | 79.9012 |
| latest | backward | final | 418 | 607 | 68.8633 |
| latest | backward | final_correct | 417 | 607 | 68.6985 |
| latest | merge | any_primary_quality | 512 | 607 | 84.3493 |
| latest | merge | track_cuts | 506 | 607 | 83.3608 |
| latest | merge | final | 435 | 607 | 71.6639 |
| latest | merge | final_correct | 434 | 607 | 71.4992 |

## 波形电荷逐值比较旧版

| 版本 | 通道 | 事件 | 逐值一致 | 非有限 | 有限负值 | 最大差 pC |
| --- | --- | --- | --- | --- | --- | --- |
| strict | Veto20 | 607 | 84 | 1 | 0 | 453140 |
| strict | Veto21 | 607 | 88 | 0 | 0 | 377720 |
| strict | Preshower0 | 607 | 18 | 3 | 3 | 5.01926 |
| strict | Preshower1 | 607 | 26 | 4 | 1 | 7.67059 |
| strict | VetoNu0_reduced | 607 | 602 | 0 | 70 | 3.12761 |
| strict | VetoNu1_reduced | 607 | 602 | 0 | 63 | 8.08051 |
| strict | Timing0 | 607 | 49 | 0 | 0 | 184.842 |
| strict | Timing1 | 607 | 54 | 0 | 0 | 1947.94 |
| strict | Timing2 | 607 | 51 | 0 | 0 | 15228.9 |
| strict | Timing3 | 607 | 53 | 0 | 0 | 16321 |
| latest | Veto20 | 607 | 607 | 0 | 0 | 0 |
| latest | Veto21 | 607 | 607 | 0 | 0 | 0 |
| latest | Preshower0 | 607 | 607 | 0 | 0 | 0 |
| latest | Preshower1 | 607 | 607 | 0 | 0 | 0 |
| latest | VetoNu0_reduced | 607 | 607 | 0 | 70 | 0 |
| latest | VetoNu1_reduced | 607 | 607 | 0 | 63 | 0 |
| latest | Timing0 | 607 | 607 | 0 | 71 | 0 |
| latest | Timing1 | 607 | 607 | 0 | 79 | 0 |
| latest | Timing2 | 607 | 607 | 0 | 76 | 0 |
| latest | Timing3 | 607 | 607 | 0 | 91 | 0 |

## 各 run 的 Merge 最终结果

| 版本 | run | 分母 | 通过 | 效率 % |
| --- | --- | --- | --- | --- |
| old | 200080 | 115 | 101 | 87.8261 |
| old | 200082 | 96 | 72 | 75 |
| old | 200083 | 104 | 64 | 61.5385 |
| old | 200089 | 65 | 41 | 63.0769 |
| old | 200094 | 221 | 154 | 69.6833 |
| old | 200100 | 6 | 5 | 83.3333 |
| strict | 200080 | 115 | 97 | 84.3478 |
| strict | 200082 | 96 | 68 | 70.8333 |
| strict | 200083 | 104 | 61 | 58.6538 |
| strict | 200089 | 65 | 41 | 63.0769 |
| strict | 200094 | 221 | 153 | 69.2308 |
| strict | 200100 | 6 | 5 | 83.3333 |
| latest | 200080 | 115 | 101 | 87.8261 |
| latest | 200082 | 96 | 69 | 71.875 |
| latest | 200083 | 104 | 63 | 60.5769 |
| latest | 200089 | 65 | 41 | 63.0769 |
| latest | 200094 | 221 | 156 | 70.5882 |
| latest | 200100 | 6 | 5 | 83.3333 |

## 全作业资源实测（各 worker wall 相加）

| 版本 | 步骤 | 事件 | jobs | 累计 wall s | job 中位 wall s | 最大 RSS KiB | events/s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| latest | runtime_copy | 15343 | 7 | 2.58 | 0.29 | 62064 | 5946.9 |
| latest | runtime_unpack | 15343 | 7 | 14.64 | 2.1 | 6144 | 1048.02 |
| latest | input | 15343 | 7 | 26.19 | 4.09 | 82896 | 585.834 |
| latest | old_runtime_copy | 15343 | 7 | 1.91 | 0.46 | 61012 | 8032.98 |
| latest | old_runtime_unpack | 15343 | 7 | 8.36 | 2.09 | 6144 | 1835.29 |
| latest | reco | 15343 | 7 | 3565.88 | 571.9 | 1245192 | 4.30272 |
| latest | forward | 15343 | 7 | 725.34 | 117.17 | 977440 | 21.1528 |
| latest | backward | 15343 | 7 | 748.79 | 118.01 | 973668 | 20.4904 |
| latest | merge | 15343 | 7 | 1542.39 | 237.62 | 2045804 | 9.94755 |
| latest | extract | 15343 | 7 | 260.96 | 36.99 | 760592 | 58.7945 |

## 同节点、交替顺序的旧版重放与计时

| index | 版本 | 顺序 | worker | 步骤 | 事件 | wall s | user s | RSS KiB |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | old | old_first | b9g23p3673.cern.ch | reco | 2500 | 300.73 | 290.1 | 1051356 |
| 0 | old | old_first | b9g23p3673.cern.ch | forward | 2500 | 79.61 | 74.4 | 904764 |
| 0 | old | old_first | b9g23p3673.cern.ch | backward | 2500 | 74.32 | 69.13 | 911976 |
| 0 | old | old_first | b9g23p3673.cern.ch | merge | 2500 | 164.14 | 143.71 | 1959816 |
| 0 | old | old_first | b9g23p3673.cern.ch | extract | 2500 | 50.32 | 45.95 | 756680 |
| 0 | latest | old_first | b9g23p3673.cern.ch | reco | 2500 | 293.15 | 285.29 | 1050900 |
| 0 | latest | old_first | b9g23p3673.cern.ch | forward | 2500 | 79.74 | 74.13 | 909224 |
| 0 | latest | old_first | b9g23p3673.cern.ch | backward | 2500 | 76.09 | 71.35 | 913676 |
| 0 | latest | old_first | b9g23p3673.cern.ch | merge | 2500 | 184.99 | 169.08 | 2045804 |
| 0 | latest | old_first | b9g23p3673.cern.ch | extract | 2500 | 44.7 | 41.19 | 760592 |
| 63 | old | latest_first | b9p20p5952.cern.ch | reco | 2500 | 258.74 | 249.88 | 1018520 |
| 63 | old | latest_first | b9p20p5952.cern.ch | forward | 2500 | 56.77 | 51.51 | 912880 |
| 63 | old | latest_first | b9p20p5952.cern.ch | backward | 2500 | 59.63 | 54.27 | 909684 |
| 63 | old | latest_first | b9p20p5952.cern.ch | merge | 2500 | 146.9 | 131.11 | 1974984 |
| 63 | old | latest_first | b9p20p5952.cern.ch | extract | 2500 | 31.23 | 27.71 | 760988 |
| 63 | latest | latest_first | b9p20p5952.cern.ch | reco | 2500 | 288.19 | 275.53 | 1033440 |
| 63 | latest | latest_first | b9p20p5952.cern.ch | forward | 2500 | 65.47 | 59.49 | 907456 |
| 63 | latest | latest_first | b9p20p5952.cern.ch | backward | 2500 | 71.6 | 65.85 | 901280 |
| 63 | latest | latest_first | b9p20p5952.cern.ch | merge | 2500 | 162.77 | 130.98 | 2038172 |
| 63 | latest | latest_first | b9p20p5952.cern.ch | extract | 2500 | 35.89 | 31.59 | 751556 |
| 125 | old | latest_first | b9p16p7014.cern.ch | reco | 2500 | 642.56 | 626.35 | 1146836 |
| 125 | old | latest_first | b9p16p7014.cern.ch | forward | 2500 | 141.58 | 134.56 | 976080 |
| 125 | old | latest_first | b9p16p7014.cern.ch | backward | 2500 | 143.73 | 136.32 | 987140 |
| 125 | old | latest_first | b9p16p7014.cern.ch | merge | 2500 | 246.4 | 221.29 | 1947116 |
| 125 | old | latest_first | b9p16p7014.cern.ch | extract | 2500 | 38.62 | 34.4 | 750364 |
| 125 | latest | latest_first | b9p16p7014.cern.ch | reco | 2500 | 659.7 | 639.89 | 1039608 |
| 125 | latest | latest_first | b9p16p7014.cern.ch | forward | 2500 | 149.74 | 140.05 | 977440 |
| 125 | latest | latest_first | b9p16p7014.cern.ch | backward | 2500 | 142.35 | 135.92 | 955744 |
| 125 | latest | latest_first | b9p16p7014.cern.ch | merge | 2500 | 306.07 | 211.92 | 1948340 |
| 125 | latest | latest_first | b9p16p7014.cern.ch | extract | 2500 | 36.99 | 31.96 | 749436 |
| 186 | old | old_first | b9p13p4324.cern.ch | reco | 2500 | 944.82 | 922.91 | 1145056 |
| 186 | old | old_first | b9p13p4324.cern.ch | forward | 2500 | 168.92 | 160.26 | 976772 |
| 186 | old | old_first | b9p13p4324.cern.ch | backward | 2500 | 157.79 | 151.42 | 986180 |
| 186 | old | old_first | b9p13p4324.cern.ch | merge | 2500 | 281.15 | 250.54 | 1998056 |
| 186 | old | old_first | b9p13p4324.cern.ch | extract | 2500 | 35.95 | 31.35 | 757012 |
| 186 | latest | old_first | b9p13p4324.cern.ch | reco | 2500 | 983.67 | 967.16 | 1167508 |
| 186 | latest | old_first | b9p13p4324.cern.ch | forward | 2500 | 162.99 | 156.39 | 976668 |
| 186 | latest | old_first | b9p13p4324.cern.ch | backward | 2500 | 171.88 | 165.51 | 973668 |
| 186 | latest | old_first | b9p13p4324.cern.ch | merge | 2500 | 280.07 | 260.67 | 1993264 |
| 186 | latest | old_first | b9p13p4324.cern.ch | extract | 2500 | 37.08 | 32.93 | 752900 |
| 251 | old | latest_first | b9p16p6284.cern.ch | reco | 2500 | 565.85 | 555.25 | 1219116 |
| 251 | old | latest_first | b9p16p6284.cern.ch | forward | 2500 | 124.12 | 117.65 | 963720 |
| 251 | old | latest_first | b9p16p6284.cern.ch | backward | 2500 | 132.72 | 127.08 | 968048 |
| 251 | old | latest_first | b9p16p6284.cern.ch | merge | 2500 | 224.52 | 206.97 | 1967724 |
| 251 | old | latest_first | b9p16p6284.cern.ch | extract | 2500 | 34.78 | 31.47 | 752552 |
| 251 | latest | latest_first | b9p16p6284.cern.ch | reco | 2500 | 571.9 | 558.19 | 1245192 |
| 251 | latest | latest_first | b9p16p6284.cern.ch | forward | 2500 | 117.17 | 110.93 | 966236 |
| 251 | latest | latest_first | b9p16p6284.cern.ch | backward | 2500 | 118.01 | 112.58 | 972188 |
| 251 | latest | latest_first | b9p16p6284.cern.ch | merge | 2500 | 250.97 | 214.82 | 1941832 |
| 251 | latest | latest_first | b9p16p6284.cern.ch | extract | 2500 | 35.72 | 31.34 | 749888 |
| 300 | old | old_first | b9p14p7506.cern.ch | reco | 2500 | 613.36 | 594.29 | 1195588 |
| 300 | old | old_first | b9p14p7506.cern.ch | forward | 2500 | 132.78 | 125.8 | 966492 |
| 300 | old | old_first | b9p14p7506.cern.ch | backward | 2500 | 140.5 | 133.69 | 960372 |
| 300 | old | old_first | b9p14p7506.cern.ch | merge | 2500 | 250.49 | 215.28 | 2059640 |
| 300 | old | old_first | b9p14p7506.cern.ch | extract | 2500 | 42.56 | 36.98 | 752292 |
| 300 | latest | old_first | b9p14p7506.cern.ch | reco | 2500 | 626.15 | 610.47 | 1214376 |
| 300 | latest | old_first | b9p14p7506.cern.ch | forward | 2500 | 120.08 | 113.76 | 965128 |
| 300 | latest | old_first | b9p14p7506.cern.ch | backward | 2500 | 134.76 | 128.67 | 965808 |
| 300 | latest | old_first | b9p14p7506.cern.ch | merge | 2500 | 237.62 | 218.04 | 1935184 |
| 300 | latest | old_first | b9p14p7506.cern.ch | extract | 2500 | 38.16 | 34.3 | 759220 |
| 342 | old | old_first | b9p18p1806.cern.ch | reco | 343 | 129.18 | 116.14 | 1097932 |
| 342 | old | old_first | b9p18p1806.cern.ch | forward | 343 | 29.86 | 24.49 | 898660 |
| 342 | old | old_first | b9p18p1806.cern.ch | backward | 343 | 33.7 | 29.03 | 939156 |
| 342 | old | old_first | b9p18p1806.cern.ch | merge | 343 | 195.12 | 91.56 | 1964280 |
| 342 | old | old_first | b9p18p1806.cern.ch | extract | 343 | 30.45 | 26.58 | 733416 |
| 342 | latest | old_first | b9p18p1806.cern.ch | reco | 343 | 143.12 | 135.65 | 1108724 |
| 342 | latest | old_first | b9p18p1806.cern.ch | forward | 343 | 30.15 | 24.96 | 902812 |
| 342 | latest | old_first | b9p18p1806.cern.ch | backward | 343 | 34.1 | 29.37 | 901916 |
| 342 | latest | old_first | b9p18p1806.cern.ch | merge | 343 | 119.9 | 103.31 | 1997364 |
| 342 | latest | old_first | b9p18p1806.cern.ch | extract | 343 | 32.42 | 28.45 | 730732 |

## 验证与可追溯数据

共同 truth 检查：True；全量输入 ID 检查：False；分片 science arrays 回读恢复：True；全部 fiducial 波形与旧版逐值一致：True。

完整统计见本目录 TSV，逐事件迁移见 `truth_accepted_migration_events.tsv`，局部 truth-pass/reco-fail 见 `local_cut_migrations.tsv`，材料与四个 smoothing 的实际配置见 `effective_configuration.json`，源码 provenance 见 `runtime_source_provenance.json`。误差条、nominal / 分 run 及阈值变化保留在原表，稀疏高能 bin 不作过度外推。
