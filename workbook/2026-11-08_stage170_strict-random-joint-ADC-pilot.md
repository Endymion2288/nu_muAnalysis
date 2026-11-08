# Stage170：严格随机触发联合ADC可用性pilot

## 阶段目标与冻结范围

承接Stage132§5.5真实联合响应及§6实际相关辅助约束，不重复Stage43四CaloNu离峰噪声实验。Stage169提交`7ca8b69`后冻结[协议](stage170_energy_ml/protocol.json)：固定已知run15838 RAW00400，同原56 PhysicsTag ADC reference先闭合，再检查同文件前8192个PhysicsTag内严格随机触发是否提供跨通道、同事件完整ADC。它是响应控制的可用性实验，不是ν能量模型或已校准联合噪声。

输入字面路径为`/eos/experiment/faser/raw/2024/015838/Faser-Physics-015838-00400.raw`，原`ntuples/energy_ml_stage43/data_noise.npz`中file_index=2的56事例；GRL来自Stage166已取得的官方v10摘要。仅读一个RAW固定前缀，不目录探测、不换文件、不复制RAW/xAOD。全部科学解析、ADC数组和统计走HTCondor；本地只冻结源码/协议、打包/调度与归档文档。

严格控制定义为PhysicsTag、唯一正确帧长且官方decoder有效的TLB、TAP==16且TBP==16。current/next input bits原样保留，不加零值要求；不按ADC电荷、status、track、GRL或尾部删事例，GRL只决定支持验收。保留最先8个严格控制及原前56 ADC的全部实际PMT硬件通道，其他事例只留触发/身份账目；最大16384 raw frames、开始下一frame前不超过128MiB。不得因少量异常停止整个物理分支。

## 程序、口径与验收

[薄reader](../ml/stage170_raw.cxx)直接用官方`DAQFormats::EventFull`、`TLBDataFormat::TLBDataFragment`和`DigitizerDataFragment`。官方TLB构造器在帧长检查前可能读checksum，故先按官方header常量与官方结构长度验证完整帧，再调用decoder；未知、缺失、多TLB与坏CRC保留为未知，不自写DAQ位解码。v1无checksum，v2/v3沿官方实现version=2语义，不将header版本与getter返回混淆。原Calypso pin d32不变，没有重建Calypso；仅编译新增薄reader。

[header来源](stage170_energy_ml/header_sources.json)记录17份静态header：EventFormats/Exceptions取原d32 runtime archive中的实际源码，Logging.hpp来自现有faser-common源commit1770d15df9311f6535c09909edf9ad64a5779e32；36892B精确header胶囊，不把外部common源版本虚称Calypso d32历史producer。硬件编号仅board×16+channel，不猜探测器物理标签。实际长度和board有效性实测后记录，不强填32通道或280采样。2ns、0.1220703125mV/ADC只沿Stage43四CaloNu参考，不自动认证全部通道量程/采样。

冻结1200累计CPU秒，smoke300/pilot600/audit300，2核/4000MB、max1job、MaxRuntime86400秒、无应用短timeout。smoke原56身份、board字段、四CaloNu ADC逐值相等且存在有效TLB后，以完整科学进程GNU CPU的三倍8192/56投影加已用成本/300audit reserve准入。compile另计GNU并进入调度总账，不混作事件steady吞吐。pilot至少4个严格控制、全部位于已取得GRL且两板/同硬件集/非空等长度支持，加独立重读通过，才称联合控制“可用”；幅度本身不作门。新联合协方差、增益、timewalk、纯电子noise、宽μ辐射尾和ν部署仍未测量。

## 执行命令

```bash
python3 ml/stage170_freeze.py
python3 ml/stage170_headers.py
python3 ml/stage170_ops.py submit --phase smoke
# 等待终态、collect后才按成本决定pilot
```

## 实测结果、成本门与程序原因

smoke job9676533.0成功终态，前56 PhysicsTag读470606B，时间1720473060859252–1720473060888811 μs（Unix），56个唯一有效TLB、0坏/歧义，严格TAP=TBP=16为0。status2有53例、status0有3例，均保留；56例中没有严格控制不说明全文件没有随机触发。原56身份/board全部字段与62720个CaloNu ADC code逐值相等，最大差0 ADC。详见[smoke摘要](stage170_energy_ml/smoke_summary.json)。本阶段没有读取8192前缀、没有测出严格控制通道/GRL/联合协方差。

[成本准入](stage170_energy_ml/admission.json)为False：完整科学进程GNU CPU4.39秒（user4.21/system0.18）、wall5.35秒；按原规则三倍8192/56投影1926.582857秒，加schedd已用8秒及300秒audit reserve，超过1200秒。reader子进程实CPU0.094516秒/wall3.711890秒；主Python CPU3.917679秒。编译另为CPU2.51秒/wall2.57秒。不得因reader较快忽略完整进程的实际成本，也不在看到成本后改原投影门。

静态检查发现`legacy()`在56次循环内重复访问压缩NPZ的`adc`/board数组，每次触发整数组解压；这个实现需要修正。重复解压单独耗时、去除后能否通过门**未测量**，不能把Python全部开销确定归给它。该程序开销不代表物理联合控制不可行。pilot/audit未提交，未扩大或更换RAW，不把未执行写作阴性物理结论。

[资源与精确归档](stage170_energy_ml/storage_cleanup.json)记录1提交/1start/exit0，schedd CPU8秒、聚合wall14秒、0live/GPU/G4/fit/forward；提交2核4000MB、schedd实际内存见同表。原56的全部硬件ADC与触发/身份保留为`ntuples/energy_ml_stage170/smoke_rows.jsonl.gz`，只留紧凑gzip，不留ROOT/xAOD/reader二进制。源码/原始GNU与日志按精确字节归档至`software/stage170/`，清理前核队列引用及Stage54原12文件size/mtime。实际最终字节和删除量以该表为准。

## 文献依据、结论与下一步

本轮联网核实[《The trigger and data acquisition system of the FASER experiment》arXiv:2110.15186](https://arxiv.org/abs/2110.15186)标题及摘要，描述FASER触发/DAQ与初始调试性能；它支持使用实际触发/原始读出控制的动机，不证明本run的随机纯度、位定义、曝光或误差。位语义按本地官方decoder与实际TLB验证，不用论文摘要替代数据校验。原Stage132 particle-flow与随机μ损失文献继续为联合响应动机，不照搬其他探测器分辨率。

本阶段只建立官方TLB可读和原ADC精确回放，原成本门阻止8192扫描。下一有界工程修正仍固定同RAW/原56/reference和严格选择，先将NPZ所需数组单次解压，原smoke全部字段及ADC精确重放，实际计量完整进程与compile，再按不增加1200秒预算的预冻结门决定是否8192及独立重读。不换样本、不放松选择、不按幅度删样本；新性能及随机联合控制仍未测量。Stage87、全部原门、pz0/raw11/typedNaN/合法signed/status0 timing/Calo缺失、pz>50GeV、全部K、角色/reserved/quarantine保持；整体目标未完成。
