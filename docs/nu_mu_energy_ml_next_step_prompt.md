# 下一轮执行 Prompt：匹配历史CaloNu条件的最小Athena响应闭合

先读AGENTS.md、修订路线第22节、`workbook/2026-11-01_stage40_calonu-full-response.md`、
stage40协议/配置/源码fixture范围及stage35–39报告。stage30–40已完成。
用户重点reco p100–1000GeV，保留100–250/250–1000；≥TeV仅参考。

**唯一主线：最小Athena数字化/重建闭合，之后才决定有限能量建模。**

最新实测：

- stage40六新原生来源2/43、49/105、111/119，共181=133常规+48诊断；142完整、39全缺。
  与stage39组隔离，但都是stage35已有fit，不能称新独立ν能量test。
  常规24/133缺失全在名义中心下游，全部空HITS；原生产status1/零读出不能区分缺失与真实阈下。
- 直接删空HITS早退不安全：两个calo生成方法均用首hit区分探测器。
  新patch新增显式CaloNu noise helper→原convolve(empty)，只影响空CaloNu且显式opt-in，默认false。
  非空信号生成/卷积函数保持，接口升2.0，使用须重建工具/算法及相关接口消费者。
  patch适用1ec47efe；未部署到外部checkout或生产。
- 源函数fixture用原create_waveform_map/generate_baseline/create_kernel/convolve及新helper，
  ID迭代/历史conditions/EventContext/Gaudi handle为明确替身。2048独立合成noise，ADC RMS3.01505对理论3.01386，
  256对无hist/全零hist全部ADC相同，理想恒定波形0/2048。原缺失ADC未补造。
  完整Athena/GeoModel、原始随机种子及RDO→rec→PHYS验证仍未测量。
- 有界时间模型固定四通道共享时间、各有符号振幅与常数baseline，中心820ns、范围±4ns、步长0.25ns。
  不接truth/PDG/matching，不裁负/删边界；一次时间导数诊断未改振幅损失，未继续扫描。
  新15常规+19诊断≥1pC，三个中心的模型最大误差4.64515%/3.82736%，中心变化0；冻结门槛通过。
  含噪声常规仍5/15误差>5%，不能称逐例5%精度或真实时序系统闭合。
- 名义109常规fixed→有界RMSE0.143794→0.160735pC，恶化11.7815% [8.6347%,14.8819%]；
  离峰RMS增加14.5725%，低于冻结25%上限。相对signed仍改善61.0335% [58.8093%,62.8819%]。
  常规信号中位0.005268pC；94弱信号中43时间触边、41总读出负，全部保留；高信号0/34触边。
  不把弱信号拟合时间当新物理特征，不开发基于truth的逐例选方法。

下一阶段任务与验收：

1. 审查现成匹配Calypso22/CaloNuMC源与几何/conditions是否可用。
   保留1ec47efe源，候选patch在`ml/patches/calonu-empty-noise-1ec47efe.patch`；
   stage38稳定积分补丁仍是源函数级，不能假定已在完整tool生效。
   优先现成build，只在隔离位置构建必要接口/工具/算法及消费者，记录2.0接口兼容性和实际成本。
   不修改共享外部工作树，不自动全量G4或全量PHYS。
2. 原生输入从已认证空/非空HITS小支持取，先smoke。
   显式装载原CaloNu几何、历史cable/payload/IOV、Digitization条件，认证实际channel/id/branch；
   当前mapping中20–23为none不可直接复现。普通runtime只读字典通过不等于几何重建正确。
   无匹配时量化缺口、推进能独立验证的部分，不虚称完整生产闭合。
3. 开新确认前冻结支持/预算/随机控制/验收：空HITS四通道有同条件噪声，
   非空信号在相同随机控制下保真，空事件插入是否改变后续随机流需单独记录；
   检查RDO→rec baseline/status/有符号电荷和存在性，保留阈下/负/失败/饱和覆盖缺口。
   source fixture合成控制不能填进旧缺失观测后冒充新原生数据。
4. 完整响应验证通过后才另冻同事件F6、原CaloNu、改进波形的有限能量模型实验。
   固定与有界时间都保留参考；本次确认不再调范围/步长，不逐例挑最优输出。
   输出映射/校准用train内部独立预测，能量test设计须明确stage34/35已评价，
   新波形来源隔离不等于新独立ν能量test。报告误差/bias/R68/尾部、p/y/primary及配对区间。
   缺失标记贡献和电荷→ν能量/谱收益继续未测量，不由电荷RMSE直接推算。

输入与资源：

- `ntuples/energy_ml_stage40/response.npz`1204523bytes：181原生ADC/保存波形/信号/固定读出及lineage；
  `source_noise.npz`39622bytes：2048独立合成读出，只作源函数控制。合计1244145bytes。
  六分片22原生字段/metadata/schema重联相等，重复分片和payload已清；汇总依赖归档前分片，勿重提旧jobs。
- stage39 cache1244048bytes、stage38 cache620787bytes、stage37 cache649006bytes可作已有开发控制。
  stage40用bigbird14、cluster17556151，3 jobs全exit0无重提，总wall479.46s/CPU349.47s、峰1447980KiB。
  新阶段另冻预算，先smoke，大批量Condor；可换空闲且资源匹配的schedd。线性分析无需GPU。
- 现成d32b0ff3只读字典持久化布局已核验，不是相同几何生产。源函数fixtureROOT6.38/LCG109_cuda；
  原积分故障重放ROOT6.28/12。vector<float>用list转换，避免PyROOT buffer类型误读。
- branch→region `[1,0,3,2]`，历史payload/IOV见stage37 conditions_audit.json，覆盖三个CC run。
  CC每HITS1000例、合并10000；PG每HITS10000、合并50000；真实entry和指纹联接不可省。
  ν近光锥质量用signed m²舍入界，barcode/生成质量/三动量严格匹配，不放宽身份。
- CaloNu MC/data均correct_gain=false，MIP_ref前向标度核验通过；约25倍q/nMIP差不等于已证标定错误。
  data安装/survey方向未认证，不能按关联峰翻转；data15838同触发两时期4.86558/.618096GeV EM原因未分离。
  data闭合、绝对MIP/强子响应、探测器/相互作用系统及最终谱收益继续未测量。
- truth/PDG/matching/isForward不入部署，不用truth_st*模长测材料能损。
  没有flux/亮度材料就沿用unit默认，不重复询问。

记录wall/CPU/RSS和失败/重复成本，保持紧凑缓存与归档，不保存新ROOT/xAOD大中间结果。
每阶段中文workbook含实测结论、单位/支持/命令/验证/系统局限及下一验收，更新路线与Prompt，
Conventional Commit，提交blob读回、工作区干净，不push。
