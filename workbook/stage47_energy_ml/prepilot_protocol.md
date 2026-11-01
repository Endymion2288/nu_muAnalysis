# stage47 预定pilot范围与输入归档审计

起点44b5898；本阶段仅普通Calo物理四模块敏感层保存能损oracle。
先按已选manifest首π=0、首K=46各取原请求前20例（共40），不按能量/位置/信号挑例。
使用已有d32b0ff3字典，逐文件layout checksum和run/event/独立ν四元签名验证；不重建历史生产。
物理模块顺序(row,module)=(0,0),(0,1),(1,0),(1,1)，production EcalCaloNu=0，候选hitID=[0,8,2,10]。
查验EcalHits branch、实际ID覆盖、单位/定义和动态范围；不将CaloNu的ID/EM标定搬用。

stage42 requests.tar.gz实际只保留原PHYS指纹请求，没有located HITS entry/ν签名；原逐源shard已归并删除。
stage44 features也未保存原PHYS entry。因此无法无损直接复用定位结果。
必要偏离：仅对原21个PHYS文件读取既有最小指纹/ν签名列，重新定位相同selected行，
不变更事件、选择、来源折或模型，记录这部分I/O及时间，不将其称为新物理支持。

pilot通过后再冻结正式提取/模型协议，不根据pilot的ν能量预测调候选；本轮不扫区域/容量。
正式目标仍同3703例/21来源/X87，最多6正式能量fit+1小smoke；缺完整支持不能删例或填0。
