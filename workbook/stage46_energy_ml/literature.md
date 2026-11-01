# stage46 文献与下一条信息诊断的依据

2026-11-01在线arXiv API检索，原查询与返回摘要见[literature_search.json](literature_search.json)。
本轮仅阅读API摘要，未新阅读全文；不将摘要当本几何中的数值证据。

- [SND@LHC, Studies of Hadronic Showers in SND@LHC, 2504.01716v2](https://arxiv.org/abs/2504.01716v2)：
  摘要明确区分target与下游calorimeter的能量份额、shower起点及信号联合。
  stage45曾阅读其理想敏感层响应段落；本轮复核摘要，不声称新阅读全文。
  可行性：支持把位置知识和不同位置的实际敏感采样分开；不能移植其100–300GeV testbeam分辨率。
- [FASER Technical Proposal, 1812.09139v1](https://arxiv.org/abs/1812.09139v1)：
  摘要描述tracker/scintillator/calorimeter及读出系统。只用作寻找现有子系统/源码的入口，
  不根据旧技术建议书断言本s0015的全局几何、通道映射或hadronic containment。
- [FASER photonic-final-state search, 2410.10363v2](https://arxiv.org/abs/2410.10363v2)：
  摘要中的electromagnetic calorimeter高能沉积是光子信号定义。
  提醒下一步普通Calo敏感沉积不能直接叫完整强子能量；本轮不使用该搜索的选择或背景数作本样本输入。
- [FASER neutrino detector upgrades, 2503.19775v1](https://arxiv.org/abs/2503.19775v1)：
  摘要提到高粒度scintillator tracking calorimeter等方案，但它们是升级研究，非当前s0015已有读出。
  不假定这些变量已经可用，不新建硬件模拟作为本轮前置条件。
- [FASER preshower monolithic ASIC, 2210.03318v1](https://arxiv.org/abs/2210.03318v1)：
  摘要的prototype空间/时间/动态范围不能当当前MC支持；不引入该ASIC的理想像素信息。

## 有限容量与因果解释

机器学习依据沿用stage45记录的Wolpert stacking/来源OOF设计，本轮不再训练辅助分类器。
真实五类one-hot和连续z对有限深度树提供不同的可分割表示；保持容量并不能把比较变成信息论上界。
stage46给出的只是此固定表示/预算下的条件风险差，不把Z−C算成唯一fine-z份额。

## 下一阶段可行性判断

选择**已有HITS中普通下游Calo敏感层沉积的信息诊断**，而非继续细分z或扩大classifier。
F6已经含普通Calo重建量，因此新对照必须是独立命名的敏感层能损oracle，不能重命名原电荷当新信息。
这能检验本生产中普通Calo理想采样相对现有读出的潜在信息；不保证有增益，也不代表可部署读出。
branch、四模块ID/单位/敏感体、完整事件覆盖和动态范围尚未测量，必须先小pilot审计。
沿用stage42的HITS身份指纹与请求清单，只提取紧凑摘要；不跑新G4或完整历史digitization。
若该族在完整支持上不可取得，明确记录不可测量，不用删例/真值能量替代，不反复扩大工程链。
