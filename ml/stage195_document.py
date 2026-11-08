"""Render only returned scalar results; no local scientific event processing."""
import csv
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage195_energy_ml'


def read(name):
    return json.loads((OUT/name).read_text())


def fmt(x):
    return '未测量' if x is None else f'{x:.9g}'


if __name__=='__main__':
    s=read('full_summary.json');a=read('independent_validation.json');ad=read('admission.json');cl=read('storage_cleanup.json')
    assert s['passed'] and a['passed'] and cl['passed']
    with (OUT/'full_noise.tsv').open() as f:noise=list(csv.DictReader(f,delimiter='\t'))
    contrast_rows=[];fit_rows=[];free_rows=[];noise_rows=[]
    for r in s['fits']:
        fit_rows.append(f"|{r['module']}|{r['train_N']}|{r['heldout_N']}|{fmt(r['rho'])}|")
    for r in s['contrasts']:
        contrast_rows.append(f"|{r['module']}|{r['mid_N']}|{r['high_N']}|{fmt(r['contrast_ratio'])}|[{fmt(r['low95'])}, {fmt(r['high95'])}]|{fmt(r['mid_median_difference_pC'])}|{fmt(r['high_median_difference_pC'])}|{fmt(r['empirical_bound_pC'])}|{r['high_beyond_bound_N']}|")
    for r in s['free_scale_constraints']:
        for g in r['groups']:
            free_rows.append(f"|{r['module']}|{g['group']}|{g['N']}|{g['required_covered_N']}|{fmt(g['necessary_rho_lower'])}|{'∞' if g['upper_unbounded'] else fmt(g['necessary_rho_upper'])}|")
    for r in s['noise']:
        noise_rows.append(f"|{r['module']}|{fmt(r['signed_residual_sd_pC'])}|{fmt(r['empirical_bound_pC'])}|{r['joint_L1_heldout_exceed_N']}/{r['heldout_controls_N']}|")
    text=f'''# Stage195：双量程幅度趋势的整流噪声界与未知比例必要条件

日期：2026-11-08。执行[Stage187有限标定支线§6](2026-11-08_stage187_post-readout-research-roadmap.md#6-有限标定支线先检验双量程比例的测量误差偏差)。问题是随机读出误差、共同分母和选择能否解释Stage180/181的幅度趋势。**本阶段测量一个有条件的扰动尺度与留出响应诊断；没有取得真实信号全幅度误差模型，因此没有校准或排除整个线性响应家族。** 无新能量fit/forward/G4/MC父，不重开已经结束的模型、窗或seed网格。

## 输入、冻结与选择

[协议](stage195_energy_ml/protocol.json)冻结于读取本阶段事件之前。真实PHYS为`{read('protocol.json')['PHYS']}`，全780874条只读原00000–00049编号合并的这一文件，不新增文件。四对普通Ecal通道Lo0–3/Hi16–19来自Stage173真实CableMapping同station/plate/row/module、不同PMT。**它们不是已经认证的同一光脉冲复制通道**，不能忽略空间/光收集/PMT涨落。

原Stage180重叠选择保持：双路exact status0，Q/peak/RMS有限且Q、RMS>0，双路peak≥10RMS。所有输入仍计入总分母；另报双status0正Q/RMS而尚未施加SNR的preSNR组。负Q、非有限和−999计数保留，不把一般signed负数改为占位。时差只访问双方status0的localtime/BCIDtime，时间有效规则和Stage181原local offset保持，诊断within/outside±2ns；无时间不删原charge分母。

全部原分母、paired-status/preSNR/SNR数和缺失/负Q计数见[完整标量](stage195_energy_ml/full_summary.json)，不由图上显示的子组代替总支持。本真实PHYS的Q负值/−999/非有限计数均0；该事实只限这一输入，不更改其他样本合法负数或占位处理政策。

新留出是原entry按8192条采集块、偶块估计每模块一个median log(Hi/Lo)、奇块验证。原Stage180逐entry偶/奇的scale、分位及全部5802/7489/4989/5850重叠精确复现，未重解释历史。新块留出仍是同一merged PHYS；真实原始源文件身份未认证，不能宣称跨文件或独立样本验证，时间offset也是此前已开发诊断。

| 模块 | 偶块拟合N | 奇块验证N | 相对比例ρ，无量纲 |
|---|---:|---:|---:|
{chr(10).join(fit_rows)}

在全量提交前另存[未知比例必要条件](stage195_energy_ml/prespecified_scale_check.json)：中位估计ρ可受整流/选择偏置，固定ρ残差失败本身不足以否定未知真实比例。该检查不添加拟合、源、窗或预算；原协议字节保持，每份提交源码与补充时间顺序均可由归档复核。

## 随机控制：测得的是扰动基准，不是信号误差分布

复用Stage183原32文件400–431缓存的全部116 strict控制，8实际普通Ecal通道、每路280 ADC采样；不重读或扩张RAW。原前16文件57条定义包络，后16文件59条验证。实际条件range=2V，源码`RawWaveform::mv_per_bit=range/16.384` mV/ADC，2ns采样/50Ω，单位转换为0.0048828125 pC/(ADC-code×sample)。源码见[原字节证据](stage195_energy_ml/source_evidence.json)。这只是ADC→积分单位转换，不是光强/能量/PMT增益标定。

冻结残差e=mean(ADC[0:40])−ADC；原Stage183信号窗[60,140)、offpulse[180,256)分别计算signed与positive-part积分。旧data rawQ正采样求和与signed噪声不能直接共用误差。逐通道均值/标准差与两种定义见[实测表](stage195_energy_ml/full_noise.tsv)；合法signed负值保留。

利用整流函数R的Lipschitz性质，对相同固定subset，`|ΣR(s+e)−ΣR(s)|≤Σ|e|`。每路B取57控制中全280采样L1积分的最大值，故在假设的固定baseline/同subset加性扰动下比原76/101保存窗保守；全280 L1不是另选最佳窗，也没有构造或拟合信号pulse模板。它不涵盖信号baseline估计改变、pulse找寻/移动窗、饱和/截断、幅度相关误差或真实不同PMT光收集涨落。纯noise也未认证。

| 模块 | signed窗(Hi−ρLo)标准差/pC | B_H+ρB_L/pC | 留出59控制联合L1超过定义包络N |
|---|---:|---:|---:|
{chr(10).join(noise_rows)}

经验最大值没有总体覆盖保证，模块3留出控制本身已有超出。不能据0/59宣称其他模块误差尾为0，也不能把有界对照当真实95% signal-error带。未执行随机文件扩张、协方差求逆、任意幅度先验或噪声注入能量模型。

## 全量留出：归一化趋势与未归一化电荷差

以下只取原高SNR且within2ns奇采集块。mid固定Lo peak100–250mV，high固定500–2000mV；Δ为high减mid的中位`Hi/(ρLo)−1`。区间是500次seed20261108195采集块bootstrap、条件于已拟合ρ的95%区间；不含比例重拟合、研究选择、跨源或真实系统误差。电荷差r=Hi−ρLo单位pC，不与同一分母耦合，但选择和两轴误差仍可相关。

| 模块 | mid N | high N | Δ，无量纲 | 条件95%区间 | mid median r/pC | high median r/pC | B/pC | high超B N |
|---|---:|---:|---:|---|---:|---:|---:|---:|
{chr(10).join(contrast_rows)}

四模块的幅度差均为负，条件区间均未覆盖0：趋势在本次采集块和时间诊断中保留。高幅组电荷差中位约−0.94至−1.68pC，均小于3.34–3.61pC的宽经验扰动界；只有模块1有12/264高幅事例超出固定ρ界，其余三模块均0。**宽界未排除并不等于噪声已解释趋势**，更不能把少量超界直接解释为非线性或删掉后认证模型。该界因全280点绝对值求和而保守，本轮没有事后改用更短窗以追求排除效果。

![固定比例下的电荷差及条件经验包络](stage195_energy_ml/conditional_noise_envelope.png)

[全32×4组分箱表](stage195_energy_ml/full_bins.tsv)保留preSNR/all/within/outside及全部原8幅度箱、空箱、r的abs95、超包络N和所需95分位扰动倍数。不能只报道有利组或据test重选阈值。实际状态不足以认证完整饱和群体的响应，bad fit/缺失和正Q/SNR选择的产生概率未测量；尚无联合二维/选择/饱和生成模型闭合。

[两轴矩表](stage195_energy_ml/full_moments.tsv)直接给Cov(r,Lo)、Cov(r,Hi/ρ)和归一化斜率，并给原signed窗与zero-signal整流窗的协方差尺度。简化独立模型中`Cov(r,Lo)=Cov(εH,εL)−ρVar(εL)`，但本次数据已经受双阈值/Good Hit/时间条件化，实际rawQ又是整流定义。因此表中的随机窗协方差仅作条件benchmark，**不能用它替代信号误差协方差进行EIV校正，或宣布误差/共同分母已解释全部趋势**。

## 不选择ρ的必要条件与不可识别性

假定每路扰动确实不超过上述B，则每个positive测量给出ρ区间：

`max(0,Hi−BH)/(Lo+BL) ≤ ρ ≤ (Hi+BH)/(Lo−BL)`，Lo≤BL时上端无界。

若一个幅度组N条中至少k=ceil(.95N)条可由同一ρ覆盖，则ρ至少为lower的第k小、至多为upper的第N−k+1小。这是必要条件，非充分条件；两组必要区间再取交集，不额外拟合新比例。

| 模块 | 固定幅度组 | N | 至少覆盖k | 必要ρ下端 | 必要ρ上端 |
|---|---|---:|---:|---:|---:|
{chr(10).join(free_rows)}

各模块“两组95%经验覆盖未被必要条件排除”标志依次为 **{[r['empirical_95pct_each_group_possible_not_excluded'] for r in s['free_scale_constraints']]}**；False只排除给定有限控制包络下的该覆盖要求，不能排除真实不同baseline/移动窗/幅度误差模型。True也不能认证加性线性模型，更非总体95%覆盖。没有事后抬B、换ρ、删离群或改覆盖门限。

本次四个必要交集均非空，所以现有宽误差界没有区分所需假说；这不是线性模型的充分拟合，也不是随机控制不足以约束任何误差的普遍结论。更窄的signed窗误差标准差仅约0.21–0.25pC，但它与历史整流rawQ/信号baseline和选择没有获得同定义迁移，不能把这个窄数字直接代入后宣布显著性。

在不限制误差与潜在幅度依赖时，同一观测对可精确写成线性模型A：a=QL、εL=0、εH=QH−ρQL；也可写成B：a=QH/ρ、εH=0、εL=QL−QH/ρ。独立标量核逐缓存事件重构精确至浮点舍入；它证明观测对本身不识别幅度误差的来源，**没有证明这些误差独立、零均值或物理上成立**。116 zero/random控制不能约束任意幅度的这两种构造；真实非线性与幅度相关误差/选择仍不可分。真实相对曲线也不能打破`fL(a),fH(a)`共同重参数化的绝对幅度自由度。

## 执行、验证、资源与存储

所有ROOT/NPZ/gzip/统计/图/审计均在HTCondor；本地只源码、调度、返回标量渲染和精确字节归档。先原8192小样本、完整GNU {ad['measured_complete_pilot_CPU_s']:.6f}CPU秒，两4096读块{ad['measured_two_chunk_CPU_s']:.9f}CPU秒，三倍投影{ad['threefold_full_CPU_s']:.9f}<800才准入；原总预算1200CPU秒，初始分配pilot200/full800/audit200。首次审计因反复按key解压NPZ耗时异常，调度CPU监测延迟，到292CPU秒才按200秒限额移除；**原审计分阶段合同失败，不追溯改为通过**。随后一次实现修复从原总预算的剩余897CPU秒中明确预留200秒，未增加1200总额、未重跑全量测量/拟合或改科学门；修复与实际超时见[恢复账目](stage195_energy_ml/audit_recovery.json)。修复一次性解压各模块缓存为内存dict，并设进程内核RLIMIT_CPU180秒，避免只依赖调度延迟监测。小样本没有拟合全量比例或产生奇块科学结果。

full内部{fmt(s['CPU_s'])}CPU秒/{fmt(s['wall_s'])}wall秒、ROOT请求{int(s['ROOT_read_bytes'])}B、RSS{int(s['RSS_KiB'])}KiB；该内部时间在画图之前结束，GNU包括画图/进程启动，二者分别保留不重复加总。4请求核/8GB，实际调度RequestCpus/Memory见[scheduler账目](stage195_energy_ml/scheduler_accounting.json)；没有受控并行加速比或GPU基准。本轮主要列I/O与小规模统计，未请求GPU。

独立审计重新读全部{a['actual_full_PHYS_N']}条ROOT，独立Python标量选择/median/分位/两轴协方差和原缓存entry/eventID/六读数精确；{a['scalar_random_integrals_N']}项signed/positive/L1积分与{a['rectifier_Lipschitz_checks_N']}项固定代数检查通过。4×32分箱、4×4矩和未知比例必要界核对，未把公式单元检查当真实误差覆盖。完整结果见[独立审计](stage195_energy_ml/independent_validation.json)。

修复后完整审计内部实测{fmt(a['CPU_s'])}CPU秒/{fmt(a['wall_s'])}wall秒；旧实现292调度CPU秒仍未完成，不将两者计算成相同完整任务的受控加速比。科学公式、选择、参考数值和验收容差均未改变。

```bash
python3 ml/stage195_freeze.py
python3 ml/stage195_ops.py submit --phase pilot
python3 ml/stage195_ops.py collect --phase pilot
python3 ml/stage195_admit.py
python3 ml/stage195_ops.py submit --phase full
python3 ml/stage195_ops.py collect --phase full
python3 ml/stage195_ops.py submit --phase audit
# 原audit被CPU策略移除，没有结果包；不把它标成功。
python3 ml/stage195_ops.py submit --phase audit_repair
python3 ml/stage195_ops.py collect --phase audit_repair
python3 ml/stage188_finalize.py 195
python3 ml/stage195_document.py
```

调度查询曾出现SECMAN安全协商失败，未据返回包重复提交；保留原cluster直到终态确认。实际{cl['starts']}start、失败/移除{len(cl['failed_jobs'])}、{fmt(cl['scheduler_CPU_s'])}累计调度CPU秒/{fmt(cl['scheduler_aggregate_wall_s'])}聚合execute wall秒、0live。GNU详见[进程资源](stage195_energy_ml/process_resources.json)，原失败audit未回传GNU/科学结果，明确缺失；scheduler的292CPU秒完整计入，不用成功修复时间替代。`~/condor/nu_muAnalysis/stage195/`终态归档为`software/stage195/terminal_spool.tar.gz`，源码/日志/历史标量精确归档；删除{cl['deleted_B']}B重复，紧凑positive-paired控制缓存留{cl['retained_cache_models_B']}B<16MiB，无完整ROOT/ADC副本。Stage54原12资产size/mtime不变，未触碰用户其他未跟踪文件。

提交前仅将TSV空尾字段显式加引号并去除Matplotlib SVG行尾空格，CSV重新解析逐字段相同、SVG仅空白变化，见[格式检查](stage195_energy_ml/table_formatting.json)。原作业输出字节仍保留于历史归档；代码与呈现版本分别保留，不重跑科学计算。

## 阶段结论、具体后续输入及验收

这次给出整流定义、有限随机控制、固定未知比例和实际选择下的定量约束；完整信号两轴误差/选择/饱和模型仍不可识别。不能凭有无超包络就宣布PMT非线性、线性响应通过、绝对校准或最低ν能量改善。原Stage87、角色/全部K、pz0-only（允许px/py、q/p、弯折）、pz>50GeV、raw/typedNaN/合法负值/status0时序及原八层三尾/双低能门保持。

有限支线本固定对照结束，不继续随机文件/拟合族/窗口/seed扫描。若要判定误差是否足以解释趋势，所需新增输入是**同设置、同pulse双路与独立监测幅度的LED/已知光强或实际标定manifest**：run/file/entry身份，PMT/HV/gain/ADC范围/光注入几何与稳定性、原波形/实际baseline与保存窗、坏状态/未检测/饱和的共同分母、独立光强读数和误差及相关性。须有真实文件级留出与覆盖100–2000mV相关范围，不能用同ADC半窗冒充独立参考。具体采样数取决于目标精度与实际产额，本轮未测量、不虚构N。

验收：一个预定线性双路与实际误差/选择模型共同预测留出二维(Q_L,Q_H)、状态/饱和和原时间诊断；只有还存在有支持的系统残差才另冻一个非线性备选。相对闭合后仍需绝对幅度锚点与MC同设置迁移才能影响能量训练。所需外部标定/误差/真实背景效率和独立确认尚未提供，不用任意prior、紧缩协方差或重复同点toy补足。

主路线A既有IFT内容阴性与身份控制保持；B实际LOS/active条件、D同设置真实控制、E新时期像素/匹配MC、F真实status0形状和独立控制、以及物理谱的背景/完整效率权重/相关辅助仍按[需求表](stage195_energy_ml/goal_requirements.tsv)推进。上述有条件标定支线不升格为所有主线前置。整体低真E优于传统、真实响应标定、完整物理谱与独立确认仍未完成。
'''
    (ROOT/'workbook/2026-11-08_stage195_dual-range-rectification-and-error-identifiability.md').write_text(text)
    requirement=(ROOT/'workbook/stage194_energy_ml/goal_requirements.tsv').read_text()
    requirement+='dual_range\tStage195 conditional rectifier noise-envelope/free-rho necessary constraints measured; signal-error/selection model not identified\tSame-setting same-pulse independent monitored amplitude/LED manifest, baseline/window/status/saturation denominators and file-level holdout\tJoint heldout two-dimensional response, status/saturation and timing closure, then absolute anchor and matched MC migration\tNo nonlinear inference from fixed-rho residual or transferring signed random covariance to rawQ\n'
    (OUT/'goal_requirements.tsv').write_text(requirement)
    title='# 当前执行更新：Stage195 双量程整流误差与未知比例的有限约束完成\n\n'
    desc=f'''[中文报告](../workbook/2026-11-08_stage195_dual-range-rectification-and-error-identifiability.md)在原780874条、原四对PMT/全部选择分母上复现180/181，原116随机控制分57/59；旧raw正采样与signed控制分开，冻结全280点L1经验界并验证。奇8192采集块within2ns的mid100–250与high500–2000mV相对残差差为{', '.join(fmt(r['contrast_ratio']) for r in s['contrasts'])}；具体区间/电荷差/超界及不拟合新ρ的必要区间均完整交付。给定经验界下两组各95%覆盖必要条件未排除标志{[r['empirical_95pct_each_group_possible_not_excluded'] for r in s['free_scale_constraints']]}，不是总体覆盖、非线性或真实加性误差认证。不同PMT光收集、信号baseline/窗与幅度误差/选择仍未标定；同merged文件块留出不称跨源独立。\n\n'''
    desc+=f'''独立全ROOT重读/2784积分/2784代数及128分箱、16矩/逐缓存身份与比例必要界通过；{cl['starts']}start全终态（含原审计超200秒限额被移除，修复NPZ重复解压问题后从原1200总预算内修复）、{fmt(cl['scheduler_CPU_s'])}CPU/{fmt(cl['scheduler_aggregate_wall_s'])}聚合wall秒、0live，留{cl['retained_cache_models_B']}B、清{cl['deleted_B']}B重复、Stage54保持。零新能量fit/G4/forward，原Stage87与全部科学门/K/角色/pz0/raw/status0保持。该固定支线结束，下一需要同设置同pulse独立幅度/LED及真实文件留出，详见[需求表](../workbook/stage195_energy_ml/goal_requirements.tsv)；B/D/E/F与真实背景效率加权/相关辅助/独立确认继续开放，整体未完成。以下历史全文保留。\n\n'''
    for relative in ['docs/nu_mu_energy_ml_revised_roadmap.md','docs/nu_mu_energy_ml_next_step_prompt.md']:
        p=ROOT/relative
        if not p.read_text().startswith(title):p.write_text(title+desc+p.read_text())
    print('Rendered Stage195 Chinese report, remaining inputs and roadmap update.')
