# stage36预注册：CaloNu穿越μ、非穿越模块与波形响应控制

冻结UTC：2026-11-01T13:56:34.015898+00:00；起点7e7f89e。此前只读首MC100049及data16000文件各2048事件的字段/读出和选择pilot；
已看MC约8GeV与data约.6GeV总量、charge/nMIP标度不符，并读正半波积分源码。不是事先未知假设或新ML test。
其余文件/正式响应统计未读；不训练/改变stage35模型，不重复其test评价。

## 问题、预算、输入

检验专门μ样本约8GeV响应是否为穿越信号、未穿越模块pedestal与MIP换算的组合；
区分物理沉积与阈值/拟合/归一化程序原因。source commit1ec47efe；MC100049/100050首bck日志均明确
CaloNu几何/backward，参考conditions OFLCOND-FASER-05，与stage35 nominal MC分支匹配。
data r0022是reco/r0022/d0b1b2dd、TI12Data04/noIFT，实际位置/HV/时序尚未证明与MC一致，
所以只能做响应控制和条件差异诊断，不能预称完全MC/data闭合。

固定manifest 18文件：MC每符号沿文件名序六等距位置取6份，各前50000例，共≤600000；
data取GRL内接近安装期起点/16000/终点的15838/16000/16923三run，各首/中间文件前100000，共≤600000。
不按读出选文件，记录prefix不是完整run。首pilot可在正式cohort重现，不当独立确认。
≤18个1CPU Condor jobs，≤1.2M input，0新fit/重模拟/xAOD，只保存选中紧凑响应及cutflow。

## 外部选择：不根据CaloNu信号挑好峰

按顺序：data GRL stable且非excluded、同束团distanceToCollidingBCID=0（MC不施加）；
longTracks=1；该最高pz轨迹nLayers≥7、nDoF≥9、chi2/nDoF<15；100≤reco p<1000GeV；
保存VetoNu外推|x|,|y|<500mm且二维角度模<25mrad，屏蔽999999失败哨兵；
VetoNu0/1与Veto20/21 raw charge各>40pC作为独立穿越符合。
没有CaloNu电荷、状态、有限性、MIP窗或普通Calo选择。混合线上trigger接受度未校正，不称无偏μ谱。
质量/动量/外推/外部符合逐步效率保留。高p不扩展；两个重点子层分别报告。
MC真值不入选择；这一cohort是reco μ候选，非严格无shower、非精确参考面或path校准真值。

## 几何与读出控制

从CVMFS只读geometry DB解析FASERNU-CALONU→Calorimeter-CALONU→CaloNu-00→TopLevel-00和switches，
结合匹配源GDML取得模块/active core名义位置、旋转和尺寸；保存实际tag/数值。
使用VetoNu z=-3112mm处保存x/y和角度作直线代理，与名义active core box求交。
不冒充native含散射/磁场传播或data对齐。nominal RxRy与反向tilt作固定几何敏感性控制。
模块core前后面均在横向边界内10mm为interior，通过box但非interior为edge，零交长为off；
另报告未能分到唯一interior的事件，不删除其读出。
模块id顺序须审计源/conditions；若data顺序未证明，用nominal proxy分层但不称正确匹配校准。

每样本/运行与模块、interior/edge/off、100–250/250–1000、status分层：
N/来源组、raw/fit电荷pC、nMIP、E_EM GeV、total、baseline rms mV、raw peak/噪声比、
有限/零/负/overflow/threshold/fit失败/缺失与invalid波形比例，q16/median/q84及source区间。
status1不是缺容器；全部输入保留，finite只作为某项量测的可验分母。
固定异常阈值|E_EM|>1000GeV或非有限；识别率/误标率描述性比较fit失败bits16/32，
以及有限raw对异常fit的支持；不据此删事件、造新的test增益或修旧生产。

raw积分源码findRawHitValues只累加正半波；FitWindowWidth75含端点共76个2ns采样。
预先比较off模块的raw charge与高斯零均值噪声预期
q_noise=2×76×baseline_rms/(50√(2π))pC，特别status bit1层。
这是假设近似：基线拟合误差/相关噪声/残余信号会偏离，不把不符直接归为程序bug。
报告q_fit/nMIP这一有效参考电荷（data含gainRatio，非原始MIP_ref），不能直接改data增益。
同事件interior模块与其他off模块比较，以及四模块off噪声贡献对total的尺度解释，
不把“非零读出”或相关性当ν新增信息，后者只由stage35受控BDT给出。

## 统计、验收、交付

500来源block bootstrap：MC在固定两个符号内按生成range文件抽；data先抽三run，再在每run抽两file。
给各量95% percentile区间，记录无支持重抽。只有三data run，不当完整conditions系统区间。
总量中位/外部efficiency、interior/off差异、noise比例和有效参考电荷是主控制；
多分层描述性不作多重检验校正，不以挑箱或改几何挑好一致性。
如匹配/几何不足，实测覆盖和响应差异可作本阶段结论，data物理闭合明确未测量。
验收必须得到一个有量化数据的pedestal/响应/拟合原因结论，不只目录搜索或计划。
小样本对照选择/几何交长后提交，记录wall/CPU/RSS/吞吐/失败；保留最小NPZ/汇总、清payload/分片，
中文workbook+路线/Prompt更新、Conventional Commit与逐blob读回，不push。
