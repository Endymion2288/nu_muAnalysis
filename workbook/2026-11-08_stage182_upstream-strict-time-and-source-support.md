# Stage182：上游严格时间、必要电荷范围与同窗源支持

## 阶段目标与冻结定义

完成Stage172§8尚未回答的上游弱信号/下游prompt有限覆盖探索。[协议](stage182_energy_ml/protocol.json)保留Stage179原12父及顺序50/70/6/21/8/63/2/15/0/1/5/12，不按时间、Q、误差或重选替换。输入为 `ntuples/energy_ml_stage179/parent_<index>_response.json.gz`、Stage179独立修正后的charge表和Stage129原MC timing calibration。仅缓存读取，无ROOT/G4/重建/fit/forward或新独立ν。

只在实际ADC存在、status==0、localtime有限且>0时给时间；其他时间为null，负raw仍保留。两个层次分开：严格时间；严格时间加原MC校准qi/qj范围。后者只是**必要条件**，本记录无actual track外推位置，不认证空间范围/弱信号迁移，也不输出校准Δt。没有将p1等动量或truth用作模型输入，没有额外TOF/phase扣除。

源电荷独立从Stage179保留六源analog按实际780–980ns端点窗积分，并与权威表闭合；另报整个保留ADC范围积分。实际600个2ns样本覆盖0–1198ns不是全物理迟到范围；源hit time已按producer传播/TOF约定处理，不直接拿hit时间与ADC积分窗比较。缺ADC与测得零信号不同，全部12父留分母。

## 实测联合覆盖

| pair | 父分母 | 两端ADC | 两端status0 | 严格时间 | 再加必要Q范围 |
|---|---:|---:|---:|---:|---:|
|VN0_VN1|12|5|1|1|0|
|V20_V21|12|12|6|6|6|
|VN0_V20|12|5|0|0|0|
|VN1_V20|12|5|2|2|0|

三种涉及VetoNu的关系均无必要Q支持：VN0−VN1唯一严格时间来自原父12，原始Δt=8.99139404297ns；VN1−V20两条为父8/1的+64.4323120117/−20.5485839844ns，均未获Q范围准入。它们不能校正成可信的shower时差或反演顶点。V20−V21有6/12必要Q支持，是下游关系，不能替代上游反向传播支持。全空间校准/真实backscatter认证为**未测量/未认证**，表中计数0表示没有本阶段认证，不能解释成物理上不存在。

[全pair表](stage182_energy_ml/full_pairs.tsv)保留48条记录，无效时间空值而非−999；[全通道表](stage182_energy_ml/full_channels.tsv)保留60行，含缺失、合法signed与非0status，不用charge恢复时间。

## 同窗来源与实际覆盖

| 硬件通道 | ADC存在父数/12 | strict父数 | 同窗analog (pC) | 全保留采样analog (pC) | 直接主μ (pC) | S0前 (pC) | 其他根 (pC) |
|---|---:|---:|---:|---:|---:|---:|---:|
|4|5|3|46.26735338|46.30998065|0|0.9671646763|45.3001887|
|5|5|3|46.10315181|46.24485442|0|0|46.10315181|
|14|12|5|152610.5073|152816.4115|849.1920791|1690.933718|150021.8855|
|6|12|6|60990.27981|61021.23202|826.5997576|3073.676374|57068.76812|
|7|12|6|47548.18351|47577.21721|836.7753177|2648.304879|44019.66015|

两个VetoNu通道合计仅5/12父有ADC，存在的上游analog主要来自其他根；这支持它们具有不同于直接主μ的**源组成**，不证明反散射。保留的persistent hit端点是local坐标，没有认证global方向，其他根亦可前向或侧向进入。所有方向继续unknown，不用“上游活动”代替“已知backscatter”，不把S0前出生等同穿越S0的能损。

全窗与保留样本范围analog的差描述固定卷积尾，不涵盖采集之外或G4 neutron150ns截断之外。无data弱信号timewalk控制、无完整空间/方向支持，不能从此12条件train控制推总体覆盖、纯度、能量因果或不可能性。

## 验证、资源、存储

[独立审计](stage182_energy_ml/independent_validation.json)按原official result重新做四pair标量计数，四张full/audit表逐字节一致，pilot首父复现；全部六源同窗积分与Stage179权威表相容，bad/absent时间均null。固定12父不丢失，原Stage54的12资产保持。

pilot GNU0.17CPU秒，三倍×12=6.12≤150，已用+投影+100audit≤300，才full。3start全exit0、0live，scheduler7CPU/24聚合wall秒。提交2核4000MB，CERN实际2核6000MB；full内部CPU1.415411170/wall1.476265899秒、RSS65020KiB，未测并行加速。微小缓存工作无GPU收益验证需求。

[存储清理](stage182_energy_ml/storage_cleanup.json)删11474365B重复包/日志/spool，新事件缓存0B；复用的Stage179响应留在原路径，不重复复制。source/计时/日志精确归档software/stage182，清理前核队列Iwd。

```bash
python3 ml/stage182_freeze.py
python3 ml/stage182_ops.py submit --phase pilot
python3 ml/stage182_ops.py collect --phase pilot
python3 ml/stage182_admit.py
python3 ml/stage182_ops.py submit --phase full
python3 ml/stage182_ops.py collect --phase full
python3 ml/stage182_ops.py submit --phase audit
python3 ml/stage182_ops.py collect --phase audit
python3 ml/stage182_finalize.py
python3 ml/stage182_document.py
python3 ml/stage182_validate_docs.py
```

## 阶段结论与下一步

本固定上游时间候选在必要电荷支持这一步已不成立，至此结束，不放松status0、不外推MIP校准、不扫时间窗或扩重放。需要真正弱信号时间校准、实际global方向/源关系以及独立支持后才能重新定义实验；“没有本校准支持”不是“没有反散射”。

Stage179普通Ecal同窗误差由噪声/基线主导的新证据，给Stage172联合噪声候选提供了具体检验理由。下一Stage183另冻同run已知RAW400–431前缀的普通Ecal Lo0–3/Hi16–19描述性联合控制，先400/401成本和原8192闭合，过门才固定30文件。原2400CPU秒、4进程、固定pedestal/signal/offpulse窗；测协方差/有效N/秩、两量程四路和方差比及fileblock区间，绝不反演或自动注入。**这不是执行历史Stage172 CaloNu合同**；旧合同原字节保持，不以坏CaloNu20–23或clock31推普通Ecal校准。实际DAQ配置/μ或quiet纯度/MC窗口迁移/信号保真/电荷误差覆盖仍缺，阳性只允许另冻估计器验证。

Stage87/原低能与八层三尾全部门、角色/全部K/reserved关闭保持。S0困难侧缺面、读出干预总体能量增益、真实高幅参考、背景效率加权账目/真实辅助约束、乳胶与独立确认仍开放，整体目标未完成。

收尾复核修正：Stage182 compact提交索引曾因复制模板写stage=181，已将实际 `~/condor/nu_muAnalysis/stage182/execution_index.json` 及生成器同步改为182；原job ID/归档路径和科学产物不变，未复算或重跑。另核Stage179/181/182/183四个索引stage字段与目录均一致，四阶段队列均为空。
