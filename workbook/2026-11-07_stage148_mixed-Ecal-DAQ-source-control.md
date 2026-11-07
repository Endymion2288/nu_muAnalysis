# Stage148：自然混合 Ecal 来源与实际 DAQ 控制

## 阶段目标与冻结输入

按[Stage147 冻结合同](stage147_energy_ml/next_execution_contract.json)，补 Stage132 §5.4 的明确覆盖缺口：Stage144 四个 Ecal 控制分别只有单一根类别，本阶段只检验一个既有自然训练父的混合 μ／其他根来源。不是新增独立ν、扩大自然ν生产、训练模型或低能性能验证。

[本阶段协议](stage148_energy_ml/protocol.json)仅使用 `ntuples/energy_ml_stage131/production_cases.json.gz`、`ntuples/energy_ml_stage137/boundary_evidence.json.gz` 等既有4032父证据。只在role1内，按原frame顺序固定至多一个 `Ecal all_MeV[0]>0 && all_MeV[1]>0` 的父；不按风险、能量、是否选中、clip或响应结果选例，不换父。原4032框架是分层支持，以下未加权计数不是总体物理混合率。

先64条缓存schema检查通过，再对全部固定证据审计：**2304个train父中266个符合混合条件，固定frame7**。35个分层／来源／原选中单元的完整计数见[支持表](stage148_energy_ml/support.tsv)。两低能层中，50–100 GeV的选中π有2个混合支持、选中K为0；100–200 GeV选中π／K分别8／7，未据此修改既定父或作功效／总体解释。K及缺失／困难者均保留原支持分母。

固定父为π来源、旧run200091、EVNT entry412863、G4 seed2026241707，真Eν=848.110006365 GeV，旧pz0=730.9504375 GeV，y=.210870792640，vertex-z=−1730.965087891 mm。输入为 `/eos/experiment/faser/gen/MC24/Genie/2025_flux_files/24_crossing_angle_distribution/wo_caloNu/sibyll-pi.EVNT.pool.root`。原重新选中数为0，**原selected raw／status参考不可得，仍保留该父**；不能转而选择有参考或低能父。该父不代表50–100 GeV性能。

## 实现、闭合与实际成本准入

复用 `software/stage142/observer-runtime.tar.gz`，无新的observer/CMake构建；ROOT Cling按需加载既有helper。pinned d32、FASERNU-04、OFLCOND-FASER-06、FTFP_BERT及原EVNT／entry／seed保持。实际G4 replay恰1个父，不当新独立ν。

以Stage143同runtime的164／247 scheduler CPU秒为已测参照，运输／Scint控制投影 `2×247+20=514` 秒；在支持审计实际5秒后，1000秒总预算中先留300秒给Ecal和审计，运输允许695秒，不设应用短超时。实际运输172秒，通过；随后剩823秒，按Stage144成功单Ecal96秒的3倍＋12秒审计预留准入。见[运输准入](stage148_energy_ml/transport_admission.json)、[Ecal准入](stage148_energy_ml/ecal_admission.json)。预测不是成本保证，实际累计CPU限制始终保留，未扩大父数或预算。

`stage142_pilot`重放及旧字段逐项精确复现；[六个HITS集合检查](stage148_energy_ml/parent_7_hitscheck.json)全部通过。五个读出hit集合的顺序、基数、identifier／barcode联结通过；Ecal持久化压缩最大逐hit能量差9.777462765×10⁻⁶ MeV、时间差.091056824 ns、位置差3.051757813×10⁻⁵ mm。时间／位置有压缩，未声称逐浮点精确；祖先标签按保留顺序联结实际SD hit，未按barcode猜根。

Ecal实际1743 hits：**1672个μ根、71个其他根、未知0**；官方SD修正后的持久化响应分别286.498076966／31.757922703 MeV。总响应318.255999669 MeV与原observer差1.518634235×10⁻⁶ MeV，过原压缩容差。它是Birks／局部响应修正后的hit量，不是incident Ecal能量、非μ出靶动能或守恒闭合量。

Scint实际7200 ADC采样逐值零差，46个采样触底；VetoNu无HITS、无ADC，与带实际ADC的signed负raw不同。Scint来源积分最大加和差7.827951549×10⁻⁵ pC，逐采样模拟加和差.002644062057 ADC单位，通过原32 float32 eps界。旧source输出的 `original_raw11_status_float32_exact=false` 在此表示原选中参考不可得；顶层摘要明确转为null，**不解释为发生raw不闭合**。

## Ecal实际ADC与同通道混合来源

沿Stage144已认证算法保留全部 **8个几何PMT的噪声随机抽样**，再比较4个有cable的PMT；同一实际780–930 ns、2 ns采样、含端点76点的raw窗，不套用Scint的780–980 ns窗。`stage144_native.py`只增加阶段／输入位置参数及新摘要，144默认数据路径和算法保持。

**2400个可读ADC逐值零差，0触底**。三个通道在同一有限窗内同时有正μ和非μ模拟信号；逐采样来源信号相加的最大差1.591979504×10⁻⁸ ADC单位，积分最大差6.234979893×10⁻¹⁰ pC，过原32 float32 eps界。这里相加的是舍入／噪声／截断前来源信号，不能把已数字化ADC或重建charge按来源直接相加。

[逐通道实测](stage148_energy_ml/parent_7_charge.tsv)，电荷单位pC：

| Calo通道 | μ根模拟信号 | 其他根模拟信号 | 总模拟信号 | 实际signed raw | status |
|---|---:|---:|---:|---:|---:|
| 0 | .000404841537 | .001122861478 | .001527703015 | .105937500000 | 1 |
| 1 | .000098501589 | .035855956366 | .035954457955 | .047949218750 | 1 |
| 2 | .056495535075 | .005662909559 | .062158445258 | .067363281250 | 1 |
| 3 | .327686811974 | 0 | .327686811974 | −.070859375000 | 1 |

全部unknown根信号0。通道0／1／2的数学来源混合成立，但信号很弱、全部status1，**不是已得到可用的强子活动判据**。通道3有正模拟信号且实际raw为负，保留合法signed测量；raw包含实际噪声、基线估计和量化，不能等同于无噪声来源信号。没有取fit charge替代raw，也没有为任何非0 status赋到达时间。

完整旧private RNG初末状态对本父未保留，只复用原seed规则，不能声称完整旧状态精确；原selected Calo status缺失保持未知，原Calo raw未持久化，不能声称原raw比较精确。全部控制输入／实际raw由新重放实际测得，不伪造旧参考。

## 为什么总hit响应不小、固定窗电荷却很弱

为区分程序／物理原因，最终同父缓存审计增加一次固定端点核查：原完整采集采样0–1198 ns、原hit数字化直方图[−20,1200) ns及原raw窗780–930 ns。不扫描窗口、不改选择／seed／风险，不引入新的可输入timing。

[端点实测](stage148_energy_ml/parent_7_window_endpoints.json)用原conditions／hit时刻／全部8-PMT顺序重新生成模拟信号，原有限窗电荷复算通过。各非零来源的raw窗／完整采集信号比均≥.999953052；没有hit响应落到hit直方图边界之外。模型pulse峰为818或820 ns，**只是内部响应QA，不是status1测得的Good-Hit到达时间**。

例如Calo3：244.047670362 MeV修正μ根hit响应，完整采集模拟.327700726671 pC，原raw窗.327686811974 pC，比值.999957538；Calo1其他根26.704162653 MeV对应.035857639811／.035855956366 pC，比值.999953052。其余通道及校正hit时间的逐来源统计完整保留。

因此本例中**不能用“有限raw窗漏掉大部分pulse”解释弱信号**。当前实际response conditions下预测的电荷本身很小，signed raw也明显受测量噪声／基线／量化影响；没有据此认定探测器绝对gain错误或给出μ／hadron总体分离能力。本阶段未测量data幅度校准、SNR效率／覆盖、真实系统误差或低能能量收益，均保持“未测量”。

## 资源、命令、存储与验证

```bash
python3 ml/stage148_submit.py support
python3 ml/stage143_monitor.py --stage 148
# 写入支持与成本准入后
python3 ml/stage148_submit.py transport
python3 ml/stage143_monitor.py --stage 148
python3 ml/stage148_submit.py ecal
python3 ml/stage143_monitor.py --stage 148
python3 ml/stage148_submit.py audit
python3 ml/stage143_monitor.py --stage 148
python3 ml/stage148_finalize.py
```

4jobs／4starts：9674514、9674522、9674537、9674554，全部exit0，均已终态。**272 scheduler CPU秒／477 aggregate execute wall秒／0GPU**，各步CPU为5／172／84／11秒，低于1000秒总预算。任务在 `~/condor/nu_muAnalysis/stage148/`；运输／Ecal请求4CPU／12GB，支持／审计请求1CPU／4GB、站点实际提高到2CPU／6GB；BLAS各1线程，本单父G4／ROOT任务没有GPU训练可加速。

运输GNU含子进程167.15 CPU秒／246.35 wall秒；G4本身29.09／39.01秒。Ecal主逻辑73.931339／92.808816秒，GNU峰RSS1,817,368 KiB为本阶段最大；Ecal ROOT读取2,525,094 B，HITS检查读取446774 B。最终端点审计6.450405 CPU秒／84.674658 wall秒，GNU峰492860 KiB，主要wall受环境／文件加载影响；嵌套计时不与scheduler相加。没有宣称GPU／多核吞吐提升或完整网络I/O总量。

核4任务终态后，四份事件文本精确合并回读为 `ntuples/energy_ml_stage148/event_records.json.gz`，659044 B；顶层原路径→原JSON文本字符串，可恢复原gzip／文本。源码版本胶囊 `software/stage148/source_snapshots.tar.gz` 为29704 B。删除37,147,359 B重复运输及分散事件副本，未保留ROOT/xAOD中间件、未动原EVNT及其他阶段。见[存储审计](stage148_energy_ml/storage_cleanup.json)。源码／shell语法、文档本地链接及diff空白检查通过，不提交事件载荷。

## 阶段结论、下一任务与整体状态

该固定自然父补上**同一Ecal通道／有限窗中混合根的DAQ来源方法控制**：标签按实际SD hit传递，8-PMT噪声／4可读PMT ADC和模拟来源加和闭合。它覆盖弱信号，未覆盖Ecal截断或总体μ辐射尾；原选择失败／参考缺失明确保留。一个848 GeV父不能认证50–100 GeV可部署收益或全样本标签质量，也不能据弱信号关闭整个Ecal／波形分支。

下一按[Stage149合同](stage148_energy_ml/next_execution_contract.json)转回§5.5真实μ状态：仅已知MC100012 HITS，先原前4条、通过实际raw／native身份／full covariance和实测成本后最多原前64条，复用pinned digitization／reconstruction提取真实5×5状态covariance、surface／单位、TSOS-PRD归属和raw响应。无新G4／ν家族／能量或响应fit，不重开Stage124 Z57模型或旧Q15／Qshape30阈值网格。输入模拟metadata缺失／不匹配照报，不用覆盖flag认证跨生产；无真实同面truth就不报pull。3000累计CPU秒、首pilot限800秒，先具体测量再定扩展，不把重复prefix计新独立N。本阶段尚未执行Stage149。

真实μ covariance校准／关联不确定度、宽μ能区与当前ν／data适用性，乳胶、曝光GRL／背景／全生成接受度、相关系统辅助输入和独立确认仍缺。Stage87 direct62、原1.05/1.01/1.03及八层三尾+2 pp、Stage137双箱5%扩大门保持；全部K／角色、pz0-only、允许px/py/q/p/弯折、raw11、typed NaN／合法signed、非0 status无timing、Calo缺失与reserved关闭保持。整体goal未完成。
