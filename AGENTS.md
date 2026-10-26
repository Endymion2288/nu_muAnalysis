# Repository Guidelines

## Project Structure & Module Organization

The analysis implementation is under `AnalysisZipFramework/`: C++ sources are in
`source/`, public headers and ROOT helper functions in `include/`, and runtime YAML
configuration in `config/`. `analysis.cxx` is the executable entry point. The Python
utility in `scripts/` generates file configuration, while `submission/` contains
HTCondor descriptors and launch scripts. Top-level `run_MC_truth.sh` and
`run_MC_asimov.sh` are batch-style examples for producing and merging MC outputs.

## Build, Test, and Development Commands

Set up the CERN software stack before configuring or running:

```bash
source AnalysisZipFramework/setup.sh
mkdir -p build && cd build
cmake ../AnalysisZipFramework
make -j$(nproc)
./analysis --input-dir /path/to/ntuples -o test.root --isMC
```

`cmake` copies YAML files into `build/config`; rerun it after changing configuration,
or pass an explicit `--*-config` path. For a configured run, use
`./analysis -r <run> -o <output.root>`. There is no dedicated automated test suite;
use a small representative ROOT input and inspect the output trees and cutflow after
building.

## Coding Style & Naming Conventions

Follow the existing C++ style: four-space indentation, descriptive `PascalCase`
types/functions where established, and `camelCase` locals. Keep declarations in
`include/` and implementations in `source/`; compile as C++17. Use `Analysis::Define`,
`Redefine`, and `Alias` for new columns so configuration data types and definition
logging remain consistent. YAML keys and column names should follow existing names
(for example, `LeadTrack_pz0` and `VetoNu_total_reduced_charge`).

## Configuration and Data Handling

Cuts, histograms, derived columns, output columns, file paths, and GRLs are controlled
by the corresponding files in `AnalysisZipFramework/config/`. Quote YAML expressions,
especially expressions beginning with `!`. Do not commit data or generated ROOT files;
repository ignores already cover `build/`, `*.root`, logs, and credentials.

## Commit & Pull Request Guidelines

Use short, imperative commit subjects that describe one change (for example, “add
option to directly run over a folder”). Pull requests should explain the analysis or
configuration impact, list validation commands and representative inputs, and call out
any changed run lists, paths, or batch resources. Include output or plots when they
make physics or configuration changes easier to review.

## 工作环境与作业提交

当前工作节点为 `lxplus-gpu`，终端可使用 GPU；交互式调试和小规模验证可利用
GPU，但大批量数据必须通过 HTCondor 提交。CVMFS 已提供所需软件包，Calypso 等
工具通常已经编译好；优先使用与实际配置匹配的现成构建，只有源码变化时才重新
构建。真实 data 和 MC 位于 `/eos/experiment/faser`。

## 阶段记录与提交

每个阶段完成后必须先在仓库根目录 `workbook/` 写中文 Markdown 阶段报告，再将
报告和相关代码或配置一起提交。推荐文件名为
`YYYY-MM-DD_stageNN_topic.md`，至少包含：阶段目标、工作内容、详细数据、阶段性
结论和下一步计划。详细数据必须记录实际测得的数值和单位、输入与配置、执行命令、
验证结果及产物路径；适用时引用数据表和图表。未测量的项目明确标注“未测量”，不
得用推测替代结果。下一步计划要列出具体任务、所需输入和验收标准。每个阶段都要
有一次 Git commit，提交信息遵循 Angular Conventional Commits，例如
`feat(config): add 2024 calo definitions`、`fix(io): reduce snapshot columns`。

## 性能、存储与验证

代码和 HTCondor 脚本都必须考虑多线程、I/O 和文件读写优化，并用实际计时、资源
使用量或事件吞吐量验证改动；提交作业前先用小样本测试。EOS 空间有限，只保留尽量
小的最终结果，避免保存 xAOD 等中间文件，并合并或去重批量作业产生的 JSON 等重复
输出。除非确有必要，避免 SHA 校验和大段防御性编程，以免增加不必要的 I/O 或运行
开销。

## 物理结论与研究方法

每一步都应推动一个有数据证据支持的明确物理结论，同时检查物理原因和程序原因；
不能因少数离群事件就停止某条分析分支，也不能把未知原因当作结论。报告中说明样本、
选择、系统效应和统计依据。需要新思路时保持发散性思维，主动检索网络论文，兼顾
高能物理、计算机科学和机器学习方法，并记录引用及其对当前分析的可行性判断。
