import os
import sys
import json
import argparse
import hashlib
import subprocess
import logging
import traceback
from openai import OpenAI

class AITestSystem:
    def __init__(self, model_name="qwen-plus"):
        self._setup_logging()
        
        self.api_key = os.environ.get("DASHSCOPE_API_KEY")
        if not self.api_key:
            self.logger.critical("Missing DASHSCOPE_API_KEY environment variable. Exiting.")
            sys.exit(1)
            
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.model_name = model_name

    def _setup_logging(self):
        self.logger = logging.getLogger("AITestSystem")
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

    def _get_generation_prompt(self):
        return """你是一个资深的 Python 自动化测试开发工程师。
请根据用户提供的 API 接口文档，生成基于 pytest 和 requests 的自动化测试脚本。

【严格要求】
1. 必须且只能输出严格的 JSON 格式数据。绝对不要输出解释性废话，不要包含 markdown 标记。
2. 必须发起真实的物理网络请求！请直接使用 requests 库调用目标 URL。严禁使用 mock 库。
3. 【测试深度要求】用例必须全面！不仅要包含“正向主流程（Happy Path）”，必须还要包含“异常负面测试（Negative Testing）”，如：非法 Token/无权限、必填参数缺失、查询不存在的 ID (404) 等。
4. 【代码规范要求】
   - 必须使用 @pytest.mark.parametrize 来实现异常场景的数据驱动测试，避免写大量重复的测试函数。
   - 强烈建议使用 pytest.fixture(autouse=False) 或 yield 机制来管理测试数据的 Setup（创建）和 Teardown（清理删除），确保“测过无痕”且用例相互独立。
5. JSON 数据格式强制如下：
{
  "cases": [
    {
      "name": "测试用例名称",
      "code": "完整可运行的 pytest 代码字符串（包含 pytest, requests 等必要 import）"
    }
  ]
}"""

    def _get_ai_eval_prompt(self):
        return """你是一个资深的 AI 测试系统裁判（LLM Judge）。
请评估以下由 AI 生成的自动化测试用例集合，依据测试完整性、异常覆盖、断言合理性进行打分。
【极度严格的格式要求】
1. 你的返回结果将被机器直接执行 json.loads()。因此，你必须且只能输出纯文本的 JSON 字符串。
2. 绝对不要在开头或结尾包含任何 Markdown 标记（不要写 ```json，也不要写 ```）。
3. 绝对不要附带任何解释性废话。
4. 格式强制如下：
{
  "ai_evaluation": {
    "score": 8,
    "reason": "评价理由（200字以内）"
  }
}
5. score 是 1-10 的整数。"""

    def _get_fix_prompt(self):
        return """你是一个资深的 Python 测试修复工程师。
以下是你之前生成的测试代码，但在执行时发生了错误。
请根据给出的执行错误日志，修复代码，并严格按照原始要求的 JSON 格式返回完整的 cases 列表。
【严格要求】
1. 只能输出严格的 JSON 格式，绝不包含 markdown 标记或解释文字。
2. 修复代码中的语法错误、断言错误或缺少依赖的问题，必须保留完整的 Mock 逻辑。
3. 格式：{"cases": [{"name": "...", "code": "..."}]}"""

    def _clean_json_string(self, text):
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    def call_model(self, system_prompt, user_content):
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.logger.error(f"Model call failed: {e}")
            return None

    def parse_result(self, raw_text):
        if not raw_text:
            return False, {"error": "Empty response"}
        cleaned_text = self._clean_json_string(raw_text)
        try:
            parsed_data = json.loads(cleaned_text)
            if "cases" not in parsed_data and "ai_evaluation" not in parsed_data:
                return False, {"error": "Missing expected key in JSON", "raw_text": cleaned_text}
            return True, parsed_data
        except json.JSONDecodeError as e:
            return False, {"error": f"JSON parse failed: {str(e)}", "raw_text": cleaned_text}

    def rule_evaluate(self, parsed_json):
        eval_results = []
        overall_passed = True
        
        cases = parsed_json.get("cases", [])
        if not cases:
            return {"overall_passed": False, "case_details": [{"error": "No cases generated"}]}
            
        for case in cases:
            code = case.get("code", "")
            name = case.get("name", "Unknown Case")
            code_lower = code.lower()
            name_lower = name.lower()
            
            has_negative = any(kw in name_lower or kw in code_lower for kw in ["invalid", "error", "fail", "404", "400", "异常", "非法", "不存在", "负数"])
            
            checks = {
                "has_pytest": "pytest" in code_lower,
                "has_requests": "requests" in code_lower,
                "has_assert": "assert " in code_lower,
                "has_status_code_check": "status_code" in code_lower,
                "has_json_check": "json()" in code_lower
            }
            
            # 【核心修改区：更智能的校验逻辑】
            # 如果是异常测试用例（has_negative 为 True），则不需要强制校验 json()
            if has_negative:
                # 只要满足基本框架和状态码断言即可
                is_case_passed = checks["has_pytest"] and checks["has_requests"] and checks["has_assert"] and checks["has_status_code_check"]
            else:
                # 如果是正常用例，所有条件都必须满足
                is_case_passed = all(checks.values())

            if not is_case_passed:
                overall_passed = False
    
            eval_results.append({
                "name": name,
                "passed": is_case_passed,
                "details": checks
            })
            
        return {
            "overall_passed": overall_passed,
            "case_details": eval_results
        }

    def ai_evaluate(self, parsed_json, rule_passed):
        cases_text = json.dumps(parsed_json, ensure_ascii=False)
        raw_eval = self.call_model(self._get_ai_eval_prompt(), f"生成的用例如下：\n{cases_text}")
        
        is_valid, parsed_eval = self.parse_result(raw_eval)
        if is_valid and "ai_evaluation" in parsed_eval:
            return parsed_eval["ai_evaluation"]
            
        self.logger.warning("AI evaluation failed, falling back to rule-based score.")
        fallback_score = 8 if rule_passed else 4
        return {"score": fallback_score, "reason": "Fallback generated score due to AI Eval parse failure."}

    def analyze_stability(self, iterations_data):
        successful_iters = [it for it in iterations_data if it["is_valid"]]
        successful_calls = len(successful_iters)
        
        if successful_calls == 0:
            return {
                "successful_calls": 0,
                "case_count_consistent": False,
                "case_names_consistent": False,
                "code_consistency": False,
                "differences": ["All iterations failed to produce valid JSON"]
            }

        case_counts = [len(it["parsed_data"].get("cases", [])) for it in successful_iters]
        count_consistent = len(set(case_counts)) == 1

        names_list = [{c.get("name") for c in it["parsed_data"].get("cases", [])} for it in successful_iters]
        names_consistent = all(names == names_list[0] for names in names_list)

        code_hashes = []
        lengths = []
        for it in successful_iters:
            concat_code = "".join([c.get("code", "") for c in it["parsed_data"].get("cases", [])])
            code_hashes.append(hashlib.md5(concat_code.encode()).hexdigest())
            lengths.append(len(concat_code))
            
        code_consistent = len(set(code_hashes)) == 1

        differences = []
        if not count_consistent:
            differences.append(f"Case counts vary: {case_counts}")
        if not names_consistent:
            differences.append("Case names vary across iterations")
        if not code_consistent:
            differences.append(f"Code implementations vary. Lengths: {lengths}, Hashes: {code_hashes}")

        return {
            "successful_calls": successful_calls,
            "case_count_consistent": count_consistent,
            "case_names_consistent": names_consistent,
            "code_consistency": code_consistent,
            "lengths_distribution": lengths,
            "differences": differences
        }

    def execute_pytest(self, code_string, filename="test_dynamic_auto.py"):
        self.logger.info(f"Preparing to execute dynamic test code in {filename}...")
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(code_string)
        except Exception as e:
            self.logger.error(f"Failed to write test file: {e}")
            return {"success": False, "error": str(e), "stdout": "", "stderr": str(e)}

        try:
            self.logger.info("Running pytest as subprocess (timeout 30s)...")
            result = subprocess.run(
                ["pytest", filename, "-v", "--disable-warnings", "--html=generated_tests/report.html", "--self-contained-html"],
                capture_output=True, 
                text=True,
                check=False,
                timeout=30
            )
            
            is_success = (result.returncode == 0)
            status_msg = "PASSED" if is_success else f"FAILED (code {result.returncode})"
            self.logger.info(f"Pytest execution {status_msg}")
            
            return {
                "success": is_success,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
            
        except subprocess.TimeoutExpired:
            self.logger.error("Pytest execution timed out.")
            return {"success": False, "error": "TimeoutExpired", "stdout": "", "stderr": "Execution exceeded 30 seconds."}
        except Exception as e:
            self.logger.error(f"Subprocess crashed: {e}")
            return {"success": False, "error": str(e), "stdout": "", "stderr": traceback.format_exc()}
        # 注意：这里已经删除了 finally: os.remove(filename) 的代码块

    def attempt_fix(self, original_code, execution_result):
        self.logger.info("Attempting AI self-healing...")
        error_info = execution_result.get("stderr", "") + "\n" + execution_result.get("stdout", "")
        prompt_context = f"【原始代码】\n{original_code}\n\n【执行错误输出】\n{error_info[-2000:]}"
        
        raw_text = self.call_model(self._get_fix_prompt(), prompt_context)
        is_valid, parsed = self.parse_result(raw_text)
        
        if is_valid:
            self.logger.info("Self-healing returned valid format.")
            return parsed
        else:
            self.logger.warning("Self-healing failed to return valid JSON.")
            return None

    def save_results(self, data, filename="result.json"):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.logger.info(f"Results successfully saved to {filename}")
        except Exception as e:
            self.logger.error(f"Failed to save results to {filename}: {e}")

    def run(self, api_doc, num_iterations=3):
        if not api_doc or len(api_doc.strip()) < 10:
            self.logger.error("API document is too short or invalid. Exiting pipeline.")
            return None

        # 新增：创建保存生成代码的目录
        output_dir = "generated_tests"
        os.makedirs(output_dir, exist_ok=True)
        self.logger.info(f"Created directory for generated tests: {output_dir}")

        self.logger.info(f"Starting AI Test System Pipeline (Iterations: {num_iterations})")
        
        report = {
            "input_api_doc": api_doc,
            "iterations": [],
            "stability_analysis": {},
            "best_iteration_idx": None,
            "best_evaluation": None,
            "best_ai_evaluation": None,
            "execution_result": None,
            "self_healing_attempted": False
        }

        best_score = -1
        best_idx = -1
        
        for i in range(1, num_iterations + 1):
            self.logger.info(f"[Iteration {i}] Generating test cases...")
            raw_text = self.call_model(self._get_generation_prompt(), f"接口文档：\n{api_doc}")
            
            iter_data = {
                "iteration": i,
                "is_valid": False,
                "parsed_data": None,
                "evaluation": None,
                "ai_evaluation": None,
                "error": None
            }
            
            is_valid, parsed = self.parse_result(raw_text)
            if is_valid:
                iter_data["is_valid"] = True
                iter_data["parsed_data"] = parsed
                
                # 新增：将这一轮生成的代码写入本地文件
                iter_filename = os.path.join(output_dir, f"test_iter_{i}.py")
                try:
                    combined_iter_code = "\n\n".join([case.get("code", "") for case in parsed.get("cases", [])])
                    with open(iter_filename, 'w', encoding='utf-8') as f:
                        f.write(combined_iter_code)
                    self.logger.info(f"[Iteration {i}] Code saved to {iter_filename}")
                except Exception as e:
                    self.logger.error(f"Failed to save iteration code: {e}")

                rule_eval = self.rule_evaluate(parsed)
                iter_data["evaluation"] = rule_eval
                
                ai_eval = self.ai_evaluate(parsed, rule_eval['overall_passed'])
                iter_data["ai_evaluation"] = ai_eval
                
                current_score = ai_eval.get("score", 0)
                self.logger.info(f"[Iteration {i}] Rule Passed: {rule_eval['overall_passed']}, AI Score: {current_score}")
                
                if current_score > best_score:
                    best_score = current_score
                    best_idx = i - 1
            else:
                iter_data["error"] = parsed.get("error")
                self.logger.warning(f"[Iteration {i}] Parse failed: {iter_data['error']}")
                
            report["iterations"].append(iter_data)

        self.logger.info("Analyzing stability...")
        stability = self.analyze_stability(report["iterations"])
        report["stability_analysis"] = stability
        
        if best_idx >= 0:
            report["best_iteration_idx"] = best_idx
            best_iter = report["iterations"][best_idx]
            report["best_evaluation"] = best_iter["evaluation"]
            report["best_ai_evaluation"] = best_iter["ai_evaluation"]
            
            if best_iter["evaluation"]["overall_passed"]:
                combined_code = "\n\n".join([case["code"] for case in best_iter["parsed_data"]["cases"]])
                
                # 修改：执行最好的一版代码时，存为特定文件放入指定目录
                best_filename = os.path.join(output_dir, "test_best_execution.py")
                exec_res = self.execute_pytest(combined_code, filename=best_filename)
                
                if not exec_res["success"]:
                    self.logger.warning("Initial execution failed. Triggering self-healing loop...")
                    report["self_healing_attempted"] = True
                    fixed_data = self.attempt_fix(combined_code, exec_res)
                    
                    if fixed_data:
                        fixed_code = "\n\n".join([case["code"] for case in fixed_data.get("cases", [])])
                        self.logger.info("Executing healed code...")
                        
                        # 修改：执行修复后的代码时，也放入指定目录
                        fixed_filename = os.path.join(output_dir, "test_dynamic_auto_fixed.py")
                        exec_res = self.execute_pytest(fixed_code, filename=fixed_filename)
                        report["fixed_execution_result"] = exec_res
                
                report["execution_result"] = exec_res
            else:
                self.logger.warning("Best code did not pass basic rules. Skipping execution.")
        else:
            self.logger.error("No valid iterations generated. Execution skipped.")

        self.save_results(report)
        return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Engineering-grade AI Test System")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--doc", type=str, help="API Document String")
    group.add_argument("--file", type=str, help="File path to API Document")
    
    args = parser.parse_args()
    
    api_content = ""
    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                api_content = f.read()
        except Exception as e:
            logging.critical(f"Failed to read file: {e}")
            sys.exit(1)
    else:
        api_content = args.doc

    system = AITestSystem()
    system.run(api_content, num_iterations=3)
