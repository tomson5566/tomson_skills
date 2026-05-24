#!/usr/bin/env python3
"""
Tag Extractor - AI 自动标签提取器
从文件内容中自动提取10个标签

使用方式：
  python3 scripts/tag_extractor.py <file_path>
  或
  python3 scripts/tag_extractor.py --content "content text"
"""

import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# 停用词列表
STOPWORDS = {
    '的', '了', '是', '在', '和', '有', '就', '不', '人', '都', '一', '一个',
    '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看',
    '好', '自己', '这', '那', '什么', '能', '对', '与', '或', '及', '等'
}

# 常用项目标识符
PROJECT_PATTERNS = [
    r'\d+\.\d+\.\d+\.\d+',  # IP 地址
    r'192\.168\.\d+\.\d+',
    r'10\.\d+\.\d+\.\d+',
    r'[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z]+',  # 域名
]

# 动作词
ACTION_WORDS = {
    '安装', '配置', '部署', '排查', '修复', '测试', '优化', '更新', '迁移',
    '检查', '启动', '停止', '重启', '创建', '删除', '备份', '恢复', '同步'
}

# 状态词
STATUS_WORDS = {
    '成功', '失败', '待处理', '进行中', '已完成', '已取消', '错误', '正常'
}

# 优先级
PRIORITY_WORDS = {'P0', 'P1', 'P2', 'P3', '高', '中', '低'}

def extract_time_tags(content, file_mtime):
    """提取时间标签"""
    # 使用文件修改时间
    return datetime.fromtimestamp(file_mtime).strftime("%Y-%m-%d")

def extract_topic_tags(content):
    """提取主题标签"""
    lines = content.strip().split('\n')
    
    topic_a = "未分类"
    topic_b = "未分类"
    
    # 尝试从第一行提取主主题
    if lines:
        first_line = lines[0].strip()
        if first_line:
            # 去除常见前缀
            first_line = re.sub(r'^#+\s*', '', first_line)
            if first_line:
                topic_a = first_line[:20]  # 取前20个字符
    
    # 尝试从包含 : 的行提取次主题
    for line in lines[1:]:
        if ':' in line:
            parts = line.split(':', 1)
            if len(parts) > 1 and parts[1].strip():
                topic_b = parts[1].strip()[:20]
                break
    
    return topic_a, topic_b

def extract_keyword_tags(content, top_n=3):
    """提取关键词标签"""
    # 移除 Markdown 语法
    text = re.sub(r'[#*`\[\]()]', ' ', content)
    # 提取词
    words = re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]+', text)
    
    # 过滤停用词
    filtered = [w for w in words if w not in STOPWORDS and len(w) > 1]
    
    # 统计频率
    counter = Counter(filtered)
    top_words = [w for w, _ in counter.most_common(top_n * 3)][:top_n * 3]
    
    return top_words[:3] if len(top_words) >= 3 else top_words + ["未分类"] * (3 - len(top_words))

def extract_project_tag(content):
    """提取项目标签"""
    for pattern in PROJECT_PATTERNS:
        matches = re.findall(pattern, content)
        if matches:
            return matches[0]
    return "通用"

def extract_action_tag(content):
    """提取动作标签"""
    for word in ACTION_WORDS:
        if word in content:
            return word
    return "其他"

def extract_status_tag(content):
    """提取状态标签"""
    for word in STATUS_WORDS:
        if word in content:
            return word
    return "待确定"

def extract_priority_tag(content):
    """提取优先级标签"""
    for word in PRIORITY_WORDS:
        if word in content:
            return word
    return "P1"

def extract_all_tags(file_path, content=None):
    """提取所有10个标签"""
    if content is None:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    
    file_stat = Path(file_path)
    file_mtime = file_stat.stat().st_mtime
    
    topic_a, topic_b = extract_topic_tags(content)
    keywords = extract_keyword_tags(content)
    project = extract_project_tag(content)
    action = extract_action_tag(content)
    status = extract_status_tag(content)
    priority = extract_priority_tag(content)
    
    return {
        "tag1_time": extract_time_tags(content, file_mtime),
        "tag2_topicA": topic_a,
        "tag3_topicB": topic_b,
        "tag4_keywordA": keywords[0] if len(keywords) > 0 else "未分类",
        "tag5_keywordB": keywords[1] if len(keywords) > 1 else "未分类",
        "tag6_keywordC": keywords[2] if len(keywords) > 2 else "未分类",
        "tag7_project": project,
        "tag8_action": action,
        "tag9_status": status,
        "tag10_priority": priority
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 tag_extractor.py <file_path> [--content 'text']")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    if sys.argv[1] == "--content" and len(sys.argv) >= 3:
        content = sys.argv[2]
        tags = extract_all_tags(__file__, content)
    else:
        tags = extract_all_tags(file_path)
    
    print("提取的标签：")
    for key, value in tags.items():
        print(f"  {key}: {value}")