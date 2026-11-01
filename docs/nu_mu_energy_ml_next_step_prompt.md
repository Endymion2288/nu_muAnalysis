# 下一轮执行 Prompt

请继续本仓库的 νμ 能量重建项目。先读 `AGENTS.md`、`docs/nu_mu_energy_ml_revised_roadmap.md` 和 workbook stage15、16、23–29。执行 stage30，目标是定位下一项可实现的物理增益，回答“主要缺少哪个隐变量，以及单值能量输出是否丢失已有信息”。不要默认延续 stage28 的逐参数覆盖率调校。

本轮在具备 CERN 环境的终端实施；复用已有软件、F5 和 stage15 truth 缓存。沿用六个 nominal run、官方 merge/without-IFT、原20 cuts、最高pz leading、truth fiducial、unit weights及来源组划分；保留全部异常和尾部。不做 SHA 验证，不重生产全量 ntuple，不因缺少正式 flux 归一化而停下。大规模计算先小样本，再走 HTCondor。

先写 stage30 预注册协议，固定一个 BDT 容量和三个 seed、来源组划分、主比较、指标、计算上限和有实际意义的最小增益。不要通过反复加树、换架构或改分箱追逐显著性。validation 已多次用于开发，本轮结果仍是开发证据。训练、早停和概率校准使用 train 内按来源组隔离的样本或 cross-fitting；calibration、locked test、SIBYLL challenge 暂不启用。

完成以下两个实验，A为主实验，B为同阶段有预算上限的表示检验：

**A．拆开 oracle 缺口。** 在完全相同事件和同一 F5 基线 X 上，比较 X、X+真实 primary μ 产生动量大小、X+真实交互 xyz、X+两者四格。保持重建输入，不额外混入真实方向、PDG或matching标记。truth 输入严格隔离为 oracle，不能进入部署 allowlist。报告总体及逐能量、leptonic y、primary-confirmed 分层的 log-RMSE、median bias、R68和尾部，给出来源组配对区间、动量/顶点增益与协同量。如果 xyz 增益明显，再用一个小型 z-only/xy-only 控制区分深度和横向位置。不得把 oracle 差距全归因于 μ 拟合；不得使用 `truth_st1` 模长测材料能损。

**B．检验单值压缩。** 同一 F5 用 BDT 学习原六能量箱的完整概率向量，保留全部六个概率。比较完整向量、同一模型压成单个平均log-energy后的表示、既有scalar+十reco类；补充 scalar-only 概率映射或廉价二维摘要，判断收益是否只是旧分箱过粗。映射与校准须使用 train 内独立预测，不能用训练集拟合内预测伪装泛化。不同训练目标或统计表示造成的差异要分清，不能全部称为压缩损失。

先固定 nominal 箱内形状、α=0。若训练先验为π_b，q_b(x)=P_train(b|x)，用 L(f)∝∏_i Σ_b f_b q_b(x_i)/π_b 比较条件谱信息；不能把posterior直接求和当成真谱，也不能将同一事例的Ehat与q当独立观测相乘。报告相同假设N=1000下的谱误差、最弱方向、偏差与有限MC敏感性，概率校准和罕见高能箱稳定性。nominal结果支持后，仅做预先指定的within±1压力测试；不要在本轮扩展α联合拟合或开发新的多层bootstrap。这个固定形状公式不能直接套到未知α；α依赖的参考密度不能随意丢掉。

如果完整概率向量未胜过scalar，也照实报告，并区分证据支持无实用收益和样本不足。不要为了“必须进步”继续扫描。四格oracle若提示动量主导，下阶段安排同参考面真动量/曲率协方差诊断；顶点主导则先检验reco深度可预测性；二者协同则考虑联合概率模型；仅概率表示有收益则保留简单BDT并改输出。若现有读出缺少可恢复信息，转向同事件有/无CaloNu或有效的新读出信息族。大规模all-track模型前先审计候选：已有validation仅27例可由其他保存轨迹新增确认primary，其余244例是未确认，不能假定全部可恢复。

最终写中文stage30报告，列出实际测量、输入/配置、单位、命令、产物、时间和资源；未完成项目标注“未测量”。用结果选定下一条主线，并明确停止哪些分支。保留BDT基线，暂不扩大Transformer/GNN竞赛；为选定信息族安排后续真实data响应控制。更新路线图并按仓库规范提交。最后给我：新物理结论、支持证据与局限、下一步唯一优先任务和一段继续执行的Prompt。
