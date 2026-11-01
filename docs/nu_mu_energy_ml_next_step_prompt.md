# 下一轮执行 Prompt：CC同事件波形读出与时间/形状控制

先读AGENTS.md、修订路线第20节、`workbook/2026-11-01_stage38_calonu-waveform-repair.md`、
stage38冻结协议/确认表及stage35–37报告。stage30–38已完成。
用户重点reco p100–1000 GeV，保留100–250/250–1000；≥TeV仅参考。

**唯一主线：另冻小预算CC同事件原生波形比较，先确认可联接与时间/形状适用性，再决定有限建模。**

最新证据：

- stage38旧开发8非有限恢复；84组合成、75组旧参数独立积分通过。
  新来源1/4/7/10、128例/512模块，96常规/32富集；原4非有限→修复0。
  新56组固定参数quadrature通过，40/40正常可辨认正脉冲保真；不强限n或删大/负/窄响应。
  time NaN注入拒绝且status32/fallback有限；无饱和覆盖。
  patch针对1ec47efe，仅源函数scaffold/ROOT解释编译验证，未完成Athena tool重建或生产修复。
- 主候选为固定生产模板+常数基线项，mean820 ns，未逐例选峰/调时间。
  96常规总电荷signed→主候选RMSE0.485709→0.135039 pC，改善72.1974%
  [69.3173%,74.3946%]，离峰RMS0.490822→0.115990 pC，常数baseline扰动不变。
  两个p层分别改善73.1825%/71.4506%。只是电荷相对名义HITS信号的条件MC证据，不是ν能量精度。
  主候选bias−0.012532 [−0.023001,−0.002063] pC仍非零，100–250 GeV层−0.032646 pC，禁止事后扣常数。
- 原数值修复fit常规仍RMSE1.760829 pC，阈下raw整流噪声没有被积分补丁消除。
  MC已知digitizer baseline解释性signed RMSE0.235104 pC，理想白噪声0.255404 pC；
  保存baseline积分偏移RMS0.409148 pC，与signed误差相关0.875539。已知MC baseline不作data输入。
- ±2 ns控制常规RMSE0.144640/0.139250 pC，但32富集从名义0.119275升至
  1.575770/1.694162 pC。强信号时间/形状失配是具体局限，不逐事件选三者最优，不忽略高信号。
  斜坡/非平稳、相关噪声及饱和精度未测量。四来源block区间不含系统误差或完整总体统计不确定性。
- stage35同事件F6+原CaloNu重点改善3.3359% [2.2676%,4.7581%]，未达冻结5%扩展门槛。
  stage34/35 test均已评价；后续变模型不能再叫新独立确认。stage38只通过μ弱信号读出门槛。

下一步具体任务：

1. 审计已有CaloNu CC来源，定位同事件PHYS/rec/RDO及历史cable/conditions，
   用实际entry、多变量fingerprint和独立真值签名核验联接。PG重复eventID不能照搬为唯一键。
   先小样本，量化可覆盖的CC事件/来源组与缺失；不能用不同几何、不同事件或普通几何helper假匹配。
2. 新冻结小预算波形支持，保留p层、低/高信号、阈下、负值、失败/饱和及固定±2 ns控制。
   部署接口只读保存waveform/ADC/baseline/conditions；HITS只作控制标签，不用truth逐例调时间。
   先查CC时间/形状和常数baseline适用性，不能把μ电荷增益直接折算为ν能量/谱收益。
3. 若可比较且读出适用，冻结同事件输入/划分/预算，比较原F6、加原CaloNu、加固定signed/模板。
   映射/校准只用train内部独立预测；不立即扫描网络或高维变量。
   报告ν能量误差、bias、R68、尾部和来源配对区间，分p/y/primary状态，明确统计与系统局限。
   新确认组和stage35已用test分开说明，不能把开发测试冒充新独立确认。
4. 若CC高信号时间控制不通过，先量化失效区域，再决定有限的时间/形状模型或生产读出约束；
   不逐例选更优输出、不删尾、不默认全量重模拟或重跑PHYS，不恢复架构竞赛。

输入与资源：

- `ntuples/energy_ml_stage38/confirmation.npz`：620787 bytes，128例ADC/波形/名义信号、保存和修复读出及lineage，
  逐字段读回，分片/payload已清，见stage38 archive.json。开发stage37 cache649006 bytes仍保留。
- stage38用了bigbird14，cluster17555947，4 jobs全exit0无重提，wall564.62 s/CPU324.11 s、峰1405544 KiB。
  大批量走Condor；繁忙schedd可换空闲且资源匹配者。优先现成build，仅改模块才构建。
- 原生产源1ec47efe；现成d32b0ff3只读字典持久化布局核验通过，但不是相同几何重建。
  原ROOT6.28/12适合源函数重放，其余统计用LCG109_cuda。
  PyROOT6.28 vector<float>用list转换并逐值检查，不能把float64 NumPy buffer误作float32。
- branch→region `[1,0,3,2]`已认证，历史payload/IOV见stage37 conditions_audit.json；
  当前tag CableMapping-00的20–23为none，不能直接复现旧生产。
  data硬件6/7/14/15、安装/survey方向未认证，不能按关联峰翻转。
- CaloNu MC和data实际均`correct_gain=false`，MIP_ref标度前向核验通过；
  MC .0757/data1.847–1.986 pC/MIP不能直接证明25倍错误，不能统一缩放。
- data15838同TBP/TAP15/15两时期仍4.86558/.618096 GeV EM；实际时序/活动/位置/HV贡献未分离。
  data闭合、绝对MIP/强子响应、探测器/相互作用系统及最终谱收益继续标注未测量。
- 不以truth_st*模长测材料能损；truth/PDG/matching/isForward不入部署输入。
  没有flux/亮度归一化材料就沿用unit默认，不重复询问。

计wall/CPU/RSS及失败/重复成本；只留紧凑最终cache，读回后清重复分片，不保存新ROOT/xAOD。
每阶段中文workbook须有实测物理结论、单位/选择/输入/命令/统计与系统局限/具体下一验收，
更新路线与Prompt，Conventional Commit，逐提交blob读回、工作区干净，不push。
