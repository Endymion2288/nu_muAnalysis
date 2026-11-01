# stage48 预测前冻结协议

唯一问题：冻结X87与X87+连续真z的条件收益能否迁移到其训练/校准之外的来源？
依据stage47后的路线§29/信息计划§14/执行Prompt。无可认证新blind同几何来源；
现有manifest所有分区均参与过stage35，fit又参与stage42 A。只采用来源外开发复现，不能称独立生产或新blind。
来源/暴露详source_exposure.tsv，选择与UTC详ml/configs/source_transfer.json。
身份轮转取4000例，无标签/残差/p选择；同原最高pz、truth fiducial含lead、PMT veto/unit MC，不截Eν或丢难例。
先首pi/首K各20例特征pilot，复用stage44原22项函数/单位/半径，不增加新变量族。
完整提取CPU1 Condor，仅最小reco列、每文件一次打开；缺失branch/错身份不可填零或删例。
只加载stage44 local和stage45 oracle_z已存模型及原assigned fold。
6份原cal概率映射可确定性重建，必须对原3703预测精确回读；无新支持标签/先验适配，0能量fit/0目标校准。
真z只oracle；无truth方向/PDG/matching输入，不用truth_st1模长测能损。
重点100–1000 GeV Z对X相对log-RMSE改善≥2%且500次component分层来源配对95%下限>0。
同报all/p/Eν/y/z/component/运动学parent代理的N、来源、误差、bias/R68/尾、proper/Brier与六箱固定响应谱诊断。
barcode不可得不称primary-confirmed；≥1TeV参考。来源区间条件于固定模型/校准，不含重训/系统/开发选择。
不为有利结果增fit/重校准/重选来源。过门槛只建立此支持等级的迁移证据，不通过也不证明信息不存在。
先中文报告再Conventional Commit，更新两路线和Prompt，回读blob/clean，不推送。
