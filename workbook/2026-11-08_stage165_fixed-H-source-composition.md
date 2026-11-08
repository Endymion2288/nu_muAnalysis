# Stage165：固定H机制预测的来源组成依赖

## 目标和冻结范围

承接[Stage164冻结合同](stage164_energy_ml/next_execution_contract.json)，使用同原3002缓存的固定AZH/AZ、AZH/H、H/A预测，检查inclusive双低箱H条件收益在原π/K/charm和manifest nominal/alternative边际划分中的支持。两个分组系统有重叠，不能当独立样本；来源标签不是独立生成家族认证，组分不是出靶粒子类别。Stage164条件H尾部未过，原4joint失败和Stage87保留；本阶段没有生产/模型扩大触发。

协议见[protocol](stage165_energy_ml/protocol.json)，与前驱合同逐字相同。先检查原3002、1708/653/641、所有source index对应Stage130原manifest/component及nominal Boolean、原HT权重/incoming/pz0，再计算全部分组。保留全部K、角色、199边界NaN和原预测，不删缺失/稀疏组、不更换源、不造flux混合prior。pz0-only一次方/允许px,py,q/p和弯折/raw11/typedNaN/signed/status0timing/Calo缺失/原cuts和所有门保持。

## 输入、执行和验收

输入为Stage131 `matched_input.npz`/`bootstrap_draws.npz`、Stage164 `energy_predictions.npz`及原inclusive `paired.tsv`、Stage130 `source_protocol.json`。所有数组/统计走`~/condor/nu_muAnalysis/stage165/`，4核12GB/最多1job，累计600CPU秒分analysis350/audit250，MaxRuntime86400秒、无应用短timeout；零fit/模型forward/ROOT/G4/digi/reco/新ν，不为GPU改变比较。

原6层为两真E低箱/all/低pz/低pz真高E/high-y；全部5分组加inclusive×2角色×6层×3比较=216单元，原500draw限制至每组、保留原HT。不足475有效draw则区间NA；空组N0不删，ESS/风险未知，不填零或借其他组。先inclusive原Stage164数值闭合，再独立fsum/显式重抽样行空间复算和来源标签独立核查。所有区间为局部条件覆盖，不含source/refit/真实系统/研究选择，不按分组结果挑winner。

```bash
python3 ml/stage165_ops.py submit --phase analysis
python3 ml/stage165_ops.py collect --phase analysis
python3 ml/stage165_ops.py submit --phase audit
python3 ml/stage165_ops.py collect --phase audit
```

## 实际支持与inclusive闭合

[分析摘要](stage165_energy_ml/analysis_summary.json)记录3002原父、578个实际source index全部映射到原Stage130 manifest，component精确；原角色1708/653/641、全部K1156保持。inclusive的432项标量与Stage164闭合，最大绝对差2.4868995751603507×10⁻¹⁴；仅直接统计原固定预测，没有模型训练或新推理。实际全部源都标alternative，nominal组原3002中为零。其风险和迁移效果是**未测量**，不能把alternative/inclusive的重复当新证据或名义确认。

[支持表](stage165_energy_ml/support.tsv)保留72个预定support单元，216个比较单元无删减；16个support空单元对应48个比较区间NA，其余168个比较都有500有效原draw。空组包括全部nominal，以及charm若干困难层；没有以“无效”之名从原inclusive移除父。

| 原组分 | cal两低箱N | 开发test两低箱N | cal/test all N（ESS） |
|---|---:|---:|---:|
| π | 132 / 133 | 135 / 124 | 391（150.519891）/378（137.770256） |
| K | 28 / 29 | 28 / 35 | 242（154.980495）/246（155.637809） |
| charm | 1 / 1 | 0 / 1 | 20（16.548059）/17（15.405598） |
| nominal | 0 / 0 | 0 / 0 | 0/0，ESS未知 |
| alternative | 161 / 163 | 163 / 160 | 653（321.737701）/641（307.627339） |

两低箱内原HT权重相同，非空低箱ESS与N一致；all跨stratum的权重不同，不能用all N替代ESS。π和K的困难侧cal/test低pz真高E分别11/11与16/10，high-y分别8/13与25/26，仍不足完整尾部或source迁移认证。

## 条件H与条件z的分组结果

下表全部为AZH/AZ的无量纲log-RMSE比及原500draw局部条件95%区间。[配对全表](stage165_energy_ml/paired.tsv)保留所有预定比较/层/三尾，[图](stage165_energy_ml/source_marginals.png)保留各组N和空支持。

| 组分 | 真E层 | cal | 开发test |
|---|---|---|---|
| π | 50–100 GeV | .715567 [.632066,.816696] | .808396 [.700383,.912952] |
| π | 100–200 GeV | .832242 [.702594,.937830] | .762770 [.656478,.880233] |
| K | 50–100 GeV | .712372 [.542941,.858499] | .798155 [.564649,1.122367] |
| K | 100–200 GeV | .773117 [.588144,1.039718] | .863245 [.644905,1.140405] |
| charm | 50–100 GeV | .968141，N=1、经验区间退化 | 未测量，N=0 |
| charm | 100–200 GeV | .626338，N=1、经验区间退化 | .476468，N=1、经验区间退化 |
| nominal | 两低箱 | 未测量，N=0 | 未测量，N=0 |

π的四个低箱支持H给定深度的固定政策收益；K三个区间含1，现有支持未确认四项共同通过。**这不是K无增量的证据，也不是π/K增量之差已显著的检验**；不做事后分组选择，不将组内显著与否的差异当异质性显著。charm只有0/1个低能父，原分层重抽样可产生数值退化的区间；500次draw不创造新父或总体覆盖，不能把零宽度称精确测量。

all的AZH/AZ cal π=.863468 [.758504,.978845]、K=.937284 [.877920,.970521]；test π=.770036 [.679447,.878181]、K=.905061 [.826962,.968367]。all支持不是低箱K未确认问题的替代。

反方向AZH/H，π两低箱cal1.002581/1.004830、test1.004977/.987890；K cal.998184/.996709、test.989045/1.016614，各区间均含1。K最低test区间[.944483,1.030485]仍允许5%改善，不能把inclusive排除某个固定幅度的结果外推到每个组。未给z或H赋予因果含义。

原H/A比较亦完整报告：π最低/第二test=.758688 [.643254,.864557]、.702664 [.591760,.814056]；K为.747056 [.551315,1.014438]、.714819 [.544460,.940904]。相对AZ的条件收益与相对A的总收益回答不同问题，不混用这些百分比。

## 尾部与范围限制

Stage164原conditional_H_continuation=False及4joint失败保持，本阶段没有重新定义晋升门。π开发test低pz正tail差为−2.330717pp，条件95%区间[−7.664316,+3.003625]pp；K同层为−1.224322pp，[−4.345859,0]pp。前者未认证+2pp安全，不能称已证实伤害，也不能按该分组切掉事件或挑K部署。charm及其他稀疏层的经验零尾变动不认证总体尾率。

这些区间不包含source层抽样、生成/响应家族、训练变动或真实flux/材料/探测器系统；π/K两个边际差异不是“改变flux”后的因果响应。全部3002都是alternative，名义通量迁移**未测量**，未取得新独立ν、真实数据校准或独立确认。

## 独立验证、资源和存储

[独立审计](stage165_energy_ml/independent_validation.json)通过全部216个预定单元：对168个非空单元用fsum及显式重抽样行列表复算2016个标量，最大绝对差2.1316282072803006×10⁻¹⁴；48个缺失区间均确认保留NA。578个来源的component/nominal标签另从原manifest逐条核查。没有重新生成draw、模型预测或source选择，区间不足时不补别组。

[资源账](stage165_energy_ml/resource_audit.json)为2job/2starts均exit0、0live、26 scheduler CPU秒/37聚合execute wall秒，远低于600秒；Request4CPU/12000MB。analysis分12个role×group任务、4进程共享原输入，GNU1.27CPU秒/1.35wall秒/43900KiB；audit18.19CPU秒/18.82wall秒/39936KiB，独立行空间核算单进程。scheduler采样最大RSS75000KiB不是GNU峰值；analysis内部父CPU.302779005秒、wall.614175975秒均为嵌套计时，不与scheduler重复相加。新fit/模型forward/ROOT/G4/digi/reco/GPU/独立ν均0；未测受控串行加速，不因小任务更换算法或要求GPU。

[精确归档清理](stage165_energy_ml/storage_cleanup.json)逐字节核对实际传输包内原NPZ/预测与本地原件，再将实际源码/协议/worker/descriptor、GNU和日志归档`software/stage165/`；不在源码归档复制原事件数组。两个result包与已收集文本/图逐字节相同后删除，清理6255140B重复，新增事件/模型持久化0B<1MiB；无ROOT/xAOD。核当前Iwd无作业后归档终态spool，只留execution_index。Stage54十二文件size/mtime保持，原输入和其他项目不动。

原Condor图和最终带N/空组说明的图分别精确保存；[排版记录](stage165_energy_ml/publication_render.json)说明本地只渲染已验证TSV，不读事件或重算风险。首次本地绘图因旧matplotlib不支持set_xticks位置标签参数退出，拆开set_xticks/set_xticklabels后成功，不重跑科学作业；图已视觉检查。图中明确N=1的退化经验区间不测总体误差，nominal空组也不画成风险零。实际本地绘图时间未测量。

```bash
python3 ml/stage165_finalize.py
# 仅渲染已验证表，保留原Condor图
python3 ml/stage165_plot.py
```

静态AST/bash、原合同字节、历史文档保持、链接/Markdown/diff和Stage54检查见[文档验证](stage165_energy_ml/document_validation.json)。

## 结论与下一步输入

本阶段预定来源组成诊断表明，inclusive条件H收益也存在于占低能多数的π组，而K低能区间与charm支持尚不足确认同等结论。没有名义通量支持，因此没有完成名义/替代迁移检验；不进行新的同类G4/模型/代理扩大。

后续具体任务和准入条件如下，不能用本轮缓存或任意prior补出输入：

1. 跨来源验证：需同样边界定义、选择/角色与来源身份可认证的名义通量H支持；先核同口径和纳入概率，再冻结困难侧N/ESS/成本与统计验收。当前缺少这一输入，不自动生产，也不把原89033已有X62当已有名义H。
2. 实际DAQ联合响应：需可认证的run/channel增益、时基与协方差控制及覆盖强μ辐射尾的纯度/响应依据，先闭合历史raw口径和实际空间/波形测量，再另冻电子可读新量与完整ν队列检验；原四data父不是总体校准/纯度/FPR。没有新测量证据，不续旧G6/Q4/网络网格。
3. 完整物理与确认：需真实曝光GRL、背景、全生成分母接受度、带相关性的辅助系统和独立生成家族manifest；电子-乳胶锚点需真实逐例匹配。验收为可复现来源、选择/缺失完整、真实辅助约束及独立锁定后原两低箱/八层三尾通过。Stage136/140有限MC/toys已完成，不重复。

以上缺口明确保持未测量，Stage87和全部原门、原角色/全部K/reserved关闭与整体目标未完成状态保持。
