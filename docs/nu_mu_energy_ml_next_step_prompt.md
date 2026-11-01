# 下一轮执行 Prompt：完整CaloNu读出响应与有限时间自由度

先读AGENTS.md、修订路线第21节、`workbook/2026-11-01_stage39_calonu-cc-waveform.md`、
stage39冻结协议/结果/源码审计及stage35–38报告。stage30–39已完成。
用户重点reco p100–1000 GeV，保留100–250/250–1000；≥TeV仅参考。

**唯一主线：先控制空HITS噪声缺失机制和强信号时间敏感性，再决定有限能量建模。**

最新证据：

- stage39冻结六来源组π/K/charm各两组，190例=142常规+48富集，皆为stage35已有fit分区。
  PHYS真实entry/fingerprint→HITS/RDO/rec及PHYS读出全部联接通过。
  固定stage38模板+常数项，没有本次CC调权、逐例选时间或用truth作输入。
- 112常规共同有效波形，signed→主候选总电荷RMSE0.484287→0.128924 pC，
  改善73.3787% [70.1344%,76.7130%]；离峰RMS0.479922→0.133249 pC。
  两p层改善76.9216%/68.6610%，常数baseline扰动最大1.421085e−14 pC。
  高p层bias−0.028192 [−0.048949,−0.006720] pC，未扣常数。不是ν能量73%收益。
- 常规30/142（21.1268%）无任何波形且空敏感HITS，全部在名义中心下游。
  全190有147完整、43全缺、无部分缺失；缺失估计保留NaN/presence mask。
  `CaloWaveformDigiAlg::execute`空HITS时在波形/噪声生成前返回，PHYS默认charge/raw0、status1。
  因而缺失是生产机制，不能当data测得的无噪声零；status1不能单独判有效波形。
  全fit零读出2403/14309、重点2074/11658只作描述；未认证全体零值均为空HITS。
  stage35约3.34%收益中缺失标记贡献未测量，不宣称全部收益为伪影。
- 常规高信号≥1pC仅17例。名义模型相对RMSE2.4062%，提前2ns为7.5224%，
  14/17误差>5%，12/17相对名义变化>5%；π/K/charm均有约−7%早移偏差。
  固定单模板时间鲁棒性不足，不能用总体平均降噪掩盖。
  常规名义信号中位0.007343pC；高y≥.8仅8例，无≥1pC参考；饱和精度未测量。
- stage38稳定CB积分/初始化/fallback源函数验证通过；正常40/40脉冲保真、time NaN注入拒绝。
  仍只是源函数scaffold，未完成完整Athena tool/生产修复。
  stage35同事件F6+原CaloNu重点改善3.3359% [2.2676%,4.7581%]，未达冻结5%扩展门槛。
  stage34/35 test已用，后续改模型不能再叫新独立确认；stage39也不是新ν能量test。

下一阶段具体任务与验收：

1. **先验证空HITS读出路径**。以已认证空/非空事件和原生产源为输入，
   定位最小源码修复或受限源函数验证：无信号也应生成同条件通道噪声，
   明确输出容器/通道/presence语义，检查PHYS缺失标记。
   只构建相关模块/函数，使用历史CaloNu映射/conditions；不默认重跑全量G4或PHYS。
   模拟控制不得伪装成新测得的原生观测，不向现有缺失ADC直接补造随机数后当真实波形。
2. **冻结一个简单时间自由度**，例如模板+时间导数联合估计或固定有界时间拟合。
   先stage37–39已有控制开发，接口仅waveform/ADC/baseline/conditions，
   HITS只用于评估；不得truth选时间、逐例选更优方法或扩大模型扫描。
   覆盖弱信号、负值/失败、名义高信号、固定±2ns，保留饱和覆盖缺口。
3. 新来源确认前，冻结来源隔离/支持/预算及噪声、偏差、强信号时间鲁棒性门槛。
   验证空HITS不再成为无噪声理想零标记、非空响应保真，并定量比较读出噪声与时间扰动。
   若未通过，定位物理/程序原因，不删尾、不把旧开发支持再称独立确认。
   若没有适用的新原生支持，明确源函数控制范围与未测量项，不能虚称全链生产验证。
4. 响应控制通过后才另冻同事件F6、加原CaloNu、加改进波形的有限能量模型实验。
   映射/校准只用train内部独立预测，划分须明确已用test。
   报告误差、bias、R68、尾部、来源组配对区间和p/y/primary支持；不立即恢复架构竞赛。

输入、条件与资源：

- `ntuples/energy_ml_stage39/cc_waveform.npz`：1244048bytes，190例ADC/保存波形/名义信号、
  存在性及固定读出、完整lineage；六分片22原生数组逐字段重联相等，metadata/schema保留。
  分片与payload已清，见archive.json；汇总脚本依赖归档前分片，不重提旧jobs重造重复产物。
  stage38 `confirmation.npz`620787bytes、stage37 cache649006bytes仍保留作开发控制。
- stage39使用bigbird14，17555948六技术失败、17555949两合并成功，严格8jobs预算已用完。
  总wall1007.52s/CPU770.33s、峰1462368KiB，最终原生0.405655events/s。
  新阶段另冻预算，先小样本；大批量走Condor，繁忙可换资源匹配的空闲schedd。
- 原生产源1ec47efe；现成d32b0ff3用于只读持久化字典，布局通过，不是相同几何重建。
  原ROOT6.28/12可源函数重放，统计用LCG109_cuda；PyROOT vector<float>用list转换，避免buffer类型误读。
  CC每HITS1000例、合并10000例；PG每HITS10000、合并50000，不能照搬。
  近无质量ν质量检查用signed m²舍入界，barcode/生成质量和三动量严格匹配；不是放宽身份。
- branch→region `[1,0,3,2]`已认证；历史payload/IOV见stage37 conditions_audit.json，IOV覆盖三个CC run。
  当前tag CableMapping-00的20–23为none，不能直接复现旧生产。
  data硬件6/7/14/15、安装/survey方向未认证，不能按关联峰翻转。
- CaloNu MC和data均`correct_gain=false`，MIP_ref前向核验通过；约25倍q/nMIP差不直接证明标定错误。
  data15838同TBP/TAP15/15两时期仍4.86558/.618096GeV EM，时序/活动/位置/HV贡献未分离。
  data闭合、绝对MIP/强子响应、探测器/相互作用系统及最终谱收益继续标注未测量。
- 不以truth_st*模长测材料能损；truth/PDG/matching/isForward不入部署。
  没有flux/亮度归一化材料就沿用unit默认，不重复询问。

计wall/CPU/RSS及失败/重复成本；只留紧凑最终cache，读回后清重复分片，不保存新ROOT/xAOD。
每阶段中文workbook记录实测物理结论、单位/选择/输入/命令/统计与系统局限及下一验收，
更新路线与Prompt，Conventional Commit，提交blob读回并确认工作区干净，不push。
