# Stage122 实现问题与修正记录

这些是程序验证记录，不能当作物理阴性结果。

1. 新 Athena/ROOT 解释代码须先独立定义 HEPMC3，再加载 RawWaveform、ScintSimEvent 字典。
2. HTCondor 文件内部默认宏覆盖命令行赋值。最终使用每 phase 固定 descriptor；9669198、9669228 在 idle 时取消，不把它们记为已执行的科学任务。
3. 27 个来源中的第 17 项尾部有零事件 HITS/no CollectionTree。先逐精确文件读取实际 entry 总数，确认严格等于原 parent_N 后排除零事件输入；所有选中父事例保留。
4. xAOD DataVector proxy 必须使用 const container 遍历。
5. 旧 Cling 的 Python 嵌套 list→vector<vector<unsigned int>> wrapper 崩溃。ADC 输入改为 flat vector，布局显式检查。
6. time_vector()/wave_vector() 按值返回；不能用两次临时对象的 begin/end 做 insert。保存局部向量再复制；aux store 比 hit container 更晚析构。
7. digitizer 会先为字典内 PMT 生成信号/噪声，ScintWaveformDigiAlg 随后依 CableMapping 排除未接线 PMT。不能按 plate 合并不同 PMT。重建仅使用实际 native readout 标识，保留完整生成输出与随机流。
8. 最根本的标识不闭合原因：新脚本漏设官方 MC 的 IOVDb.DatabaseInstance=OFLP200，默认实例须修正。实测显式 MC 实例仍不能闭合：标准重建本身已使用同一扩展字典，而历史 RDO 的 plate 位布局更旧；直接用新字典解释旧 ID 是主要映射错误。最终通过官方 CableMapping 当前 ID→硬件 channel→历史持久化 channel 联结，同时保存两种 ID，不将 PMT 合并。首轮 27 源与其 A/B/C/D 数值全部降为实现诊断；须以显式 OFLP200、FASERNU-04、OFLCOND-FASER-06 重读同一完整父队列。原 Stage119 标准 faser_reco.py 已显式使用 MC 实例，不受此新脚本错误影响。
9. C 中旧 total hit count 含窗外沉积，违反层级隔离。改为窗内 log1p(total MeV) 与窗内零标记；7 个窗内能量分箱、容量、样本/角色/超参均不变。初版和窗口修正版均保存于 ignored 缓存，不择优。
10. EOS FUSE 对部分远端新输出出现负目录缓存/I/O error。实际 XRootD stat 存在且作业 exit0；通过 XRootD 运到本地临时文件，逐成员核验返回字节后收集，不把挂载不可见误写为作业失败。

11. 原生 raw/reduced 特征核对首先在 entry88 的 reduced charge 差 0.011166992073413 pC。核对固定版本 faser_ntuple_maker.py 发现 MC 分支显式覆盖默认时间差为 Veto 27.21 ns、Preshower 51.41 ns；旧核对代码误用类默认 33.2/53.625 ns。改为 producer 的 MC 常数，35 ns 积分窗和 rtol/atol 不变，不按差异拟合常数。9669254 在缺输出目录时退出，9669256 执行后如实报闭合失败，费用全部计入。

12. 全252父核对在9669273（首次全量forward之前）又发现source39 entry4622和source54 entry2610两父、4个reduced特征不闭合。9669274完成全池诊断，没有forward。旧硬编码Veto参考[7,14]没有按官方VetoID station认证；改为对9个相同配置精确来源逐个读取官方CableMapping，用station==1严格复现NtupleDumper的veto2定义。实际9源官方映射均为Veto2=[6,7]，channel14/15属于station0，不是Veto2。首40例通过不能替代全父闭合。同时保留C++ expected float + Gaudi DoubleProperty的double积分边界，避免NumPy标量提升改变边界。完整诊断波形只保留ignored缓存，紧凑差值见roundtrip_mismatch_summary.json；不通过放宽容差处理。

保留每个作业的 stderr/事件日志与实测资源；所有失败和重做计入阶段总成本。不得只保留成功尝试的计时。

13. 最终9669279全池分析通过：252父原选择闭合，119个其他cuts有效候选的六项raw/reduced最大差0 pC；40父最终QA复核通过，2父跨进程ADC/完整随机状态一致。9669283独立复算192个RMSE最大差0、115父方差分解最大差3.9406683211701266e−16。

14. 官方NtupleDumperAlg长度2的VetoNu积分数组按整个container ordinal遍历；额外secondary会越界。本helper保留全部额外hit，仅按明确定义的前两primary积分作安全诊断，不认证历史UB。3父13个额外hit视图中，source51 entry4386有2视图其他cuts通过而原生选择未知，其原生通过概率保守[0.875,1]；另外两父其他cuts确定失败。不得把安全定义下零选择迁移写成全官方链零迁移。

`protocol.json`及冻结合同内pending是执行前历史清单；最终验收以`completion_audit.tsv`为准，未认证的producer终止/data–MC/完整GENIE输入不被成功程序检查覆盖。
