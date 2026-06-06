# Semgrep代码安全扫描报告

## 扫描概览

- 扫描时间：2026/6/4 17:57:04
- 扫描路径：/home/tangzhiang/.copaw/workspaces/
- 总问题数：103
- 高危问题：0
- 严重问题：103
- 重要问题：0
- 次要问题：0
- 提示问题：0

## 问题详情

### 🟠 严重 问题（共103个）

1. **文件**：/home/tangzhiang/.copaw/workspaces/ai_firewall_agents/skills/docx/scripts/office/helpers/simplify_redlines.py，**行号**：131
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(doc_xml_path)

2. **文件**：/home/tangzhiang/.copaw/workspaces/ai_firewall_agents/skills/docx/scripts/office/helpers/simplify_redlines.py，**行号**：155
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(f)

3. **文件**：/home/tangzhiang/.copaw/workspaces/ai_firewall_agents/skills/docx/scripts/office/validators/redlining.py，**行号**：34
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

4. **文件**：/home/tangzhiang/.copaw/workspaces/ai_firewall_agents/skills/docx/scripts/office/validators/redlining.py，**行号**：79
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

5. **文件**：/home/tangzhiang/.copaw/workspaces/ai_firewall_agents/skills/docx/scripts/office/validators/redlining.py，**行号**：81
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(original_file)

6. **文件**：/home/tangzhiang/.copaw/workspaces/ai_firewall_agents/skills/github-readme-creater/github-readme-creator/references/secret-scan.md，**行号**：40
   **问题描述**：Something that looks like a PGP private key block is detected. This is a potential hardcoded secret that could be leaked if this code is committed. Instead, remove this code block from the commit.
   **规则ID**：[generic.secrets.security.detected-pgp-private-key-block.detected-pgp-private-key-block](https://semgrep.dev/r/generic.secrets.security.detected-pgp-private-key-block.detected-pgp-private-key-block)
   **修复方案**：无自动修复方案

7. **文件**：/home/tangzhiang/.copaw/workspaces/ai_firewall_agents/skills/pptx/scripts/office/helpers/simplify_redlines.py，**行号**：131
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(doc_xml_path)

8. **文件**：/home/tangzhiang/.copaw/workspaces/ai_firewall_agents/skills/pptx/scripts/office/helpers/simplify_redlines.py，**行号**：155
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(f)

9. **文件**：/home/tangzhiang/.copaw/workspaces/ai_firewall_agents/skills/pptx/scripts/office/validators/redlining.py，**行号**：34
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

10. **文件**：/home/tangzhiang/.copaw/workspaces/ai_firewall_agents/skills/pptx/scripts/office/validators/redlining.py，**行号**：79
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

11. **文件**：/home/tangzhiang/.copaw/workspaces/ai_firewall_agents/skills/pptx/scripts/office/validators/redlining.py，**行号**：81
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(original_file)

12. **文件**：/home/tangzhiang/.copaw/workspaces/ai_firewall_agents/skills/xlsx/scripts/office/helpers/simplify_redlines.py，**行号**：131
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(doc_xml_path)

13. **文件**：/home/tangzhiang/.copaw/workspaces/ai_firewall_agents/skills/xlsx/scripts/office/helpers/simplify_redlines.py，**行号**：155
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(f)

14. **文件**：/home/tangzhiang/.copaw/workspaces/ai_firewall_agents/skills/xlsx/scripts/office/validators/redlining.py，**行号**：34
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

15. **文件**：/home/tangzhiang/.copaw/workspaces/ai_firewall_agents/skills/xlsx/scripts/office/validators/redlining.py，**行号**：79
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

16. **文件**：/home/tangzhiang/.copaw/workspaces/ai_firewall_agents/skills/xlsx/scripts/office/validators/redlining.py，**行号**：81
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(original_file)

17. **文件**：/home/tangzhiang/.copaw/workspaces/ai_firewall_agents/tool_results/9c9a080e13e84ec3894be1c9f665083c.txt，**行号**：46
   **问题描述**：Something that looks like a PGP private key block is detected. This is a potential hardcoded secret that could be leaked if this code is committed. Instead, remove this code block from the commit.
   **规则ID**：[generic.secrets.security.detected-pgp-private-key-block.detected-pgp-private-key-block](https://semgrep.dev/r/generic.secrets.security.detected-pgp-private-key-block.detected-pgp-private-key-block)
   **修复方案**：无自动修复方案

18. **文件**：/home/tangzhiang/.copaw/workspaces/ai_firewall_agents/tool_results/9c9a080e13e84ec3894be1c9f665083c.txt，**行号**：1791
   **问题描述**：Something that looks like a PGP private key block is detected. This is a potential hardcoded secret that could be leaked if this code is committed. Instead, remove this code block from the commit.
   **规则ID**：[generic.secrets.security.detected-pgp-private-key-block.detected-pgp-private-key-block](https://semgrep.dev/r/generic.secrets.security.detected-pgp-private-key-block.detected-pgp-private-key-block)
   **修复方案**：无自动修复方案

19. **文件**：/home/tangzhiang/.copaw/workspaces/ai_firewall_agents/tool_results/9c9a080e13e84ec3894be1c9f665083c.txt，**行号**：2091
   **问题描述**：Something that looks like a PGP private key block is detected. This is a potential hardcoded secret that could be leaked if this code is committed. Instead, remove this code block from the commit.
   **规则ID**：[generic.secrets.security.detected-pgp-private-key-block.detected-pgp-private-key-block](https://semgrep.dev/r/generic.secrets.security.detected-pgp-private-key-block.detected-pgp-private-key-block)
   **修复方案**：无自动修复方案

20. **文件**：/home/tangzhiang/.copaw/workspaces/ai_firewall_agents/tool_results/9c9a080e13e84ec3894be1c9f665083c.txt，**行号**：2194
   **问题描述**：Something that looks like a PGP private key block is detected. This is a potential hardcoded secret that could be leaked if this code is committed. Instead, remove this code block from the commit.
   **规则ID**：[generic.secrets.security.detected-pgp-private-key-block.detected-pgp-private-key-block](https://semgrep.dev/r/generic.secrets.security.detected-pgp-private-key-block.detected-pgp-private-key-block)
   **修复方案**：无自动修复方案

21. **文件**：/home/tangzhiang/.copaw/workspaces/dataworks_fqd_agent/dialog/2026-05-28.jsonl，**行号**：30
   **问题描述**：JWT token detected
   **规则ID**：[generic.secrets.security.detected-jwt-token.detected-jwt-token](https://semgrep.dev/r/generic.secrets.security.detected-jwt-token.detected-jwt-token)
   **修复方案**：无自动修复方案

22. **文件**：/home/tangzhiang/.copaw/workspaces/dataworks_fqd_agent/dialog/2026-05-28.jsonl，**行号**：31
   **问题描述**：JWT token detected
   **规则ID**：[generic.secrets.security.detected-jwt-token.detected-jwt-token](https://semgrep.dev/r/generic.secrets.security.detected-jwt-token.detected-jwt-token)
   **修复方案**：无自动修复方案

23. **文件**：/home/tangzhiang/.copaw/workspaces/dataworks_fqd_agent/dialog/2026-05-28.jsonl，**行号**：31
   **问题描述**：JWT token detected
   **规则ID**：[generic.secrets.security.detected-jwt-token.detected-jwt-token](https://semgrep.dev/r/generic.secrets.security.detected-jwt-token.detected-jwt-token)
   **修复方案**：无自动修复方案

24. **文件**：/home/tangzhiang/.copaw/workspaces/dataworks_fqd_agent/dialog/2026-05-28.jsonl，**行号**：108
   **问题描述**：JWT token detected
   **规则ID**：[generic.secrets.security.detected-jwt-token.detected-jwt-token](https://semgrep.dev/r/generic.secrets.security.detected-jwt-token.detected-jwt-token)
   **修复方案**：无自动修复方案

25. **文件**：/home/tangzhiang/.copaw/workspaces/dataworks_fqd_agent/skills/docx/scripts/office/helpers/simplify_redlines.py，**行号**：131
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(doc_xml_path)

26. **文件**：/home/tangzhiang/.copaw/workspaces/dataworks_fqd_agent/skills/docx/scripts/office/helpers/simplify_redlines.py，**行号**：155
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(f)

27. **文件**：/home/tangzhiang/.copaw/workspaces/dataworks_fqd_agent/skills/docx/scripts/office/validators/redlining.py，**行号**：34
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

28. **文件**：/home/tangzhiang/.copaw/workspaces/dataworks_fqd_agent/skills/docx/scripts/office/validators/redlining.py，**行号**：79
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

29. **文件**：/home/tangzhiang/.copaw/workspaces/dataworks_fqd_agent/skills/docx/scripts/office/validators/redlining.py，**行号**：81
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(original_file)

30. **文件**：/home/tangzhiang/.copaw/workspaces/dataworks_fqd_agent/skills/github-readme-creater/github-readme-creator/references/secret-scan.md，**行号**：40
   **问题描述**：Something that looks like a PGP private key block is detected. This is a potential hardcoded secret that could be leaked if this code is committed. Instead, remove this code block from the commit.
   **规则ID**：[generic.secrets.security.detected-pgp-private-key-block.detected-pgp-private-key-block](https://semgrep.dev/r/generic.secrets.security.detected-pgp-private-key-block.detected-pgp-private-key-block)
   **修复方案**：无自动修复方案

31. **文件**：/home/tangzhiang/.copaw/workspaces/dataworks_fqd_agent/skills/pptx/scripts/office/helpers/simplify_redlines.py，**行号**：131
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(doc_xml_path)

32. **文件**：/home/tangzhiang/.copaw/workspaces/dataworks_fqd_agent/skills/pptx/scripts/office/helpers/simplify_redlines.py，**行号**：155
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(f)

33. **文件**：/home/tangzhiang/.copaw/workspaces/dataworks_fqd_agent/skills/pptx/scripts/office/validators/redlining.py，**行号**：34
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

34. **文件**：/home/tangzhiang/.copaw/workspaces/dataworks_fqd_agent/skills/pptx/scripts/office/validators/redlining.py，**行号**：79
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

35. **文件**：/home/tangzhiang/.copaw/workspaces/dataworks_fqd_agent/skills/pptx/scripts/office/validators/redlining.py，**行号**：81
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(original_file)

36. **文件**：/home/tangzhiang/.copaw/workspaces/dataworks_fqd_agent/skills/xlsx/scripts/office/helpers/simplify_redlines.py，**行号**：131
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(doc_xml_path)

37. **文件**：/home/tangzhiang/.copaw/workspaces/dataworks_fqd_agent/skills/xlsx/scripts/office/helpers/simplify_redlines.py，**行号**：155
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(f)

38. **文件**：/home/tangzhiang/.copaw/workspaces/dataworks_fqd_agent/skills/xlsx/scripts/office/validators/redlining.py，**行号**：34
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

39. **文件**：/home/tangzhiang/.copaw/workspaces/dataworks_fqd_agent/skills/xlsx/scripts/office/validators/redlining.py，**行号**：79
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

40. **文件**：/home/tangzhiang/.copaw/workspaces/dataworks_fqd_agent/skills/xlsx/scripts/office/validators/redlining.py，**行号**：81
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(original_file)

41. **文件**：/home/tangzhiang/.copaw/workspaces/default/active_skills/docx/scripts/office/helpers/simplify_redlines.py，**行号**：131
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(doc_xml_path)

42. **文件**：/home/tangzhiang/.copaw/workspaces/default/active_skills/docx/scripts/office/helpers/simplify_redlines.py，**行号**：155
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(f)

43. **文件**：/home/tangzhiang/.copaw/workspaces/default/active_skills/docx/scripts/office/validators/redlining.py，**行号**：34
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

44. **文件**：/home/tangzhiang/.copaw/workspaces/default/active_skills/docx/scripts/office/validators/redlining.py，**行号**：79
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

45. **文件**：/home/tangzhiang/.copaw/workspaces/default/active_skills/docx/scripts/office/validators/redlining.py，**行号**：81
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(original_file)

46. **文件**：/home/tangzhiang/.copaw/workspaces/default/active_skills/pptx/scripts/office/helpers/simplify_redlines.py，**行号**：131
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(doc_xml_path)

47. **文件**：/home/tangzhiang/.copaw/workspaces/default/active_skills/pptx/scripts/office/helpers/simplify_redlines.py，**行号**：155
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(f)

48. **文件**：/home/tangzhiang/.copaw/workspaces/default/active_skills/pptx/scripts/office/validators/redlining.py，**行号**：34
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

49. **文件**：/home/tangzhiang/.copaw/workspaces/default/active_skills/pptx/scripts/office/validators/redlining.py，**行号**：79
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

50. **文件**：/home/tangzhiang/.copaw/workspaces/default/active_skills/pptx/scripts/office/validators/redlining.py，**行号**：81
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(original_file)

51. **文件**：/home/tangzhiang/.copaw/workspaces/default/active_skills/xlsx/scripts/office/helpers/simplify_redlines.py，**行号**：131
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(doc_xml_path)

52. **文件**：/home/tangzhiang/.copaw/workspaces/default/active_skills/xlsx/scripts/office/helpers/simplify_redlines.py，**行号**：155
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(f)

53. **文件**：/home/tangzhiang/.copaw/workspaces/default/active_skills/xlsx/scripts/office/validators/redlining.py，**行号**：34
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

54. **文件**：/home/tangzhiang/.copaw/workspaces/default/active_skills/xlsx/scripts/office/validators/redlining.py，**行号**：79
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

55. **文件**：/home/tangzhiang/.copaw/workspaces/default/active_skills/xlsx/scripts/office/validators/redlining.py，**行号**：81
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(original_file)

56. **文件**：/home/tangzhiang/.copaw/workspaces/default/scripts/fuzhou_daily_news.py，**行号**：146
   **问题描述**：Found 'subprocess' function 'run' with 'shell=True'. This is dangerous because this call will spawn the command using a shell process. Doing so propagates current shell settings and variables, which makes it much easier for a malicious actor to execute commands. Use 'shell=False' instead.
   **规则ID**：[python.lang.security.audit.subprocess-shell-true.subprocess-shell-true](https://semgrep.dev/r/python.lang.security.audit.subprocess-shell-true.subprocess-shell-true)
   **修复方案**：False

57. **文件**：/home/tangzhiang/.copaw/workspaces/default/skills/docx/scripts/office/helpers/simplify_redlines.py，**行号**：131
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(doc_xml_path)

58. **文件**：/home/tangzhiang/.copaw/workspaces/default/skills/docx/scripts/office/helpers/simplify_redlines.py，**行号**：155
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(f)

59. **文件**：/home/tangzhiang/.copaw/workspaces/default/skills/docx/scripts/office/validators/redlining.py，**行号**：34
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

60. **文件**：/home/tangzhiang/.copaw/workspaces/default/skills/docx/scripts/office/validators/redlining.py，**行号**：79
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

61. **文件**：/home/tangzhiang/.copaw/workspaces/default/skills/docx/scripts/office/validators/redlining.py，**行号**：81
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(original_file)

62. **文件**：/home/tangzhiang/.copaw/workspaces/default/skills/pptx/scripts/office/helpers/simplify_redlines.py，**行号**：131
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(doc_xml_path)

63. **文件**：/home/tangzhiang/.copaw/workspaces/default/skills/pptx/scripts/office/helpers/simplify_redlines.py，**行号**：155
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(f)

64. **文件**：/home/tangzhiang/.copaw/workspaces/default/skills/pptx/scripts/office/validators/redlining.py，**行号**：34
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

65. **文件**：/home/tangzhiang/.copaw/workspaces/default/skills/pptx/scripts/office/validators/redlining.py，**行号**：79
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

66. **文件**：/home/tangzhiang/.copaw/workspaces/default/skills/pptx/scripts/office/validators/redlining.py，**行号**：81
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(original_file)

67. **文件**：/home/tangzhiang/.copaw/workspaces/default/skills/xlsx/scripts/office/helpers/simplify_redlines.py，**行号**：131
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(doc_xml_path)

68. **文件**：/home/tangzhiang/.copaw/workspaces/default/skills/xlsx/scripts/office/helpers/simplify_redlines.py，**行号**：155
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(f)

69. **文件**：/home/tangzhiang/.copaw/workspaces/default/skills/xlsx/scripts/office/validators/redlining.py，**行号**：34
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

70. **文件**：/home/tangzhiang/.copaw/workspaces/default/skills/xlsx/scripts/office/validators/redlining.py，**行号**：79
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

71. **文件**：/home/tangzhiang/.copaw/workspaces/default/skills/xlsx/scripts/office/validators/redlining.py，**行号**：81
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(original_file)

72. **文件**：/home/tangzhiang/.copaw/workspaces/fqd_pro/skills/docx/scripts/office/helpers/simplify_redlines.py，**行号**：131
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(doc_xml_path)

73. **文件**：/home/tangzhiang/.copaw/workspaces/fqd_pro/skills/docx/scripts/office/helpers/simplify_redlines.py，**行号**：155
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(f)

74. **文件**：/home/tangzhiang/.copaw/workspaces/fqd_pro/skills/docx/scripts/office/validators/redlining.py，**行号**：34
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

75. **文件**：/home/tangzhiang/.copaw/workspaces/fqd_pro/skills/docx/scripts/office/validators/redlining.py，**行号**：79
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

76. **文件**：/home/tangzhiang/.copaw/workspaces/fqd_pro/skills/docx/scripts/office/validators/redlining.py，**行号**：81
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(original_file)

77. **文件**：/home/tangzhiang/.copaw/workspaces/fqd_pro/skills/github-readme-creater/github-readme-creator/references/secret-scan.md，**行号**：40
   **问题描述**：Something that looks like a PGP private key block is detected. This is a potential hardcoded secret that could be leaked if this code is committed. Instead, remove this code block from the commit.
   **规则ID**：[generic.secrets.security.detected-pgp-private-key-block.detected-pgp-private-key-block](https://semgrep.dev/r/generic.secrets.security.detected-pgp-private-key-block.detected-pgp-private-key-block)
   **修复方案**：无自动修复方案

78. **文件**：/home/tangzhiang/.copaw/workspaces/fqd_pro/skills/pptx/scripts/office/helpers/simplify_redlines.py，**行号**：131
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(doc_xml_path)

79. **文件**：/home/tangzhiang/.copaw/workspaces/fqd_pro/skills/pptx/scripts/office/helpers/simplify_redlines.py，**行号**：155
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(f)

80. **文件**：/home/tangzhiang/.copaw/workspaces/fqd_pro/skills/pptx/scripts/office/validators/redlining.py，**行号**：34
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

81. **文件**：/home/tangzhiang/.copaw/workspaces/fqd_pro/skills/pptx/scripts/office/validators/redlining.py，**行号**：79
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

82. **文件**：/home/tangzhiang/.copaw/workspaces/fqd_pro/skills/pptx/scripts/office/validators/redlining.py，**行号**：81
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(original_file)

83. **文件**：/home/tangzhiang/.copaw/workspaces/fqd_pro/skills/xlsx/scripts/office/helpers/simplify_redlines.py，**行号**：131
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(doc_xml_path)

84. **文件**：/home/tangzhiang/.copaw/workspaces/fqd_pro/skills/xlsx/scripts/office/helpers/simplify_redlines.py，**行号**：155
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(f)

85. **文件**：/home/tangzhiang/.copaw/workspaces/fqd_pro/skills/xlsx/scripts/office/validators/redlining.py，**行号**：34
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

86. **文件**：/home/tangzhiang/.copaw/workspaces/fqd_pro/skills/xlsx/scripts/office/validators/redlining.py，**行号**：79
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

87. **文件**：/home/tangzhiang/.copaw/workspaces/fqd_pro/skills/xlsx/scripts/office/validators/redlining.py，**行号**：81
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(original_file)

88. **文件**：/home/tangzhiang/.copaw/workspaces/nwny-big-data/skills/docx/scripts/office/helpers/simplify_redlines.py，**行号**：131
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(doc_xml_path)

89. **文件**：/home/tangzhiang/.copaw/workspaces/nwny-big-data/skills/docx/scripts/office/helpers/simplify_redlines.py，**行号**：155
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(f)

90. **文件**：/home/tangzhiang/.copaw/workspaces/nwny-big-data/skills/docx/scripts/office/validators/redlining.py，**行号**：34
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

91. **文件**：/home/tangzhiang/.copaw/workspaces/nwny-big-data/skills/docx/scripts/office/validators/redlining.py，**行号**：79
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

92. **文件**：/home/tangzhiang/.copaw/workspaces/nwny-big-data/skills/docx/scripts/office/validators/redlining.py，**行号**：81
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(original_file)

93. **文件**：/home/tangzhiang/.copaw/workspaces/nwny-big-data/skills/github-readme-creater/github-readme-creator/references/secret-scan.md，**行号**：40
   **问题描述**：Something that looks like a PGP private key block is detected. This is a potential hardcoded secret that could be leaked if this code is committed. Instead, remove this code block from the commit.
   **规则ID**：[generic.secrets.security.detected-pgp-private-key-block.detected-pgp-private-key-block](https://semgrep.dev/r/generic.secrets.security.detected-pgp-private-key-block.detected-pgp-private-key-block)
   **修复方案**：无自动修复方案

94. **文件**：/home/tangzhiang/.copaw/workspaces/nwny-big-data/skills/pptx/scripts/office/helpers/simplify_redlines.py，**行号**：131
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(doc_xml_path)

95. **文件**：/home/tangzhiang/.copaw/workspaces/nwny-big-data/skills/pptx/scripts/office/helpers/simplify_redlines.py，**行号**：155
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(f)

96. **文件**：/home/tangzhiang/.copaw/workspaces/nwny-big-data/skills/pptx/scripts/office/validators/redlining.py，**行号**：34
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

97. **文件**：/home/tangzhiang/.copaw/workspaces/nwny-big-data/skills/pptx/scripts/office/validators/redlining.py，**行号**：79
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

98. **文件**：/home/tangzhiang/.copaw/workspaces/nwny-big-data/skills/pptx/scripts/office/validators/redlining.py，**行号**：81
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(original_file)

99. **文件**：/home/tangzhiang/.copaw/workspaces/nwny-big-data/skills/xlsx/scripts/office/helpers/simplify_redlines.py，**行号**：131
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(doc_xml_path)

100. **文件**：/home/tangzhiang/.copaw/workspaces/nwny-big-data/skills/xlsx/scripts/office/helpers/simplify_redlines.py，**行号**：155
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(f)

101. **文件**：/home/tangzhiang/.copaw/workspaces/nwny-big-data/skills/xlsx/scripts/office/validators/redlining.py，**行号**：34
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

102. **文件**：/home/tangzhiang/.copaw/workspaces/nwny-big-data/skills/xlsx/scripts/office/validators/redlining.py，**行号**：79
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(modified_file)

103. **文件**：/home/tangzhiang/.copaw/workspaces/nwny-big-data/skills/xlsx/scripts/office/validators/redlining.py，**行号**：81
   **问题描述**：The native Python `xml` library is vulnerable to XML External Entity (XXE) attacks.  These attacks can leak confidential data and "XML bombs" can cause denial of service. Do not use this library to parse untrusted input. Instead  the Python documentation recommends using `defusedxml`.
   **规则ID**：[python.lang.security.use-defused-xml-parse.use-defused-xml-parse](https://semgrep.dev/r/python.lang.security.use-defused-xml-parse.use-defused-xml-parse)
   **修复方案**：defusedxml.etree.ElementTree.parse(original_file)

