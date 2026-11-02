# stage50 结果前冻结协议

依stage49复盘、修订路线§31/信息计划§16，只做一次学习能力对照。
使用stage42全部A=14309例/81来源，不作4000例或21来源抽样；原F6全部65项，不加stage44的22项。
原fold、eval=f/train=(f+1)%3/cal=(f+2)%3、最高pz leading/含lead truth fiducial/PMT veto/unit MC不变。
重点100–1000 GeV，100–250/250–1000及>=1TeV参考；Eν不封顶，全部y/proxy失败/缺失/尾部/最高箱保留。
先A0与I0在B同3703例比较原offset；再由当前eval-fold A0对真正B-cal预测拟合共同B-cal offset。
不能用cal的另一fold OOF预测代替；不看B-eval标签调offset。校准/训练人数与组成详source_roles.tsv。
完整A2x2：L3_F6复用A0；L3_F6z、L5_F6、L5_F6z各3折，固定400轮，只改变depth3->5，种子等全同。
9新正式能量fit+1小smoke，正式每fit<=120s，smoke仅L5_F6 20轮/200train/200cal/100eval。
不早停、不扫seed/深度/轮数，不重建概率映射/六箱谱、分类器或新ROOT-HITS/生产。
所有A候选用同A-cal mean-log offset，正式train/cal/eval来源无交叉。
报告完整A、B及全10606剩余事件，避免只靠特殊抽样作重要判断；这些仍是开发支持，不叫blind。
重点及原p/Eν/y/z/component/proxy逐层MSE/RMSE、mean/median bias、R68、两尾、来源配对区间。
500次component分层来源bootstrap，同支持全部模型共draw，条件于固定模型/offset，未含重训/校准不确定性/系统/选择。
报告L5_F6对L3_F6、各学习器z增量及G_L3-G_L5，G=MSE(F6)-MSE(F6z)；非互信息或唯一因果份额。
实用候选重点改善>=2%且95%下限>0；阴性不称信息不存在，不能事后换指标/加网格。
连续z仅oracle，不混truth p/方向/PDG/matching，不用truth_st1估材料能损；代理非barcode-confirmed。
结果后结束容量问题；按证据冻结reco候选或进入全81来源短段角度/会聚新信息实验，不机械继承HITS4000预算。
中文报告先写再Conventional Commit，记录真实资源/单位/命令/输入产物/限制，更新路线与Prompt，不推送。
