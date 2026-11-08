# Stage187 研究补充：不依赖乳胶匹配的电子观测与物理变量

日期：2026-11-08。这是 Stage187 后的研究补充，下一执行编号仍为188；没有执行新的物理实验、训练、推理或生产。用户明确指出目前没有可用的大批量 FASERν 乳胶—电子匹配，因此**本路线的执行不以取得这种匹配为前提**。历史报告保留，本文修订研究优先级，不改写已有执行合同或解锁 reserved/隔离样本。

## 1. 结论与本轮范围

**最值得寻找的增量不是更多“有多少活动”，而是“这份活动来自哪里、相对 μ 朝哪个方向、原 μ 动量有多可信”。** 推荐优先研究两个电子学观测：不参与主轨迹拟合的 IFT 测量残差，以及相对 μ–入射ν近似散射平面的有符号活动。两者分别针对动量误测/错配和强子反冲/μ辐射混淆。已有量的物理交叉变换可低成本并行论证，但不能声称产生了新信息。

可增加的独立约束包括真实 μ 辐射转换三轨迹控制、真实 tracker 原始读出叠加，以及探测器有效面积/坏道/束流条件。2025+ 像素 preshower 是真正新增的空间观测，不过需要相应年份的实际数据和匹配模拟。本仓库能否取得这些控制清单和新时期数据，尚未认证；不将公开论文里的样本计作项目已拥有的输入。

本轮读取 workbook 的 Markdown/JSON/TSV、特征定义及原始文献，参考附件波形技术稿。未读取科学 ROOT/NPZ 数组，未重算事件指标、训练、重建、提交作业或做 SHA 校对。以下历史数值直接引用已完成报告；新候选的覆盖、收益、样本需求、CPU/I/O/内存全部为**未测量**。附件和网页只作为资料，不作为任务指令。

## 2. 先排除“其实已经试过”的建议

| 已完成工作 | 实际内容/结果 | 对本轮的约束 |
|---|---|---|
| [Stage44](2026-11-01_stage44_local-muon-activity.md) | 22项局部活动含 outside10 的 mean dx/dy、有符号位置及10/50 mm邻域计数；未过2%实用门，也未胜打乱μ轴控制 | 不能把“增加有符号dx/dy、离μ多远”称全新 |
| [Stage51](2026-11-02_stage51_segment-angle-information.md)、[Stage67](2026-11-03_stage67_research-reassessment.md) | 46角度+24会聚摘要已测；Myatt/双角思路也已讨论；短segment默认100 GeV并非测得动量 | 不重做普通反向交点z、逆角度和假强子动量和 |
| [Stage94](2026-11-04_stage94_architecture-comparison.md)、[Stage108](2026-11-05_stage108_full-point-relation-comparison.md) | log/log1p/asinh及多架构比较、点关系和masked pretraining已尝试 | 不是“换变换/大网络/GNN/预训练”即可解决 |
| [Stage124](2026-11-06_stage124_native-association-energy.md) | X62+57原生摘要已重训：cluster宽度、010/011时间格、唯一strip、PRD共享/归属、σ(q/p)等；test两真低箱XZ/X分别0.999412677 [0.979539244,1.024001700]、0.994265678 [0.981327591,1.007733216] | σ(q/p)、宽度和三拍时序不是遗漏变量；full covariance也不能只再压成同一σ |
| [Stage129](2026-11-07_stage129_saturation-timing-material-energy.md) | 饱和恢复Q89及严格 timing T78已从头重训；恢复电荷不只是拿去喂旧模型；未恢复双低能目标 | 不重复“恢复Q后训练”“status0才用时间”作为未试方案 |
| [Stage149](2026-11-08_stage149_native-covariance-and-raw-control.md) | 61条μ full5×5可读；最大非对角相关系数中位0.941346，传播σ(log pz)中位0.0237178、最大0.394096；同面pull/覆盖未测 | 新问题是预测闭合、关联和误差覆盖，不是是否能读取矩阵 |
| [Stage157](2026-11-08_stage157_joint-muon-response-and-partition-control.md) | 已按log pz、x/y、斜率做Q15/Q15G6条件OLS、收缩残差协方差、Mahalanobis及conformal；overflow留出仍报警9/13、8/13 | 简单MIP扣除、条件白化或异常分数不是新路线；需增加方向/起始位置/未用测量 |
| [Stage158](2026-11-08_stage158_original-cohort-spatial-energy-comparison.md) | X62+A3+G6，71376 active、9 fit；test最低真E箱内容/可用性控制1.015321 [1.005710,1.024105] | 已结束的是站1–3计数+sumAbsDx表示，不能推广为所有几何信息无用 |
| [Stage174](2026-11-08_stage174_timing-dual-end-control.md)、[Stage177](2026-11-08_stage177_timing-mean-energy-content.md) | 真实差时位置abs95约163–311 mm，MC约13–31 mm；均时9 fit，test T/V两低箱0.997941 [0.991337,1.005005]、0.997533 [0.992882,1.002306] | 不照搬MC位置精度，不重开普通均时模型 |
| [Stage186](2026-11-08_stage186_original-cohort-actual-ideal-energy.md) | 原71376 active，实际/理想同PMT同窗Q共9新fit；test I/R两低箱0.997731 [0.984972,1.009262]、0.998340 [0.991194,1.006067] | 固定标量电荷路线阴性；不是所有ADC形状的信息上限 |

表中能量比均为自然对数能量RMSE比，无量纲、越小越好，区间沿用原条件incoming口径。不同队列不合并为统一改善率。Stage186实际Q模型/传统在真Eν=50–100 GeV为1.958185 [1.695659,2.293622]，主目标仍未解决。

## 3. 第一优先：让 IFT 成为主轨迹的留出测量

### 3.1 为什么比再加拟合质量摘要更有意义

当前原生主轨迹来自 `CKFTrackCollectionMergeWithoutIFT`，IFT测量没有参与该轨迹拟合；Stage124已证实station0的leading/other/shared归属计数因此自然为0，但原始IFT strips/clusters实际存在。它们可以检查从下游谱仪运输回去的主μ预测，而不需要乳胶顶点。这是**不同的一组电子测量对拟合的检验**，不是独立绝对动量真值。

IFT不是新硬件，Stage108也已用过完整点关系；本方案的新问题是实际运输/完整误差下的预测闭合和关联歧义，不是声称过去从未读取IFT。其相对X62可提供原生内容，相对包含完整测量的表示则是物理重组。station0“未归属主轨迹”也不意味着所有这些hit来自强子。

对真实measurement surface和条带测量轴，定义

\[
r_j=u_j-h_j(\widehat s_{-j}),\qquad
S_j=V_j+H_j C_{\mathrm{pred},-j}H_j^T,
\quad C_{\mathrm{pred},-j}=F_jC_{-j}F_j^T+Q_j.
\]

其中u为原生一维测量(mm)，r为mm，S为mm²；F含实际磁场/材料运输，Q为相应过程噪声，H为测量投影的导数。独立测量噪声等条件成立时可构造无量纲pull；共同alignment/条件误差需要另外处理。实际curvilinear基底必须先正确变换，不能把5×5直接解释成任意x/y/斜率基底。

候选观测不是一个全局χ²，而是：IFT各层带符号残差、弯曲/非弯曲方向的相干偏移、局部kink、预测命中有效wafer却无测量的hole、兼容候选的数量与歧义。主谱仪内部可用真正leave-module/station-out重拟合残差；参与拟合的smoothed残差不能充当独立pull。FASER[官方公开图][R05]已经使用去掉module两侧cluster后的重拟合残差，说明有现实技术路径；[GBL论文][R09]支持含材料、散射及全协方差的描述，无需因此替换现用ACTS。

### 3.2 最容易做错的地方

高占有率下“离预测最近的cluster”即便是假关联，也更容易有很小的残差。必须保留所有兼容候选、无hit状态和有效面积，按占有率校准关联，不能先挑最小pull再宣称轨迹更准。共享PRD、同一条带的组合SP也不是多个独立粒子。

IFT以前的FASERν目标内没有连续电子轨迹采样，因此不能据此测目标内MCS或给出精确产生点z。同一磁谱仪各段仍共享磁场、alignment弱模式；残差小不等于绝对曲率无偏。原8/63等困难父缺S0的事实保留，不用新控制样本替换掉。

首次应交付有实际支持范围的预测残差/错误关联/覆盖，以及其对低真E正尾和低pz真高E负尾的区分；不能只报匹配AUC。若只改善响应校准、不改善单事例能量，可进入谱响应系统约束。校准后的新内容若进入Eν模型，必须与可用性控制作完整新训练。

## 4. 第二优先：把活动旋转到 μ–ν 近似散射平面

### 4.1 物理动机与具体变量

在忽略核运动等理想化情形下，净强子横向反冲与μ横动量方向相对；μ在下游辐射产生的电磁活动则可能沿运输后的μ方向、从不同位置起始。**有相同总Q、相同径向宽度的事件，方向和纵向起始模式可能不同。** 这是待检验假说，不保证经历厚靶级联、孔径和中性漏失后仍保留，尤其高y不必对应大横动量。

先将μ状态经磁场/材料运输到IFT等统一上游参考面，以该run束流条件提供近似入射方向：

\[
\mathbf a_\mu=(p_x/p_z,p_y/p_z)_{\rm IFT}-\mathbf a_\nu^{\rm LOS},
\quad \widehat{\mathbf e}_{\parallel}=\mathbf a_\mu/|\mathbf a_\mu|.
\]

再考察合法空间位移在该方向和垂直方向上的投影、前后半平面不对称、偶极矩、二阶方向矩，以及它们从IFT到谱仪第一站的变化。对一维strips应在真实测量轴上投影，不制造每条strip的精确二维点；使用SP时按真实PRD处理ghost/reuse和相关。近束轴、方向不稳定或运输无支持时保留未知标记。

这里的新意是**束流/磁场一致的参考面＋散射平面方向＋真实测量关联**，不是Stage44已经存在的mean dx/dy，也不是Stage158的绝对距离和。旧G6只支持station1–3，不自动赋予IFT相同的实测μ-wafer锚点；IFT需要上节的预测与候选关联。

FASER[电子中微子谱论文][R08]明确处理束流交叉角造成的LOS偏移，因此不能把探测器轴角度直接当作μ–ν散射角，也不能跨年份固定同一LOS。μ在IFT的位置并非已测ν顶点，近似入射线与未知靶内散射需传播为不确定性。[HERA重建论文][R10]和[MINERvA横向不平衡论文][R11]启发使用相对方向/失衡；它们的束流、能区、完整末态条件不同，不能移植其解能公式或性能。

### 4.2 有限对照

只先冻结少量方向矩和纵向对比，与“相同输入、方向被条件打乱”的控制比较；打乱需保留pz、位置、占有率、charge/几何条件，避免把孔径效应误认作反冲。训练前定义轴与有效面积，不从test挑有利层/方向/半径。若方向内容相对可用性控制和打乱控制都无原定增量，该固定表示结束，不续开泛化GNN网格。

[Energy flow polynomials][R12]可启发少量角关联量；二值占有率不是能量流，不继承能量加权完整性或红外/共线安全性。

## 5. 可立即论证的物理交叉变换：有价值，但不是新测量

若f完全由旧X确定，则理想信息意义上 \(I(E;X,f(X))=I(E;X)\)。交叉变换可能让有限深度BDT更容易表达物理关系；它不能恢复已经侧向漏失的能量。单变量单调log/asinh对树的划分能力改变很有限，Stage94也已试过，优先级应低于有物理含义的跨变量组合。

| 变换/变量 | 要回答的问题 | 保留条件 |
|---|---|---|
| 束流相对斜率、μ散射平面坐标 | 活动相对反冲方向在哪里 | 使用实际时期LOS与上游运输，不用真z |
| \(\chi_\mu^{obs}=p_{z0}|\mathbf a_\mu|^2/(2m_N)\) | 相同pz时，小transfer与大角散射是否更易区分 | 无量纲；仅观测代理，见下段，不作硬约束 |
| μ预计穿越的Ecal模块与其他模块的有符号能量对比，结合preshower层差 | EM活动是否与μ同轴、是否从下游才开始 | 保留四原始能量和总量；模块边界结合传播误差；不是强子pT |
| \(\mathrm{asinh}(Q_i/Q_0)-\mathrm{asinh}(Q_j/Q_0)\) 加原尺度 | 活动组成与总幅度分开 | Q₀固定并有单位；保留合法负Q，避免log负数和近零比值 |
| 反冲方向到真实active边界的距离、预计穿越有效层数 | “安静”是低transfer还是探测器没看到 | 原生几何/坏道/误差支持；不能用缺失当零能量 |
| 全协方差投影到实际测量轴、局部杠杆臂/材料路径 | 哪些误差模式容易导致错误大修正 | 不重复σ(q/p)；协方差可读不等于覆盖正确 |

在产生点、自由静止核子、忽略μ质量的Born近似下，\(E_\mu(1-\cos\theta_{\mu\nu})/m_N=xy\)，小角度下约为 \(E_\mu\theta^2/(2m_N)\)。上表使用S0的pz0和运输后方向，受靶内散射/能损与未知入射线影响，**不等于已测xy、y或Q²，不能据此给出硬Eν下界/上界**；不重新引入p0/p1/pz1。若需要更完整的次级动量输入，必须另行澄清特征政策和实际测量支持，不能把默认100 GeV segment当测量。

这里应做一个有明确物理问题的小型表示对照，保留X62并从头重训；不再同时扫描几十种比值/归一化择优。全部收益和成本未测量。

## 6. 没有乳胶也可增加的辅助数据

### 6.1 μ辐射—光子转换三轨迹控制

FASER[已发表暗光子分析][R04]使用μ诱发光子转换的三轨迹事件检查E/p，也以转换质量分布比较跟踪尺度/分辨率。因此可以寻找同一时期、同一设置的真实控制清单，用于约束：μ附近EM活动的空间起始、转换/共享hits对重建的影响，以及Ecal与跟踪的相对响应。

这是公开分析已经实践的控制技术；本项目取得清单与低能相关支持仍未知。它不是ν能量真值，也不能仅靠E/p把跟踪与量能器绝对尺度同时解开；需保留测试束/MIP等外部标定及相关误差。论文中的5%/6%等属于该分析，不作为本项目当前误差常数。三轨迹身份也需显式验证，不能机械规定最高动量必为μ。

### 6.2 真实tracker原始读出叠加

同一论文[R04]已将两个真实单轨迹事件的raw tracker读出叠加后重建，研究近邻双轨效率。此思路可针对实际拥挤度、共享PRD和错配测试第一优先方案，帮助回答“轨迹残差异常是物理散射，还是重建混淆”。

必须使用真实RDO时序/重叠规则及条件匹配；二值响应不是简单把cluster数相加。它校准探测/重建机制，**不制造新的ν相互作用，不模拟完整强子级联，也不增加独立ν训练N**。PMT饱和与非线性更不能用线性波形叠加自动解决。原生完整输入若不存在，不通过反演旧摘要伪造。

### 6.3 探测器条件、未命中与触发信息

几何有效区域、模块/strip坏道、阈值、运行期alignment、磁场与beam crossing信息，使“没有看到活动”具有可解释的分母。可构造预计穿越有效wafer数、局部有效面积和hole序列，与未采集/不在接受度分开。[tracker技术论文][R02]说明二值阈值与标定的重要性，[TDAQ论文][R03]说明事件包包含BCID/orbit、prescale前后触发项等。

这些元数据优先作为响应/效率条件。BCID、相邻束团距离、baseline历史只有在真实数据证明相关电子学偏差后才进入校准；不要把run、luminosity或trigger类别当Eν标签捷径。需要实际trigger/GRL与MC条件，保留正式cuts和全部父。当前reduced ntuple保留程度未知，不为了字段目录再开启无终点审计。

### 6.4 独立测试束响应作为标定输入

[FASER量能器测试束论文][R20]还提供了电子、μ及π响应、位置/HV变化的原始资料入口。如果能取得实际数据/设置，可约束量能器对粒种、位置和幅度的响应，减少把μ/EM标定误当强子标定的风险。本轮仅核检索摘要与可见方法片段，没有取得可用测试束数据；测试束几何、能区和没有完整厚靶级联的条件都限制迁移。它能标定被探测的响应，不能补回未接受能量或直接充当ν能量训练真值。

## 7. 真正的新探测器信息：2025+ 像素 preshower

[2026探测器综述][R01]记录：2025年2月安装硅像素/钨preshower，实际是**四个仪器化平面**，不是早期方案的六平面；像素尺度约100 μm。[ASIC论文][R06]说明电荷4-bit ADC及校准、fast-OR时间读出。不能据其设计指标假定每个像素有独立高精度时间。

对有匹配数据/模拟的新时期，可研究像素占有率、多个shower core、各深度横向增长、与μ预计交点的距离、EM轴是否指回μ或更早活动，以及与四Ecal模块的一致性。这比旧preshower两层总Q新增真正空间内容，也可帮助区分ν强子簇内EM分量和μ辐射。

执行条件是实际RAW/REC/ntuple、四平面几何、噪声/阈值/ADC标定、对应MC、触发/GRL和与目标ν样本的同时覆盖。已有2022–24样本不能补造这些观测；应作为新时期独立模型/确认样本研究，不能跨硬件年份直接拼接。它位于目标下游，仍看不到大部分靶内侧漏中性/低程能量，不承诺恢复全部Ehad。

## 8. 波形的剩余可能性：来源/形状，低于上述主线

附件[波形技术稿](</Users/aaaa/Downloads/FASER Waveform Reconstruction and Energy Calibration.pdf>)内部题为 *PMT Waveform Reconstruction and Calorimeter Energy Calibration*，2023-03-01 version1，编号仍为2023-XXX；这是历史技术稿。第6页的CB fit已经排除clip点、使用干净边沿，所以“拟合未触顶前后段”并非官方此前没有做过。第7/9页有状态/持久化说明；第10页描述当时的固定模板数字化。不能据此断言当前时分辨producer也只有该模板，现有Stage80/129软件实证优先。

Stage129与186已排查固定Q恢复/理想标量路线。剩下的具体新假说是：扣除单pulse的幅度、有效时间和baseline自由度后，是否存在可复现的多分量残余形状，例如与空间起始位置一致的prompt/late结构。新信息须是**来源/时间结构**，而不是又一个peak/width/Q估计器。

[CMS multifit][R16]支持重叠pulse模型这一方法原则；[CALICE钨/钢时间结构][R15]说明强子时间响应可能含材料相关分量。它们不证明FASER已有可用中子/迟发标签。先要在真实信号与随机/LED/MIP控制中区分ringing、afterpulse、时间漂移，并证实实际MC生产支持这种物理结构与采集窗。Stage183的116 strict随机控制不支持任意高维ADC协方差的无正则反演。

**任何arrival time、lag、late fraction或多pulse时间位置特征，都仅允许原始status恰为0的Good Hit；非0、缺失或带额外bit的hit没有可用timing。** 不以拟合成功改写原status，也不借“形状特征”绕过此规则。若真实结构或相应MC不成立，此路线结束，不扩窗口/模型网格。

## 9. 有启发但不能直接搬来的路线

| 资料/想法 | 能借鉴什么 | 当前不能承诺什么 |
|---|---|---|
| [SND强子shower研究][R13] | 纵向起始与两个子系统响应的联合约束 | SND有不同的主动采样和测试束；不能把线性组合系数移到FASER总Q |
| [CALICE软件补偿][R14] | 分开密度、EM比例与总尺度 | FASER四Ecal模块无纵向分段，不是细粒度含能HCAL |
| [IceCube截断dE/dx][R17] | μ随机辐射与稳健统计的区分 | 长路径TeV能损方法不能直接用于FASER少量MIP层测50–100 GeV能量 |
| [FASERCAL表征学习研究][R18] | 新主动量能器可利用不同探测信息 | 针对另一种模拟探测器；不能证明旧FASER的GNN/预训练有增量 |
| SCT三格time pattern | 粗略一致性/效率诊断 | 三个25 ns二值格不是analog dE/dx、精密TOF；Stage124已经输入摘要 |
| 普通μ TOF估能 | 仪器/方向闭合 | 5 m、50 GeV μ的β延迟仅约0.04 ps（解析量级估计、非测量），远小于现有亚ns读出能力 |
| 反向延长多条轨迹求z | 有额外独立早期track时可再讨论约束 | 不能将已失败会聚摘要重新命名成新vertex；磁场/散射/错配须处理 |

2026 [最新综述][R07]和[官方公开图][R05]中AHCAL/FASERCal原型为**off-axis布置**。它们不是当前同一on-axis ν事件的现成下游漏能计；只有实际几何/同时触发/关联支持成立才讨论共同观测，不能直接把其能量拼进当前训练。

这点与[Stage137](2026-11-07_stage137_geometry-accepted-energy-mechanism.md)已有结果一致：test最低箱163父中154已知、unaccepted KE>0有151，accepted>0仅38；side且有下游接受仅2父，该量的条件队列均值0.000576854 GeV，并非只对两个非零父求均值。该条件队列不能推出总体比例，却足以说明“加下游读出即可补回侧漏”缺乏依据。

## 10. 下一路线与验收：研究不再等待乳胶

研究顺序是：**旧电子观测的两种物理表示 → 实际μ/转换/overlay约束 → 有输入才开的新时期像素分析**。谱响应与真实背景/效率系统作为并行物理交付；不能拿条件谱精度替代单事例最低能目标。Stage140的有限MC toys已执行，不重做相同点证明。

| 顺序 | 具体科学问题/最小对照 | 所需输入 | 验收/停止依据 |
|---|---|---|---|
| A | IFT未用测量/真正留出残差能否识别μ响应或关联错误 | 原native PRD/measurement、真实surface、全cov、field/material与实际μ控制；原困难父未知保留 | 先有支持范围/歧义/覆盖；后固定X+availability vs X+content新训练；仅σ或关联AUC改善不算能量成功 |
| B | 散射平面方向是否区分强子反冲与μ活动 | 原strips/clusters、上游μ运输、beam条件、真实active mask | 少量预定矩；同条件打乱轴控制；不相对可用性/打乱控制增加就结束固定表示 |
| C | 交叉物理变量是否改善有限BDT表示 | 已有X62及可认证几何/束流条件 | 一个固定小包，与X62从头训练；不是新信息或能量真值；不扫变换网格 |
| D | μ辐射、转换、拥挤重建能否在data约束 | 同时期真实控制manifest、外部标定/误差、必要RDO | 校准留出控制上的响应/效率，转入A/B或谱系统；无支持就记录缺口、不虚构输入 |
| E | 新像素空间信息能否改善源分辨 | 2025+实际四平面数据/匹配MC与ν共同覆盖 | 独立时期协议和低能支持；没有匹配输入则保持候选，不妨碍A–C |
| F | 严格Good Hit的非单pulse结构是否存在 | 原status0 ADC、真实控制、支持相应时间物理的producer | 先数据物理结构，再固定新训练；无结构/模拟不支持就止，不重开标量Q路线 |

各候选先判断相应字段/原生记录是否足以构造，再冻结科学对照和小样本成本；**不能把A–F全部串成新前置链，也不能以本报告自动启动生产**。新提取应按已有来源批读，复用单进程runtime，保存最小measurement摘要，不持久化大型xAOD；大批依项目要求在HTCondor。首次实测CPU、初始化/steady、I/O、峰RSS和原低箱支持后才定批量规模，本轮不给虚构预算/加速比。

部署端共同约束：保留Stage87、所有K、原train/cal/开发test与隔离/reserved、typed NaN、合法signed raw、原cuts及pz0政策。新观测或校准进入模型均要从头重训，且包含同支持availability对照；禁止只把新数值塞给旧模型。使用原两个**真Eν**低箱、其他六层和八层总/正/负tail50验收，不能改成仅reco低pz或仅全体平均。

沿用原科学门：两低箱相对传统上95%≤1.05只是非劣效；最终仍要真正优于传统。all/Stage87上95%≤1.01、其余五保护层≤1.03、八层三尾差上95%≤+2 pp；原Stage137扩展门为cal/test两个低箱点比≤0.95且上95%<1并通过尾保护。没有独立确认和真实系统校准，开发结果不作最终认证。上述门不得因某候选阴性而放宽；有限模型阴性也不证明理论信息上限。

## 11. 本轮产物、执行与验证

产物为本文、[候选表](stage187_energy_ml/electronic_only_candidates.tsv)、[文献与阅读范围](stage187_energy_ml/electronic_only_research_sources.json)、[历史数字引用](stage187_energy_ml/electronic_only_quote_evidence.json)、[文档验证](stage187_energy_ml/electronic_only_document_validation.json)，以及两个路线入口的前置研究说明。原[下一输入合同](stage187_energy_ml/next_execution_contract.json)不变；它仍允许early-track/track-reference等物理输入，并不强制乳胶。

本轮使用的操作为文本阅读/检索、联网检索与HTML正文阅读，以及附件的`pdftotext -layout`抽取、`pdftoppm`第6页渲染与目视核对；文献临时副本不入库。文档检查用Python标准库解析新增JSON/TSV、检查本地链接和旧入口后缀保留，再运行`git diff --check`。无物理复算、事件数据测试或性能基准；新方法成本/收益**未测量**。阶段文档完成后作本地Conventional Commit，不push。

## 12. 文献范围与适用性

检索覆盖FASER探测器/跟踪/DAQ/标定/升级、电子ν测量，以及DIS运动学、轨迹误差、强子采样/时间、波形分解和物理表征。以下是筛选后的原始来源与官方资料，不代表穷尽全部论文；正文段落阅读与仅摘要/预览已分别标注，未阅读的全文不伪称已核实。相近版本/HTML/PDF不重复计数。

| 编号 | 原始来源 | 实际阅读范围；本项目用途与限制 |
|---|---|---|
| R01 | [The FASER experiment at the Large Hadron Collider, 2604.19199v2][R01] | §3.3、4.3、5.1–5.3相关段；当前电子结构/四平面升级/控制技术；公开样本非仓库输入 |
| R02 | [The tracking detector of the FASER experiment, 2112.01116v2][R02] | 二值ASIC/三格流水线/§5.4标定；约束可提取变量，非analog电荷 |
| R03 | [The trigger and data acquisition system of the FASER experiment, 2110.15186v2][R03] | 事件包与BCID/触发、粗细时间相关段；元数据不是Eν标签 |
| R04 | [Search for Dark Photons with the FASER detector at the LHC, 2308.05587v2][R04] | §VIII detector系统段；E/p、转换、raw overlay，不能移植该分析误差数值 |
| R05 | [FASER Public Plots][R05] | tracker去module残差图注、2026 AHCAL/FASERCal图注；控制技术与off-axis位置，非本事件联合能量 |
| R06 | [Production monolithic silicon pixel ASIC calibration, 2409.19030v1][R06] | §2、4和设计相关段；4-bit电荷、fast-OR时间、标定，早期六平面设计非最终四平面 |
| R07 | [Neutrino Experiments at the LHC and the HL-LHC, 2609.00842v1][R07] | §5.1升级相关段；2026原型off-axis，不把未来方案当现有on-axis输入 |
| R08 | [First Measurement of the Muon Neutrino Interaction Cross Section and Flux as a Function of Energy at the LHC with FASER, 2412.03186v2][R08] | LOS/crossing、选择和系统相关正文；公开pμ>100 GeV不等于本项目pz0>50 GeV |
| R09 | [General Broken Lines as advanced track fitting method, 1201.4320v1][R09] | 摘要与§1–2；材料/全协方差方法动机，不要求替换ACTS |
| R10 | [Reconstructing the Kinematics of Deep Inelastic Scattering with Deep Learning, 2110.05505v2][R10] | §2含table1；物理组合/辐射失衡，ep公式不能照搬ν厚靶 |
| R11 | [Nuclear binding energy and transverse momentum imbalance in neutrino-nucleus reactions, 1910.08658v2][R11] | 摘要与引言横向不平衡相关；核效应/方向动机，非FASER DIS性能 |
| R12 | [Energy flow polynomials: A complete linear basis for jet substructure, 1712.07124][R12] | 摘要；少量关联量思想，二值strip不继承能量流定理 |
| R13 | [Studies of Hadronic Showers in SND@LHC, 2504.01716v2][R13] | §3.1–3.4；纵向起始/两个采样响应及测试束，探测结构不同 |
| R14 | [CALICE hadronic energy resolution using software compensation, 1207.4210][R14] | 摘要；密度/成分分离，需要细粒度和含能条件 |
| R15 | [The Time Structure of Hadronic Showers in highly granular Calorimeters with Tungsten and Steel Absorbers, 1404.6454][R15] | 摘要；迟发与材料动机，未证明FASER有可用中子标签 |
| R16 | [Reconstruction of signal amplitudes in the CMS electromagnetic calorimeter in the presence of overlapping proton–proton interactions, 2006.14359v2][R16] | 摘要/引言多pulse段；模板与噪声方法，非FASER时间效果 |
| R17 | [An improved method for measuring muon energy using the truncated mean of dE/dx, 1208.3430][R17] | 摘要；长程随机能损方法，不适用于直接精确标定本低能μ |
| R18 | [Towards foundation-style models for energy-frontier heterogeneous neutrino detectors via self-supervised pre-training, 2604.07037v2][R18] | 摘要和§IV.1–IV.2相关片段；另一模拟主动量能器，非当前FASER验证 |
| R19 | [FASER tracker performance, NIMA 1079 (2025) 170605][R19] | 出版方摘要/引言预览/summary；效率与alignment研究，未获全文不声称逐项核实 |
| R20 | [FASER’s Electromagnetic Calorimeter Test Beam Studies, Instruments 6 (2022) 31][R20] | 检索摘要与可见§3.1方法片段；独立测试束/位置与HV标定入口，出版方全文请求受限 |
| R21 | [Photographing TeV Neutrinos with FASER, official briefing][R21] | 官方说明相关段；乳胶能量/匹配工作是独立资源，不能推定本项目已有匹配清单 |
| R22 | 用户附件，2023-03-01 waveform draft | 全文文本抽取，重点第5–10页；第6页渲染目视核对；历史算法非当前producer认证 |

[R01]: https://arxiv.org/html/2604.19199v2
[R02]: https://arxiv.org/html/2112.01116v2
[R03]: https://arxiv.org/html/2110.15186v2
[R04]: https://arxiv.org/html/2308.05587v2
[R05]: https://faser-public-plots.app.cern.ch/
[R06]: https://arxiv.org/html/2409.19030v1
[R07]: https://arxiv.org/html/2609.00842v1
[R08]: https://arxiv.org/html/2412.03186v2
[R09]: https://arxiv.org/html/1201.4320v1
[R10]: https://arxiv.org/html/2110.05505v2
[R11]: https://arxiv.org/html/1910.08658v2
[R12]: https://arxiv.org/abs/1712.07124
[R13]: https://arxiv.org/html/2504.01716v2
[R14]: https://arxiv.org/abs/1207.4210
[R15]: https://arxiv.org/abs/1404.6454
[R16]: https://arxiv.org/html/2006.14359v2
[R17]: https://arxiv.org/abs/1208.3430
[R18]: https://arxiv.org/html/2604.07037v2
[R19]: https://doi.org/10.1016/j.nima.2025.170605
[R20]: https://www.mdpi.com/2410-390X/6/3/31
[R21]: https://faser.web.cern.ch/briefing-20260325/
