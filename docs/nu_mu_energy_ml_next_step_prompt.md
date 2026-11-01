# 下一轮执行 Prompt：同参考面真值与轨迹响应闭合

继续本仓库νμ能量研究。先读AGENTS.md、修订路线图第13节、
`workbook/2026-11-01_stage31_track-response-information.md`和
`workbook/stage31_energy_ml/source_audit.md`。stage30 A/B及stage31九个BDT已完成，不重跑。

本轮唯一优先任务：**用原始输入取得真实输运时刻、同参考面μ动量与reco拟合协方差，
将产生→参考面传播与reco→同面truth分开。** 保留完整F5及新增轨迹族F6这两个有限候选，
不无限加变量、扫参、扩大概率/拓扑网络或调coverage。

已有结论：同13,375例三seed，ν F5/F6 macro log-RMSE=0.378062/0.363245，
相对改善3.919% [1.957%,6.485%]，未达到中心值5%扩展门槛但不能排除5%收益。
辅助μ F5/F6=0.389132/0.366357，改善5.853% [2.440%,10.051%]，原始reco=0.517336。
不能将产生动量校正当无偏tracker测量：核心、最高能量偏差和高y存在折中。
confirmed primary p=3.2–6.4TeV有18/110电荷差异；confirmed y≥0.8的99例原始μ已相当准确，
ν F6−F5未见收益。先区分高p曲率尾与高y能量分配，不将二者全部归于μ拟合。

执行顺序：

1. 冻结有预算协议。读取manifest的实际RDO，不只检查PHYS：index101已确认保存
   `McEventCollection_p6_TruthEvent`、BeamTruthEvent、SCT_Hits、SDO与raw readout。
   uproot对1例TruthEvent报memberwise serialization不支持，这是reader限制，不能断言无输运信息。
   用匹配native POOL/ROOT字典审计μ continuation、barcode、真实顶点和覆盖；
   现成构建目录为`../calypso/build/x86_64-el9-gcc13-opt`，先核对构建版本与conditions，勿无依据全重建。
2. 设计代表性小样本：按原selected run/eventID/source键，对组件、能量、y、z分层，
   保留响应良好、尾部和未确认事件，不能只挑离群。导出reco front参考面坐标、q/p、5×5拟合协方差、
   primary输运状态/ID及匹配状态。FaserSiHit无输运动量，沉积能不能替代；
   truth_st1/t_st*模长来自产生点，禁止拿来测材料能损。
3. 如果TruthEvent仅有稀疏相互作用顶点，不能将最近顶点当精确同面真值。
   给出实际覆盖率并用有预算的少量G4步/参考面导出补齐，不保存大xAOD。
   小样本smoke后Condor；大数据不在登录节点计算，可换较空闲schedd。
4. 同confirmed支持上测传播变化、同面有符号κ残差、偏差、R68、非高斯尾、符号差异与pull，
   按能量/primary p/y/z/charge分层，来源组配对区间；未确认事件另报且不删除。
   不对近零曲率倒数再截断。无协方差或同面truth时明确未测量，不造pull。
5. 对应tracker data控制需匹配参考面、几何/对齐和conditions。
   stage31 run016000前16,000例pre-Calo tracker候选4,908例，19维有限，但MC/data端点z离散性不同；
   尚未证明模型迁移。旧data无isForward，继续只作MC诊断，不入部署。
   原“四Calo同时MIP”代理为0例且不适合单轨迹横向分块，不能声称已做MIP校准；
   Hi/Lo/status需校准与bit语义审计，不凭分布猜饱和，也不以MIP校准强子能量。

保持原六nominal run、官方merge/without-IFT、原20 cuts和最高pz leading、truth fiducial、unit权重，
不再次询问flux。F5计数、电荷、Calo、空间量全部保留，F6的19维定义不漂移；
19维含相关状态和确定性重表达，stage31并未证明每变量独立有用。
正式calibration/test/challenge先不读；同面控制完成后，为有限F5/F6候选冻结允许的校准与独立检验协议。
不按test结果回头调参再称独立。

每次推进必须得到实测物理结论，不仅提交作业或写缺字段。记录样本、选择、单位、
实际数值/来源区间、吞吐和CPU/RSS、源码/程序核查、产物路径及未测量项目。
完成后写中文workbook、更新路线/下一Prompt，去重JSON、保留紧凑缓存，Conventional Commit，
提交对象读回，不push。最终回答说明新结论、证据限制和下一条唯一优先任务。
