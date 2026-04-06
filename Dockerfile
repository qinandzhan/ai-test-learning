# 1. 选定基础集装箱：我们选一个轻量级的官方 Python 3 镜像
FROM docker.1ms.run/library/python:3.11-slim
# 2. 在集装箱里划出一块工作区，命名为 /app
WORKDIR /app

# 3. 把本地的“采购清单”放进集装箱，并让它自动安装 openai 库
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. 把你写好的 AI 脚本也放进集装箱
COPY test_llm.py .

# 5. 设定集装箱启动时的默认动作：运行你的 AI 脚本
CMD ["python", "test_llm.py"]
