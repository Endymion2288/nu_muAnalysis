# 原生输运与协方差来源核查

本阶段使用`source setup_env.sh --official`中的官方缓存，实际pilot路径
`/tmp/xcheng/nu_mu_calypso_master_d32b0ff3_180107`。`NU_MU_BUILD_INFO.txt`：

```
code_commit=d32b0ff3cc4a2dad4abfb1474a82422c3c25b305
faser_common_commit=1770d15df9311f6535c09909edf9ad64a5779e32
tracked_source_changes=none
athena=24.0.41 gcc=13.1.0 platform=x86_64-el9-gcc13-opt
build_type=Release filter=official_CI debug_symbols=stripped
built_utc=2026-10-28T12:22:31.197193+00:00
```

`../calypso`源码HEAD为35c4842，旧build的ReleaseData为1eb885ae，不能用它们冒充匹配生产。
本轮没有重编Calypso；两个诊断header在官方运行环境由ROOT解释编译。

以下均核对`git -C ../calypso show d32b0ff3:<path>`的实际内容：

| 源码 | 核查及意义 |
|---|---|
| `Generators/GenieReader/python/GenieReaderAlg.py`，`fillEvent` | GENIE动量乘Gaudi `GeV=1000`，位置乘`m=1000mm`，质量也乘GeV。 |
| `Simulation/ISF/ISF_Core/FaserISF_Services/src/FaserInputConverter.cxx`，约303–305、1032–1045行 | HepMC/ISF动量数值直接形成G4PrimaryParticle，没有再次按HepMC单位enum缩放。 |
| `Simulation/ISF/ISF_Geant4/FaserISF_Geant4Event/src/FaserGeant4TruthIncident.cxx`，约78–83、154–190、convert函数 | 顶点取G4 post-step位置；存活parent取G4DynamicParticle的post-step动量，更新CurrentlyTraced；不是产生动量复制。 |
| `Simulation/ISF/ISF_Core/FaserISF_Services/src/FaserTruthSvc.cxx`，约265–276行 | 普通再生parent barcode增加SIM_REGENERATION_INCREMENT，新旧parent接入相互作用顶点。 |

实测288/288事件HepMC动量enum声明GEV，但数值按上述源码为内部MeV；质量全部为
105.65837097167969（MeV数值）。逐事件primary px/py/pz和xyz与原PHYS真值核对通过。
这是元数据与数值约定不一致，**不是模拟能量放大1000倍的证据**。
位置数值按mm，亦逐事件核验。请求中的`LeadTrack_pz0`早已转GeV，导出时乘1000回MeV。

288条链共有1,276对相邻状态，全部同PDG且barcode差1,000,000，坐标连续、动量非增检查通过；
无分叉，链长1–18。后处理显式加上barcode检查，全部通过，不改变事件支持。
143条无有限跨面段的链，其最后μ记录均无end vertex且最后production在参考面上游；
这表示保存信息不足，不能解释为μ没有到达tracker。不得将最后动量外推为精确同面真值。

协方差来自`CKFTrackCollectionMergeWithoutIFT`、三站保存轨迹、最高pz leading的
`trackParameters()->front()->covariance()`。导出五参数、完整5×5矩阵与其`associatedSurface`
center/normal；参考面为此curvilinear plane，不能直接称某块sensor平面。
q/p单位MeV^-1，方差MeV^-2，σκ转GeV^-1乘1000。24例的原p/xyz/charge全部复现；
SDO诊断与既有primary确认标记全部一致。track_fitter原枚举0有20例、3有4例，未据此比较算法。
复用`TrackingTruthDiagnostic.h`，不通过hitSet错位索引匹配。

稀疏post-incident状态只能给动量界限。连续损失与离散损失同时存在，因此不能把一条HepMC边
保存的动量当沿途常数。被动材料、静态纯磁场及同μ延续条件下，对唯一有限跨面段取起点post-p
为上界、终点下一μ post-p为下界，扩大2e-6相对容差，不插值。此界限不提供精确pull。

方法参考（本轮实际读取，不移植材料数值）：

- [Geant4 Physics Reference Manual: Energy Loss](https://geant4.web.cern.ch/documentation/pipelines/master/prm_html/PhysicsReferenceManual/electromagnetic/energy_loss/enloss.html)：连续损失及高于阈值的离散次级产生；在线文档不是本runtime的数值验证。
- [PDG 2024: Passage of Particles Through Matter](https://pdg.lbl.gov/2024/reviews/rpp2024-rev-passage-particles-matter.pdf)：μ电离及辐射损失机制；不把其他材料的dE/dx或临界能量直接用于本探测器。

`truth_st1/t_st*`模长未用于材料能损。未重模拟，也没有把新输运truth与旧RDO配对。
