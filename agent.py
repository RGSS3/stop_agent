#!/usr/bin/env python3
import os
import sys
import re
import subprocess
import openai
from openai import OpenAI

# -----------------------------------------------------------------------------
# 1. 环境变量 & OpenRouter 配置
# -----------------------------------------------------------------------------
# 请事先在环境变量中设置 OPENAI_API_KEY（或你在 OpenRouter 控制台拿到的 key）。
# 如果要使用 OpenRouter 服务，需要指定 api_base：
#   export OPENAI_API_KEY="YOUR_OPENROUTER_KEY"
#   export OPENAI_API_BASE="https://openrouter.ai/api/v1"
#
# 脚本会读取这两个环境变量：

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://openrouter.ai/api/v1")
# 以下几个常见的
# OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "http://localhost:5001/v1/")
# OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.x.ai/v1")
# OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://generativelanguage.googleapis.com/v1beta/openai/")
if not OPENAI_API_KEY:
    print("Error: 环境变量 OPENAI_API_KEY 未设置！")
    sys.exit(1)



# 指定你想用的模型名字（OpenRouter 上可用的模型，要和你账号能调用的模型对应）
# MODEL_NAME = "grok-3-mini-beta"  # 根据实际情况改成可用的模型
# MODEL_NAME = "codegeex 9b"  # 根据实际情况改成可用的模型
MODEL_NAME = "gemini-2.5-flash-preview-04-17"
client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASE)

# -----------------------------------------------------------------------------
# 2. 定义 stop tokens
# -----------------------------------------------------------------------------
STOP_TOKENS = ["<!--WRITE", "<!--RUN", "<!--DONE"]

# -----------------------------------------------------------------------------
# 3. 从命令行或 stdin 获取初始 prompt
# -----------------------------------------------------------------------------
if len(sys.argv) < 2:
    print("用法：\n  python3 script.py \"写一个 Fibonacci 函数的 Python 代码\"\n  或者\n  echo \"写一个 Fibonacci 函数的 Python 代码\" | python3 script.py -")
    sys.exit(1)

if sys.argv[1] == "-":
    # 从标准输入读取整个 prompt
    sys.stdin.reconfigure(encoding='utf-8')
    initial_prompt = sys.stdin.read().strip()
else:
    initial_prompt = sys.argv[1]

# -----------------------------------------------------------------------------
# 4. 帮助函数：用正则提取最后一个 ```python ... ``` 代码块
# -----------------------------------------------------------------------------
def extract_last_python_block(text: str) -> str:
    """
    找到 text 中最后一个 ```python ... ``` 之间的内容，并去掉三引号和首尾空行。
    如果没有找到，返回空字符串。
    """
    pattern = r"```python\s*([\s\S]*?)```"
    matches = re.findall(pattern, text, flags=re.IGNORECASE)
    if not matches:
        return ""
    code = matches[-1]
    # strip 掉开头结尾的多余空行
    return code.strip()

# -----------------------------------------------------------------------------
# 5. 向 LLM 发送一次请求，流式读取并检测 stop token
# -----------------------------------------------------------------------------
def ask_llm_once(history_messages):
    """
    使用新版 client.chat.completions.create(..., stream=True, stop=STOP_TOKENS) 来流式读取。
    返回 (content_without_stop, triggered_token)：
      - content_without_stop: 模型生成的文本（不含 stop token）
      - triggered_token: 触发的 stop token（例如 "<!--WRITE-->"、"<!--RUN-->"、"<!--DONE-->"），
        如果没有检测到，默认为 "<!--DONE-->"。
    """
    response_content = ""
    triggered = None
    try:
        # 调用新版 API，注意参数名和旧版略有不同
        stream_iter = client.chat.completions.create(
            model=MODEL_NAME,
            messages=history_messages,
            stream=True,
            stop=["-->"],
        )
    except Exception as e:
        print(f"[Error] 调用 OpenAI API 出错：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print(MODEL_NAME + "> ", end="", flush=True)
    # 新版 client.chat.completions.create(..., stream=True) 返回一个 iterator
    for chunk in stream_iter:
        # chunk 结构示例：
        # {
        #   "id": "...", "object": "chat.completion.chunk", "created": 123456,
        #   "choices": [
        #       {
        #           "delta": {"content": "部分文本或者空"},
        #           "index": 0,
        #           "finish_reason": None 或 "stop"
        #       }
        #   ]
        # }
        delta = dict(chunk.choices[0].delta)
        if 'reasoning_content' in delta:
            key = 'reasoning_content'
        else:
            key = 'content'
        response_content += delta[key] or ''
        print(delta[key] or '', end="", flush=True)
        finish_reason = chunk.choices[0].finish_reason
        if finish_reason == "stop":
            # 当 finish_reason == "stop" 时，表示某个 stop token 生效了。
            # 但 OpenAI 并不会直接告诉你是哪一个 token，所以这里在累积的 response_content 里检查。
            for tok in STOP_TOKENS:
                if response_content.endswith(tok):
                    triggered = tok
                    response_content = response_content + "-->"
                    break
            
    print()
    
    return response_content.strip(), triggered

# -----------------------------------------------------------------------------
# 6. 主循环：根据 stop token 做 write / run / done
# -----------------------------------------------------------------------------
def main_loop(initial_user_prompt):
    # conversation history
    history = [
        # 你可以在 system 中设定一些指令，比如：
        {
            "role": "system",
            "content": (
                "你是一个自动编程辅助机器人。在每一步，输出结尾都包含下面三个 stop token 之一，说明为:\n"
                "当你需要更新文件时，请输出一个python代码块以及不含引号的`<!--WRITE-->`；\n"
                "注意，没有这个WRITE指令我们将不会写文件，哪怕你输出了一个代码块；\n\n"
                "当你想让外部运行之前写好的python文件时，请输出 `<!--RUN-->`；\n\n"
                "当你完成整个任务以及验证结果正确时，请输出最终版本和 `<!--DONE-->`。\n\n"
                "尤其注意，RUN和DONE不会保存你输出的代码块，只有在 WRITE时才会保存。\n\n"
                "请不要在其他任何地方包含这些关键token比如思考中\n\n"
                "你需要反复运行和测试直到最终成功，无论如何，在你的回复之后都要输出上述的任何一个，你可以对代码进行解释等，这样用户可以回头看你的思考或者别的过程，只要维持代码块和stop token正确即可。\n"
                "这里我们是自动化操作，除了最初的用户要求，剩下的都是根据你输出的内容，自动执行，你输出的实际上是stop token前面的一部分。"
            ),
        },
        {"role": "user", "content": initial_user_prompt},
    ]

    while True:
        # 1) 让模型产生一段新的输出（直到遇到 stop token 为止）
        assistant_chunk, stop_tok = ask_llm_once(history)

        # 2) 把模型产出的这一段文字（不含 stop token）当作 assistant 的完整回复，加到 history
        history.append({"role": "assistant", "content": assistant_chunk})

        # 3) 根据触发的 stop token 决定后续操作
        if stop_tok == "<!--WRITE":
            # 提取最后一个 python 代码块
            code_str = extract_last_python_block(assistant_chunk)
            if not code_str:
                print("[Error] 在模型输出中，没有检测到任何 ```python ... ``` 代码块。")
                sys.exit(1)

            # 写入到 tmp.py
            with open("tmp.py", "w", encoding="utf-8") as f:
                f.write(code_str + "\n")
            print("[Info] 已把模型给出的 Python 代码块写入 tmp.py。")

            # 继续进入下一轮，不直接 ask_llm，只是在 history 里再添加一条提示（可选）
            # 这里我们可以把写入文件的确认，当作新的“用户”消息，喂回给模型，让它判断下一步如何继续
            history.append({"role": "user", "content": "[SYSTEM] 已写入 tmp.py，请继续下一步。注意，写入不会自动运行。"})

            continue  # 回到循环，模型会读取到新的 history 并继续生成

        elif stop_tok == "<!--RUN":
            # 执行 tmp.py
            print("[Info] 收到 <!--RUN-->，开始运行 tmp.py......")
            try:
                proc = subprocess.run(
                    ["python", "tmp.py"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=10,  # 防止无限卡住
                )
                stdout = proc.stdout
                stderr = proc.stderr
            except Exception as e:
                stdout = ""
                stderr = f"脚本执行时出现异常: {str(e)}"

            # 把运行结果拼好：stdout + stderr
            run_feedback = "[SYSTEM] tmp.py 运行结果：\n"
            run_feedback += "=== STDOUT ===\n" + (stdout or "<无标准输出>\n")
            run_feedback += "\n=== STDERR ===\n" + (stderr or "<无标准错误输出>\n")

            print(run_feedback)

            # 然后把这个结果当作新的用户消息，喂回给模型，让它决定下一步
            history.append({"role": "user", "content": run_feedback})

            continue  # 继续下一轮

        elif stop_tok == "<!--DONE":
            # 最终完成
            print("[Info] 收到 <!--DONE-->，任务结束。")
            print("===== 模型最终输出 =====")
            print(assistant_chunk)  # 把最后一段不含 stop token 的内容打印出来
            break

        else:
            # 如果没匹配到任何 stop token（比如模型自行结束），也当作 DONE 处理
            print("[Info] 模型未显式触发 stop token，默认结束。")
            print("===== 模型输出 =====")
            print(assistant_chunk)
            history.append({"role": "user", "content": "你似乎没有输入任何命令，继续"})
            continue


if __name__ == "__main__":
    main_loop(initial_prompt)
