# stage35：CaloNu生产、单位及读出定义审计

本文件只核验已有PHYS和源码定义，不代表data/MC响应闭合或强子标定。

## 生产与几何

输入清单为`ml/configs/calonu_files.tsv`：200139/200140/200146的s0015/bck，共46/63/15文件。
逐条reference见[production_reference.tsv](production_reference.tsv)。日志reference记录
CaloNuMC/1ec47efe、Calypso22.0.49、FASERNU-CALONU、OFLCOND-FASER-05。
π首文件日志明确`--backward`；K/charm所保存的ntp reference命令没有该选项，故二者
**确切bck maker运行配置未核实**。不能把reference直接当全部bck生产证明。
本阶段控制是同一实际文件、事件、选择内的读出有/无，结论条件于该生产，不跨几何估计增益。

匹配源码树：`/eos/home-x/xcheng/FASER/calypso`，只读`git show 1ec47efe:<path>`，未重建。
`Calorimeter/CaloDetDescr/CaloNuGeoModel/data/CaloNu00.gdml`存在；
`src/CaloNuDetectorFactory.cxx`还从geometry DB取全局变换。**安装后的精确全局模块z尚未测量**。
因此只报告真交互z与信号/风险的实测关系，不由局部GDML臆造全局面、shower路程或唯一物理机制。

## 源定义与数据核验

- `PhysicsAnalysis/NtupleDumper/src/NtupleDumperAlg.cxx:244`的FillWaveBranches：
  `charge=integral/50`、`raw_charge=raw_integral/50`，单位pC；忽略secondary hit防覆盖。
- `Calorimeter/CaloRecTools/src/CaloRecTool.cxx:265`：
  `nMIP=charge*gainRatio/MIPcharge_ref`，MC不做data的HV外推；
  头文件对应通道系数为E_dep=58.5 MeV/MIP、E_EM=330 MeV/MIP。
  E_EM/1000得到GeV **EM scale**，不是独立测得的强子能量。
- 同工具中`fit_to_raw_ratio=raw_integral/integral`，integral=0时取1。
- NtupleDumper的CaloNu容器填充（约1290行）：四模块E_EM是fit值；
  `total_fit_E_EM`为其和；`total_raw_E_EM`为各模块fit值乘ratio的和；
  `total_E_EM`逐模块在overflow bit4时用fit，否则用raw校正值。
  因而total一般**不等于四模块E_EM简单和**。保留模块和total有不同定义依据。
- `xAOD/xAODFaserWaveform/xAODFaserWaveform/versions/WaveformHit_v1.h:23`定义bit序号：
  状态值1=THRESHOLD_FAILED，4=WAVE_OVERFLOW，16=GFIT_FAILED，32=CBFIT_FAILED，48为后两位同时置位。
  status1不能直接当缺容器或无效数；status位与数值分别审计，不据此删本阶段事件。

[readout_audit_summary.json](readout_audit_summary.json)实测MC fit 14309例及run016000的前2048条未选择data：
模块E_EM=330 nMIP、E_dep=58.5 nMIP在全部有限支持上0失败；
total定义分别14299/2047有限可验例，0失败；10/1例非有限不冒充通过。
容差rtol=3e−6，模块atol=.001MeV，total=.003MeV；total最大绝对差.102775/.087228MeV，
大数float舍入下均满足相对容差。模块/total异常有限值未裁剪，非有限只在XGB矩阵转NaN。

MC fit四模块非有限3/4/1/2例，负EM值15/26/12/13例；raw charge全14309例有限。
模块1最小−117895.168GeV，位于status32的6例之一；模块2最小−1670.179GeV，位于status48的9例之一。
这些是拟合输出/拟合质量问题的证据，不能解释为负物理能量；具体波形失效原因、影响量尚未隔离。
详见事后描述性[fit_quality_descriptive.tsv](fit_quality_descriptive.tsv)，无新cut/refit。
MC fit总读出零2403、有限非零11896、非有限10，overflow0；data分别0/2047/1，overflow2。

## truth与data边界

s0015缺`truth_barcode`。严格primary barcode确认未测量；不是将全部事件标成未确认。
primary候选为与入射ν交互点一致的唯一同号μ，p/y只作诊断；独立命名的kinematic-parent代理
还比较leading匹配PDG、parent PDG、产生xyz及三动量，绝不当barcode-confirmed或部署输入。
没有读取truth_st*，没有用其模长测材料能损。

data路径、状态计数和单位分布见readout audit。前2048条没有GRL、trigger或through-going μ选择，
不能用其分布直接与CC MC作物理闭合。run、HV/增益、几何、conditions和外推面须先匹配。
普通Calypso构建不自动用于重建CaloNu生产。响应系统、相互作用模型变体、物理flux归一化和最终谱收益均未测量。
