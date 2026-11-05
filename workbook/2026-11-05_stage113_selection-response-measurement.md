# Stage113：六源完整选择分母与响应测量，低能支撑不足及条件风险变化

日期：2026-11-05；起始 commit `fa63c4a`。按当前用户持续推进指令，执行[路线§94](../docs/nu_mu_energy_ml_revised_roadmap.md)所列[新工程合同](stage112_energy_ml/next_execution_contract.json)，完成Stage111原科学问题。Stage112的失败、QA与资源stop已独立报告提交，不改写历史。

## 1. 阶段结论和范围

**一次Condor任务9668067完成六个完整PHYS、全部60000条父事件的原生切选/身份隔离和传统估计风险测量；测量完成，两个主端点的统计可识别程度不同。**

- 真[50,100) GeV：两个charm来源G+及S50均0条，六源等权端点不可估，0/500完整draw；没有删去空来源后重归一。
- 真[100,200) GeV：六源等权ΔMSE=**−0.09447554689537985**（自然对数误差平方）；G+ MSE=0.15024725412432685、S50 MSE=0.055771707228947。只有**309/500**完整draw，低于冻结的475，因此**95%区间不提供**。不是达到统计确认的普遍改善。
- 原生20项有效cut与独立实现逐事件差异0，完整成员/leading一致、pz差0 GeV。程序错误未成为本次风险差的解释。
- 一个π来源显示切选伴随transfer组成变化和传统风险下降，另一π最低能略反向，K最低能不变、charm空支持；不能把选择说成所有低能优势或ML失败的唯一原因。

本次0新fit/forward/模型晋升；未重新比较ML与传统、未改善模型或认证最终能量目标。Stage110固定方向和Stage108固定方案结束状态不变。本阶段以完整结果或精确不支持原因验收，不要求有利效应。

## 2. 输入、选择与权重

精确输入沿用[六源manifest](stage111_energy_ml/source_manifest.json)：π/K/charm×历史train/cal各一个完整来源，按Stage105固定metadata中最小数值(origin,source_index)预定。六文件各10000条、67必要branch、逻辑文件合275663702 byte；没有按低能产额/结果换源，未扫其他EOS、未读旧REC/SP/波形、未生产新样本。

G0=全部有效名义MC cuts，仅去掉重建LeadTrack_pz0>50 GeV；truth νpz>50 GeV及原fitted-charge、质量、几何、requires均保留。G+=G0中有限正pz/Eν。S50=G0且pz>50 GeV；S100仅历史对照。固定传统估计Ehat=pz0/0.8，无offset/重拟合；主端点是每源log-error MSE(S50∩G+)−MSE(G+)，再六源等权。G0/G+在这六源本次相同，不推论所有样本必然相同。

模型政策维持一次方动量仅pz0，允许px/py、q/p、弯折；raw11/status、typed NaN、Calo缺失和合法signed负值保持。原生切选仍含fitted/reduced charge；本次不把同一阈值直接改套raw。pz≤50区域只诊断传统估计，不外推BDT。

|来源/成分/历史角色|PHYS父行|G0父行/eligible|S50父行/eligible|S100父行/eligible|
|---|---|---|---|---|
|55:4 / π / train|10000|383 / 321|360 / 301|334 / 275|
|55:164 / π / cal|10000|341 / 305|323 / 288|295 / 261|
|55:84 / K / train|10000|366 / 216|357 / 210|340 / 197|
|55:67 / K / cal|10000|359 / 287|341 / 269|333 / 264|
|55:116 / charm / train|10000|209 / 195|204 / 190|196 / 182|
|55:118 / charm / cal|10000|189 / 181|181 / 173|174 / 166|


完整父cutflow、每cut独立失败/unknown在[cutflow.tsv](stage113_energy_ml/cutflow.tsv)；[support.tsv](stage113_energy_ml/support.tsv)的eligible为身份隔离后的诊断父行，不代表新增训练样本。没有无轨迹时flatten丢行：例如55:4完整父行中8437条无轨迹，charm55:116为9034条；它们仍在PHYS分母，不具有可定义的估计误差。PHYS便利分母不是GENIE生成/输运/full incoming接受度或自然flux，S50/PHYS也不是实验全效率。

只读Stage87 split身份白名单incoming/role/initial_role/origin/source/group/run/eventID；test>cal>train，原隔离/低优先来源规则和全部K保持。已知test-key进入全父cutflow但隔离于主风险。新父行仅diagnostic-only，不进入训练。原生(pdg,px,py,pz) MeV精确键只是incoming代理，不是独立谱系证明。每源eligible incoming全部父视图选择前总权重1，不向幸存视图重分摊。

|source|cached选中核对|test-key|quarantine|低优先来源|未知key|eligible父行|选择前权重和|
|---|---|---|---|---|---|---|---|
|55:4|360|147|59|164|9038|9689|9468.0|
|55:164|323|172|35|0|9098|9828|9563.0|
|55:84|357|308|147|240|8852|9452|9031.0|
|55:67|341|317|72|0|8825|9683|9301.0|
|55:116|204|24|14|37|9668|9939|9472.0|
|55:118|181|36|8|0|9669|9964|9504.0|


表内test/quarantine/低优先类别存在重叠，不相加为互斥事件数。六源invalid key均0；权重和不等于父行数。[identity_audit.json](stage113_energy_ml/identity_audit.json)保留核查字段及完整计数。已有active split/模型缓存没有改写。

## 3. 主端点与统计支撑

|source|真E箱 / GeV|G+ N|S50 N|G+ MSE|S50 MSE|ΔMSE|有效draw/500|
|---|---|---|---|---|---|---|---|
|55:4|E50_100|12|10|0.0470614904759958|0.020526911527931308|-0.026534578948064495|500|
|55:164|E50_100|12|11|0.01767117042306934|0.01919662779493043|0.0015254573718610914|500|
|55:84|E50_100|2|2|0.01945397230006382|0.01945397230006382|0.0|428|
|55:67|E50_100|1|1|0.008041977340245667|0.008041977340245667|0.0|315|
|55:116|E50_100|0|0|NA|NA|NA|0|
|55:118|E50_100|0|0|NA|NA|NA|0|
|55:4|E100_200|50|45|0.305088091499621|0.0756443845471646|-0.22944370695245642|500|
|55:164|E100_200|43|40|0.18663827848922668|0.0538505257590858|-0.13278775273014087|500|
|55:84|E100_200|17|17|0.0921095301453855|0.0921095301453855|0.0|500|
|55:67|E100_200|6|5|0.2308936376889812|0.026271815999299352|-0.20462182168968185|498|
|55:116|E100_200|1|1|0.049617915510636906|0.049617915510636906|0.0|322|
|55:118|E100_200|3|3|0.03713607141210982|0.03713607141210982|0.0|481|


N是eligible父行数，不应自动称为独立事件数；incoming/权重和/ESS另见[risk.tsv](stage113_energy_ml/risk.tsv)。空支持保留NA；K最低能即使点差0，55:84只有428/500、55:67只有315/500有效draw，不强报[0,0]区间。100–200 GeV charm/train仅1条S50 incoming，322/500源内draw有效，六源共同后降至309/500。

预定seed2026110512、500次incoming-cluster Poisson(1)乘数；同incoming跨源共用乘数、保留固定源权重，无重抽直到成功。至少475完整draw才提供percentile95。源55:4在100–200 GeV的ΔMSE区间[−0.45677889328423454,−0.04398919569119209]，只是该固定来源的条件证据；55:164及55:67区间上端0，不能称全部来源显著改善。全部源内区间保存在[source_primary.tsv](stage113_energy_ml/source_primary.tsv)。

[原八层/固定真E和pz箱的全风险](stage113_energy_ml/risk.tsv)包括RMSE、bias、R68、正负/总tail50、unknown和高端；[图](stage113_energy_ml/selection_risk.svg)显示各源风险。困难层pz[50,100)且真E≥200 GeV的六源等权S50 log-RMSE=1.9493901819734019、负tail50=97.43589743589745%，39条eligible父行；这些事件未删除，也未由低能条件改善掩盖。此层的低动量仍可能对应高真能量，低pz不等于低E。

区间只条件于本六来源/incoming代理，不包含source抽样、refit、研究选择、真实系统、offset估计或新blind。cal/test早已开发，本次诊断不构成新独立确认；不将“不足以给CI”解释为零效应或物理无解。

## 4. 响应/transfer分解和物理解释

唯一有效ν顶点主μ按signed PDG、barcode/parent及0.0001 mm顶点轴容差匹配；不唯一/未知保留父行。r=ln(pz0/Eμ_vertex)，u=ln(Eμ_vertex/Eν)，c=ln0.8，e=r+u−c。r同时包含角度、材料/参考面与错leading等，不是纯tracker分辨率。六项r²、u²、c²、2ru、−2cr、−2cu保留符号，不能只比较正项并相加解释占比。

|source=55:4，真E箱/GeV|总体|r²|u²|c²|2ru|−2cr|−2cu|MSE|
|---|---|---|---|---|---|---|---|---|
|E50_100|Gplus|0.016732333768023706|0.15271503691763466|0.04979304449311734|-0.08350189125916123|0.008953475312447784|-0.09763050875606649|0.0470614904759958|
|E100_200|Gplus|0.03855766505587563|0.4782995205255541|0.04979304449311735|-0.08912603364060308|0.00392255587531812|-0.17635866080964083|0.305088091499621|
|E50_100|S50|0.001427150687311501|0.0176833661353534|0.04979304449311734|0.004515639148508255|-0.00787012107301589|-0.04502216786334331|0.020526911527931308|
|E100_200|S50|0.038281195865361904|0.1944524927779997|0.04979304449311734|-0.10102699251759688|0.006039820765862536|-0.11189517683757999|0.0756443845471646|


全部分解单位是自然对数误差平方，主μ能量GeV，顶点位置mm。55:4在100–200 GeV中平均y从0.2444648699331247降至0.18247734483038694，y<0.2权重比例从0.62升至0.6888888888888889；r均值0.008789310406274621→0.01353348714379344，u均值−0.39516862524364244→−0.25072464827813856。对应u²明显下降，r²变化很小，但signed交叉/标定项也改变，不能把全部ΔMSE归因于单一项。

最低能该来源平均y为0.162982967762638→0.09261704261457294，y<0.2比例0.75→0.9。支持“选中总体的transfer组成不同”这一有限判断；尚未证明在同完整X条件下分布改变。若S是完整X确定函数，则其支持内p(t|X,S)=p(t|X)，不能由边缘富集宣称信息界或模型必然无法学会。所有来源的y/r/u/pz/vertex分布在[variables.tsv](stage113_energy_ml/variables.tsv)，主μ/确认率在[validity.tsv](stage113_energy_ml/validity.tsv)。例如55:4全部G+父行383条主μ有效，但leading确认346条；主风险没有只保留confirmed。

## 5. 无效值、raw与fitted审计

独立typed域检查影子记录了“非有限或<0的VetoNu reduced charge，同时通过native q<30 pC”及其最终去向；**该标签只表示违反既有非负域假设，不是已证明的非物理占位**。

INVAL|source|cached选中核对|test-key|quarantine|低优先来源|未知key|eligible父行|选择前权重和|
|---|---|---|---|---|---|---|---|
|55:4|360|147|59|164|9038|9689|9468.0|
|55:164|323|172|35|0|9098|9828|9563.0|
|55:84|357|308|147|240|8852|9452|9031.0|
|55:67|341|317|72|0|8825|9683|9301.0|
|55:116|204|24|14|37|9668|9939|9472.0|
|55:118|181|36|8|0|9669|9964|9504.0|


以上按channel计数，通道可能重叠，不能相加称独立S50事件数。[完整计数](stage113_energy_ml/invalid_native_pass_counts.tsv)同时给出chi2ndf invalid单项pass为7/10/8/8/4/4，但其最终S50均0；nLayers/nDoF/radii/theta invalid单项pass本次均0。没有删除任一异常事件/修cut/换阈值。

[首40条例表](stage113_energy_ml/invalid_native_pass_examples.tsv)是全局顺序前40，均来自首源的VetoNu0，不是分层代表样本。例如55:4 entry52、run200082/event40052的reduced charge=−0.19242186844348907 pC、status0，最终S50=True且eligible=True；entry27为−0.19632811844348907 pC/status0，最终S50=False。它们不是数值−1/−999的直接证据。可能涉及带符号的基线/窗口积分，具体producer定义本轮**未核实**，不能把所有负电荷都设NaN或称cut故障。

[scintillator_audit.tsv](stage113_energy_ml/scintillator_audit.tsv)按全部父行与各选择给出fit/raw有限性、status、负raw及均值。沿用已审计FIT_INVALID=8|128|256|16|32|4、WAVE_INVALID=8|128|256，二者不同。例如55:4 PHYS的Veto20有1575/10000 fit状态无效、wave状态无效0，raw负286条；fit/raw均值1817.2667346797389/361.4896047163923 pC。这支持区分拟合状态和原始波形路径，但不同积分定义的均值差不能直接当能量偏差或标定系数。模型已用raw11，本次未将native拟合切选偷偷替换；真实占位和合法signed读数必须依赖producer/status逐变量判定。Stage112合成QA中的−999/非负变量−1/uint-wrap/NaN、合法signed量、fallback−1234控制值的处理继续适用，不宣称已识别所有真实占位约定。

## 6. 执行、资源和验证

冻结[protocol.json](stage113_energy_ml/protocol.json)后提交唯一新6CPU/12000MB任务9668067；站点改写RequestMemory=18000MB，首次start、exit0，无自动重试。沿用36真实QA，不再重复小批计时。六worker、ROOT/BLAS内线程1，0GPU；本阶段是短小I/O/向量化/原生cut工作，未训练神经网络。复用现成build/analysis，源码未改，不重编。只读67必要列，8MiB精确请求缓存，临时保类型TTree立即清理。6源67branch完整decode CPU分别可见[source_audit.json](stage113_energy_ml/source_audit.json)，没有沿用小批每行开销外推作为全量实测值。

监督器计独立进程组所有活后代自身+已reap子CPU，留60 CPU秒清理余量；wall停止阈值825秒。native本地读取在共享cap先预留16×该源完整67列压缩字节+16MiB，完成后对账，源请求同受cap。全部native与工作进程被计入，观察到最多26个进程，不等于26核并发。

|任务|GNU CPU / s|GNU任务wall / s|最大RSS / KiB|结局|
|---|---:|---:|---:|---|
|Stage112首次9668058|8.09|6.32|79080|API失败|
|Stage112补跑9668059|61.24|18.48|625752|QA通过、冻结外推stop|
|Stage113完整9668067|67.03（57.83 user+9.20 sys）|25.91|648868|完整测量exit0|
|累计|136.36|50.71|不相加|低于原3600 CPU/900 wall秒|

Condor history为58 user+9 sys CPU秒（调度取整）、slot wall32秒、ResidentSetSize750000 KiB，不与GNU外层相加。worker self5.992711 CPU秒/22.62705359 wall秒、worker/native合58.247361322 CPU秒均为嵌套诊断，不额外加到GNU67.03。[watchdog](stage113_energy_ml/watchdog.json)监测67.0 CPU秒/25.73192155 wall秒，无stop；GNU值为最终口径。GNU RSS不是整棵树同时总峰，整树峰、单核加速、GPUbusy、全会话成本均**未测量**。

新增source接口请求23299485 byte（底层read同值），native本地请求17636087 byte（返回同值），合40935572 byte。Stage112首次失败counter丢失保守上界计入后，112+113累计接口上界94323758 byte，低于原2GiB；它不是物理网络流量，物理网络**未测量**。输入逻辑文件大小不是读取流量。临时文件实际逐源byte见source_audit，六源合计上界小于128MiB；不是整棵树峰值实测。最终紧凑代码/文档/图表/日志按[storage.json](stage113_energy_ml/storage.json)清点，低于20MiB。

[测量验证](stage113_energy_ml/measurement_validation.json)：60000父事件native mask差0；e恒等式最大8.881784197001252e−16；汇总MSE六项闭合最大3.552713678800501e−15；record-space与独立incoming-key聚合bootstrap最大差2.220446049250313e−16。无来源重归一/替换、无选择/模型变化。完整数值计算在batch，本地仅stdlib汇总文本、文档/运输验证，未重新开ROOT/NPZ做数值分析。

实际主要命令：

```bash
python3 ml/package_stage113.py package
condor_submit -dry-run /tmp/nu_mu_stage113.ad AnalysisZipFramework/submission/ml_stage113.sub
condor_submit AnalysisZipFramework/submission/ml_stage113.sub  # 9668067
# worker: /usr/bin/time -v ... timeout --signal=TERM --kill-after=5 850 python -u ml/stage113_supervise.py
python3 ml/package_stage113.py collect
condor_history 9668067 -limit 1 -json -attributes ClusterId,ProcId,JobStatus,ExitCode,NumJobStarts,RequestCpus,RequestMemory,RemoteUserCpu,RemoteSysCpu,RemoteWallClockTime,ResidentSetSize,LastRemoteHost,CompletionDate
python3 workbook/stage113_energy_ml/validate.py
git diff --check
```

20项输入运输原字节一致；结果包169527 byte回收后去重，没有SHA。收集后仅将risk表空文本单元显示为NA、清除SVG行尾空白，数值和图坐标不变，记于[text_normalization.json](stage113_energy_ml/text_normalization.json)。临时ROOT/trace由worker删除；保留紧凑原生六日志和spool必要提交日志于`~/condor/nu_muAnalysis/stage113/`。确认job完成后仅删除本阶段输入/结果运输包，其他项目/旧缓存及Stage54五资产和后缀不动。[文档验证](stage113_energy_ml/document_validation.json)及[完成审计](stage113_energy_ml/completion_audit.tsv)区分本测量完成与项目目标未达。

## 7. 下一步任务与验收

本次固定六源实验结束。下一科学问题应优先解决已测的低能支撑缺口：在**已有**Stage105来源集合上，事前固定全部历史train/cal允许来源的父分母清单，使用原20cut/身份规则/选择前incoming权重，对π/K/charm×角色六个固定单元的低能及同pz高E支撑、传统风险和transfer组成做一次完整测量。所需输入为`workbook/stage105_energy_ml/identities.json`、其已知精确PHYS路径、Stage87身份白名单及本阶段已验证实现，不要求新模拟或读取test-only源。新合同必须在看扩展结果前冻结：六单元与来源层级的统计定义、共同incoming相关、支持不足判据及实际CPU/I/O上限；不能把多来源单元估计替换本次六个单文件端点，不能按低能产额挑源或逐步补到显著。验收为每单元的完整父支持/ESS与两端点或精确不可估原因，保留低pz高E和高端，实际资源与完整native闭合；来源层不确定度不足时明确不能外推。扩展的实际产额/功效/成本本轮**未测量**，不自动提交该批次或训练。

同一后续科学合同应沿精确producer实现核VetoNu reduced的signed/pedestal/fit定义、status与真实sentinel。需要与当前PHYS版本匹配的producer源/配置；只沿既知引用定位，不扫描全EOS/旧REC。输出逐变量合法域/占位/status依据表，保持signed原值；核实后才另定是否需要选择敏感性比较，不能以本次negative标签直接修cut或重训。

原最终两低能RMSE/传统上95≤1.05、all/direct≤1.01、其他五层/direct≤1.03、八层三向tail差direct上95≤+2 pp不改。真实response/interaction/FSI/材料/Calo/接受度/背景、新独立支持及locked确认仍未交付；本阶段不提供它们，不称项目完成。没有新样本不意味着全部研究无解，但本次统计稀缺不能靠改CI规则/丢charm/重抽解决。
