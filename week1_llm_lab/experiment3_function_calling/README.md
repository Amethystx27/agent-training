# 实验3目录说明

## 目录分类

```text
src/                  Python 工具、Agent、调度器和运行脚本
src/tests/            自动化测试
results/              端到端测试结果
logs/basic/           六组基础测试的 JSONL 调用日志
docs/                 实验说明和实验总结
.venv/                本地 Python 虚拟环境
```

实验总结见 `docs/实验3总结.md`，目录和文件说明见
`docs/实验3说明指南.md`。

## 运行命令

所有命令都在 `experiment3_function_calling` 目录执行：

```powershell
.\.venv\Scripts\python.exe src\check_environment.py
.\.venv\Scripts\python.exe -m unittest discover -s src\tests -t src -v
.\.venv\Scripts\python.exe src\run_basic_tests.py
.\.venv\Scripts\python.exe src\agent.py "ICCBDA 2027 的截稿日期还有多久？"
```

配置从上一级目录的 `.env` 读取，不会被复制到本实验目录。
