import subprocess
import json
from typing import List, Dict

def run_ui_tars_agent(instruction: str) -> List[Dict]:
    """
    调用UI-TARS Agent执行自然语言指令
    :param instruction: 自然语言指令，比如"打开Chrome浏览器，搜索扩散模型"
    :return: 执行过程的所有步骤数据
    """
    # Node bridge 工作目录（你的二次开发仓库内）
    project_root = r"请写你存放bridge-node的路径"
    
    # 调用Node.js脚本
    result = subprocess.run(
        ["node", "run_agent_task.js", instruction],
        cwd=project_root,
        capture_output=True,
        text=True,
        encoding="utf-8"
    )

    # 解析返回结果
    output_lines = result.stdout.strip().split("\n")
    exec_result = []
    for line in output_lines:
        if not line:
            continue
        try:
            exec_result.append(json.loads(line))
        except:
            # 忽略非JSON格式的日志
            pass

    if result.returncode != 0:
        raise Exception(f"执行失败: {result.stderr}")
    
    return exec_result

# ================== 调用示例 ==================
if __name__ == "__main__":
    # 你的指令
    instruction = "请输入一个测试指令"
    print(f"开始执行指令: {instruction}")
    
    try:
        steps = run_ui_tars_agent(instruction)
        print("\n执行过程:")
        for step in steps:
            if step["type"] == "step":
                status = step["data"].get("status", "")
                if status == "RUNNING":
                    print(f"[RUNNING] {step['data'].get('conversations', [{}])[-1].get('value', '')}")
            elif step["type"] == "finish":
                print(f"[DONE] {step['message']}")
            elif step["type"] == "error":
                print(f"[ERROR] {step['message']}")
    except Exception as e:
        print(f"[ERROR] 调用失败: {str(e)}")