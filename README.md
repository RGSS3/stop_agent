# stop_agent

一个自动化编程 Agent，基于 LLM（大语言模型）流式驱动，实现“提需求-写代码-自动运行-结果反馈”的完整闭环。适用于 OpenAI、OpenRouter 及兼容 API。

> **本项目采用 [GPLv3](LICENSE) 协议开源。**

---

## 特性

- **自动循环**：自动与大模型交互，代码生成、写入、运行、验证全流程自动化
- **流式输出**：LLM 回复实时逐步显示
- **高度兼容**：支持 OpenRouter、OpenAI 及其它兼容 API
- **自然语言驱动**：你只需描述需求，剩下交给 Agent 自动推进

---

## 环境要求

- Python 3.12（建议 3.8 及以上均可）
- openai Python SDK

---

## 安装依赖

```bash
pip install openai
```

---

## API Key 配置

请先在环境变量中设置你的 API Key，例如（以 OpenRouter 为例）：

```bash
export OPENAI_API_KEY="你的 OpenRouter Key"
export OPENAI_API_BASE="https://openrouter.ai/api/v1"
```

如需使用 OpenAI 官方接口，可不设置 `OPENAI_API_BASE` 或设置为官方地址。

---

## 使用方法

### 1. 命令行直接输入

```bash
python3 agent.py "写一个斐波那契数列的 Python 函数"
```

### 2. 标准输入输入

```bash
echo "写一个冒泡排序" | python3 agent.py -
```

---

## 工作流说明

1. **输入需求**：你用自然语言描述需求
2. **自动交互**：Agent 与 LLM 反复交互，分阶段产出
    - `<!--WRITE-->`：保存生成的代码到 `tmp.py`
    - `<!--RUN-->`：自动运行 `tmp.py`，将输出反馈给 LLM
    - `<!--DONE-->`：流程结束，输出最终代码和说明
3. **自动循环**：Agent 会根据 LLM 输出的 stop token 自动判断并推进后续步骤，直至完成

---

## 参数说明

- `OPENAI_API_KEY`：你的 OpenAI/OpenRouter API 密钥
- `OPENAI_API_BASE`：API 基础地址
- `MODEL_NAME`：在脚本内指定，需与你账号权限匹配

---

## 注意事项

- 本项目所有生成与执行代码均为自动化流程，**请注意安全风险**，避免处理敏感或危险操作。
- LLM 生成的代码未必完全安全/无错，请谨慎用于生产环境。

---

## 示例

```bash
python3 agent.py "写一个输出质数的 Python 程序"
```

流式输出、自动写入、运行与反馈。

---

## 许可证

本项目采用 [GNU GPL v3](LICENSE) 开源。

---

## 致谢

- 感谢 OpenAI、OpenRouter 等平台的 API 支持。
- 如果你有建议或遇到问题，欢迎提交 Issue！

---

如果你需要更详细的介绍或有其它自定义需求，欢迎补充说明！
