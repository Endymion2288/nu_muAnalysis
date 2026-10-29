# 利用电子探测器多变量重建入射 νμ 能量：研究路线图

版本：2026-10-29。适用仓库：`nu_muAnalysis`；调研起点为 `80d7827`。

**建议主线：固定物理样本与评价方法 → 建立 μ 动量基线 → 用 BDT 检验新增信息 → 比较 MLP、表格 ResNet、TabM → 用 Deep Sets 检验空间拓扑 → 有证据后比较 GNN/Transformer → 完成系统误差与物理测量闭合。**

最值得回答的问题是：在已经知道重建 μ 动量、方向和探测器运行条件以后，其他电子读出是否仍提供可泛化的强子能量、能量损失或 shower 泄漏信息？架构比较服务于这个问题。当前没有训练结果，不能预先指定最终最佳模型，也不能承诺某个能量分辨率。

本文将你提到的“Calomu”暂按仓库实际存在的 **CaloNu** 理解，同时纳入下游常规 **Calo**。二者是不同探测器。若实际指另一个读出，先更新变量字典即可，其他研究步骤仍可沿用。

## 1. 物理目标、可检验假设与研究边界

研究对象首先固定为本仓库现有选择覆盖的 **νμ/反νμ CC**，分别保留电荷符号与时期信息。第一阶段保持现有 cut 和 leading-track 最高 `pz` 定义；先测量能量估计的改进，再研究放宽选择。改变选择、tracking 和回归器是三个独立实验因素。

对于高能 CC 事件，可用近似关系理解信息来源：

\[
E_\nu \simeq E_{\mu,\mathrm{vertex}}+E_{\mathrm{had}},\qquad
y_{\mathrm{inel}}\simeq E_{\mathrm{had}}/E_\nu.
\]

但 spectrometer 测量的 μ 动量位于相互作用点下游，已包含材料中的能量损失；而强子 shower 的大部分可能未被电子探测器完整测量。cluster 数和闪烁体电荷是 shower/几何代理量，不是可直接相加的强子能量。因此必须检验相关性中有多少来自真实事例信息，有多少来自训练谱、材料位置和选择。

这里的非弹性度 `y_inel` 与原分析中的中微子快度 `yν` 是两个不同变量，后续分层和图轴分别标明。

| 假设 | 具体实验 | 可以支持的结论 |
|---|---|---|
| H1：新增电荷与占有率包含超出 μ 运动学的信息 | 在相同事件、权重和划分上进行变量组消融 | 哪些读出提供独立预测增益 |
| H2：空间分布比 station 总计数更有信息 | 同一组 SpacePoint 输入，比较手工矩、Deep Sets、GNN/attention | 增益来自拓扑还是仅来自计数 |
| H3：改进能跨 flux 与相互作用模型保持 | 分别做 flux 先验、interaction、shower 模型测试 | 改进是否依赖特定模拟假设 |
| H4：CaloNu 提供额外可见能量信息 | 在相同 CaloNu 事件上比较含/不含 CaloNu 输入 | CaloNu 读出的条件增益；不能由不同几何间的差异代替 |
| H5：重建进步改善最终测量 | 在相同 truth bins、背景和 nuisance 下比较闭合与总不确定度 | 是否值得替换已有分析的重建观测量 |

潜在研究成果包括：电子探测器中新增信息的定量测量、可靠的能量估计器、生成器与探测器稳健性、对能谱/二维测量的实际收益。已有 FASERν 乳胶分析已使用 ML 重建能量，不能把“首次用 ML 重建 FASER 中微子能量”作为创新点。[P1–P3]

## 2. 已有证据与本次 ROOT 小样本核查

### 2.1 仓库已有生产和分析规模

阶段 09/10 已记录并验证：342 个共同输入文件、3,374,987 个未选择事件、383,670 个 truth-fiducial 事件；完整选择后的 forward/backward/merge 分别为 **92,937 / 103,985 / 104,930 events**。这包含替代 flux 样本 SIBYLL。

排除 SIBYLL 的六个 nominal run 为 `200082/200083/200089/200093/200094/200100`，共 297 个文件、2,934,203 个未选择事件、323,636 个 truth-fiducial 事件；完整选择的 backward/merge 为 **88,965 / 89,786 events**。以上均为已有未加权计数，不能直接作为按真实 flux 配比的产额。

已有官方 merge 固定在 `d32b0ff3`，使用不含 CaloNu 的普通几何、without-IFT maker。原 index 291 的共同缺失仍需保留记录，不能在新的 train/test 清单中悄悄恢复或更换重建。

### 2.2 本次实际读取的文件

从公开 EOS 直接读取下表每个文件的 schema，并扫描**前 128 个未选择事件**。没有将 ROOT 或逐事件训练数据复制进 Git。

| 文件/样本 | 文件 entries | 分支数 | 本次扫描 events | 用途 |
|---|---:|---:|---:|---|
| SIBYLL π，200080，s0014，已有 bck PHYS | 10,000 | 426 | 128 | 早期普通 MC schema |
| EPOS π，200093，s0014，wo_caloNu，已有 bck PHYS | 10,000 | 487 | 128 | 2024 crossing-angle、普通几何 |
| EPOS π，200139，s0015，CaloNu，已有 bck PHYS | 10,000 | 487 | 128 | CaloNu 专用分支 |
| 2024 data，run 16000，r0022，首个 PHYS | 868,756 | 553 | 128 | 真实 data 读出兼容性 |

输入完整路径见 [`inputs.tsv`](../workbook/stage11_energy_ml/inputs.tsv)；完整 schema 和原始单位下的汇总值见 [`MC schema`](../workbook/stage11_energy_ml/schemas.tsv)、[`MC profiles`](../workbook/stage11_energy_ml/branch_profiles.tsv)、[`data schema`](../workbook/stage11_energy_ml/data16000/schemas.tsv)、[`data profiles`](../workbook/stage11_energy_ml/data16000/branch_profiles.tsv)。

这些现成 bck PHYS **不是**阶段 06–10 的新官方 merge 产品，不能把它们的 schema、轨迹数或计时无条件迁移到新生产。本会话为 macOS/ARM64、ROOT 6.40.02；lxplus SSH 认证未成功，EOS 用户目录的官方 merge 返回权限错误。公开实验目录可读，因此完成了上述独立核查。正式训练前仍须在 lxplus 对最终选定生产重新审计。

### 2.3 对路线有直接影响的实测发现

1. 三个 MC 和 data 都有 `nClusters0..3`、`SpacePoint_{x,y,z}`、`TrackSegment_*`、`Track_*` 和闪烁体读出。SpacePoint 三个坐标的向量长度在各自 128 个事件中均一致。说明无需新增 hit 生产即可尝试 point-set 表示；这还不证明它们是无歧义的真实粒子轨迹。
2. 200093 虽然是 **wo_caloNu**，仍包含 61 个 `CaloNu*` 分支；`CaloNu_total_E_EM` 在 **128/128 events 中为 0**。200139 相同字段为 **94/128 零值、34/128 非零值**。分支存在与探测器物理可用性必须分别判断。
3. 三个 MC 有 64 个常规 `Calo*` 分支；data 16000 无这些原生单增益分支，改为 **61 个 CaloLo + 61 个 CaloHi**。不能将高低增益当两份能量相加，也不能只靠改名证明响应已校准。
4. `Track_hitSet` 长度相对 `Track_pz0` 不一致的事件为 **27/128、21/128、26/128**；data 前缀为 0/128。阶段 06 已从官方 dumper 定位过此类筛选前填充分支风险。当前禁止用 `Track_hitSet[i]` 直接配对第 i 条轨迹。`Track_nMeasurements`、`Track_isForward` 在本次四个旧 PHYS 中均缺失；新官方产品需另查。
5. 默认 `output_columns.yaml` 明确列出了 **0 个常规 Calo、0 个 CaloLo、0 个 CaloHi、61 个 CaloNu、43 个 `t_*` 字段**。常规 Calo 是原生输入，却未默认保留；`save_all_defined_columns` 不会自动挽救未选中的原生列。应新增 ML 专用精简输出配置。
6. MC 200139 前缀的 `SpacePoints` 最大值为 **8,670 points/event**；200080 为 **8,021**。全样本尾部未测量。直接对所有点使用全连接 attention，内存随点数平方增加，必须先测占有率和保留信息的压缩策略。

以上是输入可用性与程序问题的证据。128-event 前缀、不同 production 和未经匹配的 data/MC，均不足以支持能量分辨率、物理关联或泛化优劣的结论。

## 3. 变量字典与分层输入

以下字段名已经在代码或本次 ROOT 核查中找到；“可用”仍要求有效数值、正确物理语义、相应几何和 data 可复现处理。

| 输入组 | 具体字段或拟派生量 | 物理作用与处理 |
|---|---|---|
| μ 运动学 | `Track_p0`, `Track_px0/py0/pz0`, `Track_charge`；leading 的 p、pT、θx、θy、θ | p 为主信息；原始 track 动量按仓库约定为 MeV，模型统一转 GeV；保留符号 |
| μ 拟合质量 | `Track_Chi2`, `Track_nDoF`, `Track_nLayers`, `Track_PropagationError` | 区分真实 shower 信息与 μ 动量测量误差；先拒绝无效 χ²/nDoF；错误码作为质量诊断 |
| μ 几何与传播 | `Track_x0/y0/z0`、`Track_X/Y_atVetoNu`、`*_atVetoStation2`、`*_atCalo`、`Track_r_atMaxRadius` | 单位 mm；材料路径、边缘泄漏与接受度；位置输入须检查 flux 先验依赖 |
| 全事件 tracking 占有率 | `nClusters0..3`, `SpacePoints`, `TrackSegments`, `longTracks` | 区分 SCT cluster 数、3D spacepoint 数、轨迹命中数；三个量不可互称“hit 数” |
| station 形状 | 从 SpacePoint 坐标按真实几何分 station：N、中心、横向宽度、分位数、距 leading track 的径向矩 | 先用可解释汇总；z 边界来自几何，不手猜；无逐点电荷或时间时不虚构这类输入 |
| 多轨迹/segments | `Track_*`、`TrackSegment_Chi2/nDoF/x/y/z/px/py/pz` | 次级活动与拓扑；不能把 segment 动量和完整 track 动量一律当同等可靠；先查向量对齐 |
| 上游 VetoNu 两层 | `VetoNu{0,1}_{charge,raw_charge,reduced_charge,peak,width,status}` | 背散射、活动与质量；最终选择已要求 reduced charge <30 pC，动态范围受到截断 |
| 下游 Veto | `Veto10_*`, `Veto20_*`, `Veto21_*`；时期允许时的 `Veto11_*` | 分别保留、和/差/不对称；Veto11 缺失时是 fallback，不能当独立测量 |
| Timing/Preshower | `Timing{0..3}_charge`、上下半区和差；`Preshower{0,1}_charge` 等 | MIP/shower 活动与几何；时间、幅度、宽度的单位/MC 建模须单独核实 |
| 常规 Calo | `Calo{0..3}_{charge,nMIP,E_dep,E_EM}`、`Calo_total_*`；data 的 `CaloLo/Hi*` | 优先经校准的通道能量与总量、能量比例和横向不对称；EM 标尺不能直接等同强子能量 |
| CaloNu | `CaloNu{0..3}_{charge,nMIP,E_dep,E_EM}`、`CaloNu_total_*` | 只在真实安装且模拟匹配的时期使用；同事件输入消融是首要实验 |
| 有效性与饱和 | status、缺失 mask、低/高增益交叉校验、传播失败 mask | 不是零值填充；先查 status 位定义。区分无探测器、无信号、坏读出、饱和 |

`E_EM/E_dep`、波形时间、peak、width 的**精确单位与校准版本本次未确认**。profile 文件保留原始数值；正式特征字典必须记录单位、变换、出处和适用时期后才可训练。

station 编号与 IFT/下游三站的对应应从所选几何核实；maker 的 without-IFT 描述轨迹策略，不代表 station 0 的全事件占有率自动不可用。本次 schema 未见可直接使用的 track 参数协方差/动量误差分支；如需该信息，应另查 maker 并有针对性地扩展 ntuple，不能把 χ²/nDoF 当作动量误差的等价物。

建议固定六个逐级特征版本，并做 leave-one-group-out 验证：

- **F0**：leading μ 的 p；另设 p、θ、charge 的小基线。
- **F1**：F0 + μ 方向、质量、位置、传播信息。
- **F2**：F1 + 四站计数与事件 multiplicity。
- **F3**：F2 + VetoNu/Veto/Timing/Preshower 有效电荷及质量 mask。
- **F4**：F3 + 常规 Calo；CaloNu 样本另做 F4 + CaloNu 对照。
- **F5**：F4 + 从 SpacePoint/segments 导出的形状；再与同一对象集合的学习表示比较。

F0–F5 的先后累加会受到组间相关性影响；同时比较从完整模型去掉每组后的损失。SHAP 或 importance 只能辅助解释，不能替代独立测试集上的消融，更不能直接解释为因果贡献。

## 4. 标签、真值泄漏与几何管理

### 4.1 标签必须是 Eν

当前 `truth_pz_nu = truth_pz[0]/1000` 是纵向动量，不能直接改名为精确能量。推荐新增 MC 标签：

\[
E_\nu^{\rm true}=\sqrt{p_x^2+p_y^2+p_z^2+m^2}/1000\quad[\mathrm{GeV}],
\]

其中四个量来自同一个入射 ν 的 truth 索引。对质量可忽略的入射 ν，核实 `truth_P[0]` 的语义后可用其除以 1000，并与上式交叉检查。必须验证 `truth_pdg[0]`、向量对齐、母子关系/生成记录约定、正能量与有限值；truth 数组中还包含其他末态和核相关对象，不能将全部 truth 元素当中微子。

同时记录 truth E 与现有 truth pz 的差异。第一轮为复现仓库保留原有 `truth pz>100 GeV` fiducial；后续若改成 `Eν>100 GeV`，作为独立的 fiducial 定义变更报告。

### 4.2 模型输入采用显式允许清单

以下只用于标签、权重、划分或诊断，**不得作为能量回归器输入**：

- `truth_*`, `truthM_*`, `truthd*`, `truthPdg/Barcode/Particle*`、`pTruthLepton`、`t_*`、`isFiducial` 等匹配/真值字段。
- `truth_dec_*_nu`、`is_cc`、`decay_box/lead`、`inCaloNuPMT` 等由真值派生的列。即使配置标为 ALL 或 data 中有占位分支，也仍然禁止。
- `GenWeights`、`CrossSection`、run/eventID、文件名、generator 标签、fold ID，以及由目标/生成样本决定的缩放量。
- MC 专有的 `*_fudged`：默认不使用；只有明确证明其校准能在 data 上同样定义且无 truth 依赖，才作为新的受审计特征版本。

日期、BCID、触发位、run 和 `is2024Period/isCaloNuPeriod` 首先作为分层与质量控制信息。几何/探测器可用性若作为模型条件，必须明确部署时已知，比较分时期模型和共享模型；不将具体 run number 作为连续数值输入。

### 4.3 两条探测器分支

- **A：普通 FASERν 几何。** 先使用已完成官方 merge 的 nominal 六 run，SIBYLL 200080 留作 flux-domain 检验；能量响应训练需重新提取所需重建列，阶段 10 的七列精简事件文件不够训练。
- **B：CaloNu 几何。** 从 `200139/200140/200146` 等与时期匹配的 MC 和相应 data 起步，先验证 source、maker、conditions 与信号校准；本次只读了 200139 的一个现成文件，不代表已验收全部样本。

不能把“普通几何不含 CaloNu”和“CaloNu 几何含 CaloNu”的性能差直接归因于新增读出，因为材料、接受度和谱也改变。B 分支中必须在**相同事件和选择**上做有/无该输入比较。

## 5. 模型选择与优先级

| 方法 | 本项目中的角色 | 建议起点（均为待调参设定） | 启动条件/主要风险 |
|---|---|---|---|
| 物理/一维基线 | 必做比较锚点 | p、既有 p/0.8、训练集拟合的 a·p，以及只用 p 的一维回归 | p/0.8 是已有选中样本的经验 proxy，不是普适的 y=0.2 |
| BDT/GBDT | 第一主模型 | XGBoost 或 LightGBM 选一个主实现；depth 3–8、学习率 0.02–0.1、early stopping | 适合异质表格；树对训练能量范围外的外推较弱 |
| 全连接 MLP | 深度学习基础对照 | 2–4 层、宽度 128/256、AdamW、0–0.2 dropout | 同样预处理、信息与调参预算，排除“不够强的 NN 基线” |
| 表格 ResNet | 重点比较 | 2–4 个残差块、宽度 128/256、LayerNorm | 这里是表格残差网络，不是 ResNet-50 图像网络 [M2] |
| TabM | 重点比较 | 使用作者实现的小模型，比较单模型与参数共享集成 | 适合约 10^5 量级的汇总变量；须与同预算 BDT 比 [M3] |
| FT-Transformer | 表格 attention 对照 | 2–3 块、token 维 64/128、4 个 attention heads | 每个标量有特征身份；不会自动利用真实 hit 几何 [M2] |
| Deep Sets / PFN 风格 | 第一种对象集合模型 | 分别编码 SpacePoint、segment/track；sum+mean+max pooling，与全局变量融合 | 参数较少、置换不变；先判断计数以外的信息是否有用 [M5–M6] |
| GNN / ParticleNet 风格 | 空间关系候选 | 2–4 层 message passing、k=8/16 的局部或相邻 station 图 | 用真实重建坐标建边；禁用真值边与错位 hitSet；kNN 构建成本也要测 [M7,M9] |
| 集合 Transformer / ParT 风格 | 跨 station/探测器关系候选 | station 内压缩 token，几何关系编码，与 μ/电荷 token 融合 | 不照搬 jet 的 η–φ 关系；大 N 下 attention 二次开销 [M8] |
| TabPFN-2.5 等表格预训练模型 | 有限预算的补充对照 | 本地可运行版本，先在共同小子集测试，再测全量可行性 | 2026 版文献描述的原生设计规模为 50k×2000；更大规模设置另核实，不能沿用旧版“只支持分类”的限制 [M11] |

这里的排序是**当前数据表示与实施成本下的工作优先级**，不是预测最终排名。2022 年的表格 benchmark 支持先建立强 GBDT；2025 年 TabM/TabArena 又表明，更强的 MLP、集成与训练预算会改变比较结果。因此不能简单宣称“表格任务永远 BDT 最好”。[M1–M4]

先区分两种比较：**同输入比较架构**，以及**同架构增加信息**。如果 GNN 用了完整空间点而 BDT 只有 μ 动量，结果只能证明整套方法不同，不能证明图架构更优。至少提供 BDT+空间矩、Deep Sets+同一对象集合、GNN+同一对象集合三个对照。

## 6. 回归目标与概率输出

### 6.1 第一轮统一目标

推荐统一预测 `t = log(Eν/GeV)`，先比较 log-MSE；再用 Huber(log E) 检查离群敏感性。不能让不同架构使用不同损失、不同预处理和不同训练谱后直接排名。

增加一个容易解释的残差模型：

\[
\hat E_\nu=p_{\mu,\mathrm{reco}}\exp\left[g(\mathbf{x})\right],\qquad
t_{\rm residual}=\log(E_\nu^{\rm true}/p_{\mu,\mathrm{reco}}).
\]

它使模型专注于对 μ proxy 的修正。拟合范围与 μ 基线相同，只在有效正 p 的事件使用；允许负修正，不能因为重建 μ 动量可能上涨，就强制逐事例 `Ehat≥p_reco`。也不在训练后截断到 truth 能量范围来制造更好的尾部。

log-MSE 的最优解对应条件 log 均值，指数变换后通常不等于条件能量均值；log-MAE 对应 log 中位数。报告清楚点估计的含义，需要均值时另做训练/校准集上的处理或使用完整条件分布。

### 6.2 第二轮概率输出

优先让最佳 BDT 和最佳 NN 各预测 `q0.16/q0.50/q0.84`，再补 `q0.025/q0.975`，通过独立 calibration 集处理 quantile crossing 和覆盖校准。NN 另训练 3–5 个独立 seed 作为 ensemble 诊断。[U1–U2]

只有明显非高斯/多峰且分位数不足以满足下游需求时，再比较 mixture density network 或条件 spline flow。输出 `p_train(Eν|x)` 是训练先验下的条件分布；必须记录训练谱和选择。[U3]

**不要把逐事例 posterior 直接相加当作无偏能谱。** 后验中含训练先验；能谱拟合优先采用独立 MC 建立的响应矩阵。若采用 posterior/likelihood 比方法，需显式处理训练先验、选择效率、背景和 nuisance，并单独验证闭合。

## 7. 数据划分、权重与公平比较

### 7.1 先固定最小统计单位

每条记录保存物理来源键：生产 campaign、原始生成/RDO 来源、run/eventID、重建版本、几何与系统变体。相同生成事件的 forward/backward/merge、重建变体和数据增强必须进入同一 partition。

先按源文件/原始生成批次分组，在各物理来源和能量范围上检查覆盖；若生产中不同文件或 run 重用同一批生成事件，建立关联并一起分组。不能把来自同一个事例的两个 track 当作两个独立训练样本，也不能仅凭 run 不同就判定变体独立。

建议开发阶段分成 **60% train、15% tuning-validation、10% calibration、15% locked test**。这些是待实施的分组比例，并非本次已经划分。按实际文件组调整比例并报告实际计数/权重；所有变换、填充值、标准化和 feature selection 仅从 train 拟合。

最终响应测量另需独立 MC。样本不足时采用明确的外层交叉拟合方案，并冻结 data 与 MC 一致的模型路由；不能为响应 MC 用 out-of-fold 模型、为 data 随意换成全样本重训模型却不验证两者差异。

### 7.2 区分 flux、interaction 与 detector 变化

| 检验 | 本仓库起点/所需输入 | 必须避免的误解 |
|---|---|---|
| nominal IID | 六个 nominal 普通几何 run，来源配比有权重 | π/K/charm 不能按文件数随意混合 |
| flux 先验变化 | SIBYLL π 200080、π/K/charm 组成变化、能谱倾斜 | SIBYLL vs EPOS 主要测试上游 hadron production/flux，不等于 GENIE vs 另一 interaction 模型 |
| interaction 模型 | GENIE 模型/reweights、可用时匹配的 NuWro 或其他替代样本 | 目前未确认本仓库有匹配替代 interaction 样本；没有就报告这一缺口 |
| shower 模型 | 与文献/生产对应的 Geant4 physics-list/核数据变体 | 不能用改变 flux 配比替代材料中 shower 系统误差 |
| period/geometry | 2022–23、2024 wo-CaloNu、2024 CaloNu；相应 calibration | data run 16000 与普通 MC 不能直接匹配 |
| tracking | 同源官方 backward/merge 配对结果 | 主回归先固定一种；不同模式的共同通过集合和各自完整选择分开报告 |

主训练采用可解释的 nominal 物理权重；另做训练能谱在 log E 上较平坦的模型，检查 prior 敏感性。重加权只能在共同支持区间使用；不能把极少数高能事件复制后当作新增独立统计。

记录每个来源的 N、Σw、Σw²、有效统计量 `Neff=(Σw)²/Σw²`。先核实 `GenWeights` 与 cross section/luminosity 的具体定义；本次三个前缀的 GenWeights 均为 1，不足以证明所有 production 都如此。若有负权重，单独记录符号和计数，不能直接使用只对正权重定义的分位数或把符号丢弃。

先跑每模型一个可复现配置，再按相同 trial 上限和实测 CPU/GPU-hours 两种口径记录调参成本。推荐起步各 20 trials、最佳配置 3–5 seeds；数值是预算建议，不是已经消耗的资源。OOD challenge 集和 locked test 均不参与反复调参。

## 8. 评价指标、图表与进入下一阶段的标准

定义 `r=(Ehat−Etrue)/Etrue`，每个真值能量 bin 报告：

- **偏差**：median(r)，同时给 mean(r) 和统计区间。
- **核心分辨率**：`R68=[Q84(r)−Q16(r)]/2`；不能将它与 RMS 混称。
- **总体误差**：log-RMSE、相对 RMS；后者保留非高斯尾影响。
- **尾部**：`P(|r|>0.5)`、`P(|r|>1)`，以及 95% 残差区间。
- **概率质量**：68%/95% coverage、区间宽度，适用时 pinball loss、NLL/PIT。
- **成本**：提取、预处理、训练、推理分开测墙钟、CPU、RSS、GPU 显存与 events/s。

建议主排序指标为真值 log E 分箱的 macro log-RMSE：每 bin 先求加权 log 平方误差，对有效 bin 等权平均后开根号。它同时惩罚偏差和宽度，并避免训练谱低能多数完全支配排名。另保留按物理权重积分的整体结果。

开发用能量边界可从 `[100,200,400,800,1600,3200,6400] GeV` 起步，最终按 train/validation 的支持范围冻结；不足统计的 bin 合并或标记未测量，不能在见到 test 表现后改边界。每格报告 N/Neff，建议主结论 bin 至少 Neff≈100，否则以宽区间呈现。

必须给出：Ehat–Etrue 响应图；偏差/R68/尾部随 E；按 truth z、r、非弹性度 y_inel、快度 yν、ν/反ν、π/K/charm、几何、占有率和拟合质量分层；generator/period challenge 图；同事件残差差异；coverage；资源成本。truth z/y 可用于诊断分层，不能进入预测器。

统计比较用同事件、同来源分组 bootstrap，保留模型间相关性。起步 500–1000 次重采样，报告实际稳定性；稀少异常事件保留并调查物理原因和程序原因。

下列是**建议事先登记的研究门槛**，不是实测结果或通用物理标准：

| 决策 | 建议标准 |
|---|---|
| 新变量值得保留 | validation 上同模型消融增益稳定、配对区间支持改善，且 OOD/关键 bin 无显著劣化 |
| 完整方法相对已有 proxy 有实际价值 | 争取 macro log-RMSE 相对降低 ≥10%，同时检查 bias 与 tails；达不到也保留定量信息边界结论 |
| 复杂架构值得升级为主模型 | 相同输入较强简单模型争取 ≥5% 相对改善，且改善超过 seed/统计波动，成本可接受 |
| 可以进入物理测量 | 独立闭合、systematic challenge、data 控制区均通过；最终总不确定度有可解释收益 |

若未达到门槛，先确认样本统计、训练饱和、物理可观测性、校准和代码对齐。不能因为几个离群事件停止分支，也不能无限增加网络深度代替这些检验。locked test 只在模型/特征/选择冻结后用于最终验收；失败后的修改须回到开发流程并说明测试集复用问题。

## 9. 可逐步执行的阶段安排

以下 R0–R8 是**后续研究工作包**，不表示本次已执行。每包完成后按 `AGENTS.md` 写中文 workbook，附输入、命令、计数、单位、性能、图表、结论和下一步，并进行一次 Conventional Commit。

### R0：冻结任务与数据合同

**输入**：现有 cuts/definitions、官方生产清单、四个已审计文件、相应 ntuple maker 源码/校准。

**任务**：选定主几何和 tracking；核实入射 ν 标签；核对最终 production 与 data schema；列出 calibration、饱和、缺失、aux reduced charge 的适用条件；审计所有向量索引、重复来源和 upstream preselection；定义 target/feature/weight/metadata 四张清单。明确当前 `LeadTrack_qop` 实为 charge/pz，不能直接宣称是精确 charge/p。

**产物**：样本 manifest、单位/语义字典、特征允许清单、truth 泄漏拒绝清单、实验注册文件。

**验收**：训练输入无真值/ID/权重；label 对照通过；普通/CaloNu 分开；所有未确认字段明确标注；以数据支持的结论回答“哪些电子信息实际可用”。

### R1：小样本提取与可重复数据集

**输入**：R0 清单、代表性 nominal MC、匹配 data、官方现成构建。

**任务**：新增 ML 专用 YAML，按已有 `Analysis::Define/Redefine/Alias` 创建 GeV/mm 特征。先对一个代表性文件验证完整 cutflow；提取后保留 cut flags、标签与 provenance。宽松样本只用于诊断，主训练仍用已冻结选择。冻结分组划分；比较 1/2/4 CPU 的列裁剪提取，确定资源后才提交 HTCondor。

**产物**：一份紧凑主数据集与 manifest；scalar 特征和必要 jagged 对象；划分文件；质量/吞吐报告。

**验收**：同一最终生产的 cutflow、run/eventID 与原分析一致；线程数改变不改变事件与特征；输入/输出计数、缺失与非有限值均有去向；无需为训练重新保存 xAOD。不同 production 不要求假装复现阶段 09 的逐事件轨迹值。

### R2：物理基线与信息增益

**输入**：R1 冻结数据集，F0–F5 标量版本。

**任务**：运行 p/0.8、训练校准的一维基线和主 BDT；逐组增加/去除计数、电荷、Calo、形状；比较 direct log E 与 residual log(E/p)；在 p、方向、时期相近的事件中做条件置乱和诊断，检查新增信息是否只是在识别来源。

额外检查 leading track 与 primary μ 的 truth matching，只用于 MC 诊断，分别报告匹配/错配组，不偷偷把训练样本改成“真值匹配成功”。建立只用真值 primary μ 运动学的 oracle 辅助模型，与只用重建 μ 的模型对照，分离 ν→μ 的随机非弹性损失与 tracking/材料传播造成的损失。oracle 不参与可部署模型排名，其输入仍严格禁止进入真实预测链。

**产物**：基线响应、消融表、能量分箱指标、关键异常事件的小型诊断清单。

**验收/结论**：回答“最少哪些变量提供稳定增益”；任何 improvement 均附统计区间和配置；用模型容量/学习曲线排除明显欠拟合。若 Calo 仅提供 MIP 信号，也报告其条件增益是否为零，不能假设它一定测得强子能量。

### R3：表格架构比较

**输入**：R2 确认的相同特征、partition、权重、loss 与调参预算。

**任务**：比较 MLP、ResNet、TabM、FT-Transformer；有预算时加入本地 TabPFN 对照。用训练规模学习曲线区分数据量不足与架构差异；必要时在 validation 上尝试少量 BDT+NN 集成。

**产物**：精度/偏差/尾部/训练与推理成本的 Pareto 表、3–5 seeds 的波动、冻结的主 tabular 模型。

**验收/结论**：回答“给定同样信息与资源，哪种表格方法更合适”；不能用 test 反复挑 ensemble 权重。

### R4：拓扑模型：Deep Sets → GNN/Transformer

**输入**：R1 的 SpacePoint 坐标、经过对齐验证的 tracks/segments、几何与 R3 全局特征。

**任务**：先 Deep Sets；与 BDT+同对象的空间矩对照。若有增益再测试 GNN 与集合 Transformer。建立 station 内和相邻 station 的几何关系；保留长度、总数和 mask；报告压缩/采样损失。分别做只用点数、打乱几何关系、移除全局 μ 信息的对照。

**产物**：同对象集合的三模型对照；占有率/点数尾部与显存曲线；图边定义；异常索引修复或明确绕开方案。

**验收/结论**：打乱点顺序不改变集合模型输出；padding 不贡献信号；图边不使用真值；高占有率事例不被悄悄删除；证实增益来自空间关系后才把复杂模型升为主线。

### R5：概率预测与系统稳健性

**输入**：最佳简单模型和最佳拓扑模型、独立 calibration、flux/interaction/shower/detector challenge 样本。

**任务**：分位数/ensemble 校准；分别改变训练谱和评估谱；测试动量 scale/resolution、材料、charge/光产额、饱和、增益切换、cluster efficiency/noise、tracking 与 reduced-charge 处理。系统幅度来自合作组校准或受控变体，不任意加 10% 当作正式系统误差。固定模型评估变体为主，少量重训量化训练模型依赖。

**产物**：bias/coverage/systematic response 矩阵、缺失项清单、可支持的能量与几何范围。

**验收/结论**：分别量化统计不确定度、事件内不可观测性、训练波动和物理系统误差；若无替代 interaction 样本，不宣称该项已验证。conformal 在交换性假设下的覆盖保证不自动适用于 MC→data 或生成器迁移。[U2]

在统计足够的预注册分层中，用二项区间或适合权重的 bootstrap 区间检查名义 68%/95% coverage 是否相容，同时比较区间宽度；不能通过把所有区间扩到几乎 100% 覆盖来宣称校准成功。

### R6：CaloNu 专题与扩展表示

**输入**：经过 R0/R1 验证的 CaloNu MC、对应时期 data、校准信息。

**任务**：在同一 CaloNu 事件中加入/移除 CaloNu；检查模块能量、状态、相互作用深度依赖；与普通几何分别建响应。比较分几何模型与共享条件模型，不把全零占位分支当测量。

**产物**：CaloNu 读出的实际信息增益、适用时期、分辨率和模型系统代价。

**验收/结论**：结论有同事件对照，不能由样本谱和材料变化冒充增益。本包可与 R2/R3 的普通几何研究交错开展，取决于匹配生产/校准是否就绪。

### R7：真实 data 控制与物理闭合

**输入**：冻结模型、匹配 data 控制区、独立 response MC、合作组背景及 nuisance 输入。

**任务**：用穿越 μ 检查 MIP/charge、gain、cluster 与位置依赖；用高活动/高电荷侧带检验 shower 输入与模型 score，明确侧带背景和信号污染。data/MC 分类器仅辅助定位失配，不能证明能量准确性。逐事例真能量在 data 中不可见，不能把和 MC 预测谱相似当作能量标定。

建立含效率的响应：

\[
R_{ij}=P(\mathrm{selected},\mathrm{reco\ bin}\ i\mid\mathrm{truth\ bin}\ j),\quad
n_i^{\rm pred}=\sum_jR_{ij}\mu_j+b_i,\quad
\sum_iR_{ij}=\epsilon_j.
\]

保留 ν/反ν 的电荷敏感信息和原分析需要的 rapidity 观测量；比较原 proxy 与 ML 下的能量/二维 response、背景迁移和 covariance。用独立 pseudo-data 做 nominal closure、能谱倾斜、π/K/charm 组成和系统失配测试，报告 pull 与区间覆盖，不能只测试训练先验下的 Asimov。

**产物**：同一物理问题上的分箱迁移/效率/相关性、闭合、总不确定度或预期敏感度对照。

**验收/结论**：说明“是否提高了最终物理测量”，而不只报告更窄的回归残差。若本仓库缺 likelihood/unfolding 实现，先接入并验证该模块；这是显式依赖，不把能量回归器当作完整测量。

闭合研究可从每个预注册情景 500 份 pseudo-experiments 起步（计划值，未执行），检查估计偏差、pull 均值/宽度和区间覆盖与其有限 toy 统计是否相容；MC 有限统计与重复 toy 共用响应造成的相关性须保留。不能把一次无统计涨落的 Asimov 恢复当作这些检验的替代。

### R8：部署、复现与长期研究

**输入**：R7 验收模型及预处理/校准/系统版本。

**任务**：先做离线批量推理和 `(run,eventID)` 对齐；ROOT 多线程输出顺序不保证一致，不能按行号 friend。后续再接入现有分析；比较导出模型和训练框架在代表样本上的数值，容差事先制定。研究分位数、密度模型或 inference-aware 优化须保留独立基线。[U3–U4]

**产物**：模型卡、支持区间、允许特征、预处理与 calibration、紧凑预测、响应和运行命令；只保留最佳模型与必要 ensemble checkpoint。

**验收**：新环境能从清单重建指标和推理结果；跨线程/批大小一致性通过；每个新增预测分支都有清晰语义。

## 10. 自监督预训练是否值得做

2026-09-30 的 FASERCAL 论文采用稀疏 ViT、多模态融合、masked reconstruction 和关系目标，研究 detector representation、动量与顶点等任务，是非常相关的长期参考。[M12]

但其输入是拟议高颗粒度 FASERCAL 的 3D 体素及其他子系统，不是当前四通道 CaloNu，也不是现有电子分析直接拥有的全部信息。不能照搬其性能或假定权重能直接迁移。

本项目若进入预训练，先满足三个条件：R4 已确认拓扑有价值；现有监督学习受有效样本量限制；可获得与部署同语义的大量低成本重建输入。可测试 masked station/SpacePoint 汇总重建，或同一事例不同可见子集的一致性学习；augmentation 必须保留待预测能量信息与真实几何约束。

比较 scratch、纯 masked 预训练、masked+适用辅助目标，使用相同下游标签量和计算预算，画学习曲线。MC 真值可作为辅助监督标签，**不能进入推理输入**；使用辅助真值训练的部分应称为模拟辅助监督，而不是全部称“无监督”。data 预训练需独立控制样本并核查信号/测试集接触，不能通过 transductive 流程悄悄使用 locked test。

没有真实的三维量能图时，CNN/稀疏 CNN 不是本仓库第一选择；将少量无序标量排成图片也不会创造空间信息。固定磁场、材料和 detector LOS 打破一般旋转对称性，不能不加验证地引入全 SO(3) 等变性或任意旋转增强。

## 11. 工程与资源安排

建议先保持现有 C++ 选择框架稳定，新增配置/脚本即可启动。下列是**拟新增结构，目前除 schema 审计脚本外尚未实现**：

```text
AnalysisZipFramework/config/ml_output_columns.yaml
AnalysisZipFramework/config/ml_definitions.yaml
AnalysisZipFramework/config/ml_features.yaml
AnalysisZipFramework/scripts/export_ml_dataset.py
ml/configs/{baseline,tabular,sets,graph,systematics}.yaml
ml/{data,models,train,evaluate,calibrate,infer}.py
AnalysisZipFramework/submission/ml_extract.sub
AnalysisZipFramework/submission/ml_train.sub
workbook/stageNN_energy_ml_*/
```

最终文件布局按实际规模调整；不为尚未验证的全部架构预建大框架。`Analysis::Define/Redefine/Alias` 与已有日志机制保持一致；源 YAML 改动后重跑 CMake 或显式传配置路径。

ROOT 提取按列裁剪、一次 event loop、分文件批量处理；训练反复访问时优先从一份紧凑列式缓存/分片读取，不每个 epoch 扫远端 ROOT。ROOT 或 Parquet/Awkward 的格式用小样本实测 I/O、缺失与 jagged 对齐后决定，不预设中间格式越多越好。

大批量提取、训练和推理都通过 HTCondor；GPU 用于交互小样本和合适的训练 job。CPU-only BDT 不必抢 GPU。限制 BLAS/OMP 和 dataloader 数量，避免 RDF 线程、文件并行和 GPU loader 层层超配；先测 1/2/4 CPU 与适当 batch size。

本次远端前缀读取实测如下，包含 PyROOT 首次读取开销、远端网络/缓存效应，**不能作为训练或 lxplus 生产性能预测**：

| 样本 | open s | 扫描 s | events/s | 扫描读取 bytes |
|---|---:|---:|---:|---:|
| 200080 | 2.540 | 48.613 | 2.633 | 16,412,857 |
| 200093 | 0.848 | 36.974 | 3.462 | 16,507,555 |
| 200139 | 0.887 | 43.382 | 2.951 | 17,269,098 |
| data 16000 | 3.570 | 7.237 | 17.688 | 2,272,658 |

MC 审计进程峰值 RSS **405.328 MiB**，data 进程 **408.266 MiB**；它们是各进程高水位，不是逐文件额外内存。每次只取 128 entries 仍会读入 ROOT baskets/cache，所以事件数限制不等于读取 bytes 同比例降低。训练耗时、GPU 显存、模型参数量和推理吞吐均**未测量**。

EOS 只留必要紧凑数据、模型和最终 response；不新增长期 xAOD。诊断优先留下聚合表和少量事件键；分片统计/JSON 验收后合并去重。运行记录保留配置、版本、随机 seed、来源映射与实际资源，不为普通步骤增加全文件 SHA 扫描。

## 12. 建议排期与第一个可交付结果

以下是**人力安排估计，非实际测量或保证工期**；队列、匹配系统样本和校准可用性会影响日程。

| 时间窗口 | 重点 | 必须得到的可审阅结果 |
|---|---|---|
| 第 1 周 | R0 + R1 小样本 | 数据/标签/单位合同，无泄漏、cutflow 与来源验收 |
| 第 2 周 | R1 批量紧凑提取 + R2 | p/0.8、一维基线、BDT 与主要变量组消融 |
| 第 3–4 周 | R3 | 表格模型的公平精度/成本比较 |
| 第 5–6 周 | R4；条件就绪则 R6 | 拓扑是否有额外信息，CaloNu 同事件增益 |
| 第 7–8 周 | R5 | 概率覆盖、prior、interaction/shower/detector 稳健性 |
| 第 9–10 周及以后 | R7 + R8 | 控制区、独立物理闭合与部署；预训练按证据另立工作包 |

**最优先推进的下一步是 R0/R1，不是先写 Transformer。** 第一个研究交付应是一张具有统计区间的表：同一 nominal 选择下，p/0.8、p-only 回归、p+方向、再加 station 计数、闪烁体和常规 Calo 后，各能量 bin 的 bias、R68、log-RMSE 与尾部如何变化。它会决定后续模型投资方向。

开始下一阶段前的具体清单：

- [ ] 在 lxplus 对一个最终官方 merge、一个 nominal MC、一个 CaloNu MC 和匹配时期 data 重跑 schema/对齐审计。
- [ ] 确认入射 ν 索引和 Eν 单位，写出模型输入允许清单与标签测试。
- [ ] 明确常规 Calo/双增益校准、CaloNu 有效时期、reduced-charge aux 与原生 MC 差别。
- [ ] 选定普通几何 nominal 六 run 和 tracking 主版本；将替代 flux 与系统挑战集留出。
- [ ] 只提取一份小样本，复现原选择并测资源，验收后再进入批量生产。
- [ ] 在训练前冻结指标、分组划分、调参预算和 test 使用规则。

## 13. 文献与对当前项目的可行性判断

检索日期：2026-10-29。以下引用以论文、作者页面或 CERN 官方材料为主；引用中的性能属于原论文任务，本文不将它们换算为本仓库的预期提升。

| 编号 | 文献 | 对本项目的用途与限制 |
|---|---|---|
| P1 | FASER, [First Measurement of the Muon Neutrino Interaction Cross Section and Flux as a Function of Energy at the LHC](https://arxiv.org/abs/2412.03186), PRL 134, 211801 (2025) | 电子探测器能量 proxy、响应、效率与系统误差的物理基线 |
| P2 | FASER, [Measurement of Muon Neutrinos as a Function of Energy and Rapidity](https://repository.cern/records/eg0mj-1ep53), CERN-FASER-CONF-2026-005 | 当前二维测量背景；最后应比较物理推断收益 |
| P3 | FASER, [Photographing TeV Neutrinos with FASER](https://faser.web.cern.ch/briefing-20260325/), 2026-03-25，官方说明并链接 conference note | 乳胶侧已做 ML 能量重建；其 μ/强子测量信息与本仓库不同 |
| M1 | Grinsztajn et al., [Why do tree-based models still outperform deep learning on tabular data?](https://arxiv.org/abs/2207.08815), NeurIPS 2022 | 强 GBDT 基线与特征异质性；不能作为 2026 年所有任务的绝对排名 |
| M2 | Gorishniy et al., [Revisiting Deep Learning Models for Tabular Data](https://arxiv.org/abs/2106.11959), NeurIPS 2021 | 表格 ResNet、FT-Transformer、公平比较协议 |
| M3 | Gorishniy et al., [TabM: Advancing Tabular Deep Learning with Parameter-Efficient Ensembling](https://arxiv.org/abs/2410.24210), ICLR 2025 | 值得优先加入的强 MLP 变体，避免只比较旧 MLP 和大 attention |
| M4 | Erickson et al., [TabArena: A Living Benchmark for Machine Learning on Tabular Data](https://arxiv.org/abs/2506.16791), NeurIPS 2025 | 验证协议、预算与集成会改变结论；公共表格排名不能代替 HEP 系统验证 |
| M5 | Zaheer et al., [Deep Sets](https://arxiv.org/abs/1703.06114), NeurIPS 2017 | 可变长、无序 SpacePoint/track 集合的直接起点 |
| M6 | Komiske et al., [Energy Flow Networks: Deep Sets for Particle Jets](https://arxiv.org/abs/1810.05165), JHEP 01 (2019) 121 | 学习“逐对象编码+求和+事件输出”；当前点没有可靠能量权重时采用 PFN 风格，不强套 EFN |
| M7 | Qu & Gouskos, [ParticleNet: Jet Tagging via Particle Clouds](https://arxiv.org/abs/1902.08570), PRD 101, 056019 (2020) | 局部图关系候选；jet tagging 的结果不证明中微子回归会同样提升 |
| M8 | Qu et al., [Particle Transformer for Jet Tagging](https://proceedings.mlr.press/v162/qu22b.html), ICML 2022 | 成对关系进入 attention；需改用 detector 几何，并控制对象数 |
| M9 | IceCube, [Graph Neural Networks for Low-Energy Event Classification & Reconstruction](https://arxiv.org/abs/2209.03042), JINST 17 P11003 (2022) | 不规则探测器中图表示和系统学验证的先例；光探测器与本项目物理响应不同 |
| M10 | Baldi et al., [Improved Energy Reconstruction in NOvA with Regression CNNs](https://arxiv.org/abs/1811.04557), PRD 99, 012011 (2019) | 端到端能量回归、按 hadronic fraction/interaction mode 评价的先例；当前缺像素能量图时不优先 CNN |
| M11 | Grinsztajn et al., [TabPFN-2.5](https://arxiv.org/abs/2511.08667), 2025，修订 2026-02 | 新的表格预训练补充基线；先验证本地资源、样本规模和回归配置 |
| M12 | Alonso-Monsalve et al., [Towards foundation-style models for energy-frontier heterogeneous neutrino detectors via self-supervised pretraining](https://www.nature.com/articles/s42256-026-01309-6), Nature Machine Intelligence 8, 1581–1595，2026-09-30 | 高度相关的长期多探测器表示路线；依赖拟议高颗粒度 FASERCAL 输入，不等于本仓库的 CaloNu |
| U1 | Lakshminarayanan et al., [Simple and Scalable Predictive Uncertainty Estimation using Deep Ensembles](https://arxiv.org/abs/1612.01474), NeurIPS 2017 | 训练波动与预测分布诊断；ensemble 方差不能包办模拟系统误差 |
| U2 | Romano et al., [Conformalized Quantile Regression](https://arxiv.org/abs/1905.03222), NeurIPS 2019 | 分位数区间的独立校准；MC→data 非交换时无自动覆盖保证 |
| U3 | Durkan et al., [Neural Spline Flows](https://arxiv.org/abs/1906.04032), NeurIPS 2019 | 有需要时的条件密度输出，不是第一阶段必须组件 |
| U4 | de Castro & Dorigo, [INFERNO: Inference-Aware Neural Optimisation](https://arxiv.org/abs/1806.04743), CPC 244 (2019) | 后期将 nuisance 下的最终不确定度纳入优化；先有可验证 likelihood/response 再启动 |

## 14. 本次完成与仍未测量的内容

本次完成代码/配置调查、四文件 schema 与 512-event 前缀审计、公开文献检索、研究设计和资源实测；对应阶段记录见 [`阶段 11`](../workbook/2026-10-29_stage11_energy-ml-roadmap.md)。

尚未测量：任何 ML 能量分辨率/排名、变量与 Eν 的条件关联、标签逐事件交叉核对、完整数据集重复率、最终官方 merge 的本次 schema、全量 CaloNu 统计、data 能量真值、systematic envelope、GPU 训练/推理成本、最终 flux/cross-section 精度。后续每一项都须通过上述工作包取得数据证据。

## 15. 2026-10-29 执行进展：阶段 12/13

以上第 14 节记录制定路线图时的状态。当前已经完成官方 merge 的全量精简提取和
首轮单位权重 validation BDT 探索，详见
[阶段 12](../workbook/2026-10-29_stage12_energy-ml-input-contract.md)、
[阶段 13](../workbook/2026-10-29_stage13_energy-ml-bdt-first-results.md)。
342 文件/3,374,987 raw events，nominal 89,786、SIBYLL challenge 15,144 selected
events，逐文件 cutflow/最终事件键与阶段 09/10 一致，五个分区已冻结。

train/validation 为 54,196/13,375 events。首轮 macro log-RMSE：p/0.8 0.631674，
p-only BDT 0.543307，+ μ context 0.516713，+ 计数 0.434073，+ 闪烁体 0.390037，
+ Calo 0.387153，+ 全局 SpacePoint 矩 0.385054。计数和闪烁体的累加改善有
500 次同来源组配对 bootstrap 支持，但完整模型去计数/Calo 与空间矩增益的区间
包含零，不能将累加结果理解成各组的不可替代贡献或因果贡献。

仍缺物理 flux 权重、完整来源谱系、容量/seed/条件置乱、primary-μ oracle 与 data
响应校准；高能 bin 仍有显著负偏差。测试集/校准集/挑战集未参与模型评价或选择。
因此 R0/R2 尚未完整验收，不以该表直接替换物理分析或进入架构最终排名；下一步
先完成这些 BDT 输入与稳健性检查，再按同预算比较 MLP/ResNet/TabM，随后 Deep Sets。
