# stage35预注册：同事件CaloNu读出有/无，有限BDT预算

冻结UTC：2026-11-01 12:43:05；起点bfec61d。在此之前只读三个首文件schema与200139首文件
（固定fit pilot）的10000事件；只有该pilot的218个selected事件及诊断已读，未读新calibration/test事件。
manifest按文件名、组件和固定seed生成，未用事件值决定划分。旧stage34分区不作为本阶段新独立证据。

## 物理问题与样本边界

问题：在CaloNu几何的同一事件、同一选择及其余相同重建量上，额外5个CaloNu读出能否降低ν能量风险，
特别是100–1000 GeV与高y？不比较两个几何的性能差，不改变tracking或重建样本。

输入是已有200139(π)/200140(K)/200146(charm)的s0015 **bck PHYS**，46/63/15文件，共124份。
这是独立的CaloNu生产分支，不是普通几何d32b0ff3官方merge。生产日志reference为CaloNuMC/1ec47efe、
Calypso22.0.49、FASERNU-CALONU/OFLCOND-FASER-05。π首文件日志显式backward；K/charm所存日志未显式
对应bck maker运行，确切bck执行配置不能仅由目录证明，单列为来源局限。两个候选始终使用同一份实际bck事件，
因此不会把这类差异当新增读出收益。不调用不支持CaloNu的普通几何master重建。

原20cuts逐项保留；其中原就存在的CaloNu PMT truth z∈[−2928,−2812]mm veto在本几何实际生效。
leading仍为最高pz，原truth fiducial/reduced-charge/100GeV pz门槛保持。没有按CaloNu信号切样本；
零读出保留，非有限值保持XGB missing策略，不删未确认/尾/高y。unit MC，无额外flux归一化。

已有s0015 PHYS缺truth_barcode，**严格barcode-primary确认未测量**。primary p/y按唯一sign-correct μ
与ν交互顶点一致定义；另列matched t_pdg、parent PDG、产生xyz和三动量逐项一致的代理，不能叫严格确认。
代理不作为选择或部署输入；truth_st*不读取，不用于材料能损。

## 输入和训练冻结

- C0：全部F6的65维reco，C1：相同65维+四CaloNu模块E_EM和CaloNu_total_E_EM，共70维。
  所有EM-scale能量由MeV/1000转GeV；不叫已标定强子能量。
  模块fit值与total的raw/overflow处理不等价，按源定义保留，不能强制total=模块和。
  status/饱和、charge/nMIP/Edep仅作审计，不额外入模，不尝试第二变量族。
- 数据在124来源组内按组件打乱，固定seed20261102；每组件首文件强制fit以供pilot，累计比例
  0.65/0.75/0.85/1四舍五入。实际组数：fit81、stop11、calibration14、test18。
  π为30/4/5/7，K为41/6/7/9，charm为10/1/2/2。组件+生成range为组，不按能量重新划分。
  来源互斥不证明生成flux-library谱系独立，保持该局限。
- 两候选×三seed(20261102/03/04)，相同fit/stop、log(Eν/GeV)平方损失、原base其余XGB参数，
  depth5/max1600/patience80/nthread4，每fit wall上限120s；达到时间如实报告，不补fit。
  最多六个正式fit，不扫参、不增加架构。最多两个20-round fit/stop split smoke作为技术验收。
  不把旧ordinary模型分数当本几何中的受控消融，旧模型仅固定参考，不借其参数挑新模型。
- seed取best_iteration+1，log预测平均后指数化；每ensemble只允许calibration均值log residual一个offset。
  主结果calibrated，raw为控制；不条件校准，不按test改读出、budget、seed或offset。
  提取器可统一提取全部分区标签以紧凑落盘，但拟合脚本只加载fit/stop，校准脚本只加载calibration；
  人工和统计评价在六fit及offset冻结后才启用test。该规则不同于stage34逐分区物理提取，须照实记录。

## 评价和物理控制

- headline完整selected test的micro及六Eν箱macro（中心N≥100的箱等权，active集合在bootstrap固定）。
  主重点为data可执行reco p∈[100,1000)，固定子层[100,250)、[250,1000)、[1000,∞)参考。
  truth p相同层、primary-valid、上述proxy/非proxy、六leptonic y、六Eν箱、高y≥0.8且truth重点交叉层
  都是MC诊断；不把代理分层说成严格primary-confirmed。没有支持就明确未测量。
- 所有方法报告log-RMSE、mean/median relative bias、R68、relative RMS、|relative error|>0.5和>1。
  基线原始pμ、pμ/0.8不拟合。500来源组bootstrap，各候选共享评价重抽，另独立重抽calibration组
  传播两个offset误差，给95%percentile区间及配对候选差，稀疏层缺支持重复逐项记录。
  这些是描述性分层/多指标区间，没有多重检验校正。
- 预先设物理读出控制：CaloNu总读出为零/非零；vertex z分层[−3000,−2928)、[−2812,−2650)、
  [−2650,−2300)、[−2300,−1950)、lead block[−1769.65,−1619.65)，跨PMT被veto支持不补造；
  报各层N/非零率、读出分布及与transfer proxy Eν−Eμ,vertex的秩相关。
  相关不等于独立条件信息，只有同事件有/无风险差回答BDT可利用增益。
  不以“有非零信号”直接宣布有用；zero可能含无击中/低阈值/缺容器，须结合源代码/status审计，不一概当故障。
- 优先结论准则：重点相对log风险改善中心≥5%、配对区间下限>0，且完整支持micro改善下限>−1%，
  才支持进一步投入该读出建模；未达仍报区间/子层，不能将不显著说成无信息。
  高y有无收益独立报告，不要求≥TeV达到低p精度。即使有收益也不自动部署，data/响应闭合另需验证。

## 验证、预算和交付

先在fit pilot对照现成C++/YAML：20步cutflow和selected事件键完全一致，46维F5值在数值容差内一致，
19维复用stage31定义。CaloNu单位、status/饱和、total/模块定义与生产提交源核对，真实data小前缀只做读出
有效性/尺度审计，不当MC/data谱一致性或强子标定。大批量124份提取≤13 Condor jobs，训练3jobs×2fit。
同一worker4CPU训练，提取1CPU；实测wall/CPU/RSS/吞吐，记录失败和重复，不保存大ROOT/xAOD。
最终小cache读回，清shards/payload；中文阶段报告必须有实测物理结论、输入/单位/命令/成本/局限/下一验收标准，
更新路线及下一Prompt，Conventional Commit并逐blob读回，不push。
