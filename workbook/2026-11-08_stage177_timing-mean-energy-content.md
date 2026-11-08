# Stage177：Timing双端均时的新训练与状态内容对照

## 阶段目标和固定实验

Stage175已实测原队列有可校准Timing均时支持，本阶段按用户Stage172要求对新的表示从头训练，区分新增时间内容与状态/可用性信息，不重跑旧Stage129 Veto四pair或Q89。研究条件限于已开发MC，真实控制尾部和跨时期误差尚未认证；不以MC支持声明可部署精度。

[冻结协议](stage177_energy_ml/protocol.json)固定X62、V66（X+每片strict-reference/range共4状态）、T68（V+两片校准相对均时ns）。原89033/train46575/cal11612/development-test13189/隔离17657全部保持，含所有K、困难、无时间与缺PHYS事例；只对role>0预测，不开reserved/隔离。NaN保持，非0status不输出任何时间或由时间导出的量，不读其他一次方动量。

沿用Stage87原3seed×400轮CPU hist/nthread1和incoming单位权重；各臂独立cal一个全局log-offset。先X三fit精确复现/成本，再V/T六fit，原500次component分组incoming bootstrap及八层正/负/总tail50门不变；T/V为内容对照。低两箱相对传统上95%≤1.05仅非劣效，其他原all/f0≤1.01、五保护≤1.03和尾差上95%≤2pp不变，整体胜出/独立确认仍需更多证据。

本规模约47k×68、9个固定hist fit，使用CPU保留原参考复现口径；不是大GPU训练任务，不借更换tree_method声称基线一致。4CPU/8000MB/max1job，2400CPU秒（pilot400/full1400/audit600），无应用短timeout。

## 已测基线与成本门

X已完成三次从头fit和保存/重载，在全部active上与Stage87 direct_cal的最大绝对log差精确0；无隔离/reserved预测。训练函数41.564462CPU秒/41.917956wall秒，GNU完整46.05CPU秒；调度48CPU秒/55execute wall秒。按两候选臂三倍完整GNU外推276.3CPU秒，通过原成本门，才提交V/T。

```bash
python3 ml/stage177_freeze.py
python3 ml/stage177_ops.py submit --phase pilot
python3 ml/stage177_ops.py collect --phase pilot
python3 ml/stage177_admit.py
python3 ml/stage177_ops.py submit --phase full
```

## 新训练实测与物理结论

V/T分别从头训练各3seed，共加6fit，与X合计9fit/3600轮。训练数和cal数原样保持，保存后重载预测精确；完整全样本和原八层/三尾均已评估，没有挑Good Hit子集或剔除缺时父。全部原配对数字见[配对表](stage177_energy_ml/slab_paired.tsv)。以下比值为log-RMSE，无量纲，越小越好；区间为原条件incoming分组95%区间。

| role | 能量箱 GeV | 对照 | 比值 | 条件95%区间 |
|---|---|---|---:|---|
| 2 | 50–100 | T/X | 1.000496 | [0.993488,1.009126] |
| 2 | 50–100 | T/V | 0.996983 | [0.988673,1.006983] |
| 2 | 50–100 | T/traditional | 2.064298 | [1.765083,2.391093] |
| 2 | 100–200 | T/X | 0.999188 | [0.995259,1.003033] |
| 2 | 100–200 | T/V | 0.998179 | [0.994064,1.001487] |
| 2 | 100–200 | T/traditional | 1.144270 | [1.052788,1.247181] |
| 3 | 50–100 | T/X | 1.002528 | [0.995877,1.009171] |
| 3 | 50–100 | T/V | 0.997941 | [0.991337,1.005005] |
| 3 | 50–100 | T/traditional | 1.945326 | [1.653993,2.264715] |
| 3 | 100–200 | T/X | 0.996298 | [0.992024,1.000866] |
| 3 | 100–200 | T/V | 0.997533 | [0.992882,1.002306] |
| 3 | 100–200 | T/traditional | 0.989835 | [0.920503,1.063122] |

**新增两片均时没有在这一次固定表示中兑现有统计支持的双低能改善。** 开发test的T/V分别0.997941、0.997533，两个95%区间均包含1；T/X最低箱1.002528、第二箱0.996298。最低箱仍明显差于传统（T/traditional=1.945326，95%[1.653993,2.264715]）；第二箱点估计0.989835，但上95%=1.063122，仍未过1.05非劣效门，不能据点估计声称胜出。

| test T层 | RMSE上95% | 原门 | RMSE通过 | 三尾同时通过 |
|---|---:|---:|---|---|
| E50_100 | 2.264715 | 1.05 | False | True |
| E100_200 | 1.063122 | 1.05 | False | True |
| all | 1.000262 | 1.01 | True | True |
| E200_inf | 1.000357 | 1.03 | True | True |
| pz50_100 | 1.004475 | 1.03 | True | True |
| pz50_100_trueE200 | 1.006187 | 1.03 | True | True |
| high_y | 1.003989 | 1.03 | True | True |
| unconfirmed | 1.005791 | 1.03 | True | True |

原[门表](stage177_energy_ml/slab_gates.tsv)的cal/test X、V、T joint均false；Stage87冠军不替换。test中T最低箱相对X正tail50点差+0.546448pp、第二箱负tail50点差+0.235018pp，仍按原95%上界而非仅点差验收。其他六层RMSE保护和八层三尾对本T均通过，但不能补偿两低箱主门失败。

这一区间只覆盖原已开发输入上的incoming统计、固定模型及校准；没有认证独立生成族、重训不确定度、真实条件/控制校准系统误差。真实μ校准的大尾/跨期误差未被本结果解决。结论限于这两片均时的固定X/V/T表示，不推广为所有时间/波形均无信息，也不因阴性调整门、再扫窗口或增加模型容量。

## 输入占位值的实际独立核对

[附加审计合同](stage177_energy_ml/sentinel_audit_addendum.json)在原audit600CPU秒内，只实际重读Stage174同三源各4096例，验证非物理χ²与精确-999位置是否混入μ控制；没有改拟合输入或扫新样本。单独的χ²上cut可能容许负χ²，因此先作实际检查，若有污染必须停止解释并另冻校准修正，不能静默删尾。

- data8006：4096输入/2998原控制，负χ²0、非有限χ²50、Trig x/y精确-999 0，原控制中非物理值0例。
- MC100012：4096输入/3611原控制，负χ²0、非有限χ²401、Trig x/y精确-999 0，原控制中非物理值0例。
- data15838：4096输入/2587原控制，负χ²0、非有限χ²44、Trig x/y精确-999 0，原控制中非物理值0例。

此次控制不受该实现缺口影响，原校准系数/实际控制/物理结果不变。后续入口补上有限非负χ²和明确位置占位排除；没有把合法负rawQ或有符号坐标中的-1当缺失。原audited62对非负χ²、pz0正域、计数、charge sign、producer 999999位置及合法signed raw的typedNaN规则保持。

## 独立验证与计算/存储

[独立验证](stage177_energy_ml/independent_validation.json)实际重载9个模型，在全部active独立重建ensemble和cal-offset，全部精确；cal/test×8层×3臂的48组RMSE/正负总tail50中心指标逐项标量核对，最大差1.42e-14。隔离/reserved预测均0。

调度3start全部exit0、0live，累计170.0CPU秒、155.0聚合execute wall秒；实际RequestCpus=[4]、RequestMemory=[12000]MB，在原2400CPU秒内。GNU成本如下（子步骤不再与调度CPU相加）：

| GNU任务 | CPU秒 | wall秒 | maxRSS KiB |
|---|---:|---:|---:|
| audit_time | 12.79 | 15.46 | 427340 |
| full_time | 106.63000000000001 | 73.94 | 580824 |
| pilot_time | 46.05 | 48.97 | 386828 |

[存储账](stage177_energy_ml/storage_cleanup.json)保存9模型和预测于`ml/artifacts/stage177/`，合计12146630B；来源64逻辑版本/32独立内容原字节归档重读，删131145585B重复运输/日志/提交文件。仅在本stage队列Iwd无引用后清理`~/condor/nu_muAnalysis/stage177/`，Stage54原12项大小/mtime保持。原事件ROOT不改，无新G4/新独立ν/GPU或role改变。


收尾命令：

```bash
python3 ml/stage177_ops.py collect --phase full
python3 ml/stage177_ops.py submit --phase audit
python3 ml/stage177_ops.py collect --phase audit
python3 ml/stage177_finalize.py
python3 ml/stage177_document.py
python3 ml/stage177_validate_docs.py
git diff --check
```

## 下一步与分支边界

这一次新Timing均时表示已完成训练和原完整评估，按未达标结束，不扩同族窗口/模型网格。Stage176继续实际S0过面/出生位置小pilot，先闭合和成本后才原其余11父；若面前/后源分解在同窗响应有明确机制支持，再寻找可测伴随量，不能直接部署真位置或重复计入已测μ能量。匹配实际DAQ的同窗actual/noiseless/no-clip响应仍是新问题，不以本均时阴性替代它。

只有真实新高幅参考/新支持到来才考虑hybridQ或Q+T；普通Ecal双量程不能移植到原单路MC。弱信号上游backscatter须真实status0/采集范围/校准支持；实际背景、效率、全生成加权及相关辅助约束缺口继续，外部乳胶/独立确认仍需实际输入。整体目标未完成，最低能优于传统及物理精度仍未实现。
