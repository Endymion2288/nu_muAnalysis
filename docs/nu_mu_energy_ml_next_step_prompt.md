# 下一轮执行 Prompt：stage47 普通Calo理想敏感采样，结束区域扫描

先读AGENTS.md、stage46中文报告/冻结协议/全量表，修订路线§28、信息预算计划§13。
stage46已完成：同3703例/21来源（pi8/k10/charm3）、重点3024例，X=F6全65+22局部活动。
真实五区域C对X改善.5705% [.2581%,.9353%]，C对预测区域R .4697% [.2260%,.7632%]；
连续真z的Z对C仍3.0997% [1.8109%,4.3441%]。重点I0/X/R/C/Z log-RMSE
.28709694/.28740092/.28710998/.28576139/.27690373。
多数下游2062例Z对C4.0932%，高y90例/19来源7.5791%，下限均>0；上游C局部小样本价值保留。
C对X proper有小收益，六箱谱未确认。3正式+1smoke已完成，回读模型/offset/scalar精确一致。
粗区域完全已知仍不足以保留连续z收益；不把缺口全归classifier，也不把有限BDT差当信息论上界。

本轮唯一主线：**已有HITS中普通下游Calo四模块敏感能损的信息诊断**。
停止区域细分/classifier/容量/网络扫描。F6已有普通Calo重建量，新增的是敏感层保存沉积oracle，
不是重命名原电荷，不叫完整强子能量，不当reco部署特征。其可得性及ν收益目前未测量。

1. 只读stage42 development、stage44 features与stage45/46预测，复用同3703例/21来源/三折/X87。
   stage42 requests已匹配PHYS↔HITS，复用其请求和源文件路径，不重新定位大样本。
   原最高pz/含lead的fiducial/PMT veto/unit MC不变。重点100≤reco pμ<1000 GeV及100–250/250–1000，
   ≥1TeV参考，不截Eν，不丢高y/代理失败/最高能箱/缺失/尾部。不得重开stage34/35旧test冒充独立确认。
2. 先做≤2来源、总≤40事件pilot：按manifest顺序首个已选pi和K来源，各取请求中前20例，
   不依Eν/y/z或沉积挑事件。检查普通Calo敏感branch/persistent schema、物理四模块ID/单位、
   当前生产中的位置/模块含义与保存沉积定义、全事件身份指纹、动态范围。
   参考ml/read_calonu_sensitive_summary.py及stage42匹配脚本，不能照抄CaloNu ID/EM标定。
   优先匹配的现成Calypso构建，不新编完整软件栈；较重I/O和完整提取走Condor。
3. pilot可用后，拟合前冻结S_Calo四模块敏感能损（MeV→GeV），只此一个新族；
   总粒子沉积不扣truth μ，不输入真实方向/PDG/matching，不引入truth可见强子能量。
   同21来源完整≤4000事件（目标3703），只读必要branch/entries，每文件尽量一次读，写紧凑摘要。
   空hit是可定义的零；缺失branch/无法匹配不能假填零或删例。不能以完整子样本重训并称原总体收益。
   全支持不可取得则不启动比较或新生产链，明确记录不可测量，转来源/生产谱系独立支持审计。
4. 完整支持确认后仅拟合X+S_Calo和X+S_Calo+连续真z：≤6正式400轮depth3能量fit+1小smoke。
   X/Z复用stage45精确缓存，原来源角色、种子20261101+fold、独立cal offset/scalar不变。
   冻结重点S对X≥2%且500次pi/k/charm来源配对95%下限>0、S+z对Z的条件增量，
   原log-RMSE/bias/R68/尾/p/Eν/y/z/component/独立primary运动学parent代理、proper/Brier/六箱谱同报。
   真z/S仅oracle，不用truth_st1模长估能损；barcode缺失不冒充primary-confirmed。
   不追加种子/噪声/阈值/容量/新读出族扫描，不因少数离群或不利能箱停止物理分支。
5. 若S有实用且已知z后仍有的条件收益，区分理想沉积与已有重建量，再决定可实现响应/独立确认；
   若只在少数区域有效，报告占比/来源/区间，不扩大为全部ν收益；无实用收益则结束这条采样支线，
   转新的来源/生产谱系支持，不继续网络或电子学前置链。有限模型oracle仍非严格信息上界。

资源：小smoke后Condor，CVMFS现成LCG/匹配Calypso；提取按来源限制线程/I/O，训练CPU1足够。
切schedd先hold回读启动/完整输出，不并发重复fit。EOS访问失败先XRootD核验，不盲目重训。
只保留模块摘要/小模型/紧凑预测及单份表/SVG，记录计时/CPU/RSS/吞吐/实际I/O。
模型序列化、校准映射、精确事件rejoin与缓存/角色/预算必须验证。

先中文stage47报告，再报告与相关代码/配置Conventional Commit；更新两份计划及本Prompt，回读blob/clean，不推送。
明确真实data/系统/归一化/新独立ν确认与最终谱总误差仍未测量，不把unit开发MC收益升级为实际物理测量收益。
本轮必须形成有数据证据的物理判断；不能以多写计划或只通过schema/软件检查代替信息诊断结果。
