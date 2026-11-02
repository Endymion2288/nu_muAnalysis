# stage56 变量语义与占位值：有界源码核对

源码仓库为既有 `/tmp/calypso-t62p`，读取已知commit的指定文件；没有下载/重建Calypso或递归扫描EOS。
本轮 nominal PHYS 为官方 master `d32b0ff3` merge/without-IFT。`1ec47efe`和data已知`d0b1b2dd`仅作历史比较，不能用旧版算法代替实际nominal版本。

## 动量

`d32b0ff3:PhysicsAnalysis/NtupleDumper/src/NtupleDumperAlg.cxx`约L1690–1715：
`p0/p1`分别为同一拟合轨迹最前/最后measurement处的三维动量模长；`pz0/pz1`为各处纵向分量。
因此不是两次独立能量测量。`log(p1/p0)`不直接测量入射ν能量或完整靶区能损；小差也可能含同拟合传播/数值效应。
按用户澄清，F7只保留线性模长/纵向量`pz0`，保留`px/py`、`q/p`、两端方向弯折；删`p0,p1,pz1`及动量比对数的模型列。
`q/p`仍以历史前/后动量模长为分母，但仅输出被允许的逆动量参数化，不声称新增独立测量。

## 闪烁体与raw积分

`d32b0ff3:.../NtupleDumperAlg.cxx` L246–266：primary hit的`charge=integral/50`、`raw_charge=raw_integral/50`，单位pC。
`d32b0ff3:Waveform/WaveRecTools/src/WaveformReconstructionTool.cxx` L839–841：raw积分为`2*accumulate(wave.begin(),wave.end(),0.)`，整窗基线扣除后有符号求和；负的raw数值可能是正常低信号涨落，不应当作缺失。
相反，旧`1ec47efe`及已知data `d0b1b2dd`的同名函数约L706–738只将正wave样本加入积分。
这证明已知源码实现不同；本轮未重新认证data完整生产flags或测量全量data响应。pC单位相同不保证MC/data的raw响应完全相同。

`d32b0ff3:.../NtupleDumperAlg.cxx`约L1570–1632：`VetoNu*_reduced_charge`是按参考时刻截止的原始wave样本积分；缺参考时刻时回退raw总电荷。
它不是CrystalBall拟合电荷，也不是把`charge`乘一个尺度。F7保留此独立时间窗读出，仍按其自身波形的baseline/missing/invalid状态做缺失处理；时间窗/参考时刻系统仍待data核查。

## 状态位与缺失

实际`d32b0ff3:xAOD/xAODFaserWaveform/xAODFaserWaveform/WaveformDefs.h`：

| 位mask | 意义 | F7处理 |
|---:|---|---|
|1|THRESHOLD_FAILED|不等同无波形；保留有限raw，包括0/负值|
|4|WAVE_OVERFLOW|raw保留实际截断积分；不解释为未饱和真实电荷；calo拟合能量标缺失|
|8|BASELINE_FAILED|依赖该基线的电荷标缺失|
|16/32|GFIT_FAILED/CBFIT_FAILED|raw仍可用；calo拟合能量标缺失|
|128/256|WAVEFORM_MISSING/INVALID|波形读出标缺失|

raw/reduced无效mask=392；calo拟合无效mask=444。status仅供清理和诊断，不添加为新的模型特征。
`clearTree`默认charge/raw_charge=0、status=1，不能把所有0或status=1都当缺失；这种默认与below-threshold的区分有接口限制。
原track外推失败坐标为999999 mm。应在坐标差/斜率等派生前传播NaN，不把这个标记推广为任意量/单位里的999999。
`Tracker/TrackerDetDescr/TrackerIdDictFiles/data/IdDictTracker.xml`允许eta_module=-1,+1，phi_module=0,1,2,3；eta的-1是合法类别。
`-999`、`-1`在正/非负变量中由物理域识别，MeV→GeV后的-.999/-.001也同样识别；uint32的-1可变4294967295，再经float32变4294967296，计数规则覆盖两者。
坐标、transverse momentum、q/p、符号、baseline扣除积分允许负值。未知signed变量的-999只审计并注明来源，不能一刀切删除；当前95,748个实际F6模型输入未发现这些-999类标记残留。
