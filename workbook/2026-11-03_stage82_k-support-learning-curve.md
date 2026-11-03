# Stage82：放宽 K 重建时限并完成 π＋K 支持学习曲线

## 阶段目标与用户修订

用户本轮明确要求“放开那个时限，把K文件的样本也用起来”。本阶段因此覆盖历史文档不自动RDO生产/不重试失败K、0新ROOT和3600秒/累计7200CPU秒支持预算；保留原物理定义、角色、去重和风险门槛。不以旧限制阻止已授权生产，不运行新GENIE/G4。

旧stage70 K作业9662832.1在CPU3532秒、wall3604秒时被SYSTEM_PERIODIC_REMOVE，运行观察约8801/10000事例。此前未交付完整K，并非已证明输入损坏。stage81的两个现成K PHYS实际为BackwardWithoutIFT而不是名义MergeWithoutIFT，故不能直接并入原模型；缺失Track_isForward只是诊断问题，不是唯一拒绝原因。

## 输入、配置与实施

复用三个此前已冻结合法train来源，不按产额/残差另挑：200081 k:00630–00639（stage70）、k:00090–00099和k:00160–00169（stage81）。完整RDO路径、历史角色、选择概率和逻辑大小见[生产协议](stage82_energy_ml/production_protocol.json)。source概率仅描述历史抽样，不作为物理flux权重。

采用现有d32b0ff3/Athena24.0.41/EL9/GCC13运行包、TI12MC04/FASERNU-04/OFLCOND-FASER-06，无IFT，ntuple使用`--CKFTrackType merge`；原pz>50 GeV/geometry/quality/truth fiducial/全部困难和尾不变。原62列中一次方动量仅pz0，px/py、q/p、弯折允许；11signed raw_charge、VetoNu reduced、typed domain/status/dependency NaN维持。原fitted-charge选择不改，fitted scintillator charge不入模型。

新K native Calo03-LG经实际charge→E_EM formula与当前COOL payload核查后，仅四模块E_EM按1.061711079650782转换至参考01-LG，再以传播NaN的普通sum重算总量，其余57列逐值不动。旧stage70/81 π缓存已经01-LG，绝不二次缩放。当前payload新读结果与stage70全部measurements精确一致，见[条件](stage82_energy_ml/calo_conditions_qa.json)。完整响应系统效应仍未认证。

小样本：实际转移包在stage70固定K的前16身份跑通reco→merge ntuple→原选择/62提取，全部exit0，RDO/xAOD/ntuple均16事件。reco wall26.70秒、user11.51秒、sys2.37秒、peak1067424KiB；ntuple wall10.65秒、user5.61秒、sys1.60秒、peak918116KiB；提取wall10.76秒、user7.24秒、sys0.95秒、peak660148KiB。merge输出3条backward轨迹，forward0，此小样本不证明完整文件的方向分布。Calo有效非零formula覆盖module0/1/2为2/1/1例，module3小QA未测量，完整文件另查。官方既有geometry overlap/clock/FPE诊断保留，不据这些日志或困难轨迹另删事例。

正式生产3个10000-event完整文件，Condor9663277.0–2，每1CPU/3000MB/8000MB disk、workday/MaxRuntime28800秒；worker无旧3600秒timeout或累计CPU截止。RDO只复制worker scratch，xAOD/PHYS/完整日志提取后随scratch删除，仅回传紧凑selected及QA/计时/日志摘要。未安装或编译软件。

实际命令（工作目录仓库根，QA worker在`/tmp/nu_mu_stage82_qa`，两个既有软件包为软链接）：

```bash
bash AnalysisZipFramework/submission/run_ml_k_support.sh 0 16
condor_submit -dry-run /afs/cern.ch/user/x/xcheng/nu_mu_stage82/dryrun.ads AnalysisZipFramework/submission/ml_k_support.sub
condor_submit -terse AnalysisZipFramework/submission/ml_k_support.sub
# worker内：
faser_reco.py --isMC --geom TI12MC04 --nevents -1 input-RDO.root
faser_ntuple_maker.py --isMC --geom TI12MC04 --CKFTrackType merge --nevents -1 --outfile ntuple.root input-xAOD.root
# 生产完成后：
bash /tmp/stage69_python.sh ml/k_support_curve.py collect
bash /tmp/stage69_python.sh ml/k_support_curve.py prepare
bash /tmp/stage69_python.sh ml/submit_k_support_curve.py
bash /tmp/stage69_python.sh ml/k_support_curve.py report
bash /tmp/stage69_python.sh ml/validate_k_support_curve.py
```

生产实际进度的只读SSH日志快照见`stage82_energy_ml/runtime_observations.json`；初次monitor的多行命令被SSH折叠而产生SyntaxError，随后改为无换行编码后成功，不影响任何生产作业。第一次本地QA从错误cwd启动，读取包前exit2；修正为上述QA目录后链路一次exit0，无正式作业重试。

## 完整 K 支持与资源

三源全部10000事件、RDO/xAOD/ntuple计数相同、528分支、完整merge输出forward/backward均非零；三源一次exit0、无正式重试。完整四模块Calo formula均通过，原62/raw/status/typed域、Calo缺失传播和小QA同身份数组精确闭合。

| K来源 | selected | 复用stage55 | 内部重复 | 新唯一key |
|---|---:|---:|---:|---:|
| k:00630–00639 |378|17|5|356|
| k:00090–00099 |369|15|12|343|
| k:00160–00169 |347|12|19|317|
| 合计 |1094|44|36|1016|

内部重复按首次来源稳定保留，源内8、跨源28；44旧复用与36内部重复有2行重叠，不能直接1094−44−36算new。与stage70新28/stage81新742复用均0。selected 11路raw中704个合法负读数、新增unique行659个负读数保留，不做统一负值删除。完整身份、特征和cutflow见[K交付](stage82_energy_ml/K_delivery.json)、[支持层](stage82_energy_ml/K_support.tsv)、[cutflow](stage82_energy_ml/K_cutflow.tsv)、[占位/域统计](stage82_energy_ml/K_feature_validity.tsv)。

K新增true50–100 **0**、100–200 **14**；reco pz50–100为18，其中true≥200为17；high-y37、未确认43。低能0是这三个完整选中并去重来源的测量，不是K所有flux/接受度不可能提供最低能事件的证明。未单独保存完整raw真能谱和各truth-E阶段接受度，不能将flux分布与原选择的原因分开归因，也不能降低原选择来凑数。

三个K实际reco wall3446.83/3717.00/3285.01秒，ntuple716.51/761.44/700.23秒，extract24.19/25.60/23.53秒，reco峰值1024.504/1122.465/1064.527 MiB。全流水线子进程计时见[资源表](stage82_energy_ml/production_resources.tsv)，记录copy/reco/ntuple/extract而非未测worker总I/O。remote CPU4140/4421/3969秒、execute wall4216/4537/4038秒，累计CPU12530秒、wall12791秒；**三源均超过旧3600秒**，新28800秒足够，不再沿旧累计7200CPU秒阻止。

逻辑RDO复制3,919,239,502bytes，scratch disk实测峰值见Condor userlog（约4GB）、请求8GB，最终不保留ROOT。实际EOS物理网络字节未测量；提取Uproot请求、C++ ROOT请求和复制大小不是同一计数。正式history来自当前phase小型`condor_history -userlog`，请求值来自提交时实际ClassAds并标出provenance；全局history按cluster查询等待时因未满足limit3扫描旧历史而取消，未影响作业。实际运行快照证实CPU soft/hard unlimited。

## 固定学习曲线与独立验证

已完成6正式fit、0pilot、0新F7 fit/推理。实际训练前冻结协议见[protocol](stage82_energy_ml/protocol.json)：stage70新28＋stage81新742唯一π＋本轮实际新K；对stage55全部95748曝光/66843 unique及支持源内/源间精确native-MeV(pdg,px,py,pz) key去重，不仅对41447 eligible去重。按group排序、seed2026110382逐source均匀抽floor(N/2)，半量为全量子集；实际新全量1786=770π＋1016K、6来源，半量892=385π＋507K。各source half/full为k0090 171/343、k0160 158/317、k0630 178/356、π00100–00109 194/388、π00250–00259 177/354、π00440–00449 14/28；group实际键见协议，不根据产额改源。两档train42339/43233，原41447/8440/14057与91/16/22来源、缺失21/3/7＋11保护保持，test/locked不读。

size0直接复用stage56 F7预测/offset，0新基线fit/推理。half/full各原3seed2026110255/56/57、400轮、原depth5参数、原XGBoost2.1.3默认初始化语义/unit direct logE，共6fit、0pilot。各三seed平均raw后在原cal做一个unit global log offset，主full_cal，half仅诊断；不按表现挑大小/seed/raw/cal。训练2Condor9663288.0–1各1CPU3000MB，请求wall上限1800秒、CPU合计1800秒，实际CERN espresso改写为1200秒（仍在上限内）；worker另CPU soft880/hard900秒、timeout1750秒。原计划CPU/墙钟约束不作用于已获授权的K生产。实际包两档零fit import/DMatrix/输入/参数QA先行。初次提交后校验误要求实际MaxRuntime精确1800导致assert，正式作业已提交且均成功，未重复提交/训练；修正为900–1800秒预算内验收并保留原记录，不能把此程序断言当模型失败。

两档脚本wall15.698087/21.553420秒、CPU15.574145/21.248314秒、peak266.066/265.055 MiB；remote CPU18/25秒、wall22/29秒，累计43CPU秒/51wall秒。初始化实际learner_model_param和原参数逐seed保留，未设置base_score/boost_from_average。half/full原cal unit offset0.003217017758/0.003355846015；cal/eval身份和旧F7预测逐位相同。

全量相对原train增量4.309118%，两低E新23/105，即原767/3564的2.998696%/2.946128%；同低pz真≥200新29/1005=2.885572%，high-y54/1204=4.485050%、未确认66/1495=4.414716%，3200–6400新32/282=11.347518%，≥6400仍0、无该层验证能力。新全量缺失1例、半量0例，原21/3/7＋11不动。[训练支持表](stage82_energy_ml/training_support.tsv)逐层记录。

| eval log-RMSE | 传统μ | 原F7 | half_cal | 主full_cal |
|---|---:|---:|---:|---:|
| true50–100 GeV |.145487|.312816|.310312|.311861|
| true100–200 GeV |.226876|.265014|.263432|.263216|
| all |.568069|.296363|.296002|.295603|
| reco pz50–100 GeV |1.336853|.502965|.502695|.502823|

主full/传统两低E比 **2.143572 [1.824836,2.464666] / 1.160175 [1.089366,1.237750]**，均未恢复。相对F7第二低E .993214 [.987763,.997794]有小幅改善，最低能 .996949 [.987368,1.011914]未证改善；all/F7 **.997438 [.996118,.998709]** 有小幅收益。主full低pz/F7 .999717 [.992558,1.006390]未证增量，不能凭all改善声称用户关切的低pz恢复。

all/≥200/低pz/high-y/未确认对F7 RMSE95上限.998709/.998977/1.006390/.999405/1.001381，原保护全部通过；原关键层7×总/正/负tail50保护全部通过，不应写风险门槛全失败。最低能总/正tail上限+1.373162pp、第二低能+.560273/+.659341pp；困难最大总尾上限未确认+1.435624pp。**额外诊断**同低pz真≥200 RMSE/F7=1.000684 [.992246,1.008766]，总/负tail50上限+2.233589/+2.162810pp，仍须保留，不能用总低pz过保护掩盖这一侧；该额外层不是本轮事前7层推广门槛，且主候选因低E失败早已不能推广。

full/half来源配对all .998654 [.997525,.999905]，两低E1.004991 [.997509,1.011991] / .999180 [.993115,1.004164]、低pz1.000255 [.995598,1.005179]均无低能/低pz单调改善证据。各source中央风险比F7改善：主all17/22、最低能8/19、第二低能14/22、低pz10/22；仅描述方向、不伪造单源显著性。half不替代预定full主候选。

最低能主median bias+17.8561%、正tail50仍31/208=14.9038%，占该层平方log损失71.3916%；第二低能正尾76/906=8.3885%，占55.9970%。高端3200–6400主RMSE.748931、median−42.5010%，相对F7比.991372 [.986182,.995643]小幅改善仍有偏。训练内full两低E raw .243521/.224563，原nominal单列.243222/.224316；训练内最低能偏差仍在，且新增支持最低能仅23例，不能把程序修正后余下问题唯一归因过拟合/缺数据/信息上限。

完整raw/cal指标、分seed和来源表、恢复/保护判断见[full指标](stage82_energy_ml/full/metrics.tsv)、[paired](stage82_energy_ml/full/paired.tsv)、[门槛](stage82_energy_ml/full/gates.tsv)、[curve](stage82_energy_ml/curve.tsv)及[曲线图](stage82_energy_ml/learning_curve.png)。两档均未过低E恢复门槛，继续F7。

500component分层保守来源paired fixed prediction区间，eval seed2026111382；两低E/传统RMSE95%上限1.05，all/F7 1.01、≥200/低pz/high-y/未确认1.03，关键层总/正/负tail50增量上限2pp原门槛不变。全部能箱/confirmed低transfer/同低pz真高E/high-y/未确认/高端/缺失、bias/R68/双向tail50/100、来源方向和训练内风险并报，full/half也配对报告。

区间排除重训、增补抽样、offset估计、上游谱系/共同响应/研究选择，非联合覆盖；cal/eval已开发。重复incoming精确key干净不证明完整parent/subfile/seed独立，仅development enrichment，不称随机独立确认。功效未测量，有限增补失败不能否证缺数据假说，也不能唯一归因缺数据。

## 阶段性结论和下一步

1. 用户指出的K时限问题确实存在：本轮3个完整K生产均实际超过3600秒，放宽至28800秒后全部一次完成；交付1016新增唯一K并已用于half/full六次训练，而非仅提交作业或改文档。
2. π＋K固定增补在all、第二低能和部分高端有小幅开发集收益，未恢复最低能或测出低pz增量。所有原保护通过仍不足以替代两低E恢复要求，继续F7。
3. K此次新增最低能0，说明随机补K并不等同为50–100 GeV问题补足训练支持；只测到选择后组成，尚未分开flux/接受度因果。现有π池20个完整未交付兼容来源可直接提取，成本远低于新K重建；下一阶段优先完成这些实际低能可用支持，保留已经用上的K，不再受旧K禁令限制。

唯一下一项stage83：在stage81已冻结合法train候选中去掉两已完整交付π及stage70完整交付范围，**全取剩余20个已知兼容π PHYS（不按残差或产额选源）**，0模型fit/新F7推理/重建/生成。先复用≤40身份实际62/raw/条件/01-LG/I/O QA，再最多4Condor、各1CPU3000MB、每1800秒、CPU累计1800秒、完整输入≤200000事件/10GB/最终10MB；仅上限，实际成本/新N/功效未测量。已有stage81 π总22文件673397029bytes，两交付61408284bytes，剩余**611988745bytes**为已测逻辑PHYS大小，不是物理I/O。

对stage55全部曝光、stage70/81/82新支持及源内/源间精确key去重，交两真低E、同低pz真高E/high-y/未确认/高端/缺失的实际增量与cutflow；验收完整20来源可追溯/原选择与01表示闭合/角色干净/紧凑缓存可回读/资源实测。不能把20文件或大量selected当足量；不得根据prefix或低E产额换源。兼容入口不可交付交具体路径/条件差异，不混入backward-only。stage83只交支持与测量，后续训练需以实际支持量另冻合同，不自动扫描更多学习曲线。

完整上游parent/subfile/seed、真正随机未开发确认与共同raw/stage54、Calo/脉冲/interaction/FSI/材料/接受度/背景仍待交付，不因本轮小幅all改善而省略。


## 验证、留存与阶段提交

6个模型逐位重读预测、原F7参数/seed/轮数/默认初始化政策、原角色与62矩阵、pooled key对stage55全曝光及旧支持去重、原缺失、source半量重现、03→01 payload转换与cal offset全部通过。全部500draw逐事件权重对368条paired区间及46条full/half曲线区间复核，最大区间数值差1.443290e−15。见[独立验证](stage82_energy_ml/validation.json)与[摘要](stage82_energy_ml/summary.json)。

清理新增传输包、生产分片、临时QA运行目录、训练prepared大输入与重复预测，共31,454,308逻辑bytes；官方既有runtime归公共软件不计本阶段新存储。保留`ntuples/energy_ml_stage82/support.npz`、`qa0.npz`、`ml/artifacts/stage82/{half,full}`六模型与comparison、本报告和紧凑JSON/TSV/PNG；不提交事件缓存/模型到Git，不保留ROOT/xAOD。删除prepared输入与重复predictions后，再次以`review_input`从保留scalar及旧缓存复建并运行独立验证，全部通过，0 ROOT读取/新F7推理/重训。资源/存储见[cleanup](stage82_energy_ml/cleanup.json)、[storage](stage82_energy_ml/storage.json)。物理EOS网络I/O未测量。

本地Conventional Commit主题`feat(ml): use K support in fixed learning curve`，不push、不外发消息。原stage54五项未跟踪工作保持，独立支持协议及原stage54 Prompt后缀逐字保留。下一阶段stage83已给具体输入与验收，未执行。
