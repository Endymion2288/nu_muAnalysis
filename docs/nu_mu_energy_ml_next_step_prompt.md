# 下一轮执行 Prompt：原生CaloNu响应链与通道映射审计

先读AGENTS.md、修订路线第18节、`workbook/2026-11-01_stage36_calonu-muon-response.md`、
stage36冻结协议/source_audit与stage35报告。stage30–36已完成，不重复已评价test或旧模型训练。
用户重点100–1000GeV，保留100–250和250–1000子层，≥TeV只参考。

**唯一主线：有界原生HITS→RDO waveform→xAOD/PHYS响应链和通道映射核验，暂不建模。**

已测依据：

- stage35同事件C0全部65维F6、C1加五CaloNu量，重点2689例改善3.3359% [2.2676%,4.7581%]，
  未达冻结5%架构扩展门槛；不降低门槛、不扫描。收益随交互深度变化，只是unit-MC条件证据。
- stage36独立外部符合选择，262236 μ MC+248323 data候选；18 Condor jobs，0新fit。
  MC四通道全低于5σ阈值88.2865%；该层total中位8.26571GeV EM，正半波噪声预期7.93610，
  逐例比值1.04178 [1.04106,1.04246]，约8GeV主要有整流噪声pedestal贡献。
  源findRawHitValues只积正采样，76×2ns；公式冻结前提出，没有用正式结果调参数。
  仍有约4%残差，不叫精确纯噪声闭合、MIP峰或真实强子能量，不对CC逐例扣除。
- data全阈下4.9009%，同层.287250/.276203GeV EM，比值1.04523 [1.03424,1.05126]。
  MC/data raw约.46–.48/.48–.52pC，但有效charge/nMIP=.0757对1.847–1.986pC/MIP。
  data含HV外推，不等同原MIP_ref；不能据25倍差直接改增益或缩放旧模型。
- 名义DB+GDML box中心[10,−21,−2605.68]mm，非实测安装；直线±tilt不是native传播。
  事后raw关联候选排列MC[1,0,3,2]、data[3,2,1,0]，未被认证或应用。
  冻结的分支=region假设下paired interior/off负值不能解释成物理反向信号。
- data15838首/中文件4.76952/.610798GeV EM，有效MIP比例基本不变、raw和阈值率不同；
  不用单一MIP系数漂移解释，不删除该时期。data几何/HV/conditions和MC不相同，物理闭合未测。
- MC模块非有限21例全无fit failure位，data117中114无该位，raw全有限；
  固定源fitCBall time NaN分支没清valid是具体可疑路径，但未case replay，不归因所有异常。

下一步依次执行：

1. 有界查已有同源HITS/RDO/xAOD及原生dictionary/匹配build、合并次序、ChannelMapping和conditions。
   source commit1ec47efe，Calypso22.0.49，优先现成build，不用普通master替代CaloNu。
   先小样本证明能读和联接，再冻结≤4来源组（两符号各2）、≤128个预定义μ候选及异常对照的协议。
   无新ML fit，不自动全量G4；有必要的有界重放先计预算再Condor。
2. 独立认证geometry region→identifier→hardware→ntuple分支，给MC/data适用时期。
   不把stage36关联峰当硬件真值，不在同样本上调排列造MIP闭合。
3. 同例比较active真实Edep MeV、波形signed/正半波积分pC、baseline/noise、峰位置/时间窗，
   digitization kernel/gain/MIP_ref/HV条件；区分信号弱、窗口漏失、标度不同和噪声整流。
   保存失败/缺失与各环节覆盖，不能用truth_st*模长测材料能损。
4. 重放代表非有限/未标flag和正常对照，检验valid/status路径；查data15838两时期trigger/conditions。
   验收要以数值判断哪个响应环节可闭合/不闭合，含来源/统计与程序解释；不能只做目录搜索。
   缺匹配输入就量化未测量，禁止用跨几何分布冒充闭合；响应核验后再决定修生产/校准/建模。

身份、来源、存储与禁止事项：

- `ntuples/energy_ml_stage36/{MC,data}.npz`共66953477bytes，53字段，全字段读回。
  18分片/payload已清；提取全部原ROOT不再重跑。PG eventID在同一合并文件中重启！
  cache的(file group, source_selected_row)唯一，但selected ordinal不是原ROOT entry。
  native配对需input entry/生成子文件顺序，不得仅run/eventID或selected ordinal强行联接。
- MC实际输入在bck/s0015；μ−6日志显式backward，μ+0020/0040/0059日志reference没有backward，
  不能证明三份实际bck maker。data6日志均backward。日志和fingerprint不证明完整生成谱系独立。
- stage35六模型及四分区/两预测保持；stage34/35 test已用，之后调模型不再作为独立确认。
  不追加架构/tracking变量/概率扫描，不按truth p切换部署；truth/PDG/matching/isForward不入部署。
- 无新flux归一化材料继续unit默认，不重复问。真实data闭合、强子标定、探测器/相互作用系统、
  最终谱收益仍未测量；不得把统计条件区间当这些系统的包络。

LCG109_cuda CVMFS现成环境；大批量Condor，可换空闲schedd，stage36用bigbird21。
小样本先验，计wall/CPU/RSS/吞吐与失败；只留紧凑最终cache，不留ROOT/xAOD/重复JSON。
每阶段写中文workbook，含实测数值单位、输入/选择/命令/验证/产物/统计及系统局限/下一验收，
更新路线和Prompt，Conventional Commit，逐提交blob读回、工作区干净，不push。
