# Old/strict：电荷和接受度详细实测表

所有计数未加权；accepted 分母为三站 truth acceptance proxy。电荷替换是缓存条件控制，未重建或修改任何波形。

## 相同事件四种 tracking/waveform 组合

| 方法 | 轨迹和 Timing Y | 波形电荷 | 最终事件 | 相对 old 损失 | 新增 | 效率差 pp | 配对95% CI pp |
| --- | --- | --- | --- | --- | --- | --- | --- |
| forward | old | old | 91270 | 0 | 0 | 0.00000 | 0.00000～0.00000 |
| forward | old | strict | 90262 | 1011 | 3 | -0.71932 | -0.76370～-0.67494 |
| forward | strict | old | 88542 | 3478 | 750 | -1.94674 | -2.03711～-1.85636 |
| forward | strict | strict | 87566 | 4452 | 748 | -2.64322 | -2.74313～-2.54332 |
| backward | old | old | 101356 | 0 | 0 | 0.00000 | 0.00000～0.00000 |
| backward | old | strict | 100261 | 1098 | 3 | -0.78141 | -0.82764～-0.73518 |
| backward | strict | old | 99084 | 4070 | 1798 | -1.62133 | -1.72813～-1.51452 |
| backward | strict | strict | 98009 | 5127 | 1780 | -2.38846 | -2.50403～-2.27289 |
| merge | old | old | 102273 | 0 | 0 | 0.00000 | 0.00000～0.00000 |
| merge | old | strict | 101166 | 1110 | 3 | -0.78997 | -0.83645～-0.74349 |
| merge | strict | old | 102810 | 1070 | 1607 | 0.38321 | 0.31087～0.45555 |
| merge | strict | strict | 101692 | 2175 | 1594 | -0.41461 | -0.50045～-0.32877 |

## 通道电荷分布与异常，单位 pC

| 通道 | 版本 | NaN | +Inf | −Inf | 有限负值 | 0.1% | 中位数 | 99% | 99.9% |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Veto20 | old | 0 | 0 | 0 | 0 | 66.53456 | 759.00970 | 179208.83969 | 271174.34488 |
| Veto20 | strict | 0 | 0 | 33 | 0 | 66.50241 | 718.16296 | 7875.66547 | 14272.43666 |
| Veto21 | old | 0 | 0 | 0 | 0 | 66.39131 | 669.86237 | 192437.60734 | 277359.63506 |
| Veto21 | strict | 0 | 0 | 30 | 1 | 66.37277 | 667.00403 | 8227.75459 | 15506.58407 |
| Preshower0 | old | 0 | 0 | 0 | 0 | 3.81839 | 5.69122 | 1131.58064 | 3175.24614 |
| Preshower0 | strict | 0 | 0 | 308 | 333 | -0.50729 | 5.68520 | 1127.10347 | 3442.70537 |
| Preshower1 | old | 0 | 0 | 0 | 0 | 3.81427 | 5.87945 | 1534.85142 | 3936.68454 |
| Preshower1 | strict | 0 | 0 | 330 | 342 | -0.32625 | 5.87431 | 1529.87618 | 4501.37151 |
| VetoNu0_reduced | old | 0 | 0 | 0 | 15054 | -0.24477 | 0.00000 | 349.48352 | 1020.06057 |
| VetoNu0_reduced | strict | 0 | 0 | 0 | 14929 | -0.23662 | 0.00000 | 349.48352 | 1020.06057 |
| VetoNu1_reduced | old | 0 | 0 | 0 | 14534 | -0.24313 | 0.00000 | 416.97322 | 1110.97972 |
| VetoNu1_reduced | strict | 0 | 0 | 0 | 14409 | -0.23358 | 0.00000 | 416.97322 | 1110.97972 |
| Timing0 | old | 0 | 0 | 0 | 20806 | -0.69312 | 27.81544 | 2990.56813 | 10961.32836 |
| Timing0 | strict | 0 | 0 | 4 | 50 | 0.00608 | 27.79994 | 2867.99289 | 8071.93304 |
| Timing1 | old | 0 | 0 | 0 | 20951 | -0.69371 | 27.81741 | 2968.08901 | 10534.40554 |
| Timing1 | strict | 0 | 0 | 5 | 48 | 0.00361 | 27.80466 | 2845.43752 | 8018.00210 |
| Timing2 | old | 0 | 0 | 0 | 18381 | -0.68456 | 28.76497 | 3317.60698 | 11881.12189 |
| Timing2 | strict | 0 | 0 | 6 | 48 | 0.04459 | 28.75492 | 3129.15204 | 8617.27808 |
| Timing3 | old | 0 | 0 | 0 | 18267 | -0.68088 | 28.75464 | 3310.55490 | 11770.50364 |
| Timing3 | strict | 0 | 0 | 4 | 42 | 0.06542 | 28.74287 | 3116.75150 | 8736.97350 |

## 单通道阈值迁移，包含非有限值的实际比较结果

| 通道 | 阈值 pC | 旧通过 | strict通过 | 旧通过/strict失败 | 旧失败/strict通过 |
| --- | --- | --- | --- | --- | --- |
| Veto20 | 40 | 140132 | 140097 | 35 | 0 |
| Veto21 | 40 | 140132 | 140098 | 34 | 0 |
| Preshower0 | 2.5 | 140131 | 139461 | 671 | 1 |
| Preshower1 | 2.5 | 140132 | 139435 | 697 | 0 |
| VetoNu0_reduced | 30 | 130635 | 130629 | 6 | 0 |
| VetoNu1_reduced | 30 | 129359 | 129348 | 13 | 2 |

## 固定 strict 轨迹，仅换一通道为旧电荷

| 方法 | 通道 | strict原通过 | 替换后通过 | 丢失 | 恢复 | 净效率 pp |
| --- | --- | --- | --- | --- | --- | --- |
| forward | Veto20 | 87566 | 87588 | 0 | 22 | 0.01570 |
| forward | Veto21 | 87566 | 87587 | 0 | 21 | 0.01499 |
| forward | Preshower0 | 87566 | 88018 | 1 | 453 | 0.32255 |
| forward | Preshower1 | 87566 | 88028 | 0 | 462 | 0.32969 |
| forward | VetoNu0_reduced | 87566 | 87566 | 0 | 0 | 0.00000 |
| forward | VetoNu1_reduced | 87566 | 87567 | 1 | 2 | 0.00071 |
| forward | Timing0 | 87566 | 87571 | 0 | 5 | 0.00357 |
| forward | Timing1 | 87566 | 87572 | 0 | 6 | 0.00428 |
| forward | Timing2 | 87566 | 87574 | 0 | 8 | 0.00571 |
| forward | Timing3 | 87566 | 87574 | 0 | 8 | 0.00571 |
| backward | Veto20 | 98009 | 98032 | 0 | 23 | 0.01641 |
| backward | Veto21 | 98009 | 98034 | 0 | 25 | 0.01784 |
| backward | Preshower0 | 98009 | 98499 | 1 | 491 | 0.34967 |
| backward | Preshower1 | 98009 | 98525 | 0 | 516 | 0.36822 |
| backward | VetoNu0_reduced | 98009 | 98010 | 0 | 1 | 0.00071 |
| backward | VetoNu1_reduced | 98009 | 98009 | 2 | 2 | 0.00000 |
| backward | Timing0 | 98009 | 98014 | 0 | 5 | 0.00357 |
| backward | Timing1 | 98009 | 98015 | 0 | 6 | 0.00428 |
| backward | Timing2 | 98009 | 98018 | 0 | 9 | 0.00642 |
| backward | Timing3 | 98009 | 98017 | 0 | 8 | 0.00571 |
| merge | Veto20 | 101692 | 101717 | 0 | 25 | 0.01784 |
| merge | Veto21 | 101692 | 101718 | 0 | 26 | 0.01855 |
| merge | Preshower0 | 101692 | 102201 | 1 | 510 | 0.36323 |
| merge | Preshower1 | 101692 | 102229 | 0 | 537 | 0.38321 |
| merge | VetoNu0_reduced | 101692 | 101693 | 0 | 1 | 0.00071 |
| merge | VetoNu1_reduced | 101692 | 101692 | 2 | 2 | 0.00000 |
| merge | Timing0 | 101692 | 101697 | 0 | 5 | 0.00357 |
| merge | Timing1 | 101692 | 101698 | 0 | 6 | 0.00428 |
| merge | Timing2 | 101692 | 101701 | 0 | 9 | 0.00642 |
| merge | Timing3 | 101692 | 101700 | 0 | 8 | 0.00571 |

## 五组电荷的全部32种组合：跨替换顺序平均边际恢复

| 方法 | 电荷组 | 平均边际恢复事件 | 效率 pp |
| --- | --- | --- | --- |
| forward | veto | 43.50000 | 0.03104 |
| forward | timing | 16.00000 | 0.01142 |
| forward | preshower | 915.50000 | 0.65331 |
| forward | VetoNu0 | 0.00000 | 0.00000 |
| forward | VetoNu1 | 1.00000 | 0.00071 |
| backward | veto | 49.00000 | 0.03497 |
| backward | timing | 17.00000 | 0.01213 |
| backward | preshower | 1008.00000 | 0.71932 |
| backward | VetoNu0 | 1.00000 | 0.00071 |
| backward | VetoNu1 | 0.00000 | 0.00000 |
| merge | veto | 52.00000 | 0.03711 |
| merge | timing | 17.00000 | 0.01213 |
| merge | preshower | 1048.00000 | 0.74787 |
| merge | VetoNu0 | 1.00000 | 0.00071 |
| merge | VetoNu1 | 0.00000 | 0.00000 |

## 固定 strict tracking，全部换旧电荷的 final 迁移互斥分类

| 方法 | actual strict final | 类型（优先非有限、负值、其余） | 事件数 |
| --- | --- | --- | --- |
| backward | False | other_waveform | 68 |
| backward | False | preshower_finite_negative | 528 |
| backward | False | preshower_finite_nonnegative_below_threshold | 43 |
| backward | False | preshower_nonfinite | 439 |
| backward | True | old_other_waveform | 2 |
| backward | True | old_preshower_below_threshold | 1 |
| forward | False | other_waveform | 61 |
| forward | False | preshower_finite_negative | 493 |
| forward | False | preshower_finite_nonnegative_below_threshold | 41 |
| forward | False | preshower_nonfinite | 383 |
| forward | True | old_other_waveform | 1 |
| forward | True | old_preshower_below_threshold | 1 |
| merge | False | other_waveform | 71 |
| merge | False | preshower_finite_negative | 551 |
| merge | False | preshower_finite_nonnegative_below_threshold | 45 |
| merge | False | preshower_nonfinite | 454 |
| merge | True | old_other_waveform | 2 |
| merge | True | old_preshower_below_threshold | 1 |

## 轨迹效率各层迁移

| 方法 | 层级 | old事件 | strict事件 | 丢失 | 新增 | 效率差 pp |
| --- | --- | --- | --- | --- | --- | --- |
| forward | primary_raw | 123523 | 122456 | 1315 | 248 | -0.76142 |
| backward | primary_raw | 124727 | 123757 | 1320 | 350 | -0.69220 |
| merge | primary_raw | 125346 | 125374 | 315 | 343 | 0.01998 |
| forward | primary_long | 107806 | 104775 | 3530 | 499 | -2.16296 |
| backward | primary_long | 120618 | 117053 | 4567 | 1002 | -2.54403 |
| merge | primary_long | 121143 | 120834 | 1222 | 913 | -0.22051 |
| forward | primary_quality | 105335 | 102054 | 3933 | 652 | -2.34136 |
| backward | primary_quality | 116148 | 113334 | 4552 | 1738 | -2.00811 |
| merge | primary_quality | 117190 | 117619 | 1119 | 1548 | 0.30614 |
| forward | has_long | 108427 | 105595 | 3418 | 586 | -2.02095 |
| backward | has_long | 122171 | 119334 | 4559 | 1722 | -2.02452 |
| merge | has_long | 122772 | 123068 | 1321 | 1617 | 0.21123 |
| forward | correct_leader | 107732 | 104691 | 3548 | 507 | -2.17010 |
| backward | correct_leader | 120512 | 116945 | 4578 | 1011 | -2.54546 |
| merge | correct_leader | 121019 | 120701 | 1244 | 926 | -0.22693 |
| forward | track_cuts | 103299 | 100184 | 3933 | 818 | -2.22290 |
| backward | track_cuts | 113912 | 111246 | 4557 | 1891 | -1.90249 |
| merge | track_cuts | 114941 | 115439 | 1182 | 1680 | 0.35538 |
| forward | actual_final | 91270 | 87566 | 4452 | 748 | -2.64322 |
| backward | actual_final | 101356 | 98009 | 5127 | 1780 | -2.38846 |
| merge | actual_final | 102273 | 101692 | 2175 | 1594 | -0.41461 |
| forward | fixed_old_waveform | 91270 | 88542 | 3478 | 750 | -1.94674 |
| backward | fixed_old_waveform | 101356 | 99084 | 4070 | 1798 | -1.62133 |
| merge | fixed_old_waveform | 102273 | 102810 | 1070 | 1607 | 0.38321 |

## Forward/backward 的互补性

| 版本 | 层级 | 事件集合 | 事件数 |
| --- | --- | --- | --- |
| old | primary_raw | both_FB | 122898 |
| old | primary_raw | F_only | 625 |
| old | primary_raw | B_only | 1829 |
| old | primary_raw | neither_FB | 14780 |
| old | primary_raw | FB_union | 125352 |
| old | primary_raw | merge_outside_FB | 0 |
| old | primary_raw | FB_union_missing_merge | 6 |
| old | primary_long | both_FB | 107225 |
| old | primary_long | F_only | 581 |
| old | primary_long | B_only | 13393 |
| old | primary_long | neither_FB | 18933 |
| old | primary_long | FB_union | 121199 |
| old | primary_long | merge_outside_FB | 0 |
| old | primary_long | FB_union_missing_merge | 56 |
| old | has_long | both_FB | 107758 |
| old | has_long | F_only | 669 |
| old | has_long | B_only | 14413 |
| old | has_long | neither_FB | 17292 |
| old | has_long | FB_union | 122840 |
| old | has_long | merge_outside_FB | 0 |
| old | has_long | FB_union_missing_merge | 68 |
| old | track_cuts | both_FB | 102119 |
| old | track_cuts | F_only | 1180 |
| old | track_cuts | B_only | 11793 |
| old | track_cuts | neither_FB | 25040 |
| old | track_cuts | FB_union | 115092 |
| old | track_cuts | merge_outside_FB | 1 |
| old | track_cuts | FB_union_missing_merge | 152 |
| old | fixed_old_waveform | both_FB | 90210 |
| old | fixed_old_waveform | F_only | 1060 |
| old | fixed_old_waveform | B_only | 11146 |
| old | fixed_old_waveform | neither_FB | 37716 |
| old | fixed_old_waveform | FB_union | 102416 |
| old | fixed_old_waveform | merge_outside_FB | 1 |
| old | fixed_old_waveform | FB_union_missing_merge | 144 |
| strict | primary_raw | both_FB | 120836 |
| strict | primary_raw | F_only | 1620 |
| strict | primary_raw | B_only | 2921 |
| strict | primary_raw | neither_FB | 14755 |
| strict | primary_raw | FB_union | 125377 |
| strict | primary_raw | merge_outside_FB | 0 |
| strict | primary_raw | FB_union_missing_merge | 3 |
| strict | primary_long | both_FB | 100952 |
| strict | primary_long | F_only | 3823 |
| strict | primary_long | B_only | 16101 |
| strict | primary_long | neither_FB | 19256 |
| strict | primary_long | FB_union | 120876 |
| strict | primary_long | merge_outside_FB | 0 |
| strict | primary_long | FB_union_missing_merge | 42 |
| strict | has_long | both_FB | 101812 |
| strict | has_long | F_only | 3783 |
| strict | has_long | B_only | 17522 |
| strict | has_long | neither_FB | 17015 |
| strict | has_long | FB_union | 123117 |
| strict | has_long | merge_outside_FB | 0 |
| strict | has_long | FB_union_missing_merge | 49 |
| strict | track_cuts | both_FB | 95934 |
| strict | track_cuts | F_only | 4250 |
| strict | track_cuts | B_only | 15312 |
| strict | track_cuts | neither_FB | 24636 |
| strict | track_cuts | FB_union | 115496 |
| strict | track_cuts | merge_outside_FB | 0 |
| strict | track_cuts | FB_union_missing_merge | 57 |
| strict | fixed_old_waveform | both_FB | 84761 |
| strict | fixed_old_waveform | F_only | 3781 |
| strict | fixed_old_waveform | B_only | 14323 |
| strict | fixed_old_waveform | neither_FB | 37267 |
| strict | fixed_old_waveform | FB_union | 102865 |
| strict | fixed_old_waveform | merge_outside_FB | 0 |
| strict | fixed_old_waveform | FB_union_missing_merge | 55 |

## 固定旧电荷后的 cutflow；首失败互斥

| 方法 | 版本 | cut | 单cut通过 | 累计通过 | 首失败 |
| --- | --- | --- | --- | --- | --- |
| forward | old | long | 108427 | 108427 | 31705 |
| forward | old | veto | 140132 | 108427 | 0 |
| forward | old | timing | 108382 | 108382 | 45 |
| forward | old | preshower | 140131 | 108381 | 1 |
| forward | old | pz | 107199 | 107162 | 1219 |
| forward | old | layers | 107878 | 106747 | 415 |
| forward | old | ndof | 105840 | 104873 | 1874 |
| forward | old | chi2 | 108276 | 104828 | 45 |
| forward | old | rmax | 107676 | 104378 | 450 |
| forward | old | rIFT | 107246 | 103372 | 1006 |
| forward | old | rVetoNu | 108216 | 103333 | 39 |
| forward | old | theta | 108149 | 103298 | 35 |
| forward | old | VetoNu0 | 130635 | 95049 | 8249 |
| forward | old | VetoNu1 | 129359 | 91270 | 3779 |
| backward | old | long | 122171 | 122171 | 17961 |
| backward | old | veto | 140132 | 122171 | 0 |
| backward | old | timing | 122170 | 122170 | 1 |
| backward | old | preshower | 140131 | 122169 | 1 |
| backward | old | pz | 120354 | 120353 | 1816 |
| backward | old | layers | 120961 | 119387 | 966 |
| backward | old | ndof | 116970 | 115775 | 3612 |
| backward | old | chi2 | 121831 | 115741 | 34 |
| backward | old | rmax | 120700 | 115221 | 520 |
| backward | old | rIFT | 119915 | 114019 | 1202 |
| backward | old | rVetoNu | 121050 | 113950 | 69 |
| backward | old | theta | 121037 | 113911 | 39 |
| backward | old | VetoNu0 | 130635 | 105344 | 8567 |
| backward | old | VetoNu1 | 129359 | 101356 | 3988 |
| merge | old | long | 122772 | 122772 | 17360 |
| merge | old | veto | 140132 | 122772 | 0 |
| merge | old | timing | 122749 | 122749 | 23 |
| merge | old | preshower | 140131 | 122748 | 1 |
| merge | old | pz | 120994 | 120974 | 1774 |
| merge | old | layers | 121577 | 120075 | 899 |
| merge | old | ndof | 117989 | 116830 | 3245 |
| merge | old | chi2 | 122458 | 116810 | 20 |
| merge | old | rmax | 121230 | 116274 | 536 |
| merge | old | rIFT | 120470 | 115048 | 1226 |
| merge | old | rVetoNu | 121590 | 114979 | 69 |
| merge | old | theta | 121561 | 114940 | 39 |
| merge | old | VetoNu0 | 130635 | 106294 | 8646 |
| merge | old | VetoNu1 | 129359 | 102273 | 4021 |
| forward | strict | long | 105595 | 105595 | 34537 |
| forward | strict | veto | 140132 | 105595 | 0 |
| forward | strict | timing | 105547 | 105547 | 48 |
| forward | strict | preshower | 140131 | 105546 | 1 |
| forward | strict | pz | 104348 | 104309 | 1237 |
| forward | strict | layers | 104885 | 103787 | 522 |
| forward | strict | ndof | 102668 | 101711 | 2076 |
| forward | strict | chi2 | 105581 | 101711 | 0 |
| forward | strict | rmax | 104730 | 101258 | 453 |
| forward | strict | rIFT | 104416 | 100255 | 1003 |
| forward | strict | rVetoNu | 105352 | 100215 | 40 |
| forward | strict | theta | 105258 | 100183 | 32 |
| forward | strict | VetoNu0 | 130635 | 92195 | 7988 |
| forward | strict | VetoNu1 | 129359 | 88542 | 3653 |
| backward | strict | long | 119334 | 119334 | 20798 |
| backward | strict | veto | 140132 | 119334 | 0 |
| backward | strict | timing | 119326 | 119326 | 8 |
| backward | strict | preshower | 140131 | 119325 | 1 |
| backward | strict | pz | 116588 | 116586 | 2739 |
| backward | strict | layers | 118002 | 115875 | 711 |
| backward | strict | ndof | 114922 | 113073 | 2802 |
| backward | strict | chi2 | 119219 | 113070 | 3 |
| backward | strict | rmax | 117903 | 112559 | 511 |
| backward | strict | rIFT | 117223 | 111352 | 1207 |
| backward | strict | rVetoNu | 118332 | 111283 | 69 |
| backward | strict | theta | 118191 | 111245 | 38 |
| backward | strict | VetoNu0 | 130635 | 102940 | 8305 |
| backward | strict | VetoNu1 | 129359 | 99084 | 3856 |
| merge | strict | long | 123068 | 123068 | 17064 |
| merge | strict | veto | 140132 | 123068 | 0 |
| merge | strict | timing | 123039 | 123039 | 29 |
| merge | strict | preshower | 140131 | 123038 | 1 |
| merge | strict | pz | 120374 | 120352 | 2686 |
| merge | strict | layers | 121852 | 119764 | 588 |
| merge | strict | ndof | 119096 | 117323 | 2441 |
| merge | strict | chi2 | 122971 | 117320 | 3 |
| merge | strict | rmax | 121563 | 116782 | 538 |
| merge | strict | rIFT | 121017 | 115548 | 1234 |
| merge | strict | rVetoNu | 122139 | 115475 | 73 |
| merge | strict | theta | 121970 | 115438 | 37 |
| merge | strict | VetoNu0 | 130635 | 106822 | 8616 |
| merge | strict | VetoNu1 | 129359 | 102810 | 4012 |

## 固定旧电荷，仅移去一项轨迹cut的敏感性（诊断，不代表可接受修改）

| 方法 | 版本 | 移去cut | 额外通过事件 |
| --- | --- | --- | --- |
| forward | old | pz | 709 |
| forward | old | layers | 0 |
| forward | old | ndof | 1569 |
| forward | old | chi2 | 41 |
| forward | old | rmax | 366 |
| forward | old | rIFT | 948 |
| forward | old | rVetoNu | 39 |
| forward | old | theta | 31 |
| backward | old | pz | 882 |
| backward | old | layers | 1 |
| backward | old | ndof | 2583 |
| backward | old | chi2 | 30 |
| backward | old | rmax | 420 |
| backward | old | rIFT | 1110 |
| backward | old | rVetoNu | 67 |
| backward | old | theta | 35 |
| merge | old | pz | 838 |
| merge | old | layers | 0 |
| merge | old | ndof | 2279 |
| merge | old | chi2 | 16 |
| merge | old | rmax | 432 |
| merge | old | rIFT | 1134 |
| merge | old | rVetoNu | 67 |
| merge | old | theta | 35 |
| forward | strict | pz | 640 |
| forward | strict | layers | 2 |
| forward | strict | ndof | 1777 |
| forward | strict | chi2 | 0 |
| forward | strict | rmax | 366 |
| forward | strict | rIFT | 944 |
| forward | strict | rVetoNu | 39 |
| forward | strict | theta | 28 |
| backward | strict | pz | 1163 |
| backward | strict | layers | 1 |
| backward | strict | ndof | 2337 |
| backward | strict | chi2 | 0 |
| backward | strict | rmax | 427 |
| backward | strict | rIFT | 1126 |
| backward | strict | rVetoNu | 68 |
| backward | strict | theta | 34 |
| merge | strict | pz | 1107 |
| merge | strict | layers | 0 |
| merge | strict | ndof | 2051 |
| merge | strict | chi2 | 0 |
| merge | strict | rmax | 446 |
| merge | strict | rIFT | 1153 |
| merge | strict | rVetoNu | 72 |
| merge | strict | theta | 33 |

## Timing 位置和电荷四组合

| 方法 | Timing Y版本 | 电荷版本 | Timing单cut通过 | 仅替换Timing后的strict final |
| --- | --- | --- | --- | --- |
| forward | old | old | 108382 | 87295 |
| forward | old | strict | 108362 | 87279 |
| forward | strict | old | 105547 | 87582 |
| forward | strict | strict | 105527 | 87566 |
| backward | old | old | 122170 | 97478 |
| backward | old | strict | 122148 | 97461 |
| backward | strict | old | 119326 | 98026 |
| backward | strict | strict | 119305 | 98009 |
| merge | old | old | 122749 | 101287 |
| merge | old | strict | 122727 | 101270 |
| merge | strict | old | 123039 | 101709 |
| merge | strict | strict | 123017 | 101692 |

## 轨迹正负电荷识别（全 fiducial，正确主μ，purity≥0.7）

| 方法 | 版本 | 选择 | truth pz下限 GeV | 上限 GeV | 主μ样本 | 错误sign |
| --- | --- | --- | --- | --- | --- | --- |
| forward | old | final | 0 | inf | 91763 | 1085 |
| forward | old | final | 100 | 300 | 25110 | 11 |
| forward | old | final | 300 | 1000 | 49741 | 241 |
| forward | old | final | 1000 | 3000 | 16096 | 682 |
| forward | old | final | 3000 | inf | 789 | 151 |
| forward | old | fixed_final | 0 | inf | 91763 | 1085 |
| forward | old | fixed_final | 100 | 300 | 25110 | 11 |
| forward | old | fixed_final | 300 | 1000 | 49741 | 241 |
| forward | old | fixed_final | 1000 | 3000 | 16096 | 682 |
| forward | old | fixed_final | 3000 | inf | 789 | 151 |
| backward | old | final | 0 | inf | 101823 | 1297 |
| backward | old | final | 100 | 300 | 26685 | 28 |
| backward | old | final | 300 | 1000 | 55265 | 305 |
| backward | old | final | 1000 | 3000 | 18853 | 780 |
| backward | old | final | 3000 | inf | 989 | 183 |
| backward | old | fixed_final | 0 | inf | 101823 | 1297 |
| backward | old | fixed_final | 100 | 300 | 26685 | 28 |
| backward | old | fixed_final | 300 | 1000 | 55265 | 305 |
| backward | old | fixed_final | 1000 | 3000 | 18853 | 780 |
| backward | old | fixed_final | 3000 | inf | 989 | 183 |
| merge | old | final | 0 | inf | 102749 | 1059 |
| merge | old | final | 100 | 300 | 26916 | 15 |
| merge | old | final | 300 | 1000 | 55738 | 210 |
| merge | old | final | 1000 | 3000 | 19057 | 667 |
| merge | old | final | 3000 | inf | 1006 | 166 |
| merge | old | fixed_final | 0 | inf | 102749 | 1059 |
| merge | old | fixed_final | 100 | 300 | 26916 | 15 |
| merge | old | fixed_final | 300 | 1000 | 55738 | 210 |
| merge | old | fixed_final | 1000 | 3000 | 19057 | 667 |
| merge | old | fixed_final | 3000 | inf | 1006 | 166 |
| forward | strict | final | 0 | inf | 88003 | 34 |
| forward | strict | final | 100 | 300 | 24032 | 3 |
| forward | strict | final | 300 | 1000 | 47664 | 12 |
| forward | strict | final | 1000 | 3000 | 15530 | 10 |
| forward | strict | final | 3000 | inf | 759 | 9 |
| forward | strict | fixed_final | 0 | inf | 88982 | 34 |
| forward | strict | fixed_final | 100 | 300 | 24291 | 3 |
| forward | strict | fixed_final | 300 | 1000 | 48204 | 12 |
| forward | strict | fixed_final | 1000 | 3000 | 15701 | 10 |
| forward | strict | fixed_final | 3000 | inf | 768 | 9 |
| backward | strict | final | 0 | inf | 98398 | 44 |
| backward | strict | final | 100 | 300 | 25655 | 4 |
| backward | strict | final | 300 | 1000 | 53413 | 14 |
| backward | strict | final | 1000 | 3000 | 18328 | 13 |
| backward | strict | final | 3000 | inf | 985 | 13 |
| backward | strict | fixed_final | 0 | inf | 99479 | 44 |
| backward | strict | fixed_final | 100 | 300 | 25942 | 4 |
| backward | strict | fixed_final | 300 | 1000 | 53987 | 14 |
| backward | strict | fixed_final | 1000 | 3000 | 18537 | 13 |
| backward | strict | fixed_final | 3000 | inf | 996 | 13 |
| merge | strict | final | 0 | inf | 102122 | 45 |
| merge | strict | final | 100 | 300 | 26652 | 4 |
| merge | strict | final | 300 | 1000 | 55397 | 17 |
| merge | strict | final | 1000 | 3000 | 19032 | 9 |
| merge | strict | final | 3000 | inf | 1023 | 15 |
| merge | strict | fixed_final | 0 | inf | 103246 | 45 |
| merge | strict | fixed_final | 100 | 300 | 26946 | 4 |
| merge | strict | fixed_final | 300 | 1000 | 56000 | 17 |
| merge | strict | fixed_final | 1000 | 3000 | 19248 | 9 |
| merge | strict | fixed_final | 3000 | inf | 1034 | 15 |

