# 阶段23预注册：选中样本条件能谱前向闭合（2026-10-30）

在任何响应矩阵或本阶段谱拟合结果出现前冻结本协议及ml/configs/closure.yaml。
不训练新模型、不扫超参/分箱/正则化；不评价calibration/test/SIBYLL challenge。
沿用stage12选择、全部异常及冻结validation 13,375例、22来源组。
这是已用于既有选参/早停的validation再诊断，不是独立test或真实data闭合。

## 样本及观测量

候选为mu_p、mu_p/0.8、阶段22 CPU长预算BDT UU/FU及阶段21 TabM UU/FU。
学习器每个seed分别评价，最终平均损失/方差量，不平均事件预测；mu基线只有一个确定观测量。
不同候选的历史训练硬件/预算不同，不推广为架构的普适排序。
模型预测、mu动量及truth/key只读现成紧凑缓存，无ROOT/xAOD扫描或新逐事件副本。
六truth bins为100–6400 GeV原倍增bin。原unit MC是默认目标混合，不是flux权重。

charm/k/pi来源组分别按字典序交替分A/B，首组分别A/B/A，得到11/11组；
组内两种run/nu符号不拆开。做A响应→B伪数据及反方向，不交叉使用同组估计与闭合。
组分割仅用来源标识，在读取模型输出分布前冻结，不按精度调划分。

## 响应、似然与信息

主reco为9个内部边界[200,200sqrt2,400,400sqrt2,800,800sqrt2,1600,1600sqrt2,3200]，
共10类，首类包含全部<200、末类包含全部>=3200，所有上下溢出保留。
另按原100–6400倍增bin记录<100/>=6400流出，不能删掉极端事件。
辅助rank reco为响应折自身的10等频分箱（9个分位边界），随后在另一折固定应用；
边界只用响应折观测量，不用truth或伪数据，bootstrap条件于这些固定边界。
mu_p与mu_p/0.8的rank响应/信息应相等，这是单调尺度变换对照。

R_jb=P(reco j | truth b, selected)按响应折单位权重计数/列总数估计。
形状f_b>=0且sum f=1，q_j=R_jb f_b，使用多项分布NLL -sum p_obs log(R f)。
固定uniform初值、解析梯度、SLSQP ftol1e-13/maxiter500，无平滑、pseudo-count、ridge或正则化。
零响应支撑但伪数据非零的类别保留并标记support failure，不用伪计数填平；
优化失败/零truth bin如实计数，不能因少数事件删除某模型或异常事件。

N=1000 selected events仅作共同统计基准，不是实际data预期产额。
在已知f_true及固定R处求五个独立形状方向的Fisher矩阵，逆矩阵映回六bin协方差。
相对特征值<1e-10判为不可辨识，不用伪逆制造有限误差。
报告各bin相对sigma、六bin RMS相对sigma、最高bin误差、相关及矩阵条件数。
这些是响应已知、无背景/系统误差的局部统计信息；MC响应不确定度另作组bootstrap，
不把此sigma当完整测量误差或实际灵敏度。

## 闭合压力测试与MC统计

五个主case：nominal；w=(E/800GeV)^(-0.5/+0.5)；
within_minus/plus为(E/E_bin_geomean)^(-1/+1)，在每个伪数据truth bin内归一到原bin计数，
使六bin true fractions不变，专门检验bin内谱形改变。所有权重只用于伪数据压力测试，R不重拟。
第六个component_matched是中心值诊断：响应/伪数据折都按full-validation的unit
charm/k/pi比例匹配，控制奇数组划分导致的组分占比差；不是flux归一化。
该诊断不做bootstrap或toy，不给它未测量的显著性。

每case报告fhat/ftrue-1及reco deviance，不用两方向signed bias抵消代替闭合。
主闭合指标为各bin/seed/方向的相对偏差平方平均后开方，并记录每方向及最坏bin。
500次组配对bootstrap：每折独立重抽11组，跨模型/seed/case共用同一批抽样，
同一组计数同时用于R、truth及reco，不独立随机这些相关量。平均各seed/方向的平方量。
空truth bin/响应支撑/优化失败逐项计数，配对区间使用共同有效replicate并报告次数，
失败比例>1%时不得把条件区间作为无条件稳定性证据。bootstrap反映该来源抽样的MC变化，
不是生成器/探测器系统学，也不补足仅3个charm来源组的总体不确定度。

nominal下每seed/方向/binning做200个固定R多项分布toy，N=1000，检验boundary频率、
相对RMS、pull与局部Fisher 68%区间coverage；这是已知响应的程序/统计检查，不是独立MC闭合。
在真实响应矩阵上另做nominal及高两truth bin乘2的exact forward self-closure，
重建谱形与前向分布须闭合（可辨识时fractions误差<2e-5、reco误差<1e-7）。
合成矩阵恢复及解析梯度差分也先验证；不按闭合结果改变拟合或选模型。

## 执行及验收

先本地按每折每truth bin至多150例、seed0、8 bootstrap/8 toys验证mu/TabM分支，
短跑不用于物理结论；随后6个Condor CPU作业分别计算6观测量，单线程BLAS/OpenMP，
一次读入，预聚合group×truth×reco小表后重采样，scratch写出最终紧凑结果。
正式500次组bootstrap与200 toys在批处理执行；汇总阶段可本地读小表和绘图。

同时回答：回归精度优势是否保留为条件谱统计信息？flat改善端点后是否改善闭合，
尤其bin内谱变化？固定能量与rank分箱的结论是否一致？有限MC/边界是否限制判断？
用配对来源组区间及toy检查给出明确结论，不承诺每个指标必有显著赢家。
只保留紧凑矩阵/拟合表/不确定度，合并模型重复JSON，清理核对后的源码包。
写中文阶段报告及Conventional Commit，实际记录耗时/CPU/RSS/事件数/资源。

参考：Cousins, May, Sun (2016), https://arxiv.org/abs/1607.07038，支持直接在重建分布比较；
Schmitt (2012), https://arxiv.org/abs/1205.6201，提醒迁移校正中的病态和正则化代价。
本阶段采用无正则化的前向形状拟合，先暴露信息与MC局限，不引入未经验证的平滑收益。
