# 下一轮执行 Prompt：CaloNu匹配μ与波形响应控制

先读AGENTS.md、修订路线第17节、`workbook/2026-11-01_stage35_calonu-readout-information.md`、
stage35冻结协议与source_audit。stage30–35已完成，不重跑已评价test或旧模型训练。
用户重点100–1000 GeV，保留100–250和250–1000子层，≥TeV只参考。

**唯一主线：以已有匹配CaloNu through-going μ MC/data控制读出响应和拟合质量，暂不扩模型。**

已测物理依据：

- 同事件C0=65维F6，C1=70维，额外四模块+total EM-scale；CaloNu bck124 PHYS，
  test3247例/18组，重点2689例风险改善3.3359% [2.2676%,4.7581%]；总体2.9276%。
  两低p子层均约3.3%；重点R68从16.6154%降至15.5974%，50%尾从3.9048%降至3.3842%。
  这些是500来源组配对且传播calibration统计的unit-MC结果，不是系统闭合或最终谱收益。
- 收益明显随交互z分层：最前57例改善21.33%；−2650至−2300mm的573例改善7.51%；
  −2300至−1950mm占2201例，仅1.01%且区间跨0，total中位7.5911GeV EM、q84=8.8760GeV。
  lead block中位0，88/264有限非零。尚不能叫约8GeV响应为MIP或强子标定。
- 预注册重点改善中心≥5%扩展门槛未达，区间上限亦<5%。不降低门槛、不加架构/扫描。
- s0015缺truth_barcode，严格primary确认未测；kinematic-parent代理不能冒充确认。
  真p重点高y仅40例、代理仅8例，不能声称解决stage34 confirmed高y缺口。
- MC fit14309及未选择run016000 data前2048条的有限读出代数/单位核验0失败；
  MC total10个非有限，模块1最小−117895.168GeV且status32=CB fit failed，模块2最小−1670.179GeV且status48。
  异常fit未删/裁剪，非有限按XGB missing；具体失效波形机制和收益影响未隔离。
  status1是threshold failed，不能一律当missing；total raw/overflow定义不等于四模块fit和。

下一步依次执行：

1. 查找已有CaloNu through-going μ MC/data及生产记录，核验通道映射、安装全局位置/外推面、
   几何/材料、时期、HV/增益、conditions、bck maker。reference为Calypso22.0.49、CaloNuMC/1ec47efe，
   **K/charm exact bck maker未核实**，所存forward ntp日志不能证明它。
   本地匹配源树`/eos/home-x/xcheng/FASER/calypso`，优先现成构建；不自动用ordinary master重建CaloNu。
2. 先小样本确认支持，再冻结有预算的响应控制协议。through-going μ选择与轨迹外推使用data可执行量，
   不按CaloNu信号本身挑出好峰；报告选择效率/覆盖/失败，避免只选好波形。MC真值仅诊断，禁入部署。
3. 四模块检查raw/fit电荷(pC)、nMIP、E_EM(GeV EM)、status/overflow、轨迹交点/路径长度依赖，
   分来源/运行块给区间及匹配条件。检验窄响应是否符合μ穿越/标定，及极端fit是否能由raw/status识别。
   单位公式通过不是data/MC物理闭合；阈值失败与缺容器分开。不得臆造精确安装全局z。
4. 必须得到实测响应/覆盖/拟合原因的物理结论；若缺匹配输入，量化缺口、记录未测量，不用不相容
   CC MC/data分布造闭合，不预报控制结果、不自动全量重模拟或重训模型。

状态、存储和禁止事项：

- `ntuples/energy_ml_stage35/`四分区和两预测NPZ共9607764bytes；
  `ml/artifacts/stage35/seed_{0,1,2}/{C0,C1}.ubj`共7667374bytes，六fit已冻结，勿覆盖。
  紧凑cache已逐字段读回；13shards、2payload已清。不重复PHYS提取。训练配置重复JSON已合并。
- stage34 calibration/test/challenge和stage35 calibration/test均已评价；以后据此调模型只能当开发，
  新独立确认要新未使用来源。旧ordinary模型只作域外参考，不以跨几何差估计CaloNu读出收益。
- 不加tracking变量/拓扑/概率大架构，不追逐TeV精度，不按truth p切换部署。
  truth方向、PDG、matching、isForward均不入部署；truth_st*/t_st*模长禁止测材料能损。
- 无新flux归一化材料继续unit默认，不重复询问。来源组互斥不保证完整flux-library谱系独立。
  MIP/强子标定、data/探测器/相互作用系统以及最终谱收益尚未完成。

LCG109_cuda CVMFS现成环境；大批量Condor，可换空闲schedd，stage35用bigbird21。
小样本先验证，计wall/CPU/RSS/吞吐和失败成本；只留紧凑最终cache，不留ROOT/xAOD和分片/重复JSON。
每阶段中文workbook含实测数值/单位、输入/选择/命令/验证/产物/统计和系统局限/下一验收标准，
更新路线与Prompt，Conventional Commit、逐提交blob读回、工作区干净，不push。
