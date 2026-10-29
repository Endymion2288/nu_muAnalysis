# 能量 ML 首轮执行合同

日期：2026-10-29。对应路线图 R0/R1，随后进入 R2。顺序固定为物理基线、
BDT 变量组消融、同输入 MLP/ResNet/TabM、Deep Sets、空间关系模型、系统误差与闭合。

## 样本、来源与划分

`ml/configs/files.tsv` 从阶段 09 已验收的 342 个共同来源生成，不恢复缺失 index 291。
主版本固定官方 `d32b0ff3` merge / without-IFT、TI12MC04、FASERNU-04、
OFLCOND-FASER-06、s0014；使用现有 `cuts.yaml` 的 20 项 MC/native-reduced-charge
选择与最高 pz leading-track。保留原 truth pz > 100 GeV fiducial。

nominal 六 run 为 200082/200083/200089/200093/200094/200100；200080 单独留作
SIBYLL flux challenge。不同 flux 不是不同 interaction generator。

按 π/K/charm 与原 RDO 的五位生成范围配对早期/2024 run，保守地放进同一组。
这不声称已证明跨时期文件是否复用同一生成事件。种子 20261029，在每种来源内
先打乱组再按 60/15/10/15 的边界划分。再检查 train/validation 精确 truth
动量与相互作用位置的重复；不能把此检查当成完整生成谱系证明。

| 分区 | 文件 | 来源组 | 已有选择预期 events |
|---|---:|---:|---:|
| train | 178 | 91 | 54,196 |
| validation | 44 | 22 | 13,375 |
| calibration | 32 | 16 | 9,727 |
| locked test | 43 | 22 | 12,488 |
| SIBYLL challenge | 45 | 45 | 15,144 |

上述为阶段 09 计数，不冒充本次重新提取结果。各源完整路径、期望计数和分区全部
在 manifest 内。validation 用于 early stopping 和消融开发；calibration/test
不打开做模型选择。本轮不能据 validation 排名宣称最终泛化精度。

## 标签、输入与单位

新增列全部通过合并 YAML 交给已有 `Analysis::Define`，不改框架 C++。
`ML_truth_E_GeV = sqrt(px²+py²+pz²+m²)/1000`，所有分量来自 truth 索引 0。
官方 dumper 将前十个 TruthParticle 按容器顺序写入，无重新排序；需要逐文件验证
索引 0 的 PDG、barcode、分量与 `truth_P`，选后要求 |PDG|=14、E>0 且有限。
上游生成记录完整母子谱系尚未重新审计；不能把任意 truth 元素当入射 ν。

`ml/configs/baseline.yaml` 是唯一模型输入允许清单，同时给出表达式和单位。
truth、t_*、ID、run、权重、flux 标签、fold 均只用于标签/诊断/划分。
禁止输入 fudged、Track_hitSet、Track_nMeasurements。后两者在新官方产品中仍有
对齐问题。μ 的 p 来自 `Track_p0` /1000，索引保持最高 pz；已有 pz/0.8 也单独报告。

| 版本 | 累加输入 | 标量数 |
|---|---|---:|
| F0 | μ p | 1 |
| F1 | 方向、电荷、拟合质量、位置/传播 | 17 |
| F2 | nClusters0..3、SpacePoints、TrackSegments、longTracks | 24 |
| F3 | 原生 scintillator 电荷和两层 reduced charge | 37 |
| F4 | 常规 Calo 四通道及 total E_EM | 42 |
| F5 | SpacePoint 全局 x/y 均值、RMS 宽度 | 46 |

F5 只是全局横向矩，**不是**按 station 分组的拓扑，不能据此验收 R4。
没有新增几何边界或截断点数。未使用 Track_nMeasurements、hitSet 或任何真值边。
status 保留为诊断元数据，不在尚未核实各状态语义时自动当成回归特征。
非有限特征逐列计数并转为 NaN，采用 XGBoost 原生 missing handling；不删除事件。
非法标签或主 p 直接使提取验收失败。

长度单位 mm，原生动量 MeV→GeV，电荷 pC。常规 Calo E_EM 是 EM 标尺，
按官方 dumper 能量为 MeV 的实现转为 GeV；不等同强子能量，不裁剪负的读出值。
原生 2024 data 使用 CaloLo/CaloHi，尚未完成双增益合并与 MC 匹配校准，
本轮 MC Calo 模型没有宣称可部署到 data。CaloNu 单独留待匹配样本。

## 权重与损失

首个 200093 文件 10,000 events 的 `GenWeights=[1]`、`CrossSection=1`。
官方生产脚本没有传 `--genie`；dumper 在未启用 genie/fluka 权重时写常数 1。
因此本轮明确为 **unit-weight diagnostic**，不能把文件数隐含配比当作物理 flux。
恢复各源生成 luminosity/flux 配比是正式 R2 结论的前置依赖。

比较 p、p/0.8、原 pz/0.8、train 拟合的 `a*p`（最小化 log-MSE）、F0 p-only
XGBoost；再逐组累加与 F5 leave-one-group-out。所有树采用同一配置、一个固定
seed、direct log E / residual log(E/p)、validation early stopping。
当前是一次配置的起步实验，不是已完成 20 trials 或 3–5 seeds 公平预算。
不将 Ehat 截断到 truth 范围，也不强制 Ehat≥p。

预注册 energy bins 为 [100,200,400,800,1600,3200,6400] GeV；范围外另记，
N<100 的格不用于主 macro log-RMSE。报告 median/mean bias、R68、log-RMSE、
relative RMS、|r|>0.5/1 尾部。主差值区间按同一来源组配对 bootstrap 500 次；
区间只描述给定已拟合模型的 validation 抽样，不能代替训练 seed 波动和独立 test。

## 执行与验收

```bash
source AnalysisZipFramework/setup.sh
python3 ml/make_manifest.py
python3 AnalysisZipFramework/scripts/export_ml_dataset.py \
  --input <official-merge.root> --index <stage09-index> \
  --executable build/analysis --threads 1 --output <cache.npz>
condor_submit AnalysisZipFramework/submission/ml_extract.sub
# 仅在全部缓存通过来源、计数和事件键验收后，通过 HTCondor 运行：
python3 ml/train_bdt.py --output-dir workbook/stage13_energy_ml \
  --model-dir ml/artifacts/stage13
```

提取只读取已有 PHYS；临时 ROOT、eventID_pass 写在 scratch，核对阶段 09
全部 cutflow 和阶段 10 精确最终事件键后删除，最终只保存标量 NPZ。
报告并保留配置、完整输入清单和聚合质量数据；不新增 xAOD、不做全文件 SHA。
1/2/4 CPU 实测见阶段报告；批量每作业 1 CPU、1800 MB RAM，避免嵌套 BLAS 线程。

R2 仍须完成物理权重、按来源/时期/电荷/能量的条件诊断、容量/学习曲线、重复 seed、
条件置乱和 primary μ matching/oracle 后，才讨论稳定的物理信息增益。
