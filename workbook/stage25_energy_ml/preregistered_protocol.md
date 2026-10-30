# 阶段25预注册：未知共同箱内形状的实际剖面似然（2026-10-30）

在任何本阶段unknown-alpha拟合/区间/coverage结果出现前冻结本协议及ml/configs/profile_response.yaml。
沿用stage24全部13375例validation、22配对来源组、A/B双向折、单位MC权重、
六个100–6400 GeV倍增报告truth箱、十energy reco类及全部异常/流出。
固定μ/0.8、阶段22 BDT UU及阶段21 TabM UU三seed，不新训练、选架构或打开保留集。

## 模型、算法和数值压力范围

形状注入alpha=-1,0,+1仍按(E/箱几何中心)^alpha，在每个伪数据报告truth箱恢复原bin计数。
六个真实fractions不变。响应仅来自另一来源折的连续重加权，未知共同alpha与六fractions一起拟合。
alpha限制[-3,+3]仅为预先固定的数值压力范围，不是物理先验或理论系统学幅度。
f>=0,sum f=1；五个独立谱方向+一个共同alpha不超过九个reco形状自由度。
不自由放开六箱独立alpha，无平滑、伪计数、正则化或alpha惩罚。

SLSQP，归一多项分布NLL，解析f/alpha梯度，ftol1e-13/maxiter500。
unknown全局拟合从alpha=-3,0,+3及uniform f分别开始，取成功解最小NLL，保存起点差异/失败。
fixed-f条件拟合两起点：全局解投影到指定f_b，再用该alpha及其相反侧端点（alpha_hat>=0时-3，否则+3）。
固定alpha的条件问题为凸simplex拟合，单起点，先比较已知真实alpha控制。
所有边界/失败保留。LR<-1e-5视为优化一致性失败，不能静默截断为零；
更小量级的负LR当作数值零并记录最小值。不因少数异常中止分析分支或删除事件。

连续响应使用原事件log(E/Ecenter)的0–16阶指数矩预聚合；在[-3,+3]用Taylor多项式及解析导数。
|alpha log(E/Ecenter)|<=3 log(2)/2，余项有确定界；正式运行前核查直接事件重加权的R/导数、
负概率、列和、端点及注入点的误差。moment压缩仅加速数值求值，不更改物理分箱或模型。

## 评价与区间

比较两种推断：known_alpha固定注入真值；profile_alpha实际估计共同alpha。
中心伪数据每alpha报告fractions、alpha_hat、偏差、deviance、边界、优化/KKT及局部sigma。
对六个f_b及alpha反演2N*(NLL_profile(value)-NLL_MLE)<=1的68.27%渐近LR置信集合。
中心值给出包含MLE的连通分支端点：每侧12个平方间隔扫描点找首次LR=1穿越，再brentq；
同时记录扫描中再进入集合的提示，若端点碰到0/1或alpha数值域必须标记domain-limited，
不伪装成域外已排除或无边界区间。离散扫描不是对所有不连通分支的数学保证。

Toy覆盖无需逐toy求全部端点：在注入true f_b/alpha处作条件最大化，直接判定LR_true<=1，
这等价于上述LR集合覆盖，计算更省；不把它称Wald误差条。
同时记录known-alpha Fisher ±sigma覆盖供与stage24对照，但unknown的主验收使用实际LR。
主统计为response_control及cross_source分别、每alpha的六bin覆盖率、最坏bin、最高bin，
以及unknown-alpha的覆盖率/偏差/碰域率。两推断使用同一toy counts。
所有模型seed/方向等权汇总；不能以signed方向平均抵消谱bias。

每seed/方向/alpha/law200 toys，N=1000只是共同选中数基准，不是实际data预期产额。
两law与stage24相同：cross_source=另一来源折加权reco经验分布；
response_control=响应折连续R(alpha)*ftrue，是已知模型程序控制，不是独立MC闭合。
RNG沿用stage24的SeedSequence，保证与历史toy实验可核对；跨law未配对。
coverage仍条件于固定经验R/均值，响应MC、模型误差和真实data的无条件覆盖未测量。

500次配对来源组bootstrap，沿用stage23/24同一A/B组draws，重新构造moment响应、
pseudo truth/reco并重做known/unknown点拟合，不嵌套toy或区间反演。
与stage24 coarse6/continuous点偏差作共享draw的配对比较，报告有效重复及失败。
区间为未作多重比较校正的95%组百分位，条件于既有validation和固定模型，不作独立test确认。
RMS正区间不能检验零bias。固定数值域外的形状、独立六箱形状、生成器/探测器系统学均不在本阶段。

## 程序与执行验收

先合成模型的梯度/真值恢复/条件约束/LR反演检查；
本地smoke每折每报告truth箱最多150例，seed0、4 bootstrap、4 toys，
中心仅对alpha0的alpha/最高f_bin反演端点，不用于物理结论。
正式7个单核CPU Condor作业按model×seed划分，预聚合一次，BLAS/OpenMP单线程，
3000MB，按短跑估计选择批次flavour；现成LCG109 NumPy/SciPy，无GPU训练。
保存紧凑toy counts/fit/LR与组bootstrap点数组、中心响应和区间，合并报告/去重JSON，
无新逐事件缓存/模型checkpoint/ROOT数据；核对源码包后删除。

必须给出物理结论：形状未知时是否保持谱信息收益？实际LR覆盖能否支持局部Fisher判断？
alpha被多少程度约束、是否碰数值域？额外自由度是否只吸收了来源差异而未恢复真谱？
若coverage不足，区分程序控制与跨来源压力，查明数值或经验响应原因，不能只以deviance下降验收。
保留3个charm来源组/最高内部箱23与26例的有限MC限制；unit归一化沿用用户授权，
flux/接受度、背景和真实data控制区仍未测量。写中文阶段报告、更新路线图并作Conventional Commit。

参考沿用stage24已检索的Cowan et al. arXiv:1007.1727、Cranmer arXiv:1503.07622；
仅以LR=1作为待实测的渐近阈值，用边界与实际toy覆盖检验适用性。

数值角点实现约定（首次数值结果前补充）：f_b=1时其余fractions确定，
fixed-alpha直接评价似然；unknown-alpha退化为有界一维最小化，并比较alpha端点及0。
若某hypothesis使有观测的reco类别概率严格为0，其NLL/LR为无穷，表示被排除，不能填伪计数。
