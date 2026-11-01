# stage34冻结协议：100 GeV–1 TeV重点与有限F5/F6独立检验

冻结时间：2026-11-01 12:05:51 UTC；起点`06224d5`。此时仅读路线、开发结果、模型metadata及
`files.tsv`元信息，**未读取calibration/test/challenge事件或标签**。本协议写入后才解封。
用户将重点扩大到100–1000 GeV；保留100–250、250–1000子层，≥1000仅作参考。

## 输入、候选与预算

- 选择、fiducial、最高pz leading、六nominal run、ordinary几何、official withoutIFT均不变；
  unit权重，无额外flux归一化；所有selected事件均保留，不能删未确认、非有限truth诊断或离群。
- F5=原46维，F6=F5+stage31原19维。固定现成三seed模型，各seed取best_iteration+1，
  将三个**log(E/GeV)**输出作算术平均，再float64指数化。与旧“各seed风险均值”不是同一量。
  部署输入不含truth、PDG、matching或isForward。μ辅助模型不启用。零新fit，不扫参。
- 两个固定物理基线：原始pμ及pμ/0.8，均不拟合、不校准。
- 每个F5/F6 ensemble仅允许一个全局log offset：c=mean_cal(log Etrue−log Epred)，
  在calibration上优化micro log-MSE。主结果为校准后，raw为控制；不用宏风险挑offset。
  不加条件校准、分位/coverage调参、seed筛选或truth p驱动的模型切换。
- 冻结顺序：先validation小样本重现程序；再calibration提取/推理并保存两个offset；
  保存后才解封test；test报告固定后才解封challenge。不用后两者返调任何参数。
  每分区PHYS仅一遍所需branch提取，F5已有cache，复用原19维定义；不重建RDO。
  大批量通过Condor，每批≤12 PHYS，1 CPU/1500 MB；先小样本，保存压缩小cache后删shards。

## 评价与统计（提前固定）

- 完整selected支持为headline，重点data可执行层为reco p∈[100,1000) GeV。
  子层[100,250)、[250,1000)、[1000,∞)。truth产生p相同分层、primary-confirmed/未确认、
  leptonic y六层、六Eν箱仅作MC诊断，并报告confirmed truth-p重点且y≥0.8的交叉层。
  truth缺失单列，不从headline删除。边界下闭上开，最后y箱包含1。
- 所有方法报告micro log-RMSE、相对误差mean/median bias、R68=(q84−q16)/2、relative RMS、
  |Epred/Etrue−1|>0.5与>1尾率；headline另报六真能箱等权macro log-RMSE。
  macro沿原约定只纳入中心样本N≥100的真能箱，bootstrap固定该active集合，报告支持。
- 500次来源组bootstrap，组定义沿原component+生成range（两period整组），95% percentile区间。
  同一重复所有方法共享评价组抽样；calibration独立组重抽计算两个offset，与评价组独立、两模型配对，
  因而校准后区间传播offset统计误差。raw不带该误差。报告各指标区间及F6相对F5风险改善/差值、
  F5相对固定pμ/0.8对照。分层稀少的零支持重复计数，不能补造测量。
  分层/多指标区间为描述性，不作多重检验校正，不据某个显著子层选择部署。
- 有限候选的扩展参考：校准后headline macro改善中心≥5%、95%下限>0，且reco重点micro
  改善95%下限>−1%；任一不满足则不据此扩架构。无论结果均报告所有子层，不自动部署。
  即使满足也不替代data/系统闭合。主比较是F6/F5，基线只是物理参考，不能把全部收益称新读出贡献。

## 挑战与解释边界

- manifest预计calibration 9727例/16组/32文件，test 12488例/22组/43文件，
  challenge 15144例/45组/45文件。challenge只有SIBYLL π，不是六run全混合。
- 先报challenge原unit分布；再与test的nominal π比较，在相同六真能箱逐箱比较误差，
  并计算二者共同N≥100真能箱的等权macro，避免把全混合差异全说成flux效应。
  不按challenge重新校准或重权拟合；π-only对照仍不能完全隔离其他生成/谱/来源差异。
  SIBYLL是flux/母粒子挑战，不是相互作用生成器或探测器系统误差的完整替代。
- 缺少匹配detector/interaction变体及data控制闭合，明确“未测量”；本阶段是独立保留分区
  单事件性能与迁移诊断，**不是最终能谱测量收益**。来源独立不保证完整生成谱系独立，
  旧flux-library入射ν复用问题保留为局限，不声称完全生成独立。
- 不扩大tracking审计，不追逐≥TeV达到低p精度，不用truth_st1模长测材料能损。
  低p μ准确而ν不准确时讨论能量分配/非μ信息；不能将oracle差全归拟合。

## 验证和交付

validation单PHYS重现原19维及六模型预测，检查run/eventID/manifest_index、reco p/charge、
truth E/xyz及matching与旧cache一致，再提交；零新训练。记录wall/CPU/RSS/吞吐和失败。
offset/test/challenge按顺序单独落盘并留时间戳。最终压缩cache读回一致、清分片和payload，
写中文stage34报告、更新路线与下一任务，Conventional Commit及提交blob读回，不push。
