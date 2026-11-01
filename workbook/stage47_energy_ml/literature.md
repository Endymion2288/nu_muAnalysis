# stage47 文献复核

2026-11-01在线arXiv API按SND hadronic shower/FASER technical proposal标题检索，返回2篇，
原查询与摘要见literature_search.json。进一步阅读SND@LHC的相关HTML段落，摘录范围见literature_excerpts.json。

- [SND@LHC, Studies of Hadronic Showers in SND@LHC, 2504.01716v2](https://arxiv.org/html/2504.01716v2)：
  相关段落将target与下游HCAL能损作为ideal响应参考，并讨论shower起点对采样份额的影响。
  可行性：支持本轮X/S/z/S+z四格，分开位置知识与实际敏感采样；没有用其testbeam分辨率、
  采样/标定系数或结论替代FASER数值。FASER普通Ecal是不同的几何与响应，不是SND HCAL。
- [FASER Technical Proposal, 1812.09139v1](https://arxiv.org/abs/1812.09139v1)：
  本轮仅读API摘要，描述tracker/scintillator/calorimeter/readout；不当作当前s0015几何/条件认证。
  本轮模块与单位以生产1ec47efe源码+实际HITS校验为准，见source_audit.md。

统计/机器学习继续使用固定来源隔离交叉拟合、独立cal scalar映射和来源配对bootstrap；
没有新架构、超参数扫描或根据相关性选变量。X已有普通Calo重建量，所以S增量必须由同事件条件风险测得。
纯相关、理想能损与读出比值不能给唯一因果解释，也不是数学信息上界。
