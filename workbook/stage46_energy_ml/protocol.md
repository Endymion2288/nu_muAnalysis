# stage46 拟合前冻结协议

配置`ml/configs/true_coarse_depth.json`记录UTC冻结时间与起点commit；此时本轮尚未拟合。
本轮只回答真实粗区域能否解释stage45连续真z/预测区域概率之间的差距。
只读stage42 development、stage44 features、stage45 predictions，不重开stage34/35 test。
同3703例/21来源（pi8/k10/charm3），F6全65+22局部活动=X87，最高pz/原fiducial含lead/PMT veto/unit MC不变。
重点100≤reco pμ<1000 GeV，保留100–250/250–1000子层和≥1TeV参考，不截Eν，不删困难/高y/代理失败/缺失/尾部。

## 唯一候选及预算

C=oracle_region：X+真实五区域one-hot，共92列，与stage45的R同列数。
固定半开z区间（mm）：[-3000,-2928)、[-2812,-2600)、[-2600,-2300)、[-2300,-1950)、[-1769.65,-1619.65)。
原区域计数62/246/568/2510/317；unknown/outside应为0，失败须查错，不能删例。
-2600/-2300为分析界，非探测器模块界；原选择已排除材料窗口[-2928,-2812)。
真区域只oracle，不进入部署，不加入真实方向/PDG/matching、source/run/event/fold等特征。

仅3正式能量fit（3外折×1），最多1个20轮/200训练/200校准/100评估的小smoke。
不重训depth classifier，不扫描区域/容量/半径/种子，不新ROOT/G4/Athena。
固定400轮depth3/eta.04/minchild20/lambda10/subsample.8/hist/nthread1，种子20261101+fold。
外eval=f，train=(f+1)%3，cal=(f+2)%3；来源无交叉。
独立cal offset与原灵活scalar六箱映射不变，不用eval标签拟合/校准。
每fit壁钟120s上限，同一Condor作业内三折，1CPU/1GB请求，单任务1800s上限。
I0/X/R/Z逐项复用stage45缓存，不新增基线fit。正式模型文件存在时拒绝覆盖，避免无意重训。

## 报告与决策

预定主比较C对X、C对R、Z对C；附C对I0与Z对X原参考。
重点C对X改善≥2%且500次pi/k/charm分层来源bootstrap95%下限>0仅作oracle信息诊断，不能部署。
报告all/p/Eν/y/z/component/独立primary运动学parent代理的log-RMSE、mean/median bias、R68、尾>50%/100%。
同报独立cal scalar proper/Brier与原六箱N=1000固定响应经验谱及来源配对区间。
bootstrap条件于固定拟合，不含重训和探测器/生成系统；charm仅3来源，不作独立生产确认。

C接近Z支持完美粗知识有用，约束当前估计/利用不足；C接近X且Z有益支持本粗粒度不足。
不把不显著当等价，给C−R和Z−C差区间。连续z与one-hot的有限BDT表示不同，C可能优于Z，
不能机械相减得到唯一因果分账或严格信息上界。不得把差距全归μ拟合，不用truth_st1模长测能损。
完成后停止区域分类/容量扫描，只选择有效新读出信息族或新的独立物理支持。
当前尚未测量C结果；下一步具体方向在实测后按证据确定。

## 核验与交付

先小smoke，再Condor；精确cache_row/run/event/fold对齐、全部来源角色与基线回读。
保存3模型/逐折紧凑预测/单份表与SVG，记录实际时间、CPU、RSS、队列及迁移状态。
序列化模型回读复算能量和scalar校准；机器精度容差与缓存精确rejoin分开。
中文阶段报告先于Conventional Commit，报告输入/命令/实际数字/单位/程序及物理原因/限制/下一步验收。
不推送。未测data/归一化/系统与最终谱收益必须明确，不能用unit开发MC结果替代。
