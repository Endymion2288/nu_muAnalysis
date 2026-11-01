# 阶段29：研究进展复盘与路线重排

日期：2026-11-01。性质：基于既有 workbook 的研究评估与文献调研，不是一次新的数值分析。

## 阶段目标

回答当前工作是否取得实质进展、哪些分支已缺少新增物理收益，以及怎样继续达到“利用多变量改善 νμ 单事例能量重建并体现物理收益”的最终目标。交付修订路线和可直接执行的下一轮 Prompt。

用户明确要求本终端不复现代码结果、不建立 CERN 工作环境、不做 SHA 验证；本阶段全部遵守。没有读取 ROOT 或训练缓存，没有训练、拟合、伪实验或作业提交。

## 工作内容与输入

- 复核 stage13–28，重点核对 stage15 oracle 的输入语义、stage16 架构和高能表现、stage18–19 空间表示、stage21–22 先验重权、stage23–28 能谱与有限 MC 结论；参考旧路线图和已有配置。
- 联网检索高能中微子能量/非弹性度、shower 深度与响应、分类似然比、score 压缩、推断目标训练和有限 MC 文献。题名、链接与对本项目的适用边界汇总在修订路线文献节；对 SND@LHC 与 Kopp 等工作还参考公开 HTML 正文。
- 将后续主线改为：隔离信息缺口 → 检验概率表示 → 按结果选择物理分支 → data/模型响应控制 → 独立检验 → 最终测量。
- 保留 stage27–28 的统计发现，将进一步 MC-aware 方法对照限制为服务于冻结观测量的一项有上限任务。

实际使用的文本读取/定位方式包括：

```bash
git status --short --branch
rg --files -g 'AGENTS.md' -g '*.md' workbook docs
sed -n '1,240p' workbook/2026-11-01_stage28_mc-bootstrap-physics.md
sed -n '1,230p' workbook/2026-10-30_stage15_primary-muon-inelasticity.md
sed -n '1,180p' workbook/2026-10-30_stage23_forward-spectrum-closure.md
sed -n '1,125p' ml/configs/physics_decomposition.yaml
```

联网通过搜索工具查询与打开 arXiv 摘要/HTML；没有下载新的模拟样本或执行论文代码。本报告数值由原阶段报告引用，未重新计算，不额外制作看似独立的新误差条。

## 详细数据与证据评估

### 输入范围与独立性

普通几何，FASERNU-04/TI12MC04/OFLCOND-FASER-06/s0014，nominal run 200082/200083/200089/200093/200094/200100，官方 merge/without-IFT、原20 cuts和truth fiducial，unit weights。

已有 train 54,196 例/91来源组，validation 13,375 例/22来源组。validation 已被多轮用于训练选择与诊断，各阶段报告的置信区间不消除这种开发选择。正式 calibration 9,727 例、test 12,488 例、SIBYLL challenge 15,144 例尚未用于模型评价；stage28 的 calibration/test trial 是伪实验编号，不是这几个正式保留分区。

正式物理归一化、背景、接受度、真实data和生成器/探测器系统误差的完整收益：**未测量**。本轮没有要求补齐归一化才允许继续 unit-weight 条件研究。

### 实质进展

| 指标/量 | 已有结果 | 原始来源与解释 |
|---|---|---|
| μ/0.8 → F1 → F2 → F3 → F5，macro log-RMSE | 0.631674 → 0.516713 → 0.434073 → 0.390037 → 0.385054，无量纲 | [stage13](2026-10-29_stage13_energy-ml-bdt-first-results.md)；主要信息增益来自计数、电荷 |
| oracle O0/O1/O2 | 0.344342/0.241081/0.212329，无量纲 | [stage15](2026-10-30_stage15_primary-muon-inelasticity.md)；O0已含真实μ动量、方向、符号、真实xyz，不能归为只改善动量 |
| oracle电荷增益O2−O1 | −0.028752，95%来源组区间[−0.035312,−0.022389] | 同上；支持超出μ重建修正的能量分配条件信息 |
| BDT/ResNet/TabM F5 | 0.373879/0.373799/0.367379，macro log-RMSE | [stage16](2026-10-30_stage16_tabular-model-physics.md)；架构差小于前期读出增益 |
| 高能median bias，3200–6400 GeV | BDT −36.598%，TabM −37.064% | 同上；高能问题没有被架构替换解决 |
| full Deep Sets−summary | −0.000451，95%区间[−0.002160,+0.001491] | [stage19](2026-10-30_stage19_deep-sets-physics.md)；未确立独立空间增益，不代表所有拓扑方法无效 |
| N=1000、已知响应的fraction相对σ RMS | μ/0.8 39.797%，BDT UU 26.752%，TabM UU 28.049% | [stage23](2026-10-30_stage23_forward-spectrum-closure.md)；条件统计信息收益，非最终测量精度 |

### 当前分支的瓶颈

1. **信息缺口未分解。** stage15 的强 oracle 同时知道多个真实量；部署模型的差距还不能决定应优先改 tracker、重建深度还是补新读出。四格增加信息实验是下一项廉价而有判别力的工作。
2. **输出与任务可能错配。** stage23 的模型排序随 energy/rank reco 分箱改变，提示单个点估计加直方图的压缩可能限制谱信息。该解释需要新对照，不能视为已经测得信息损失。
3. **先验重权是性能交换。** stage21–22 的 flat 改善某些分箱和宏平均，代价包括 integrated loss和尾部；加大树预算没有解除交换。继续扫 flat/轮数不是新增信息。
4. **统计修补逐渐挤占原目标。** stage27 的单侧MC导致BDT覆盖67.097%→65.333%；stage28校准使macro65.556%→68.444%，但最高箱覆盖仍63.000%，alpha73.000%。两阶段RNG不同，不能把固定阈值中心变化当新方法收益。stage28点估计和bias未改变，最高fraction区间宽度+4.777%仅在16个测试trial测量。继续调阈值不会提高事件能量分辨率。
5. **独立信息和真实响应不足。** validation最高箱268例，251K/17charm/0π；stage24最细尾箱两折26/23例。重抽样不能增加独立来源。F5新增电荷仍需data控制和interaction/shower变体，而非仅SIBYLL flux挑战。

stage25–26 未发现一种统一修复所有跨来源闭合的方法。共同alpha只是人工箱内形状压力参数；来源置换中差异不异常也不证明不存在域偏移。当前没有证据把剩余偏差全部归为额外探测器/生成器系统误差。

primary诊断也限制模型投资方向：leading确认13,104例，任意保存轨迹可确认13,131例，额外仅27例；剩余244例未确认，不等于确定无轨迹。不能以“修复全部271例”为理由直接上大规模all-track GNN。`truth_st1`模长不能用于材料能损，相关新诊断需同参考面真值和协方差。

## 阶段性结论

**项目并非没有进展。** 当前最强、可作为研究基础的发现是：station计数和闪烁体电荷提供超出μ信息的增益，并在特定假设下提高选中样本能谱统计信息。尚未建立的是增益的物理分解、真实响应稳健性和独立样本确认。

**路线需要重排。** BDT/TabM基线保留；空间点云扩容、flat/树预算扫描、逐参数bootstrap调校暂时降低优先级。下一轮优先采用四格oracle和完整能量概率输出，分别判断可恢复信息缺失与输出压缩。更具创新性的后续候选是联合μ/transfer/depth概率模型及已知谱重权score学习，均以新实验支持为启动条件。

论文支持的是设计原则，不是本项目的预期分辨率。SND@LHC的起点/饱和控制、IceCube的μ与cascade分解、分类似然比与score压缩可借鉴；DUNE、SND、IceCube和新型高粒度量热器的性能数值不能搬用。

本轮新模型的性能、oracle各因素贡献、概率向量收益、CaloNu条件收益、真实data一致性、运行时间/吞吐/资源：全部**未测量**。这是一轮研究方案，不是声称已经找到最佳架构。

## 产物与文档验证

- [修订研究路线](../docs/nu_mu_energy_ml_revised_roadmap.md)：证据边界、缺口定位、概率表示、物理建模、新读出、data控制、统计分支上限、后续阶段和11项文献。
- [下一轮执行Prompt](../docs/nu_mu_energy_ml_next_step_prompt.md)：可直接在具备CERN环境的终端使用。
- [历史路线图](../docs/nu_mu_energy_ml_roadmap.md)：添加修订入口，保留旧阶段记录。

文档校验仅检查新增/修改文档的相对文件链接和空白格式，不执行物理验证或SHA校验。新增三份文档及历史路线入口共检查21个本地链接，缺失0个；文本空白检查通过。检查命令包括`git diff --check`、暂存后的`git diff --cached --check`及一次性Python相对路径存在性检查；没有新物理产物。

## 下一步计划

| 任务 | 所需输入 | 验收标准 |
|---|---|---|
| stage30 A：四格oracle | train/validation F5、stage15 primary产生动量和真实xyz、source groups | 同事件/同预算的增益与协同量，来源组区间、能量/y/matching分层，明确哪一信息缺口值得投入 |
| stage30 B：概率输出与压缩对照 | 相同F5、六箱标签、train内部组隔离校准 | 完整向量相对scalar/二维表示的条件谱信息、偏差、概率校准、有限MC敏感性和成本；不启用正式保留集 |
| 按A/B选择下一条物理主线 | 已测结果、曲率/深度可用性或匹配的CaloNu输入 | 明确选择μ响应、深度/联合模型、概率表示或新读出中的优先项，写清停止分支和必要新数据 |
| 冻结后独立检验与data响应控制 | calibration/test/challenge，MIP/高活动控制区和物理nuisance变体 | 区分开发与确认、flux与interaction、MIP与强子校准；无新数据时明确不能回答的物理问题 |

本阶段仅提交报告和研究文档；不提交训练数据，不修改现有模型或生产配置，不推送远端。
