# 下一轮执行 Prompt：稳定积分、失败回退与弱信号读出验证

先读AGENTS.md、修订路线第19节、`workbook/2026-11-01_stage37_calonu-native-response.md`、
stage37协议/source_audit/逐例表与stage35–36报告（注意HV更正）。stage30–37已完成。
用户重点reco p100–1000GeV，保留100–250/250–1000；≥TeV仅参考。

**唯一主线：在原波形上有界验证稳定积分、完整初始化与有限性fallback，再检验弱信号读出。**
不先重训BDT、扩架构、全量重模拟或重复已用test。

已测证据：

- stage35同事件65维F6加5CaloNu量，重点改善3.3359% [2.2676%,4.7581%]，
  没达到冻结5%扩展门槛；仍是生产条件下的信息，不是data可部署能量精度。
- stage36 MC约8GeV EM主要有正半波噪声pedestal贡献。
  stage37固定4来源/128例，96常规不切CaloNu质量，32诊断富集，原生联接全部通过。
  常规敏感层保存能量中位85.7583MeV、预测信号.115149pC、整流噪声1.78828pC；
  最大名义信号峰中位.797585σ，89/96<5σ；名义窗口捕获中位99.9956%、最小99.9382%。
  这是TOF采用名义GDML的卷积预测，不是完整digitization随机种子重放；
  signed−预测均值.0328667 [.0174613,.0482721]pC仍非零，不能声称精确信号闭合或直接扣常数。
- 8个诊断模块保存−inf/status0。原源码+ROOT6.28/12重放4个，4/4重现−inf，
  CB valid/fit_status正常、time有限；这四例不是time NaN。
  ROOT解析原函数中间项A=(n/|alpha|)^n exp(−alpha²/2)溢出：8例log(A)>double上限。
  同保存参数稳定积分全部有限正(.858457–65.9948pC)，细网格核验通过，无输出修改。
  富集样本不给总体失败率；两个故障fit数值不精确重现，不把全部异常归成一种机制。
- WaveformFitResult::clear()没有初始化全部字段，time NaN fallback未同步valid，
  最终积分有限性未检查，都是独立待验证程序路径。
- **HV更正**：MC源1ec47efe、data源d0b1b2dd实际CaloNu均correct_gain=false。
  2040682对通过q=MIP_ref*nMIP的float32前向关系，10个subnormal保留；
  q/nMIP是MIP_ref，旧报告“data含HV gainRatio”不适用。
  MC .0757/data1.847–1.986pC/MIP不自动证明25倍错误，不统一缩放。
- MC branch→GDML region [1,0,3,2]由factory/bit布局、历史payload和native id32认证。
  当前global tag的CableMapping-00标20–23为none，不能直接复现旧生产。
  历史四条payload/IOV在stage37 conditions_audit.json，后续显式固定。
  data hardware从20–23变6/7/14/15，实际survey/全球安装方向未认证，禁止按关联峰翻转。
- data15838同TBP/TAP15/15下两时期仍4.86558/.618096GeV EM，
  不由触发位模式混合或单一MIP常数改变解释。实际时序、活动、位置/硬件HV贡献未分离。

下一步：

1. 以stage37原波形作为修复开发控制，固定保存参数，比较稳定解析/数值积分和原ROOT路径。
   首先读明确的源1ec47efe；需要修改源码时只编译相关模块，优先匹配现成runtime。
   不为了避免溢出强行限制n、删除大信号或改物理标度。
2. 完整初始化fit结果；明确Gaussian/CB失败、time NaN、积分非有限等的valid/status和raw fallback。
   验证普通有效信号不受破坏、异常不无标记传播；不把仍不可靠的窄尖峰宣布修成物理信号。
   区分固定参数积分检查、源函数重放、完整tool重建，不相互冒充。
3. 冻结新来源组的有限原波形确认预算，保留两个p层、阈下/高信号/饱和/窄峰。
   先小样本核验，再Condor；如当前schedd繁忙可换空闲且有相应资源的schedd。
   不自动全量G4/重模拟/重跑PHYS，不以重复开发样本代替独立确认。
4. 在同一确认事件比较可于data执行的signed积分/固定模板振幅，报告噪声、偏差、baseline敏感性。
   truth HITS只作控制标签；没有精确匹配就保留未测量。
   验收通过后才另冻小预算同事件CC读出实验；stage35 test已用，不再作为新独立确认。

资源与保留支持：

- ntuples/energy_ml_stage37/native_response.npz为649006bytes，128例ADC、保存波形/时间、
  fit/status/参数、名义信号、敏感层汇总和完整lineage，逐字段读回；四个大HITS分片/payload已清。
  原HITS/波形源路径在冻结request与lineage，PG eventID重复，必须用真实input entry/子文件次序。
- 原生产CaloNu AFS build不可读；d32b0ff3只读字典相关五文件与源相同、持久化布局核验通过。
  禁止因此调用普通几何CaloHit helper或普通master几何重建。
- stage37共6 jobs（4成功、2因mass一float ULP技术失败），wall629.28s、CPU531.61s，峰2899424KiB。
  非有限解析积分重放使用原ROOT6.28/12，LCG109_cuda适合其余Python统计。
  PyROOT6.28构造vector<float>不能直接传float64 NumPy buffer，必须list转换并逐值检查。
- HITS保存energyLoss含Birk/nonuniform修正，不是未修正G4总沉积；不以truth_st*模长测材料能损。
- stage34/35 test已经评价，冻结结果/模型保持；truth/PDG/matching/isForward不进部署输入。
  无正式flux归一化材料就沿用unit默认，不重复询问；真实data闭合、强子标定、
  detector/interaction系统与最终谱收益仍未测量。

计wall/CPU/RSS、失败和重复检查成本；只留紧凑最终cache，不保存ROOT/xAOD/重复大JSON。
每阶段中文workbook须有实测物理结论、单位/输入/选择/命令/统计及系统局限/下一验收，
更新路线与Prompt，Conventional Commit，逐提交blob读回、工作区干净，不push。
