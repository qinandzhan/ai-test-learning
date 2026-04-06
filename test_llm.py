import os
import sys
import argparse
from openai import OpenAI

class AITestCaseGenerator:
    """AI 测试用例生成器核心类"""
    
    def __init__(self, model_name="qwen-plus"):
        # 初始化时，自动完成身份验证和配置
        self.api_key = os.environ.get("DASHSCOPE_API_KEY")
        if not self.api_key:
            print("❌ 致命错误：找不到 API Key！请在运行 Docker 时通过 -e 参数传入。")
            sys.exit(1)
            
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.model_name = model_name

    def generate_cases(self, feature_name, count=3):
        """核心业务方法：根据传入的功能名称生成测试用例"""
        print(f"🚀 正在请教 AI，为您生成【{feature_name}】的 {count} 个测试思路...\n")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "你是一个资深的软件测试架构师。请直接输出精简的测试用例，不要废话。"},
                    {"role": "user", "content": f"请为【{feature_name}】设计{count}个核心的异常测试用例。"}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"❌ 运行报错：{e}"

# 程序的入口点
if __name__ == "__main__":
    # 引入 argparse 库，让我们的脚本能够接收终端传来的动态参数
    parser = argparse.ArgumentParser(description="AI 自动化测试用例工具")
    parser.add_argument("feature", type=str, nargs="?", default="微信朋友圈点赞功能", help="需要测试的功能名称")
    args = parser.parse_args()

    # 1. 实例化我们的生成器对象
    generator = AITestCaseGenerator()
    
    # 2. 调用对象的方法，并传入终端捕获的功能名称
    result = generator.generate_cases(feature_name=args.feature)
    
    # 3. 打印结果
    print("🤖 AI 架构师输出的用例：")
    print(result)
