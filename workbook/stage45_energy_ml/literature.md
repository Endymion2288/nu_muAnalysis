# stage45 文献复核与适用性

检索日期2026-11-01。本轮配置/区域/预算在拟合前已冻结；此复核不改变本轮候选。

## HEP：shower起点与能量采样

通过[arXiv API检索](https://export.arxiv.org/api/query?search_query=all%3A%22neutrino%22+AND+all%3A%22hadronic+shower%22&max_results=5&sortBy=submittedDate&sortOrder=descending)，
返回的最近五条依次为2510.12873、2508.02795、2504.01716、2501.06257、2304.14526。
本轮实际阅读全文相关段落的是：

**SND@LHC, Studies of Hadronic Showers in SND@LHC**, [arXiv:2504.01716v2](https://arxiv.org/html/2504.01716v2)。
作者分别讨论target SciFi与下游HCAL信号随shower起点的变化；在模拟校准中用这两部分敏感体的
总能损代替数字化总信号，得到ideal参考。原文：

> instead of using the total signal per event registered in the SciFi and US detectors,
> in the calibration we used the total energy losses per event in these detectors
> to obtain energy response and resolution that represent an ideal case.

可行性判断：支持将“起点是否可知”与“探测器采样/电子学能看到多少”分开，本轮只测前者的软区域表示。
若该表示无ν实用增益，可以在已有HITS上问另一个已存在读出族的理想采样信息，而不是自动增加网络容量。
SND有target内多层SciFi和HCAL，其精度、阈值、响应系数不能移植到FASER；不能把真实能损称部署输入。

其余检索结果仅阅读API摘要：

- [2510.12873v2](https://arxiv.org/abs/2510.12873v2)：JUNO散裂背景/中子标记，不适合作为本项目删去困难ν事例的理由。
- [2508.02795v1](https://arxiv.org/abs/2508.02795v1)：IceCube以inelasticity测ν/反ν组成；支持能量分配的物理重要性，
  但TeV–PeV冰中起始轨迹与本几何不同，不采用其分辨率或方法收益作预测。
- [2501.06257v2](https://arxiv.org/abs/2501.06257v2)：IceCube级联方向分辨率限制，分开物理横向展宽、传播与读出噪声的思路相关，
  本轮不是方向重建实验，不借此扩大模型。
- [2304.14526v1](https://arxiv.org/abs/2304.14526v1)：Prometheus冰/水中ν望远镜模拟，对本轮现成PHYS缓存没有直接增益，不引入新模拟基建。

## 机器学习：stacking与独立预测

**D. H. Wolpert, Stacked generalization**, 1992,
[DOI:10.1016/S0893-6080(05)80023-1](https://doi.org/10.1016/S0893-6080(05)80023-1)。
本轮用CrossRef API核对了作者、标题、年份和DOI，未下载论文全文。
这里以来源OOF实现辅助深度概率的stacking：能量训练事件的深度概率来自未见该来源的classifier；
独立cal/eval由外训练来源classifier提供。该设计避免直接in-sample预测造成的训练输入泄漏，
不保证OOF与全外训练模型的概率分布完全相同，更不保证ν收益。
不将机器学习的一般方法依据当本探测器有可恢复顶点或额外物理信息的证据。
