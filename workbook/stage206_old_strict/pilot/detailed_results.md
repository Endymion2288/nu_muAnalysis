# Old/strict：电荷和接受度详细实测表

所有计数未加权；accepted 分母为三站 truth acceptance proxy。电荷替换是缓存条件控制，未重建或修改任何波形。

## 相同事件四种 tracking/waveform 组合

| 方法 | 轨迹和 Timing Y | 波形电荷 | 最终事件 | 相对 old 损失 | 新增 | 效率差 pp | 配对95% CI pp |
| --- | --- | --- | --- | --- | --- | --- | --- |
| forward | old | old | 1112 | 0 | 0 | 0.00000 | 0.00000～0.00000 |
| forward | old | strict | 1096 | 16 | 0 | -0.92593 | -1.37752～-0.47433 |
| forward | strict | old | 1087 | 37 | 12 | -1.44676 | -2.23780～-0.65571 |
| forward | strict | strict | 1072 | 52 | 12 | -2.31481 | -3.21563～-1.41400 |
| backward | old | old | 1237 | 0 | 0 | 0.00000 | 0.00000～0.00000 |
| backward | old | strict | 1221 | 16 | 0 | -0.92593 | -1.37752～-0.47433 |
| backward | strict | old | 1206 | 49 | 18 | -1.79398 | -2.71855～-0.86941 |
| backward | strict | strict | 1190 | 65 | 18 | -2.71991 | -3.74528～-1.69454 |
| merge | old | old | 1247 | 0 | 0 | 0.00000 | 0.00000～0.00000 |
| merge | old | strict | 1230 | 17 | 0 | -0.98380 | -1.44916～-0.51844 |
| merge | strict | old | 1252 | 12 | 17 | 0.28935 | -0.32131～0.90002 |
| merge | strict | strict | 1236 | 28 | 17 | -0.63657 | -1.39687～0.12372 |

## 通道电荷分布与异常，单位 pC

| 通道 | 版本 | NaN | +Inf | −Inf | 有限负值 | 0.1% | 中位数 | 99% | 99.9% |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Veto20 | old | 0 | 0 | 0 | 0 | 67.83898 | 796.97202 | 162182.09766 | 268425.26722 |
| Veto20 | strict | 0 | 0 | 0 | 0 | 67.83893 | 733.19711 | 7659.84769 | 9648.40828 |
| Veto21 | old | 0 | 0 | 0 | 0 | 67.94176 | 711.69873 | 195552.70250 | 247502.71273 |
| Veto21 | strict | 0 | 0 | 0 | 0 | 67.94172 | 692.11737 | 7813.41615 | 14013.11808 |
| Preshower0 | old | 0 | 0 | 0 | 0 | 3.81333 | 5.78334 | 1090.69077 | 2563.76381 |
| Preshower0 | strict | 0 | 0 | 3 | 5 | -4.78672 | 5.77666 | 1091.48391 | 3034.61839 |
| Preshower1 | old | 0 | 0 | 0 | 0 | 3.79268 | 6.07489 | 1621.73029 | 3804.83212 |
| Preshower1 | strict | 0 | 0 | 3 | 5 | -0.58764 | 6.07283 | 1671.43476 | 4114.95012 |
| VetoNu0_reduced | old | 0 | 0 | 0 | 178 | -0.21804 | 0.00000 | 300.96932 | 844.36632 |
| VetoNu0_reduced | strict | 0 | 0 | 0 | 177 | -0.21804 | 0.00000 | 300.96932 | 844.36632 |
| VetoNu1_reduced | old | 0 | 0 | 0 | 169 | -0.24938 | 0.00000 | 386.06289 | 1056.34342 |
| VetoNu1_reduced | strict | 0 | 0 | 0 | 166 | -0.22862 | 0.00000 | 386.06289 | 1056.34342 |
| Timing0 | old | 0 | 0 | 0 | 248 | -0.72712 | 27.73338 | 3198.11638 | 13271.48223 |
| Timing0 | strict | 0 | 0 | 0 | 0 | 0.26877 | 27.73335 | 3070.67427 | 7645.95051 |
| Timing1 | old | 0 | 0 | 0 | 254 | -0.59415 | 27.73374 | 3217.66713 | 12404.25103 |
| Timing1 | strict | 0 | 0 | 0 | 0 | 0.17981 | 27.73374 | 2873.32714 | 6275.22670 |
| Timing2 | old | 0 | 0 | 0 | 234 | -0.76041 | 28.98650 | 4080.12023 | 13031.22101 |
| Timing2 | strict | 0 | 0 | 1 | 1 | 0.00000 | 28.95144 | 3520.34590 | 9264.40567 |
| Timing3 | old | 0 | 0 | 0 | 222 | -0.63887 | 28.91913 | 4030.43779 | 10312.30857 |
| Timing3 | strict | 0 | 0 | 0 | 1 | 0.00000 | 28.91713 | 3502.65823 | 10312.30208 |

## 单通道阈值迁移，包含非有限值的实际比较结果

| 通道 | 阈值 pC | 旧通过 | strict通过 | 旧通过/strict失败 | 旧失败/strict通过 |
| --- | --- | --- | --- | --- | --- |
| Veto20 | 40 | 1728 | 1728 | 0 | 0 |
| Veto21 | 40 | 1728 | 1728 | 0 | 0 |
| Preshower0 | 2.5 | 1728 | 1718 | 10 | 0 |
| Preshower1 | 2.5 | 1728 | 1719 | 9 | 0 |
| VetoNu0_reduced | 30 | 1625 | 1625 | 0 | 0 |
| VetoNu1_reduced | 30 | 1583 | 1582 | 1 | 0 |

## 固定 strict 轨迹，仅换一通道为旧电荷

| 方法 | 通道 | strict原通过 | 替换后通过 | 丢失 | 恢复 | 净效率 pp |
| --- | --- | --- | --- | --- | --- | --- |
| forward | Veto20 | 1072 | 1072 | 0 | 0 | 0.00000 |
| forward | Veto21 | 1072 | 1072 | 0 | 0 | 0.00000 |
| forward | Preshower0 | 1072 | 1080 | 0 | 8 | 0.46296 |
| forward | Preshower1 | 1072 | 1078 | 0 | 6 | 0.34722 |
| forward | VetoNu0_reduced | 1072 | 1072 | 0 | 0 | 0.00000 |
| forward | VetoNu1_reduced | 1072 | 1073 | 0 | 1 | 0.05787 |
| forward | Timing0 | 1072 | 1072 | 0 | 0 | 0.00000 |
| forward | Timing1 | 1072 | 1072 | 0 | 0 | 0.00000 |
| forward | Timing2 | 1072 | 1072 | 0 | 0 | 0.00000 |
| forward | Timing3 | 1072 | 1072 | 0 | 0 | 0.00000 |
| backward | Veto20 | 1190 | 1190 | 0 | 0 | 0.00000 |
| backward | Veto21 | 1190 | 1190 | 0 | 0 | 0.00000 |
| backward | Preshower0 | 1190 | 1199 | 0 | 9 | 0.52083 |
| backward | Preshower1 | 1190 | 1196 | 0 | 6 | 0.34722 |
| backward | VetoNu0_reduced | 1190 | 1190 | 0 | 0 | 0.00000 |
| backward | VetoNu1_reduced | 1190 | 1191 | 0 | 1 | 0.05787 |
| backward | Timing0 | 1190 | 1190 | 0 | 0 | 0.00000 |
| backward | Timing1 | 1190 | 1190 | 0 | 0 | 0.00000 |
| backward | Timing2 | 1190 | 1190 | 0 | 0 | 0.00000 |
| backward | Timing3 | 1190 | 1190 | 0 | 0 | 0.00000 |
| merge | Veto20 | 1236 | 1236 | 0 | 0 | 0.00000 |
| merge | Veto21 | 1236 | 1236 | 0 | 0 | 0.00000 |
| merge | Preshower0 | 1236 | 1245 | 0 | 9 | 0.52083 |
| merge | Preshower1 | 1236 | 1242 | 0 | 6 | 0.34722 |
| merge | VetoNu0_reduced | 1236 | 1236 | 0 | 0 | 0.00000 |
| merge | VetoNu1_reduced | 1236 | 1237 | 0 | 1 | 0.05787 |
| merge | Timing0 | 1236 | 1236 | 0 | 0 | 0.00000 |
| merge | Timing1 | 1236 | 1236 | 0 | 0 | 0.00000 |
| merge | Timing2 | 1236 | 1236 | 0 | 0 | 0.00000 |
| merge | Timing3 | 1236 | 1236 | 0 | 0 | 0.00000 |

## 五组电荷的全部32种组合：跨替换顺序平均边际恢复

| 方法 | 电荷组 | 平均边际恢复事件 | 效率 pp |
| --- | --- | --- | --- |
| forward | veto | 0.00000 | 0.00000 |
| forward | timing | 0.00000 | 0.00000 |
| forward | preshower | 14.00000 | 0.81019 |
| forward | VetoNu0 | 0.00000 | 0.00000 |
| forward | VetoNu1 | 1.00000 | 0.05787 |
| backward | veto | 0.00000 | 0.00000 |
| backward | timing | 0.00000 | 0.00000 |
| backward | preshower | 15.00000 | 0.86806 |
| backward | VetoNu0 | 0.00000 | 0.00000 |
| backward | VetoNu1 | 1.00000 | 0.05787 |
| merge | veto | 0.00000 | 0.00000 |
| merge | timing | 0.00000 | 0.00000 |
| merge | preshower | 15.00000 | 0.86806 |
| merge | VetoNu0 | 0.00000 | 0.00000 |
| merge | VetoNu1 | 1.00000 | 0.05787 |

## 固定 strict tracking，全部换旧电荷的 final 迁移互斥分类

| 方法 | actual strict final | 类型（优先非有限、负值、其余） | 事件数 |
| --- | --- | --- | --- |
| backward | False | other_waveform | 1 |
| backward | False | preshower_finite_negative | 8 |
| backward | False | preshower_finite_nonnegative_below_threshold | 3 |
| backward | False | preshower_nonfinite | 4 |
| forward | False | other_waveform | 1 |
| forward | False | preshower_finite_negative | 8 |
| forward | False | preshower_finite_nonnegative_below_threshold | 3 |
| forward | False | preshower_nonfinite | 3 |
| merge | False | other_waveform | 1 |
| merge | False | preshower_finite_negative | 8 |
| merge | False | preshower_finite_nonnegative_below_threshold | 3 |
| merge | False | preshower_nonfinite | 4 |

## 轨迹效率各层迁移

| 方法 | 层级 | old事件 | strict事件 | 丢失 | 新增 | 效率差 pp |
| --- | --- | --- | --- | --- | --- | --- |
| forward | primary_raw | 1519 | 1507 | 14 | 2 | -0.69444 |
| backward | primary_raw | 1533 | 1511 | 26 | 4 | -1.27315 |
| merge | primary_raw | 1540 | 1539 | 5 | 4 | -0.05787 |
| forward | primary_long | 1318 | 1292 | 34 | 8 | -1.50463 |
| backward | primary_long | 1480 | 1424 | 66 | 10 | -3.24074 |
| merge | primary_long | 1484 | 1474 | 19 | 9 | -0.57870 |
| forward | primary_quality | 1281 | 1250 | 42 | 11 | -1.79398 |
| backward | primary_quality | 1415 | 1375 | 57 | 17 | -2.31481 |
| merge | primary_quality | 1423 | 1427 | 13 | 17 | 0.23148 |
| forward | has_long | 1327 | 1301 | 33 | 7 | -1.50463 |
| backward | has_long | 1500 | 1457 | 63 | 20 | -2.48843 |
| merge | has_long | 1506 | 1506 | 17 | 17 | 0.00000 |
| forward | correct_leader | 1315 | 1288 | 35 | 8 | -1.56250 |
| backward | correct_leader | 1477 | 1421 | 66 | 10 | -3.24074 |
| merge | correct_leader | 1481 | 1470 | 20 | 9 | -0.63657 |
| forward | track_cuts | 1259 | 1230 | 41 | 12 | -1.67824 |
| backward | track_cuts | 1388 | 1352 | 55 | 19 | -2.08333 |
| merge | track_cuts | 1400 | 1403 | 14 | 17 | 0.17361 |
| forward | actual_final | 1112 | 1072 | 52 | 12 | -2.31481 |
| backward | actual_final | 1237 | 1190 | 65 | 18 | -2.71991 |
| merge | actual_final | 1247 | 1236 | 28 | 17 | -0.63657 |
| forward | fixed_old_waveform | 1112 | 1087 | 37 | 12 | -1.44676 |
| backward | fixed_old_waveform | 1237 | 1206 | 49 | 18 | -1.79398 |
| merge | fixed_old_waveform | 1247 | 1252 | 12 | 17 | 0.28935 |

## Forward/backward 的互补性

| 版本 | 层级 | 事件集合 | 事件数 |
| --- | --- | --- | --- |
| old | primary_raw | both_FB | 1512 |
| old | primary_raw | F_only | 7 |
| old | primary_raw | B_only | 21 |
| old | primary_raw | neither_FB | 188 |
| old | primary_raw | FB_union | 1540 |
| old | primary_raw | merge_outside_FB | 0 |
| old | primary_raw | FB_union_missing_merge | 0 |
| old | primary_long | both_FB | 1312 |
| old | primary_long | F_only | 6 |
| old | primary_long | B_only | 168 |
| old | primary_long | neither_FB | 242 |
| old | primary_long | FB_union | 1486 |
| old | primary_long | merge_outside_FB | 0 |
| old | primary_long | FB_union_missing_merge | 2 |
| old | has_long | both_FB | 1319 |
| old | has_long | F_only | 8 |
| old | has_long | B_only | 181 |
| old | has_long | neither_FB | 220 |
| old | has_long | FB_union | 1508 |
| old | has_long | merge_outside_FB | 0 |
| old | has_long | FB_union_missing_merge | 2 |
| old | track_cuts | both_FB | 1246 |
| old | track_cuts | F_only | 13 |
| old | track_cuts | B_only | 142 |
| old | track_cuts | neither_FB | 327 |
| old | track_cuts | FB_union | 1401 |
| old | track_cuts | merge_outside_FB | 0 |
| old | track_cuts | FB_union_missing_merge | 1 |
| old | fixed_old_waveform | both_FB | 1101 |
| old | fixed_old_waveform | F_only | 11 |
| old | fixed_old_waveform | B_only | 136 |
| old | fixed_old_waveform | neither_FB | 480 |
| old | fixed_old_waveform | FB_union | 1248 |
| old | fixed_old_waveform | merge_outside_FB | 0 |
| old | fixed_old_waveform | FB_union_missing_merge | 1 |
| strict | primary_raw | both_FB | 1479 |
| strict | primary_raw | F_only | 28 |
| strict | primary_raw | B_only | 32 |
| strict | primary_raw | neither_FB | 189 |
| strict | primary_raw | FB_union | 1539 |
| strict | primary_raw | merge_outside_FB | 0 |
| strict | primary_raw | FB_union_missing_merge | 0 |
| strict | primary_long | both_FB | 1242 |
| strict | primary_long | F_only | 50 |
| strict | primary_long | B_only | 182 |
| strict | primary_long | neither_FB | 254 |
| strict | primary_long | FB_union | 1474 |
| strict | primary_long | merge_outside_FB | 0 |
| strict | primary_long | FB_union_missing_merge | 0 |
| strict | has_long | both_FB | 1252 |
| strict | has_long | F_only | 49 |
| strict | has_long | B_only | 205 |
| strict | has_long | neither_FB | 222 |
| strict | has_long | FB_union | 1506 |
| strict | has_long | merge_outside_FB | 0 |
| strict | has_long | FB_union_missing_merge | 0 |
| strict | track_cuts | both_FB | 1179 |
| strict | track_cuts | F_only | 51 |
| strict | track_cuts | B_only | 173 |
| strict | track_cuts | neither_FB | 325 |
| strict | track_cuts | FB_union | 1403 |
| strict | track_cuts | merge_outside_FB | 0 |
| strict | track_cuts | FB_union_missing_merge | 0 |
| strict | fixed_old_waveform | both_FB | 1041 |
| strict | fixed_old_waveform | F_only | 46 |
| strict | fixed_old_waveform | B_only | 165 |
| strict | fixed_old_waveform | neither_FB | 476 |
| strict | fixed_old_waveform | FB_union | 1252 |
| strict | fixed_old_waveform | merge_outside_FB | 0 |
| strict | fixed_old_waveform | FB_union_missing_merge | 0 |

## 固定旧电荷后的 cutflow；首失败互斥

| 方法 | 版本 | cut | 单cut通过 | 累计通过 | 首失败 |
| --- | --- | --- | --- | --- | --- |
| forward | old | long | 1327 | 1327 | 401 |
| forward | old | veto | 1728 | 1327 | 0 |
| forward | old | timing | 1326 | 1326 | 1 |
| forward | old | preshower | 1728 | 1326 | 0 |
| forward | old | pz | 1311 | 1310 | 16 |
| forward | old | layers | 1319 | 1302 | 8 |
| forward | old | ndof | 1288 | 1275 | 27 |
| forward | old | chi2 | 1327 | 1275 | 0 |
| forward | old | rmax | 1320 | 1271 | 4 |
| forward | old | rIFT | 1313 | 1259 | 12 |
| forward | old | rVetoNu | 1326 | 1259 | 0 |
| forward | old | theta | 1323 | 1259 | 0 |
| forward | old | VetoNu0 | 1625 | 1172 | 87 |
| forward | old | VetoNu1 | 1583 | 1112 | 60 |
| backward | old | long | 1500 | 1500 | 228 |
| backward | old | veto | 1728 | 1500 | 0 |
| backward | old | timing | 1500 | 1500 | 0 |
| backward | old | preshower | 1728 | 1500 | 0 |
| backward | old | pz | 1472 | 1472 | 28 |
| backward | old | layers | 1476 | 1452 | 20 |
| backward | old | ndof | 1427 | 1407 | 45 |
| backward | old | chi2 | 1496 | 1407 | 0 |
| backward | old | rmax | 1484 | 1403 | 4 |
| backward | old | rIFT | 1472 | 1389 | 14 |
| backward | old | rVetoNu | 1487 | 1388 | 1 |
| backward | old | theta | 1484 | 1388 | 0 |
| backward | old | VetoNu0 | 1625 | 1301 | 87 |
| backward | old | VetoNu1 | 1583 | 1237 | 64 |
| merge | old | long | 1506 | 1506 | 222 |
| merge | old | veto | 1728 | 1506 | 0 |
| merge | old | timing | 1505 | 1505 | 1 |
| merge | old | preshower | 1728 | 1505 | 0 |
| merge | old | pz | 1481 | 1480 | 25 |
| merge | old | layers | 1483 | 1461 | 19 |
| merge | old | ndof | 1435 | 1418 | 43 |
| merge | old | chi2 | 1504 | 1418 | 0 |
| merge | old | rmax | 1490 | 1414 | 4 |
| merge | old | rIFT | 1478 | 1401 | 13 |
| merge | old | rVetoNu | 1492 | 1400 | 1 |
| merge | old | theta | 1489 | 1400 | 0 |
| merge | old | VetoNu0 | 1625 | 1311 | 89 |
| merge | old | VetoNu1 | 1583 | 1247 | 64 |
| forward | strict | long | 1301 | 1301 | 427 |
| forward | strict | veto | 1728 | 1301 | 0 |
| forward | strict | timing | 1300 | 1300 | 1 |
| forward | strict | preshower | 1728 | 1300 | 0 |
| forward | strict | pz | 1287 | 1286 | 14 |
| forward | strict | layers | 1292 | 1278 | 8 |
| forward | strict | ndof | 1258 | 1247 | 31 |
| forward | strict | chi2 | 1301 | 1247 | 0 |
| forward | strict | rmax | 1293 | 1243 | 4 |
| forward | strict | rIFT | 1287 | 1230 | 13 |
| forward | strict | rVetoNu | 1301 | 1230 | 0 |
| forward | strict | theta | 1298 | 1230 | 0 |
| forward | strict | VetoNu0 | 1625 | 1145 | 85 |
| forward | strict | VetoNu1 | 1583 | 1087 | 58 |
| backward | strict | long | 1457 | 1457 | 271 |
| backward | strict | veto | 1728 | 1457 | 0 |
| backward | strict | timing | 1457 | 1457 | 0 |
| backward | strict | preshower | 1728 | 1457 | 0 |
| backward | strict | pz | 1415 | 1415 | 42 |
| backward | strict | layers | 1432 | 1403 | 12 |
| backward | strict | ndof | 1394 | 1372 | 31 |
| backward | strict | chi2 | 1456 | 1372 | 0 |
| backward | strict | rmax | 1439 | 1367 | 5 |
| backward | strict | rIFT | 1426 | 1353 | 14 |
| backward | strict | rVetoNu | 1439 | 1352 | 1 |
| backward | strict | theta | 1436 | 1352 | 0 |
| backward | strict | VetoNu0 | 1625 | 1267 | 85 |
| backward | strict | VetoNu1 | 1583 | 1206 | 61 |
| merge | strict | long | 1506 | 1506 | 222 |
| merge | strict | veto | 1728 | 1506 | 0 |
| merge | strict | timing | 1505 | 1505 | 1 |
| merge | strict | preshower | 1728 | 1505 | 0 |
| merge | strict | pz | 1465 | 1464 | 41 |
| merge | strict | layers | 1483 | 1454 | 10 |
| merge | strict | ndof | 1444 | 1423 | 31 |
| merge | strict | chi2 | 1505 | 1423 | 0 |
| merge | strict | rmax | 1488 | 1418 | 5 |
| merge | strict | rIFT | 1476 | 1404 | 14 |
| merge | strict | rVetoNu | 1489 | 1403 | 1 |
| merge | strict | theta | 1486 | 1403 | 0 |
| merge | strict | VetoNu0 | 1625 | 1315 | 88 |
| merge | strict | VetoNu1 | 1583 | 1252 | 63 |

## 固定旧电荷，仅移去一项轨迹cut的敏感性（诊断，不代表可接受修改）

| 方法 | 版本 | 移去cut | 额外通过事件 |
| --- | --- | --- | --- |
| forward | old | pz | 10 |
| forward | old | layers | 0 |
| forward | old | ndof | 23 |
| forward | old | chi2 | 0 |
| forward | old | rmax | 4 |
| forward | old | rIFT | 12 |
| forward | old | rVetoNu | 0 |
| forward | old | theta | 0 |
| backward | old | pz | 15 |
| backward | old | layers | 0 |
| backward | old | ndof | 33 |
| backward | old | chi2 | 0 |
| backward | old | rmax | 3 |
| backward | old | rIFT | 14 |
| backward | old | rVetoNu | 1 |
| backward | old | theta | 0 |
| merge | old | pz | 13 |
| merge | old | layers | 0 |
| merge | old | ndof | 30 |
| merge | old | chi2 | 0 |
| merge | old | rmax | 3 |
| merge | old | rIFT | 13 |
| merge | old | rVetoNu | 1 |
| merge | old | theta | 0 |
| forward | strict | pz | 8 |
| forward | strict | layers | 0 |
| forward | strict | ndof | 28 |
| forward | strict | chi2 | 0 |
| forward | strict | rmax | 4 |
| forward | strict | rIFT | 13 |
| forward | strict | rVetoNu | 0 |
| forward | strict | theta | 0 |
| backward | strict | pz | 15 |
| backward | strict | layers | 0 |
| backward | strict | ndof | 20 |
| backward | strict | chi2 | 0 |
| backward | strict | rmax | 4 |
| backward | strict | rIFT | 14 |
| backward | strict | rVetoNu | 1 |
| backward | strict | theta | 0 |
| merge | strict | pz | 14 |
| merge | strict | layers | 0 |
| merge | strict | ndof | 22 |
| merge | strict | chi2 | 0 |
| merge | strict | rmax | 4 |
| merge | strict | rIFT | 14 |
| merge | strict | rVetoNu | 1 |
| merge | strict | theta | 0 |

## Timing 位置和电荷四组合

| 方法 | Timing Y版本 | 电荷版本 | Timing单cut通过 | 仅替换Timing后的strict final |
| --- | --- | --- | --- | --- |
| forward | old | old | 1326 | 1067 |
| forward | old | strict | 1325 | 1067 |
| forward | strict | old | 1300 | 1072 |
| forward | strict | strict | 1299 | 1072 |
| backward | old | old | 1500 | 1190 |
| backward | old | strict | 1499 | 1190 |
| backward | strict | old | 1457 | 1190 |
| backward | strict | strict | 1457 | 1190 |
| merge | old | old | 1505 | 1236 |
| merge | old | strict | 1504 | 1236 |
| merge | strict | old | 1505 | 1236 |
| merge | strict | strict | 1504 | 1236 |

## 轨迹正负电荷识别（全 fiducial，正确主μ，purity≥0.7）

| 方法 | 版本 | 选择 | truth pz下限 GeV | 上限 GeV | 主μ样本 | 错误sign |
| --- | --- | --- | --- | --- | --- | --- |
| forward | old | final | 0 | inf | 1118 | 10 |
| forward | old | final | 100 | 300 | 303 | 0 |
| forward | old | final | 300 | 1000 | 598 | 3 |
| forward | old | final | 1000 | 3000 | 204 | 5 |
| forward | old | final | 3000 | inf | 12 | 2 |
| forward | old | fixed_final | 0 | inf | 1118 | 10 |
| forward | old | fixed_final | 100 | 300 | 303 | 0 |
| forward | old | fixed_final | 300 | 1000 | 598 | 3 |
| forward | old | fixed_final | 1000 | 3000 | 204 | 5 |
| forward | old | fixed_final | 3000 | inf | 12 | 2 |
| backward | old | final | 0 | inf | 1243 | 12 |
| backward | old | final | 100 | 300 | 319 | 0 |
| backward | old | final | 300 | 1000 | 668 | 3 |
| backward | old | final | 1000 | 3000 | 243 | 6 |
| backward | old | final | 3000 | inf | 12 | 3 |
| backward | old | fixed_final | 0 | inf | 1243 | 12 |
| backward | old | fixed_final | 100 | 300 | 319 | 0 |
| backward | old | fixed_final | 300 | 1000 | 668 | 3 |
| backward | old | fixed_final | 1000 | 3000 | 243 | 6 |
| backward | old | fixed_final | 3000 | inf | 12 | 3 |
| merge | old | final | 0 | inf | 1252 | 13 |
| merge | old | final | 100 | 300 | 320 | 0 |
| merge | old | final | 300 | 1000 | 673 | 5 |
| merge | old | final | 1000 | 3000 | 246 | 5 |
| merge | old | final | 3000 | inf | 12 | 3 |
| merge | old | fixed_final | 0 | inf | 1252 | 13 |
| merge | old | fixed_final | 100 | 300 | 320 | 0 |
| merge | old | fixed_final | 300 | 1000 | 673 | 5 |
| merge | old | fixed_final | 1000 | 3000 | 246 | 5 |
| merge | old | fixed_final | 3000 | inf | 12 | 3 |
| forward | strict | final | 0 | inf | 1078 | 0 |
| forward | strict | final | 100 | 300 | 293 | 0 |
| forward | strict | final | 300 | 1000 | 576 | 0 |
| forward | strict | final | 1000 | 3000 | 197 | 0 |
| forward | strict | final | 3000 | inf | 11 | 0 |
| forward | strict | fixed_final | 0 | inf | 1093 | 0 |
| forward | strict | fixed_final | 100 | 300 | 299 | 0 |
| forward | strict | fixed_final | 300 | 1000 | 584 | 0 |
| forward | strict | fixed_final | 1000 | 3000 | 198 | 0 |
| forward | strict | fixed_final | 3000 | inf | 11 | 0 |
| backward | strict | final | 0 | inf | 1194 | 0 |
| backward | strict | final | 100 | 300 | 306 | 0 |
| backward | strict | final | 300 | 1000 | 645 | 0 |
| backward | strict | final | 1000 | 3000 | 229 | 0 |
| backward | strict | final | 3000 | inf | 13 | 0 |
| backward | strict | fixed_final | 0 | inf | 1210 | 0 |
| backward | strict | fixed_final | 100 | 300 | 312 | 0 |
| backward | strict | fixed_final | 300 | 1000 | 654 | 0 |
| backward | strict | fixed_final | 1000 | 3000 | 230 | 0 |
| backward | strict | fixed_final | 3000 | inf | 13 | 0 |
| merge | strict | final | 0 | inf | 1241 | 0 |
| merge | strict | final | 100 | 300 | 314 | 0 |
| merge | strict | final | 300 | 1000 | 669 | 0 |
| merge | strict | final | 1000 | 3000 | 244 | 0 |
| merge | strict | final | 3000 | inf | 13 | 0 |
| merge | strict | fixed_final | 0 | inf | 1257 | 0 |
| merge | strict | fixed_final | 100 | 300 | 320 | 0 |
| merge | strict | fixed_final | 300 | 1000 | 678 | 0 |
| merge | strict | fixed_final | 1000 | 3000 | 245 | 0 |
| merge | strict | fixed_final | 3000 | inf | 13 | 0 |

