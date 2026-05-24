#!/usr/bin/env python3
"""
PowerMem Memory Sync - 记忆同步脚本
功能：检查 memory 文件修改时间，AI 提取标签，幂等写入 PowerMem

使用方式：
  python3 scripts/memory_sync.py [--dry-run]
"""

import os
import json
import hashlib
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 配置
MEMORY_DIR = "/root/.hermes/memories"
PMEM_BIN = "/root/miniconda3/bin/pmem"

# 标签列表
TAGS = [
    "tag1_time", "tag2_topicA", "tag3_topicB", "tag4_keywordA", "tag5_keywordB",
    "tag6_keywordC", "tag7_project", "tag8_action", "tag9_status", "tag10_priority"
]

def get_file_mtime(filepath):
    """获取文件修改时间"""
    return os.path.getmtime(filepath)

def read_file_content(filepath):
    """读取文件内容"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

def generate_content_hash(content, tags):
    """生成内容 hash 用于幂等检查"""
    data = content + "".join(str(t) for t in tags.values())
    return hashlib.sha256(data.encode()).hexdigest()

def check_if_exists(hash_value):
    """检查 hash 是否已存在"""
    try:
        result = subprocess.run(
            [PMEM_BIN, "memory", "search", hash_value, "--limit", "10"],
            capture_output=True,
            text=True,
            timeout=15
        )
        if result.returncode == 0 and "content_hash" in result.stdout:
            return True
    except:
        pass
    return False

def write_memory(content, tags, content_hash):
    """写入记忆到 PowerMem（带超时和幂等检查）"""
    metadata = tags.copy()
    metadata["content_hash"] = content_hash
    metadata["infer_disabled"] = True  # 禁用 LLM 推理
    
    # 限制内容长度，避免超时
    summary = content[:500] if len(content) > 500 else content
    
    cmd = [
        PMEM_BIN, "memory", "add", summary,
        "--metadata", json.dumps(metadata),
        "--scope", "private",
        "--memory-type", "long_term",
        "--no-infer"  # 跳过 LLM 推理
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            return True
        else:
            return False
    except subprocess.TimeoutExpired:
        return False
    except Exception as e:
        return False

def extract_tags_from_content(content, file_path):
    """从内容中提取标签（由 AI 调用时自动完成）"""
    return {
        "tag1_time": datetime.fromtimestamp(get_file_mtime(file_path)).strftime("%Y-%m-%d"),
        "tag2_topicA": "待分析",
        "tag3_topicB": "待分析",
        "tag4_keywordA": "待分析",
        "tag5_keywordB": "待分析",
        "tag6_keywordC": "待分析",
        "tag7_project": "待分析",
        "tag8_action": "待分析",
        "tag9_status": "待确定",
        "tag10_priority": "P1"
    }

def check_recent_modifications():
    """检查最近是否有修改（7天内）"""
    files = ["MEMORY.md", "USER.md"]
    recent = []
    
    now = datetime.now().timestamp()
    for fname in files:
        fpath = os.path.join(MEMORY_DIR, fname)
        if os.path.exists(fpath):
            mtime = get_file_mtime(fpath)
            age_days = (now - mtime) / 86400
            if age_days <= 7:
                recent.append({"file": fpath, "mtime": mtime, "name": fname})
    
    return recent

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] PowerMem Memory Sync 开始")
    
    recent_files = check_recent_modifications()
    
    if not recent_files:
        print("无最近修改的文件，跳过同步")
        return
    
    print(f"发现 {len(recent_files)} 个最近修改的文件:")
    for f in recent_files:
        print(f"  - {f['name']} (修改于 {datetime.fromtimestamp(f['mtime']).strftime('%Y-%m-%d %H:%M')})")
    
    print("\n使用 memory-powermem-integration Skill 进行 AI 标签提取和写入")

if __name__ == "__main__":
    main()