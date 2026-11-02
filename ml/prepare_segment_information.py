#!/usr/bin/env python3
"""Freeze stage51 features, complete support, resource budget and controls before residuals."""
import json
import subprocess
from datetime import datetime,timezone
import numpy as np
from segment_information import REPO,OUT,CACHE,feature_names
from learning_capacity import load_inputs
from train_bdt import write_table

path=REPO/'ml/configs/segment_information.json';assert not path.exists(),'Do not redefine frozen experiment'
pilot=json.loads((OUT/'pilot.json').read_text());d,x=load_inputs();a,c=feature_names();indices=sorted(set(map(int,d['manifest_index'])))
cfg=json.loads((REPO/'ml/configs/learning_capacity.json').read_text())
cfg.update(stage=51,starting_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),frozen_utc=datetime.now(timezone.utc).isoformat(),
    baseline='L5_F6 cached stage50',candidates=['angles','convergence','shuffle'],truth_inputs=[],max_formal_fits=9,max_smoke_fits=1,
    indices=indices,extraction_batches=[indices[i:i+9] for i in range(0,len(indices),9)],max_pilot_events=40,
    collection='GhostBustedTrackSegment_',raw_collection='TrackSegment_',station_z_tolerance_mm=1.,convergence_half_span_mm=31.5,convergence_grid_points=65,
    convergence_scope='within each station fitted silicon-layer span only; no target-vertex extrapolation or cross-magnet transport',
    shuffle_seed=20261151,shuffle='identity-specific within event/station permutation of local slopes at common station-centre positions; fixed points allowed and reported',
    angle_feature_names=a,convergence_feature_names=c,formal_extraction_wall_limit_s=600,formal_extraction_total_bytes_limit=2000000000,
    pilot_wall_s=pilot['wall_s'],pilot_bytes=sum(r['bytes_read'] for r in pilot['records']),
    segment_quality='finite 8-vectors, no 999999 sentinel, pz>0, ndof>=0, finite chi2 without sign/size selection, station centre within 1mm; exact duplicate removal only; no chi2/angle cut',
    main_gain_gate=.02,relation_gain_CI025_above=0,model_selection_scans=False)
cfg['xgboost']=dict(cfg['xgboost'],max_depth=5)
path.write_text(json.dumps(cfg,indent=2)+'\n');CACHE.mkdir(parents=True,exist_ok=True)
write_table(OUT/'support_sources.tsv',[dict(index=i,N=int((d['manifest_index']==i).sum()),group=str(d['group'][d['manifest_index']==i][0]),fold=int(d['fold'][d['manifest_index']==i][0])) for i in indices])
(OUT/'protocol.md').write_text('''# stage51 新残差前冻结协议

完整stage42开发支持14309例/81来源，原F6/角色/选择/unit MC不变，全部B和剩余60来源分别报告；不使用旧test。
固定stage50 L5_F6/400轮/seed/独立A-cal mean-log offset。基线精确复用，角度/会聚/配对打乱3族各3折，总9新正式fit；至多1小smoke，不扫描。
采用GhostBusted短段，普通段只作覆盖/对齐/重复诊断。固定100GeV模长不能当测得动量或强子pT。
方向有效性和全部46角度+24会聚特征见冻结JSON；不以chi2或角度阈值挑有利子样本，ndof0段保留。
各station自己63mm拟合范围内计算直线集合均方横向离散的会聚曲线，不把它称ν顶点，也不回推靶区。
该曲线为二次几何摘要，不能表示多峰；宽度是相对最小离散+10%的几何宽度，不是拟合协方差或置信区间。
station0/1/3可用传播μ切线只用于相对角度，不把未知μ参考面的station2混入；相对角边际在控制中不变。
打乱只重配同事件/station共同参考面位置与斜率，所有角集合/位置集合/计数/missing/中心离散保留。固定点允许并实际报告。
9个Condor提取作业、每job9来源，CPU1/1GB、600s硬上限，累计2GB计数字节上限；先完成全覆盖再判断。
主报重点100–1000GeV、100–250/250–1000、>=1TeV参考及原E/y/z/component/proxy，风险/bias/R68/两尾，500次component分层来源配对。
额外只诊断IFT有/无有效段、任一station有>=2有效段；这些层在新残差前固定，非筛选。
重点相对F6改善>=2%且来源95%下限>0为实用门槛，会聚相对shuffle下限>0另作关系证据，同时报告角度->会聚增量。
来源区间条件于固定模型/offset，未含校准/重训/研究选择/系统。角度missing可含occupancy信息，不能把合并表示增益全部归纯角度。
阴性不证明真实输运后角/靶区深度无信息；只关闭当前局部表示，不追加网络/半径/容量。无新oracle/概率映射/谱/toys。
本轮不测data/interaction/响应系统或独立生产；不让更好风险替代实际谱收益。中文报告先写再提交并更新路线。
''')
print(json.dumps(dict(events=len(x),sources=len(indices),batches=len(cfg['extraction_batches']),angle_features=len(a),convergence_features=len(c),frozen_utc=cfg['frozen_utc'])))
