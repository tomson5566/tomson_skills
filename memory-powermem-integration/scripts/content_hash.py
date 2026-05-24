#!/usr/bin/env python3
"""
Content Hash Generator - 内容哈希生成器
用于幂等检查，避免重复写入相同的记忆

使用方式：
  python3 scripts/content_hash.py "content" '{"tag1":"val1",...}'
"""

import hashlib
import json
import sys

def generate_hash(content, metadata):
    """生成内容 hash"""
    # 将 metadata 中的标签值按顺序拼接
    tag_values = []
    for key in sorted(metadata.keys()):
        tag_values.append(str(metadata[key]))
    
    data = content + "".join(tag_values)
    return hashlib.sha256(data.encode()).hexdigest()

def verify_hash(content, metadata, expected_hash):
    """验证 hash 是否匹配"""
    actual = generate_hash(content, metadata)
    return actual == expected_hash

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 content_hash.py <content> <metadata_json>")
        sys.exit(1)
    
    content = sys.argv[1]
    metadata = json.loads(sys.argv[2])
    
    hash_value = generate_hash(content, metadata)
    print(f"Content Hash: {hash_value}")
    
    # 验证
    if len(sys.argv) >= 4:
        expected = sys.argv[3]
        if verify_hash(content, metadata, expected):
            print("✓ Hash 匹配")
        else:
            print("✗ Hash 不匹配")