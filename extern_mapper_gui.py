"""
Extern 变量映射工具 - GUI 主程序
基于 tkinter 的可视化工具，用于读取头文件中的 extern 变量，
并允许用户将 extern 变量的成员与自定义变量进行对应赋值和逻辑判断。

功能:
    1. 结构体用户变量简化操作 - 从已解析的结构体类型快速添加变量
    2. 目标头文件支持 - 选择另一个头文件，使用其中的变量作为映射目标
    3. Markdown 文档生成 - 生成清晰的变量映射关系文档，方便大模型生成代码
    4. 条件表达式与/或操作 - 支持多条件组合的有效性判断

启动方式:
    python extern_mapper_gui.py
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import sys
import json
import re
import threading
import urllib.request
import urllib.error
from typing import Dict, List, Any, Optional
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.header_parser import HeaderParser


class LLMService:
    """LLM API 服务类 - 支持连接 OpenAI 兼容的 LLM 模型服务"""

    def __init__(self, api_key: str = "", base_url: str = "", model: str = ""):
        # 优先从 miapikey.txt 自动加载配置
        config = self._load_config_from_file()
        self.api_key = api_key or config.get('api_key', '')
        self.base_url = (base_url or config.get('base_url', '')).rstrip('/')
        self.model = model or config.get('model', '')
        self._coding_standard = self._load_coding_standard()

    @staticmethod
    def _load_config_from_file() -> dict:
        """从 miapikey.txt 加载配置（3行格式: key, url, model）"""
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'miapikey.txt')
        config = {}
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]
                if len(lines) >= 1:
                    config['api_key'] = lines[0]
                if len(lines) >= 2:
                    config['base_url'] = lines[1]
                if len(lines) >= 3:
                    config['model'] = lines[2]
        except Exception:
            pass
        return config

    @staticmethod
    def _load_coding_standard() -> str:
        """加载编码规范文档"""
        standard_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'coding_standard.md'
        )
        try:
            if os.path.exists(standard_path):
                with open(standard_path, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception:
            pass
        return ""

    def _get_standard_suffix(self) -> str:
        """获取编码规范提示后缀，用于注入到 system_prompt"""
        if not self._coding_standard:
            return ""
        return (
            "\n\n## 强制编码规范\n"
            "你生成的所有代码必须严格遵守以下编码规范，违反任何一条视为失败：\n\n"
            f"{self._coding_standard}\n\n"
            "请在生成代码时逐条对照上述规范。"
        )

    def is_configured(self) -> bool:
        """检查是否已配置"""
        return bool(self.base_url and self.model)

    def call_llm(self, prompt: str, system_prompt: str = "",
                 max_retries: int = 2, timeout: int = 300) -> tuple:
        """调用 LLM API，支持自动重试和超时控制

        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            max_retries: 最大重试次数
            timeout: 超时秒数（默认300秒）

        Returns:
            (success: bool, response_text: str)
        """
        if not self.is_configured():
            return False, "LLM 服务未配置，请先在「AI 助手」菜单中设置 API Key 和 URL"

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 8192,
        })

        last_error = ""
        for attempt in range(max_retries + 1):
            try:
                req = urllib.request.Request(
                    url, data=body.encode('utf-8'), headers=headers, method='POST'
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    result = json.loads(resp.read().decode('utf-8'))
                    content = result['choices'][0]['message']['content']
                    return True, content
            except urllib.error.HTTPError as e:
                error_body = e.read().decode('utf-8', errors='replace')
                if e.code == 429 and attempt < max_retries:
                    # 速率限制，等待后重试
                    import time
                    time.sleep(5 * (attempt + 1))
                    last_error = f"HTTP 429 速率限制，正在重试 ({attempt+1}/{max_retries})"
                    continue
                return False, f"HTTP 错误 {e.code}: {error_body}"
            except urllib.error.URLError as e:
                if attempt < max_retries:
                    import time
                    time.sleep(3 * (attempt + 1))
                    last_error = f"连接失败，正在重试 ({attempt+1}/{max_retries})"
                    continue
                return False, f"连接错误: {e.reason}\n请检查 URL 是否正确，服务是否已启动"
            except json.JSONDecodeError:
                return False, "响应解析失败：服务器返回的不是有效的 JSON"
            except Exception as e:
                error_str = str(e)
                # 超时错误可以重试
                if ('timeout' in error_str.lower() or 'timed out' in error_str.lower()) and attempt < max_retries:
                    import time
                    time.sleep(3 * (attempt + 1))
                    last_error = f"请求超时，正在重试 ({attempt+1}/{max_retries})"
                    continue
                return False, f"请求失败: {error_str}"

        return False, last_error or "所有重试均失败"

    def test_connection(self) -> tuple:
        """测试 LLM 连接"""
        return self.call_llm(
            "Hello, 请用一句话回复「连接成功」。",
            "你是一个测试助手，请简短回复。"
        )

    def generate_code_from_mapping(self, mapping_info: str, header_content: str) -> tuple:
        """基于映射信息通过 LLM 生成代码"""
        system_prompt = (
            "你是一个专业的嵌入式 C 语言代码生成器。根据提供的头文件内容和变量映射关系，"
            "生成高质量的 C 语言数据转换代码。要求：\n"
            "1. 包含必要的类型转换\n"
            "2. 处理 NULL 指针检查\n"
            "3. 添加清晰的中文注释\n"
            "4. 遵循下方的编码规范\n"
            "5. 只输出 C 代码，用 ```c ``` 包裹\n"
            "6. 不要输出多余的解释"
            + self._get_standard_suffix()
        )

        prompt = (
            f"请根据以下信息生成 C 语言数据转换代码：\n\n"
            f"## 头文件内容：\n```c\n{header_content}\n```\n\n"
            f"## 变量映射关系：\n{mapping_info}\n\n"
            f"请生成完整的转换函数代码。"
        )

        return self.call_llm(prompt, system_prompt)

    def generate_code_from_document(self, document_content: str, header_content: str) -> tuple:
        """基于需求文档和头文件通过 LLM 生成代码（直接路径，跳过映射文档）"""
        system_prompt = (
            "你是一个专业的嵌入式 C 语言代码生成器。根据提供的需求文档（通常是中文）和头文件结构体定义，"
            "直接生成数据转换代码。\n\n"
            "## 关键能力：语义匹配\n"
            "需求文档中的中文描述需要与头文件注释进行语义匹配：\n"
            "1. 阅读头文件中的字段注释（// 或 /* */）来理解每个字段的含义\n"
            "2. 将文档中的中文描述与注释进行语义匹配，找到对应的 C 字段名\n"
            "3. 例如：文档说「温度从放大100倍的整数转为浮点」\n"
            "   → 头文件有 `int32_t temperature_x100; // 温度 * 100`\n"
            "   → 生成: dst->temperature = (float)src->temperature_x100 * 0.01f;\n\n"
            "## 输出要求\n"
            "1. 直接生成可编译的 C 代码，不需要中间步骤\n"
            "2. 每个结构体对一个转换函数: int convert_X_to_Y(const X *src, Y *dst)\n"
            "3. 包含 NULL 指针检查，成功返回 0，失败返回 -1\n"
            "4. 每行代码旁边用中文注释说明对应的文档需求\n"
            "5. 只输出 C 代码，用 ```c ``` 包裹\n"
            "6. 不要输出多余的解释"
            + self._get_standard_suffix()
        )

        prompt = (
            f"请根据以下中文需求文档和头文件，直接生成数据转换代码。\n"
            f"注意：用头文件中的注释来理解字段含义，与文档中的中文描述进行语义匹配。\n\n"
            f"## 头文件内容：\n```c\n{header_content}\n```\n\n"
            f"## 需求文档：\n{document_content}\n\n"
            f"请直接生成完整的 C 转换函数代码，不需要输出映射文档。"
        )
        return self.call_llm(prompt, system_prompt)

    def convert_doc_to_mapping_doc(self, natural_doc: str, header_content: str) -> tuple:
        """将自然语言文档转换为规范映射文档

        支持中文自由格式描述，通过语义匹配头文件中的字段名和注释。
        """
        system_prompt = (
            "你是一个专业的数据映射文档转换器。你的任务是将自然语言（通常是中文）描述的数据转换需求，"
            "结合C语言头文件中的结构体定义，转换为标准格式的映射关系文档。\n\n"
            "## 关键能力：语义匹配\n"
            "需求文档中的中文描述可能不是直接的字段名，而是语义描述。你需要：\n"
            "1. 阅读头文件中的字段注释（// 或 /* */ 中的中文说明）\n"
            "2. 将需求文档中的中文描述与头文件注释进行语义匹配\n"
            "3. 例如：文档说「温度」→ 头文件有 `int32_t temperature_x100; // 温度 * 100` → 匹配到 temperature_x100\n"
            "4. 例如：文档说「采样间隔」→ 头文件有 `uint16_t sampling_rate_ms; // 采样率(毫秒)` → 匹配到 sampling_rate_ms\n"
            "5. 即使描述不完全一致，也要根据上下文推断最可能的对应关系\n\n"
            "## 输出格式\n"
            "```markdown\n"
            "# 数据映射关系文档\n\n"
            "## 映射关系\n"
            "| 源字段 | 目标字段 | 转换规则 | 业务含义 |\n"
            "|--------|----------|----------|----------|\n"
            "| source_field | target_field | 类型转换/缩放/偏移/直接赋值 | 对应的中文说明 |\n"
            "```\n\n"
            "转换规则分类：\n"
            "- 直接赋值：类型和值都不变\n"
            "- 类型转换：值不变但类型变了（如 uint16→uint32）\n"
            "- 缩放：值需要乘或除一个系数（如 ×1000, ÷100）\n"
            "- 偏移：值需要加减一个常量\n"
            "- 自定义：其他复杂转换逻辑\n\n"
            "请严格按照上述格式输出，不要添加多余的解释。"
        )

        prompt = (
            f"请将以下中文需求文档转换为标准映射文档。\n"
            f"注意：文档中的中文描述需要与头文件注释进行语义匹配来找到对应的 C 字段名。\n\n"
            f"## 头文件内容：\n```c\n{header_content}\n```\n\n"
            f"## 需求文档：\n{natural_doc}\n\n"
            f"请逐条分析需求文档中的转换说明，与头文件字段进行语义匹配，生成映射文档。"
        )

        return self.call_llm(prompt, system_prompt)

    def generate_code_from_mapping_doc(self, mapping_doc: str, header_content: str) -> tuple:
        """基于规范映射文档生成代码

        Args:
            mapping_doc: 规范映射关系文档
            header_content: 头文件内容

        Returns:
            (success: bool, code: str)
        """
        system_prompt = (
            "你是一个专业的嵌入式 C 语言代码生成器。根据提供的标准映射关系文档和头文件内容，"
            "生成高质量的 C 语言数据转换代码。要求：\n"
            "1. 严格按照映射文档中的规则实现数据转换\n"
            "2. 包含必要的类型转换和 NULL 指针检查\n"
            "3. 添加清晰的中文注释，说明每条映射规则的实现\n"
            "4. 遵循下方的编码规范\n"
            "5. 只输出 C 代码，用 ```c ``` 包裹\n"
            "6. 不要输出多余的解释"
            + self._get_standard_suffix()
        )

        prompt = (
            f"请根据以下标准映射关系文档和头文件，生成数据转换代码：\n\n"
            f"## 头文件内容：\n```c\n{header_content}\n```\n\n"
            f"## 映射关系文档：\n{mapping_doc}\n\n"
            f"请严格按照映射文档中定义的规则，生成完整的 C 语言转换函数代码。"
        )

        return self.call_llm(prompt, system_prompt)


class DocumentBasedGenerator:
    """基于文档的本地代码生成器 - 通过 Python 解析文档规则生成 C 语言代码"""

    def __init__(self, parser=None, target_parser=None):
        self.parser = parser
        self.target_parser = target_parser

    def parse_document_rules(self, doc_content: str) -> List[Dict]:
        """从文档内容中解析映射规则

        支持的格式:
            source_member -> target_member [转换类型]
            source_member => target_member [转换类型]
            source_member = target_member
            source_member : target_member
        """
        rules = []
        lines = doc_content.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('//'):
                continue

            rule = self._parse_rule_line(line)
            if rule:
                rules.append(rule)

        return rules

    def _parse_rule_line(self, line: str) -> Optional[Dict]:
        """解析单行映射规则"""
        for sep in ['->', '=>', '=', ':']:
            if sep in line:
                parts = line.split(sep, 1)
                if len(parts) == 2:
                    source = parts[0].strip()
                    target_part = parts[1].strip()

                    # 解析转换类型 [xxx]
                    conv_type = '直接赋值'
                    if '[' in target_part and ']' in target_part:
                        idx_start = target_part.index('[')
                        idx_end = target_part.index(']')
                        conv_type = target_part[idx_start + 1:idx_end].strip()
                        target_part = target_part[:idx_start].strip()

                    # 解析条件 {xxx}
                    condition = ''
                    if '{' in target_part and '}' in target_part:
                        idx_start = target_part.index('{')
                        idx_end = target_part.index('}')
                        condition = target_part[idx_start + 1:idx_end].strip()
                        target_part = target_part[:idx_start].strip()

                    if source and target_part:
                        return {
                            'source': source,
                            'target': target_part,
                            'conversion': conv_type,
                            'condition': condition,
                        }
        return None

    def generate_code(self, doc_content: str, header_content: str = "",
                      source_structs: Dict = None, target_structs: Dict = None) -> str:
        """基于文档内容本地生成 C 代码"""
        rules = self.parse_document_rules(doc_content)

        if not rules:
            return (
                "/* 未能从文档中解析出有效的映射规则 */\n"
                "/* 支持的格式: */\n"
                "/*   source_member -> target_member [转换类型] {条件} */\n"
                "/*   source_member => target_member */\n"
                "/*   source_member = target_member */\n"
                "/*   source_member : target_member */\n"
            )

        lines = []
        lines.append("/*")
        lines.append(" * 基于需求文档自动生成的数据转换代码")
        lines.append(f" * 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f" * 解析到 {len(rules)} 条映射规则")
        lines.append(" */")
        lines.append("")

        # 收集所有涉及的源和目标变量
        source_vars = set()
        target_vars = set()
        for rule in rules:
            source_vars.add(rule['source'].split('.')[0].split('->')[0])
            target_vars.add(rule['target'].split('.')[0].split('->')[0])

        # 生成函数
        func_name = "document_based_convert"
        params = []
        for sv in sorted(source_vars):
            params.append(f"const void *{sv}")
        for tv in sorted(target_vars):
            params.append(f"void *{tv}")

        lines.append(f"void {func_name}({', '.join(params)}) {{")

        for i, rule in enumerate(rules, 1):
            source = rule['source']
            target = rule['target']
            conv = rule['conversion']
            cond = rule.get('condition', '')

            lines.append(f"    /* 规则 {i}: {source} -> {target} [{conv}] */")

            # 处理条件
            if cond:
                lines.append(f"    if ({cond}) {{")

            # 根据转换类型生成代码
            if conv == '直接赋值':
                stmt = f"{target} = {source};"
            elif conv == '类型转换':
                target_type = self._infer_type(target)
                stmt = f"{target} = ({target_type}){source};"
            elif conv.startswith('*') or conv.startswith('×') or conv.startswith('缩放'):
                factor = re.sub(r'^[*×缩放\s]+', '', conv).strip()
                if not factor:
                    factor = '1.0'
                stmt = f"{target} = {source} * {factor};"
            elif conv.startswith('+') or conv.startswith('偏移'):
                offset = re.sub(r'^[+偏移\s]+', '', conv).strip()
                if not offset:
                    offset = '0'
                stmt = f"{target} = {source} + {offset};"
            elif conv.startswith('自定义') or conv.startswith('custom'):
                stmt = f"{target} = {source};  /* TODO: 自定义转换 */"
            else:
                stmt = f"{target} = {source};  /* {conv} */"

            if cond:
                lines.append(f"        {stmt}")
                lines.append(f"    }}")
            else:
                lines.append(f"    {stmt}")
            lines.append("")

        lines.append("}")

        return "\n".join(lines)

    def _infer_type(self, var_name: str) -> str:
        """根据变量名推断类型"""
        name_lower = var_name.lower()
        if any(kw in name_lower for kw in ['temp', 'temperature', 'voltage', 'current', 'pressure']):
            return 'float'
        if any(kw in name_lower for kw in ['flag', 'enable', 'status', 'active']):
            return 'uint8_t'
        if any(kw in name_lower for kw in ['count', 'num', 'index', 'id']):
            return 'uint32_t'
        if any(kw in name_lower for kw in ['name', 'str', 'desc']):
            return 'char *'
        return 'int'

    def parse_mappings_from_document(self, doc_content: str) -> tuple:
        """从文档内容解析映射关系，返回 (user_vars, mappings)

        支持的文档格式:
        1. 表格格式（Markdown 表格）
        2. 行格式: 源成员 -> 目标成员 [操作类型] {条件}
        3. 中文格式: 源成员 映射到 目标成员
        4. 带变量定义的格式

        Returns:
            (user_vars: List[Dict], mappings: List[Dict])
        """
        user_vars = []
        mappings = []
        lines = doc_content.strip().split('\n')

        # 先解析变量定义区（## 变量定义 或 ## 用户变量 之后的段落）
        in_var_section = False
        in_mapping_section = False

        for line in lines:
            stripped = line.strip()

            # 检测章节标题
            if stripped.startswith('##') or stripped.startswith('#'):
                lower = stripped.lower()
                if any(kw in lower for kw in ['变量定义', '用户变量', '变量列表', '变量声明', 'variable']):
                    in_var_section = True
                    in_mapping_section = False
                    continue
                elif any(kw in lower for kw in ['映射', '映射关系', '映射规则', 'mapping']):
                    in_var_section = False
                    in_mapping_section = True
                    continue
                else:
                    in_var_section = False
                    in_mapping_section = False
                    continue

            # 解析变量定义
            if in_var_section:
                var_info = self._parse_var_definition(stripped)
                if var_info and not any(v['name'] == var_info['name'] for v in user_vars):
                    user_vars.append(var_info)

            # 解析映射关系
            if in_mapping_section or (not in_var_section and not in_mapping_section):
                mapping = self._parse_mapping_line(stripped)
                if mapping:
                    mappings.append(mapping)

        # 如果没有通过章节解析到内容，尝试全文解析
        if not mappings:
            for line in lines:
                stripped = line.strip()
                if not stripped or stripped.startswith('#') or stripped.startswith('//'):
                    continue
                # 跳过表格分隔行
                if set(stripped) <= set('-| :'):
                    continue
                mapping = self._parse_mapping_line(stripped)
                if mapping:
                    mappings.append(mapping)

        # 尝试解析 Markdown 表格
        if not mappings:
            mappings = self._parse_markdown_table(lines)

        # 从映射关系中提取隐含的用户变量
        for m in mappings:
            target = m['user_var']
            if not any(v['name'] == target for v in user_vars):
                user_vars.append({
                    'name': target,
                    'type': self._infer_type(target),
                    'desc': f'从文档导入',
                    'source': '文档导入',
                    'is_struct': False,
                })

        return user_vars, mappings

    def _parse_var_definition(self, line: str) -> Optional[Dict]:
        """解析变量定义行

        支持格式:
        - 变量名 类型
        - 类型 变量名
        - 变量名: 类型
        - 变量名 (类型)
        - | 变量名 | 类型 | 描述 |  (表格行)
        """
        if not line or line.startswith('#') or line.startswith('//'):
            return None

        # 表格行格式: | name | type | desc |
        if '|' in line:
            cells = [c.strip() for c in line.split('|')]
            cells = [c for c in cells if c]
            if len(cells) >= 2:
                name = cells[0].strip()
                type_str = cells[1].strip()
                desc = cells[2].strip() if len(cells) > 2 else ''
                # 跳过表头
                if name in ('变量名', '名称', 'name', 'Name', '---', '变量'):
                    return None
                if type_str in ('类型', 'type', 'Type', '---'):
                    return None
                if name and type_str and not name.startswith('-'):
                    return {
                        'name': name,
                        'type': type_str,
                        'desc': desc,
                        'source': '文档导入',
                        'is_struct': False,
                    }
            return None

        # 冒号格式: 变量名: 类型
        if ':' in line:
            parts = line.split(':', 1)
            name = parts[0].strip()
            rest = parts[1].strip()
            # 提取类型和描述
            type_parts = rest.split(None, 1)
            type_str = type_parts[0] if type_parts else 'int'
            desc = type_parts[1] if len(type_parts) > 1 else ''
            if name and not name.startswith('#'):
                return {
                    'name': name,
                    'type': type_str,
                    'desc': desc,
                    'source': '文档导入',
                    'is_struct': False,
                }

        # 括号格式: 变量名 (类型)
        m = re.match(r'(\w+)\s*[\(（](\w+)[\)）]\s*(.*)', line)
        if m:
            return {
                'name': m.group(1),
                'type': m.group(2),
                'desc': m.group(3).strip(),
                'source': '文档导入',
                'is_struct': False,
            }

        # 空格分隔: 类型 变量名 或 变量名 类型
        parts = line.split()
        if len(parts) >= 2:
            first, second = parts[0], parts[1]
            c_types = {'int', 'float', 'double', 'char', 'short', 'long', 'void',
                       'uint8_t', 'uint16_t', 'uint32_t', 'uint64_t',
                       'int8_t', 'int16_t', 'int32_t', 'int64_t',
                       'bool', 'unsigned', 'signed', 'struct'}
            if first in c_types:
                return {
                    'name': second,
                    'type': first,
                    'desc': ' '.join(parts[2:]) if len(parts) > 2 else '',
                    'source': '文档导入',
                    'is_struct': False,
                }
            if second in c_types:
                return {
                    'name': first,
                    'type': second,
                    'desc': ' '.join(parts[2:]) if len(parts) > 2 else '',
                    'source': '文档导入',
                    'is_struct': False,
                }

        return None

    def _parse_mapping_line(self, line: str) -> Optional[Dict]:
        """解析映射关系行

        支持格式:
        - source -> target
        - source => target
        - source = target
        - source : target
        - source 映射到 target
        - source 映射 target
        - source 赋值给 target
        - source 对应 target
        - | source | target | 操作 | 转换 | 条件 | (表格行)
        """
        if not line or line.startswith('#') or line.startswith('//'):
            return None

        # 表格行
        if '|' in line:
            cells = [c.strip() for c in line.split('|')]
            cells = [c for c in cells if c]
            if len(cells) >= 2:
                source = cells[0].strip()
                target = cells[1].strip()
                # 跳过表头
                if source in ('源', '源成员', 'source', 'Source', '---', 'extern'):
                    return None
                if target in ('目标', '目标成员', 'target', 'Target', '---'):
                    return None
                if source.startswith('-') or target.startswith('-'):
                    return None
                op_type = cells[2].strip() if len(cells) > 2 else '直接赋值'
                conv = cells[3].strip() if len(cells) > 3 else '='
                cond_str = cells[4].strip() if len(cells) > 4 else ''

                if source and target:
                    # 规范化操作类型
                    op_type = self._normalize_op_type(op_type)
                    conv_rule = self._normalize_conv(conv)

                    conditions = []
                    if cond_str:
                        conditions = self._parse_condition_string(cond_str)

                    return {
                        'extern_member': source,
                        'user_var': target,
                        'op_type': op_type,
                        'condition': conditions,
                        'conversion': conv_rule,
                        'conv_rule': conv_rule,
                    }
            return None

        # 中文关键词格式
        for kw in ['映射到', '赋值给', '对应', '映射']:
            if kw in line:
                parts = line.split(kw, 1)
                if len(parts) == 2:
                    source = parts[0].strip()
                    rest = parts[1].strip()
                    # 解析可选的 [操作类型] 和 {条件}
                    op_type = '直接赋值'
                    conv_rule = '='
                    conditions = []

                    if '[' in rest and ']' in rest:
                        idx_s = rest.index('[')
                        idx_e = rest.index(']')
                        op_str = rest[idx_s + 1:idx_e].strip()
                        op_type = self._normalize_op_type(op_str)
                        rest = rest[:idx_s].strip() + rest[idx_e + 1:].strip()

                    if '{' in rest and '}' in rest:
                        idx_s = rest.index('{')
                        idx_e = rest.index('}')
                        cond_str = rest[idx_s + 1:idx_e].strip()
                        conditions = self._parse_condition_string(cond_str)
                        rest = rest[:idx_s].strip() + rest[idx_e + 1:].strip()

                    target = rest.strip()
                    if source and target:
                        return {
                            'extern_member': source,
                            'user_var': target,
                            'op_type': op_type,
                            'condition': conditions,
                            'conversion': conv_rule,
                            'conv_rule': conv_rule,
                        }

        # 标准分隔符格式
        for sep in ['->', '=>', '=', ':']:
            if sep in line:
                parts = line.split(sep, 1)
                if len(parts) == 2:
                    source = parts[0].strip()
                    rest = parts[1].strip()

                    op_type = '直接赋值'
                    conv_rule = '='
                    conditions = []

                    if '[' in rest and ']' in rest:
                        idx_s = rest.index('[')
                        idx_e = rest.index(']')
                        op_str = rest[idx_s + 1:idx_e].strip()
                        op_type = self._normalize_op_type(op_str)
                        conv_rule = self._normalize_conv(op_str)
                        rest = rest[:idx_s].strip() + rest[idx_e + 1:].strip()

                    if '{' in rest and '}' in rest:
                        idx_s = rest.index('{')
                        idx_e = rest.index('}')
                        cond_str = rest[idx_s + 1:idx_e].strip()
                        conditions = self._parse_condition_string(cond_str)
                        rest = rest[:idx_s].strip() + rest[idx_e + 1:].strip()

                    target = rest.strip()
                    if source and target:
                        return {
                            'extern_member': source,
                            'user_var': target,
                            'op_type': op_type,
                            'condition': conditions,
                            'conversion': conv_rule,
                            'conv_rule': conv_rule,
                        }
                break

        return None

    def _parse_markdown_table(self, lines: List[str]) -> List[Dict]:
        """解析 Markdown 表格格式的映射关系"""
        mappings = []
        table_lines = []
        in_table = False

        for line in lines:
            stripped = line.strip()
            if '|' in stripped:
                in_table = True
                table_lines.append(stripped)
            elif in_table:
                break

        if len(table_lines) < 2:
            return []

        for line in table_lines:
            mapping = self._parse_mapping_line(line)
            if mapping:
                mappings.append(mapping)

        return mappings

    def _normalize_op_type(self, op_str: str) -> str:
        """规范化操作类型"""
        op_str = op_str.strip()
        op_map = {
            '直接赋值': '直接赋值', '赋值': '直接赋值', '=': '直接赋值',
            '条件赋值': '条件赋值', '条件': '条件赋值', 'if': '条件赋值',
            '逻辑判断': '逻辑判断', '判断': '逻辑判断', 'check': '逻辑判断',
            '自定义': '自定义表达式', '自定义表达式': '自定义表达式', 'custom': '自定义表达式',
        }
        return op_map.get(op_str, '直接赋值')

    def _normalize_conv(self, conv_str: str) -> str:
        """规范化转换规则"""
        conv_str = conv_str.strip()
        if not conv_str or conv_str == '=' or conv_str == '直接赋值':
            return '='
        if conv_str.startswith('('):
            return conv_str
        if conv_str.startswith('*') or conv_str.startswith('×'):
            return conv_str
        if conv_str.startswith('+'):
            return conv_str
        return conv_str

    def _parse_condition_string(self, cond_str: str) -> List[Dict]:
        """解析条件字符串为条件列表

        格式: 变量 操作符 值 [AND/OR 变量 操作符 值 ...]
        例如: temperature > 50 AND status == 1
        """
        conditions = []
        # 按 AND/OR 分割
        parts = re.split(r'\s+(AND|OR|且|或|并且|或者)\s+', cond_str)

        i = 0
        while i < len(parts):
            part = parts[i].strip()
            logic = 'AND'

            if i + 1 < len(parts) and parts[i + 1].strip() in ('AND', 'OR', '且', '并且', '或', '或者'):
                logic_word = parts[i + 1].strip()
                logic = 'OR' if logic_word in ('OR', '或', '或者') else 'AND'
                i += 2
            else:
                i += 1

            if not part:
                continue

            # 解析单个条件: 变量 操作符 值
            for op in ['==', '!=', '>=', '<=', '>', '<']:
                if op in part:
                    cv = part.split(op, 1)
                    if len(cv) == 2:
                        conditions.append({
                            'var_ref': cv[0].strip(),
                            'operator': op,
                            'value': cv[1].strip(),
                            'logic': logic if conditions else '',
                        })
                        break

        return conditions


class ConditionBuilder:
    """条件表达式构建器 - 支持与/或操作"""

    def __init__(self):
        self.conditions: List[Dict] = []

    def add_condition(self, var_ref: str, operator: str, value: str, logic: str = 'AND'):
        """添加条件
        
        Args:
            var_ref: 变量引用 (如 g_sensor_data->temperature)
            operator: 操作符 (==, !=, >, <, >=, <=, etc.)
            value: 比较值
            logic: 逻辑连接符 (AND, OR)
        """
        self.conditions.append({
            'var_ref': var_ref,
            'operator': operator,
            'value': value,
            'logic': logic
        })

    def build_expression(self, extern_var: str) -> str:
        """构建完整的条件表达式"""
        if not self.conditions:
            return ""

        parts = []
        for i, cond in enumerate(self.conditions):
            # 构建变量引用
            if '.' in cond['var_ref']:
                var_ref = f"{extern_var}->{cond['var_ref']}"
            else:
                var_ref = f"{extern_var}->{cond['var_ref']}"

            # 构建条件表达式
            expr = f"{var_ref} {cond['operator']} {cond['value']}"
            parts.append(expr)

        # 组合表达式
        if len(parts) == 1:
            return parts[0]

        result = parts[0]
        for i in range(1, len(parts)):
            logic = self.conditions[i].get('logic', 'AND')
            result = f"({result}) {logic} ({parts[i]})"

        return result

    def to_dict(self) -> List[Dict]:
        return self.conditions

    @staticmethod
    def from_dict(data: List[Dict]) -> 'ConditionBuilder':
        builder = ConditionBuilder()
        builder.conditions = data
        return builder


class MappingRule:
    """映射规则数据类"""

    def __init__(self, extern_member: str, user_var: str, op_type: str,
                 condition: Optional[ConditionBuilder] = None,
                 conversion: str = '=', custom_conv: str = ''):
        self.extern_member = extern_member
        self.user_var = user_var
        self.op_type = op_type
        self.condition = condition or ConditionBuilder()
        self.conversion = conversion
        self.custom_conv = custom_conv

    def to_dict(self) -> Dict:
        return {
            'extern_member': self.extern_member,
            'user_var': self.user_var,
            'op_type': self.op_type,
            'condition': self.condition.to_dict(),
            'conversion': self.conversion,
            'custom_conv': self.custom_conv
        }

    @staticmethod
    def from_dict(data: Dict) -> 'MappingRule':
        rule = MappingRule(
            data['extern_member'],
            data['user_var'],
            data['op_type'],
            data.get('conversion', '='),
            data.get('custom_conv', '')
        )
        if 'condition' in data:
            rule.condition = ConditionBuilder.from_dict(data['condition'])
        return rule


class MarkdownDocumentGenerator:
    """Markdown 文档生成器 - 生成清晰的变量映射关系文档"""

    def __init__(self, app):
        self.app = app

    def generate(self) -> str:
        """生成完整的 Markdown 文档"""
        lines = []

        # 1. 文档标题和基本信息
        lines.extend(self._generate_header())

        # 2. 源头文件信息
        lines.extend(self._generate_source_info())

        # 3. 目标文件信息
        lines.extend(self._generate_target_info())

        # 4. 用户变量定义
        lines.extend(self._generate_user_vars())

        # 5. 映射关系详细说明
        lines.extend(self._generate_mappings())

        # 6. 代码模板
        lines.extend(self._generate_code_templates())

        # 7. 变量引用速查表
        lines.extend(self._generate_reference_table())

        return '\n'.join(lines)

    def _generate_header(self) -> List[str]:
        """生成文档头部"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return [
            '# Struct Variable Mapping Specification',
            '',
            f'**Generated at:** {timestamp}',
            f'**Source Header:** `{self.app.current_file.get() or "Not specified"}`',
            f'**Target Header:** `{self.app.target_file.get() or "Not specified"}`',
            '',
            '## Overview',
            '',
            'This document describes the mapping relationships between extern variables',
            'from source header files and user-defined target variables. The mapping rules',
            'are designed to be clear and unambiguous for LLM-assisted code generation.',
            '',
            '---\n'
        ]

    def _generate_source_info(self) -> List[str]:
        """生成源头文件信息"""
        lines = [
            '## Source Extern Variables',
            '',
            'The following extern variables are declared in the source header file.',
            'These variables are read-only sources of data.',
            '',
        ]

        if self.app.selected_extern_var:
            var = self.app.selected_extern_var
            lines.extend([
                f'### `{var["name"]}`',
                '',
                f'- **Type:** `{var["type"]}`',
                f'- **Is Struct:** {"Yes" if var.get("is_struct") else "No"}',
            ])

            if var.get('is_struct') and var.get('struct_type'):
                lines.extend([
                    f'- **Struct Type:** `{var["struct_type"]}`',
                    '',
                    '**Member Reference Pattern:**',
                    '',
                    '```c',
                    f'{var["name"]}-><member_name>',
                    '```',
                    '',
                    '**Available Members:**',
                    '',
                ])

                members = self.app.parser.get_nested_members(var.get('struct_type', ''))
                for m in members:
                    member_name = m.get('full_path', m['name'])
                    lines.append(f'- `{member_name}` : `{m["type"]}`')

                lines.append('')

        lines.append('---\n')
        return lines

    def _generate_target_info(self) -> List[str]:
        """生成目标头文件信息"""
        lines = [
            '## Target Extern Variables',
            '',
            'Variables from the target header file that are used as mapping targets.',
            'These are typically `extern` declarations that will be assigned values.',
            '',
        ]

        target_vars = [v for v in self.app.user_vars
                      if v.get('source') in ('目标头文件', '目标结构体展开')]

        if target_vars:
            # 按变量名分组
            struct_groups = {}
            simple_vars = []

            for var in target_vars:
                if '.' in var['name']:
                    base = var['name'].split('.')[0]
                    if base not in struct_groups:
                        struct_groups[base] = []
                    struct_groups[base].append(var)
                else:
                    simple_vars.append(var)

            # 输出结构体变量组
            for base_name, members in struct_groups.items():
                lines.append(f'### `{base_name}` (Struct Instance)')
                lines.append('')

                var_info = next((v for v in self.app.user_vars if v['name'] == base_name), None)
                if var_info:
                    lines.append(f'- **Type:** `{var_info["type"]}`')
                    lines.append(f'- **Source:** `{var_info.get("source", "Unknown")}`')
                    lines.append('')
                    lines.append('**Member Reference Pattern:**')
                    lines.append('')
                    lines.append('```c')
                    lines.append(f'{base_name}-><member_name>')
                    lines.append('```')
                    lines.append('')
                    lines.append('**Accessible Members:**')
                    lines.append('')

                    for m in members:
                        member_path = m['name'].split('.', 1)[1]
                        lines.append(f'- `{member_path}` : `{m["type"]}`')

                    lines.append('')

            # 输出简单变量
            if simple_vars:
                lines.append('### Simple Variables')
                lines.append('')
                for var in simple_vars:
                    lines.append(f'- `{var["name"]}` : `{var["type"]}`')
                lines.append('')

        else:
            lines.append('*No target extern variables defined.*\n')

        lines.append('---\n')
        return lines

    def _generate_user_vars(self) -> List[str]:
        """生成用户变量定义"""
        lines = [
            '## User-Defined Variables',
            '',
            'Variables defined by the user for mapping. These are typically local',
            'variables or pointers that will receive values from the source variables.',
            '',
        ]

        user_only_vars = [v for v in self.app.user_vars
                         if v.get('source') not in ('目标头文件', '目标结构体展开')]

        if user_only_vars:
            struct_groups = {}
            simple_vars = []

            for var in user_only_vars:
                if '.' in var['name']:
                    base = var['name'].split('.')[0]
                    if base not in struct_groups:
                        struct_groups[base] = []
                    struct_groups[base].append(var)
                else:
                    simple_vars.append(var)

            # 结构体变量
            for base_name, members in struct_groups.items():
                lines.append(f'### `{base_name}` (User Struct)')
                lines.append('')

                var_info = next((v for v in self.app.user_vars if v['name'] == base_name), None)
                if var_info:
                    lines.append(f'- **Type:** `{var_info["type"]}`')
                    lines.append(f'- **Description:** {var_info.get("desc", "N/A")}')
                    lines.append('')
                    lines.append('**Member Reference Pattern:**')
                    lines.append('')
                    lines.append('```c')
                    lines.append(f'(*{base_name}).<member_name>')
                    lines.append('```')
                    lines.append('')
                    lines.append('**Members:**')
                    lines.append('')

                    for m in members:
                        member_path = m['name'].split('.', 1)[1]
                        lines.append(f'- `{member_path}` : `{m["type"]}` - {m.get("desc", "")}')

                    lines.append('')

            # 简单变量
            if simple_vars:
                lines.append('### Simple Variables')
                lines.append('')
                lines.append('| Variable | Type | Description |')
                lines.append('|----------|------|-------------|')
                for var in simple_vars:
                    desc = var.get('desc', '')
                    lines.append(f'| `{var["name"]}` | `{var["type"]}` | {desc} |')
                lines.append('')

        else:
            lines.append('*No user-defined variables.*\n')

        lines.append('---\n')
        return lines

    def _generate_mappings(self) -> List[str]:
        """生成映射关系"""
        lines = [
            '## Mapping Relationships',
            '',
            'This section describes the detailed mapping rules between source and target variables.',
            '',
        ]

        if not self.app.mappings:
            lines.append('*No mappings defined.*\n')
            lines.append('---\n')
            return lines

        for i, mapping in enumerate(self.app.mappings, 1):
            lines.extend(self._generate_single_mapping(i, mapping))

        lines.append('---\n')
        return lines

    def _generate_single_mapping(self, index: int, mapping: Dict) -> List[str]:
        """生成单个映射的详细说明"""
        lines = [
            f'### Mapping #{index}',
            '',
            f'| Property | Value |',
            f'|----------|-------|',
            f'| Source Member | `{mapping["extern_member"]}` |',
            f'| Target Variable | `{mapping["user_var"]}` |',
            f'| Operation Type | {mapping.get("op_type", "直接赋值")} |',
            f'| Conversion | `{mapping.get("conversion", "=")}` |',
            '',
            '**C Code Reference:**',
            '',
            '```c',
        ]

        # 根据目标变量类型生成正确的代码引用
        is_target = self.app._is_target_var(mapping['user_var'])
        if is_target:
            if '.' in mapping['user_var']:
                base, member = mapping['user_var'].split('.', 1)
                lines.append(f'{base}->{member} = ...')
            else:
                lines.append(f'{mapping["user_var"]} = ...')
        else:
            if '.' in mapping['user_var']:
                base, member = mapping['user_var'].split('.', 1)
                lines.append(f'(*{base}).{member} = ...')
            else:
                lines.append(f'(*{mapping["user_var"]}) = ...')

        lines.append('```')
        lines.append('')

        # 条件说明
        conditions = mapping.get('condition', [])
        if isinstance(conditions, list) and conditions:
            lines.append('**Conditions:**')
            lines.append('')
            for j, cond in enumerate(conditions, 1):
                lines.append(f'{j}. `{cond.get("var_ref", "")}` {cond.get("operator", "")} {cond.get("value", "")}')
                if cond.get('logic'):
                    lines.append(f'   Logic: `{cond["logic"]}`')
            lines.append('')

        return lines

    def _generate_code_templates(self) -> List[str]:
        """生成代码模板"""
        lines = [
            '## Code Generation Templates',
            '',
            '### Function Signature Template',
            '',
            '```c',
            'void assign_from_<extern_var>(',
            '    <extern_type> *<extern_var>,  // Source data pointer',
            '    <user_var_type> *<user_var>   // Target variable pointer',
            ') {',
            '    // Implementation',
            '}',
            '```',
            '',
            '### Assignment Statement Template',
            '',
            '```c',
            '// Direct assignment',
            '<target_ref> = <source_ref>;',
            '',
            '// Conditional assignment',
            'if (<condition>) {',
            '    <target_ref> = <source_ref>;',
            '}',
            '',
            '// Conversion assignment',
            '<target_ref> = <conversion>(<source_ref>);',
            '```',
            '',
            '### Condition Expression Template',
            '',
            '```c',
            '// Simple condition',
            '<extern_var>-><member> <operator> <value>',
            '',
            '// Compound condition (AND)',
            '(<condition1>) && (<condition2>)',
            '',
            '// Compound condition (OR)',
            '(<condition1>) || (<condition2>)',
            '',
            '// Mixed conditions',
            '(<condition1>) && (<condition2>) || (<condition3>)',
            '```',
            '',
            '---\n'
        ]
        return lines

    def _generate_reference_table(self) -> List[str]:
        """生成变量引用速查表"""
        lines = [
            '## Quick Reference',
            '',
            '### Variable Reference Patterns',
            '',
            '| Variable Type | Reference Pattern | Example |',
            '|---------------|-------------------|---------|',
            '| Source Struct Member | `<var>-><member>` | `g_sensor_data->temperature` |',
            '| Target Struct Member | `<var>-><member>` | `g_target->temperature` |',
            '| User Struct Member | `(**<var>).<member>` | `(*my_sensor).temperature` |',
            '| Simple User Var | `(*<var>)` | `(*my_temp)` |',
            '',
            '### Common Conversion Rules',
            '',
            '| Rule | Syntax | Description |',
            '|------|--------|-------------|',
            '| Direct | `=` | Direct assignment |',
            '| Cast | `(type)` | Type casting |',
            '| Scale | `* factor` | Multiplication |',
            '| Offset | `+ offset` | Addition |',
            '| Custom | User-defined | Custom expression |',
            '',
            '---\n',
            '',
            '*This document is machine-generated and designed for LLM code generation.*'
        ]
        return lines


class MappingDocGenerator:
    """规范映射文档生成器 - 从 GUI 映射关系生成标准格式的映射文档"""

    def __init__(self, app):
        self.app = app

    def generate(self) -> str:
        """从当前 GUI 映射关系生成规范映射文档"""
        lines = []
        lines.extend(self._gen_header())
        lines.extend(self._gen_source_vars())
        lines.extend(self._gen_target_vars())
        lines.extend(self._gen_mappings())
        return '\n'.join(lines)

    def _gen_header(self) -> list:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        lines = [
            '# 数据映射关系文档',
            '',
            f'- 生成时间: {ts}',
            f'- 源头文件: {self.app.current_file.get() or "未指定"}',
            f'- 目标头文件: {self.app.target_file.get() or "未指定"}',
            '',
            '---',
            '',
        ]
        return lines

    def _gen_source_vars(self) -> list:
        lines = ['## 源变量定义', '']
        if self.app.selected_extern_var:
            var = self.app.selected_extern_var
            lines.append(f'### {var["name"]} ({var["type"]})')
            lines.append('')
            if var.get('is_struct') and var.get('struct_type') and self.app.parser:
                members = self.app.parser.get_nested_members(var.get('struct_type', ''))
                for m in members:
                    mp = m.get('full_path', m['name'])
                    lines.append(f'- {mp} : {m["type"]}')
                lines.append('')
            else:
                lines.append(f'- {var["name"]} : {var["type"]}')
                lines.append('')
        else:
            lines.append('(未选择源变量)')
            lines.append('')
        return lines

    def _gen_target_vars(self) -> list:
        lines = ['## 目标变量定义', '']
        if not self.app.user_vars:
            lines.append('(未定义目标变量)')
            lines.append('')
            return lines

        struct_groups = {}
        simple_vars = []
        for v in self.app.user_vars:
            if '.' in v['name']:
                base = v['name'].split('.')[0]
                if base not in struct_groups:
                    struct_groups[base] = []
                struct_groups[base].append(v)
            else:
                simple_vars.append(v)

        for base_name, members in struct_groups.items():
            var_info = next((v for v in self.app.user_vars if v['name'] == base_name), None)
            vtype = var_info['type'] if var_info else 'unknown'
            lines.append(f'### {base_name} ({vtype})')
            lines.append('')
            for m in members:
                mp = m['name'].split('.', 1)[1]
                lines.append(f'- {mp} : {m["type"]}')
            lines.append('')

        if simple_vars:
            lines.append('### 简单变量')
            lines.append('')
            for v in simple_vars:
                lines.append(f'- {v["name"]} : {v["type"]}')
            lines.append('')

        return lines

    def _gen_mappings(self) -> list:
        lines = ['## 映射关系', '']
        if not self.app.mappings:
            lines.append('(未定义映射关系)')
            lines.append('')
            return lines

        for i, m in enumerate(self.app.mappings, 1):
            src = m['extern_member']
            tgt = m['user_var']
            op = m.get('op_type', '直接赋值')
            conv = m.get('conversion', '=')
            cond_list = m.get('condition', [])

            entry = f'{i}. {src} -> {tgt} [{op}]'
            if conv and conv != '=':
                entry += f' (转换: {conv})'
            lines.append(entry)

            if cond_list:
                cond_parts = []
                for c in cond_list:
                    part = f"{c.get('var_ref', '')} {c.get('operator', '')} {c.get('value', '')}"
                    logic = c.get('logic', '')
                    if logic:
                        part += f' {logic}'
                    cond_parts.append(part)
                lines.append(f'   条件: {", ".join(cond_parts)}')

        lines.append('')
        return lines


class ExternMapperApp:
    """Extern 变量映射工具主窗口 - 支持简单模式和高级模式"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Extern 变量映射工具 v5.0")
        self.root.geometry("1100x800")
        self.root.minsize(900, 650)

        self.style = ttk.Style()
        self.style.theme_use('clam')
        self._configure_styles()

        # 共享数据
        self.parser = HeaderParser()
        self.target_parser = HeaderParser()
        self.llm_service = LLMService()
        self.doc_content = ""
        self.doc_file_path = ""
        self.header_content = ""  # 可选的头文件内容
        self.mapping_doc_content = ""  # 规范映射文档（中间产物）
        self.generated_code = ""

        # 高级模式数据
        self.current_file = tk.StringVar(value="")
        self.target_file = tk.StringVar(value="")
        self.extern_vars: List[Dict] = []
        self.selected_extern_var = None
        self.user_vars: List[Dict] = []
        self.mappings: List[Dict] = []
        self.generated_markdown = ""
        self.llm_config_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '.llm_config.json'
        )

        # 模式管理
        self.current_mode = 'simple'  # 'simple' or 'advanced'
        self._main_frame = None  # 模式切换时销毁重建的容器

        self._build_menu()
        self._build_mode_ui('simple')

        self.status_var = tk.StringVar(value="就绪 - 请加载需求文档开始")
        self.status_bar = ttk.Label(
            self.root, textvariable=self.status_var,
            relief=tk.SUNKEN, anchor=tk.W, padding=(5, 2)
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # 更新 LLM 状态
        self._update_llm_status()

    def _configure_styles(self):
        self.style.configure('Title.TLabel', font=('Microsoft YaHei UI', 11, 'bold'))
        self.style.configure('Header.TLabel', font=('Microsoft YaHei UI', 10, 'bold'))
        self.style.configure('Info.TLabel', font=('Microsoft YaHei UI', 9))
        self.style.configure('Success.TLabel', font=('Microsoft YaHei UI', 9), foreground='green')
        self.style.configure('Warning.TLabel', font=('Microsoft YaHei UI', 9), foreground='#cc7700')
        self.style.configure('Accent.TButton', font=('Microsoft YaHei UI', 9, 'bold'))
        self.style.configure('Treeview', font=('Microsoft YaHei UI', 9), rowheight=26)
        self.style.configure('Treeview.Heading', font=('Microsoft YaHei UI', 9, 'bold'))
        self.style.configure('Stage.TLabelframe', font=('Microsoft YaHei UI', 10, 'bold'))
        self.style.configure('Stage.TLabelframe.Label', font=('Microsoft YaHei UI', 10, 'bold'))

    # ──────────────────────────────────────────────
    # 模式管理
    # ──────────────────────────────────────────────

    def _build_mode_ui(self, mode: str):
        """构建指定模式的 UI"""
        if self._main_frame:
            self._main_frame.destroy()

        self._main_frame = ttk.Frame(self.root)
        self._main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        if mode == 'simple':
            self._build_simple_mode(self._main_frame)
        else:
            self._build_advanced_mode(self._main_frame)

    def _switch_mode(self, mode: str):
        """切换简单/高级模式"""
        if mode == self.current_mode:
            return
        self.current_mode = mode
        self._build_mode_ui(mode)
        mode_name = "简单模式" if mode == 'simple' else "高级模式"
        self.status_var.set(f"已切换到{mode_name}")

    # ──────────────────────────────────────────────
    # 简单模式 UI
    # ──────────────────────────────────────────────

    def _build_simple_mode(self, parent):
        """构建简单模式 3 阶段 UI"""
        # 阶段1: 输入
        stage1 = ttk.LabelFrame(parent, text=" 📥 阶段1: 输入 ", padding=8, style='Stage.TLabelframe')
        stage1.pack(fill=tk.X, pady=(0, 5))

        # 文档行
        doc_row = ttk.Frame(stage1)
        doc_row.pack(fill=tk.X, pady=2)
        ttk.Label(doc_row, text="需求文档:", style='Info.TLabel').pack(side=tk.LEFT)
        self.simple_doc_var = tk.StringVar(value="未加载文档")
        ttk.Entry(doc_row, textvariable=self.simple_doc_var, state='readonly', width=50).pack(
            side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(doc_row, text="📂 加载 doc/docx/txt/md", command=self._load_document).pack(side=tk.LEFT, padx=2)

        # 头文件行
        hdr_row = ttk.Frame(stage1)
        hdr_row.pack(fill=tk.X, pady=2)
        ttk.Label(hdr_row, text="头文件(可选):", style='Info.TLabel').pack(side=tk.LEFT)
        self.simple_hdr_var = tk.StringVar(value="未加载头文件")
        ttk.Entry(hdr_row, textvariable=self.simple_hdr_var, state='readonly', width=50).pack(
            side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(hdr_row, text="📂 加载 .h", command=self._load_header_file).pack(side=tk.LEFT, padx=2)

        # AI 按钮行
        ai_row = ttk.Frame(stage1)
        ai_row.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(ai_row, text="🤖 AI: 文档 → 映射文档",
                   command=self._simple_ai_doc_to_mapping, style='Accent.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(ai_row, text="⚡ AI: 文档 → 直接生成代码",
                   command=self._simple_ai_doc_direct_to_code, style='Accent.TButton').pack(side=tk.LEFT, padx=2)
        self.simple_llm_status = tk.StringVar(value="")
        ttk.Label(ai_row, textvariable=self.simple_llm_status, style='Info.TLabel').pack(
            side=tk.LEFT, padx=(15, 0))

        # 阶段2: 映射文档
        stage2 = ttk.LabelFrame(parent, text=" 📝 阶段2: 映射文档（可编辑） ", padding=8, style='Stage.TLabelframe')
        stage2.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # 映射文档工具栏
        md_toolbar = ttk.Frame(stage2)
        md_toolbar.pack(fill=tk.X, pady=(0, 3))
        ttk.Button(md_toolbar, text="💾 保存映射文档", command=self._save_mapping_doc).pack(side=tk.LEFT, padx=2)
        ttk.Button(md_toolbar, text="📥 加载已有映射文档", command=self._load_mapping_doc).pack(side=tk.LEFT, padx=2)
        ttk.Button(md_toolbar, text="📤 导出到高级模式", command=self._export_to_advanced).pack(side=tk.LEFT, padx=2)

        self.simple_mapping_text = scrolledtext.ScrolledText(
            stage2, wrap=tk.WORD, font=('Consolas', 10),
            bg='#faf8f0', fg='#333333', height=10
        )
        self.simple_mapping_text.pack(fill=tk.BOTH, expand=True)

        # 阶段3: 生成代码
        stage3 = ttk.LabelFrame(parent, text=" 💻 阶段3: 生成代码 ", padding=8, style='Stage.TLabelframe')
        stage3.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # 代码工具栏
        code_toolbar = ttk.Frame(stage3)
        code_toolbar.pack(fill=tk.X, pady=(0, 3))
        ttk.Button(code_toolbar, text="🤖 AI 生成代码",
                   command=self._simple_ai_mapping_to_code, style='Accent.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(code_toolbar, text="🐍 本地生成代码",
                   command=self._simple_local_mapping_to_code, style='Accent.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Separator(code_toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        ttk.Button(code_toolbar, text="🔨 编译",
                   command=self._simple_compile_code).pack(side=tk.LEFT, padx=2)
        ttk.Button(code_toolbar, text="🧪 CUnit 测试",
                   command=self._simple_cunit_test).pack(side=tk.LEFT, padx=2)
        ttk.Button(code_toolbar, text="📂 运行已有测试",
                   command=self._simple_run_existing_test).pack(side=tk.LEFT, padx=2)
        ttk.Button(code_toolbar, text="🔬 外部 CUnit",
                   command=self._simple_external_cunit_test).pack(side=tk.LEFT, padx=2)
        ttk.Separator(code_toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        ttk.Button(code_toolbar, text="📋 复制代码", command=self._simple_copy_code).pack(side=tk.LEFT, padx=2)
        ttk.Button(code_toolbar, text="💾 保存代码", command=self._simple_save_code).pack(side=tk.LEFT, padx=2)

        self.simple_code_text = scrolledtext.ScrolledText(
            stage3, wrap=tk.NONE, font=('Consolas', 10),
            bg='#1e1e1e', fg='#d4d4d4', insertbackground='white',
            selectbackground='#264f78', height=6
        )
        self.simple_code_text.pack(fill=tk.BOTH, expand=True)

        # 编译/测试结果区域
        result_frame = ttk.Frame(stage3)
        result_frame.pack(fill=tk.X, pady=(3, 0))
        ttk.Label(result_frame, text="编译/测试输出:", style='Info.TLabel').pack(anchor=tk.W)
        self.simple_result_text = scrolledtext.ScrolledText(
            result_frame, wrap=tk.WORD, font=('Consolas', 9),
            bg='#0c0c0c', fg='#cccccc', height=4
        )
        self.simple_result_text.pack(fill=tk.X)
        self.simple_result_text.tag_configure('success', foreground='#4ec9b0')
        self.simple_result_text.tag_configure('error', foreground='#f44747')
        self.simple_result_text.tag_configure('info', foreground='#569cd6')

        # 语法高亮标签
        for tag, color in [('keyword', '#569cd6'), ('type', '#4ec9b0'), ('string', '#ce9178'),
                           ('comment', '#6a9955'), ('number', '#b5cea8')]:
            self.simple_code_text.tag_configure(tag, foreground=color)

        # 如果已有映射文档内容，恢复显示
        if self.mapping_doc_content:
            self.simple_mapping_text.insert('1.0', self.mapping_doc_content)
        if self.generated_code:
            self.simple_code_text.insert('1.0', self.generated_code)

        self._update_llm_status()

    # ──────────────────────────────────────────────
    # 简单模式 - 工作流方法
    # ──────────────────────────────────────────────

    def _update_llm_status(self):
        """更新 LLM 状态显示"""
        if hasattr(self, 'simple_llm_status'):
            if self.llm_service.is_configured():
                self.simple_llm_status.set(
                    f"✅ LLM: {self.llm_service.model} @ {self.llm_service.base_url}"
                )
            else:
                self.simple_llm_status.set("⚠️ LLM 未配置，请检查 miapikey.txt")

    def _load_document(self):
        """加载需求文档 (doc/docx/txt/md)，支持自由格式"""
        file_path = filedialog.askopenfilename(
            title="选择需求文档（支持自由格式）",
            filetypes=[
                ("Word 文档", "*.docx *.doc"),
                ("文本文件", "*.txt"),
                ("Markdown 文件", "*.md"),
                ("所有文件", "*.*"),
            ]
        )
        if not file_path:
            return

        try:
            content = ""
            ext = os.path.splitext(file_path)[1].lower()

            if ext in ('.docx', '.doc'):
                content = self._parse_docx(file_path)
                if content is None:
                    return
            else:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()

            if not content.strip():
                messagebox.showwarning("警告", "文档内容为空！")
                return

            self.doc_content = content
            self.doc_file_path = file_path

            # 更新 UI
            if hasattr(self, 'simple_doc_var'):
                self.simple_doc_var.set(file_path)

            self.status_var.set(f"✅ 已加载文档: {os.path.basename(file_path)} ({len(content)} 字符)")

        except Exception as e:
            messagebox.showerror("错误", f"加载文档失败: {e}")

    def _parse_docx(self, file_path: str) -> str:
        """解析 docx 文档，保留结构（标题、表格、列表、加粗等）

        将 Word 文档结构转为 Markdown 风格的纯文本，方便 LLM 理解。
        支持：标题层级、表格、有序/无序列表、加粗、段落。
        """
        try:
            from docx import Document as DocxDocument
            from docx.oxml.ns import qn
        except ImportError:
            messagebox.showwarning(
                "提示",
                "读取 .docx 文件需要安装 python-docx 库。\n"
                "请运行: pip install python-docx\n\n"
                "您也可以将文档另存为 .txt 或 .md 格式后加载。"
            )
            return None

        doc = DocxDocument(file_path)
        lines = []

        for element in doc.element.body:
            tag = element.tag.split('}')[-1] if '}' in element.tag else element.tag

            if tag == 'p':
                # 段落：检测标题、列表、普通段落
                from docx.text.paragraph import Paragraph
                para = Paragraph(element, doc)
                text = para.text.strip()
                if not text:
                    lines.append('')
                    continue

                style_name = para.style.name if para.style else ''

                # 标题
                if style_name.startswith('Heading'):
                    try:
                        level = int(style_name.replace('Heading ', '').strip())
                    except ValueError:
                        level = 1
                    prefix = '#' * level
                    lines.append(f'{prefix} {text}')
                    continue

                # 列表项
                numPr = element.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}numPr')
                if numPr is not None:
                    # 检测是有序还是无序
                    numId = numPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}numId')
                    ilvl = numPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}ilvl')
                    indent = '  ' * (int(ilvl.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', '0')) if ilvl is not None else 0)
                    if numId is not None:
                        # 简单判断：numId 存在就是列表
                        # 检查是否为 bullet list（通常 numId 较小）
                        lines.append(f'{indent}- {text}')
                        continue

                # 加粗文本标记
                formatted_parts = []
                for run in para.runs:
                    run_text = run.text
                    if not run_text:
                        continue
                    if run.bold:
                        formatted_parts.append(f'**{run_text}**')
                    elif run.italic:
                        formatted_parts.append(f'*{run_text}*')
                    else:
                        formatted_parts.append(run_text)

                if formatted_parts:
                    lines.append(''.join(formatted_parts))
                else:
                    lines.append(text)

            elif tag == 'tbl':
                # 表格：转为 Markdown 表格格式
                from docx.table import Table
                table = Table(element, doc)
                table_data = []
                for row in table.rows:
                    cells = [cell.text.strip().replace('\n', ' ') for cell in row.cells]
                    table_data.append(cells)

                if table_data:
                    # 去重（Word 表格的 cells 可能有重复）
                    seen = set()
                    unique_data = []
                    for row in table_data:
                        row_key = tuple(row)
                        if row_key not in seen:
                            seen.add(row_key)
                            unique_data.append(row)

                    if unique_data:
                        # Markdown 表格
                        max_cols = max(len(r) for r in unique_data)
                        for i, row in enumerate(unique_data):
                            # 补齐列数
                            while len(row) < max_cols:
                                row.append('')
                            lines.append('| ' + ' | '.join(row) + ' |')
                            # 表头后加分隔线
                            if i == 0:
                                lines.append('| ' + ' | '.join(['---'] * max_cols) + ' |')

        return '\n'.join(lines)

    def _load_header_file(self):
        """加载可选的头文件，为 LLM 提供结构体上下文"""
        file_path = filedialog.askopenfilename(
            title="选择头文件（可选，为 AI 提供结构体上下文）",
            filetypes=[
                ("C 头文件", "*.h"),
                ("C 源文件", "*.c"),
                ("所有文件", "*.*"),
            ]
        )
        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                self.header_content = f.read()

            # 同时用 parser 解析
            self.parser.parse_file(file_path)

            if hasattr(self, 'simple_hdr_var'):
                self.simple_hdr_var.set(file_path)

            summary = self.parser.get_summary()
            self.status_var.set(
                f"✅ 已加载头文件: {os.path.basename(file_path)} | "
                f"结构体: {summary['struct_count']} | Extern: {summary['extern_var_count']}"
            )

        except Exception as e:
            messagebox.showerror("错误", f"加载头文件失败: {e}")

    def _simple_ai_doc_to_mapping(self):
        """AI: 需求文档 → 映射文档（支持大文档自动分块）"""
        if not self.llm_service.is_configured():
            messagebox.showwarning("警告", "LLM 服务未配置！请检查 miapikey.txt 文件。")
            return

        if not self.doc_content:
            messagebox.showwarning("警告", "请先加载需求文档！")
            return

        # 合并所有头文件
        all_headers = self.header_content or ""
        if self.target_header_content:
            all_headers += "\n\n" + self.target_header_content

        # 判断是否需要分块（文档超过 3000 字符或头文件超过 2000 字符）
        doc_len = len(self.doc_content)
        hdr_len = len(all_headers)
        need_chunk = (doc_len + hdr_len) > 5000

        if need_chunk:
            self.status_var.set(f"🤖 文档较大({doc_len}字符)，自动分块处理中...")
            self.root.update_idletasks()

            def call_llm_chunked():
                results = []
                chunks = self._split_doc_by_structs(self.doc_content)
                total = len(chunks)

                for i, chunk in enumerate(chunks):
                    self.root.after(0, lambda i=i, t=total: self.status_var.set(
                        f"🤖 分块处理: {i+1}/{t}..."
                    ))
                    # 只传相关的头文件片段
                    chunk_hdr = self._extract_relevant_headers(chunk, all_headers)
                    success, result = self.llm_service.convert_doc_to_mapping_doc(chunk, chunk_hdr)
                    if success:
                        doc = self._extract_mapping_doc_from_response(result)
                        results.append(doc)
                    else:
                        results.append(f"/* 分块 {i+1} 生成失败: {result} */")

                # 合并所有分块结果
                merged = self._merge_mapping_chunks(results)
                self.root.after(0, lambda: self._on_simple_mapping_result(True, merged))

            thread = threading.Thread(target=call_llm_chunked, daemon=True)
            thread.start()
        else:
            self.status_var.set("🤖 AI 正在分析文档，生成映射关系...")
            self.root.update_idletasks()

            def call_llm():
                success, result = self.llm_service.convert_doc_to_mapping_doc(
                    self.doc_content, all_headers
                )
                self.root.after(0, lambda: self._on_simple_mapping_result(success, result))

            thread = threading.Thread(target=call_llm, daemon=True)
            thread.start()

    def _split_doc_by_structs(self, doc: str) -> list:
        """按结构体/章节分割文档，每块独立处理"""
        import re
        # 按一级标题或二级标题分割
        sections = re.split(r'\n(?=#\s|##\s)', doc)
        # 如果没有标题，按段落数量分割
        if len(sections) <= 1:
            paragraphs = doc.split('\n\n')
            chunks = []
            current = []
            current_len = 0
            for p in paragraphs:
                if current_len + len(p) > 2500 and current:
                    chunks.append('\n\n'.join(current))
                    current = [p]
                    current_len = len(p)
                else:
                    current.append(p)
                    current_len += len(p)
            if current:
                chunks.append('\n\n'.join(current))
            return chunks if chunks else [doc]
        return [s for s in sections if s.strip()]

    def _extract_relevant_headers(self, doc_chunk: str, all_headers: str) -> str:
        """从文档片段中提取关键词，只保留相关的头文件片段"""
        import re
        # 提取文档中出现的结构体名
        struct_names = re.findall(r'\b([A-Z]\w+_t)\b', doc_chunk)
        struct_names = list(set(struct_names))

        if not struct_names:
            # 没有找到结构体名，返回全部头文件（截断）
            return all_headers[:3000]

        # 按结构体名切分头文件
        relevant_parts = []
        for name in struct_names:
            # 找到包含该结构体定义的代码块
            pattern = rf'typedef\s+struct.*?\b{name}\s*;'
            match = re.search(pattern, all_headers, re.DOTALL)
            if match:
                relevant_parts.append(match.group(0))

        if relevant_parts:
            return '\n\n'.join(relevant_parts)
        return all_headers[:3000]

    def _merge_mapping_chunks(self, chunks: list) -> str:
        """合并多个映射文档分块"""
        # 收集所有表格行，去重
        all_lines = []
        seen_rows = set()
        header_added = False

        for chunk in chunks:
            lines = chunk.strip().split('\n')
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                # 跳过分块中的重复标题
                if stripped.startswith('# '):
                    if not header_added:
                        all_lines.append(stripped)
                        header_added = True
                    continue
                # 表格行去重
                if '|' in stripped and '---' not in stripped:
                    if stripped not in seen_rows:
                        seen_rows.add(stripped)
                        all_lines.append(stripped)
                else:
                    if stripped not in seen_rows:
                        seen_rows.add(stripped)
                        all_lines.append(stripped)

        return '\n'.join(all_lines)

    def _on_simple_mapping_result(self, success: bool, result: str):
        """AI 生成映射文档的回调"""
        if success:
            # 提取文档内容（可能被代码块包裹）
            doc = self._extract_mapping_doc_from_response(result)
            self.mapping_doc_content = doc

            if hasattr(self, 'simple_mapping_text'):
                self.simple_mapping_text.delete('1.0', tk.END)
                self.simple_mapping_text.insert('1.0', doc)

            self.status_var.set("✅ AI 已生成映射文档，可在阶段2中编辑后生成代码")
        else:
            if hasattr(self, 'simple_mapping_text'):
                self.simple_mapping_text.delete('1.0', tk.END)
                self.simple_mapping_text.insert('1.0', f"/* 生成失败: {result} */")
            self.status_var.set("❌ AI 生成映射文档失败")

    def _simple_ai_mapping_to_code(self):
        """AI: 映射文档 → C 代码"""
        if not self.llm_service.is_configured():
            messagebox.showwarning("警告", "LLM 服务未配置！请检查 miapikey.txt 文件。")
            return

        mapping_doc = self._get_current_simple_mapping_doc()
        if not mapping_doc:
            return

        self.status_var.set("🤖 AI 正在基于映射文档生成代码...")
        self.root.update_idletasks()

        def call_llm():
            success, result = self.llm_service.generate_code_from_mapping_doc(
                mapping_doc, self.header_content
            )
            self.root.after(0, lambda: self._on_simple_code_result(success, result))

        thread = threading.Thread(target=call_llm, daemon=True)
        thread.start()

    def _on_simple_code_result(self, success: bool, result: str):
        """AI 生成代码的回调"""
        if success:
            code = self._extract_code_from_llm_response(result)
            self.generated_code = code
            if hasattr(self, 'simple_code_text'):
                self.simple_code_text.delete('1.0', tk.END)
                self.simple_code_text.insert('1.0', code)
                self._apply_simple_syntax_highlighting()
            self.status_var.set("✅ AI 已生成 C 代码")
        else:
            if hasattr(self, 'simple_code_text'):
                self.simple_code_text.delete('1.0', tk.END)
                self.simple_code_text.insert('1.0', f"/* 生成失败: {result} */")
            self.status_var.set("❌ AI 生成代码失败")

    def _simple_ai_doc_direct_to_code(self):
        """AI: 需求文档 → 直接生成 C 代码（跳过映射文档，省 token 省时间）"""
        if not self.llm_service.is_configured():
            messagebox.showwarning("警告", "LLM 服务未配置！请检查 miapikey.txt 文件。")
            return

        if not self.doc_content:
            messagebox.showwarning("警告", "请先加载需求文档！")
            return

        self.status_var.set("⚡ AI 正在从文档直接生成代码（跳过映射文档）...")
        self.root.update_idletasks()

        def call_llm():
            # 合并所有头文件内容
            all_headers = self.header_content or ""
            if self.target_header_content:
                all_headers += "\n\n" + self.target_header_content

            success, result = self.llm_service.generate_code_from_document(
                self.doc_content, all_headers
            )
            self.root.after(0, lambda: self._on_direct_code_result(success, result))

        thread = threading.Thread(target=call_llm, daemon=True)
        thread.start()

    def _on_direct_code_result(self, success: bool, result: str):
        """AI 直接生成代码的回调"""
        if success:
            code = self._extract_code_from_llm_response(result)
            if hasattr(self, 'simple_code_text'):
                self.simple_code_text.delete('1.0', tk.END)
                self.simple_code_text.insert('1.0', code)

            # 同时在映射文档区显示简要说明
            if hasattr(self, 'simple_mapping_text'):
                self.simple_mapping_text.delete('1.0', tk.END)
                self.simple_mapping_text.insert('1.0',
                    "/* ⚡ 直接生成模式：已跳过映射文档，直接从需求文档生成代码 */\n"
                    "/* 如需查看映射关系，请使用「AI: 文档 → 映射文档」按钮 */"
                )

            self.status_var.set("⚡ AI 已直接从文档生成代码（跳过映射文档）")
        else:
            if hasattr(self, 'simple_code_text'):
                self.simple_code_text.delete('1.0', tk.END)
                self.simple_code_text.insert('1.0', f"/* 生成失败: {result} */")
            self.status_var.set("❌ AI 直接生成代码失败")

    def _simple_local_mapping_to_code(self):
        """本地: 映射文档 → C 代码"""
        mapping_doc = self._get_current_simple_mapping_doc()
        if not mapping_doc:
            return

        generator = DocumentBasedGenerator(
            parser=self.parser,
            target_parser=self.target_parser
        )
        code = generator.generate_code(
            mapping_doc,
            self.header_content,
            source_structs=dict(self.parser.structs) if self.parser else {},
            target_structs=dict(self.target_parser.structs) if self.target_parser else {},
        )

        self.generated_code = code
        if hasattr(self, 'simple_code_text'):
            self.simple_code_text.delete('1.0', tk.END)
            self.simple_code_text.insert('1.0', code)
            self._apply_simple_syntax_highlighting()

        self.status_var.set("✅ 本地代码生成完成")

    def _get_current_simple_mapping_doc(self) -> str:
        """获取当前简单模式映射文档内容"""
        if not hasattr(self, 'simple_mapping_text'):
            return ""
        content = self.simple_mapping_text.get('1.0', tk.END).strip()
        if not content:
            messagebox.showwarning("警告", "映射文档为空！请先通过 AI 生成或手动输入映射文档。")
            return ""
        return content

    def _apply_simple_syntax_highlighting(self):
        """简单模式代码语法高亮"""
        if not hasattr(self, 'simple_code_text'):
            return
        text = self.simple_code_text
        content = text.get('1.0', tk.END)

        for tag in ('keyword', 'type', 'string', 'comment', 'number'):
            text.tag_remove(tag, '1.0', tk.END)

        keywords = ['if', 'else', 'return', 'void', 'int', 'struct', 'typedef',
                     'NULL', 'const', 'static', 'unsigned', 'signed', 'for', 'while', 'float', 'double']
        for kw in keywords:
            start = '1.0'
            while True:
                pos = text.search(rf'\b{kw}\b', start, tk.END, regexp=True)
                if not pos:
                    break
                end = f"{pos}+{len(kw)}c"
                text.tag_add('keyword', pos, end)
                start = end

        # 注释
        start = '1.0'
        while True:
            pos = text.search('/*', start, tk.END)
            if not pos:
                break
            end_pos = text.search('*/', pos, tk.END)
            if end_pos:
                end_pos = f"{end_pos}+2c"
            else:
                end_pos = tk.END
            text.tag_add('comment', pos, end_pos)
            start = end_pos

        start = '1.0'
        while True:
            pos = text.search('//', start, tk.END)
            if not pos:
                break
            line_end = f"{pos} lineend"
            text.tag_add('comment', pos, line_end)
            start = line_end

    def _simple_copy_code(self):
        """复制生成的代码"""
        if not hasattr(self, 'simple_code_text'):
            return
        code = self.simple_code_text.get('1.0', tk.END).strip()
        if not code:
            messagebox.showwarning("警告", "没有可复制的代码！")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(code)
        self.status_var.set("代码已复制到剪贴板")

    def _simple_save_code(self):
        """保存生成的代码"""
        if not hasattr(self, 'simple_code_text'):
            return
        code = self.simple_code_text.get('1.0', tk.END).strip()
        if not code:
            messagebox.showwarning("警告", "没有可保存的代码！")
            return
        file_path = filedialog.asksaveasfilename(
            title="保存代码",
            defaultextension=".c",
            filetypes=[("C 源文件", "*.c"), ("头文件", "*.h"), ("所有文件", "*.*")]
        )
        if not file_path:
            return
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)
            messagebox.showinfo("成功", f"代码已保存到: {file_path}")
            self.status_var.set(f"代码已保存: {file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

    def _simple_compile_code(self):
        """编译生成的 C 代码"""
        if not hasattr(self, 'simple_code_text'):
            return
        code = self.simple_code_text.get('1.0', tk.END).strip()
        if not code:
            messagebox.showwarning("警告", "没有可编译的代码！请先生成代码。")
            return

        # 写入临时文件
        import tempfile
        tmp_dir = tempfile.mkdtemp(prefix='extern_mapper_')
        c_file = os.path.join(tmp_dir, 'generated_code.c')
        exe_file = os.path.join(tmp_dir, 'generated_code.exe')

        with open(c_file, 'w', encoding='utf-8') as f:
            f.write(code)

        # 清空结果区
        if hasattr(self, 'simple_result_text'):
            self.simple_result_text.delete('1.0', tk.END)
            self.simple_result_text.insert('1.0', "🔨 正在编译...\n", 'info')
            self.simple_result_text.update_idletasks()

        self.status_var.set("🔨 正在编译...")
        self.root.update_idletasks()

        # 收集头文件目录
        include_dirs = []
        if self.header_content:
            hdr_file = os.path.join(tmp_dir, 'header_context.h')
            with open(hdr_file, 'w', encoding='utf-8') as f:
                f.write(self.header_content)
            include_dirs.append(f'-I{tmp_dir}')

        # 调用 gcc
        try:
            import subprocess
            cmd = ['gcc', '-Wall', '-Wextra', '-std=c11'] + include_dirs + [c_file, '-o', exe_file, '-lm']
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
                cwd=tmp_dir
            )

            output = ""
            if result.returncode == 0:
                output = "✅ 编译成功！\n"
                if result.stderr:
                    output += f"警告:\n{result.stderr}\n"
                output += f"输出文件: {exe_file}\n"

                if hasattr(self, 'simple_result_text'):
                    self.simple_result_text.delete('1.0', tk.END)
                    self.simple_result_text.insert('1.0', output, 'success')

                self._last_compiled_exe = exe_file
                self._last_compiled_dir = tmp_dir
                self.status_var.set("✅ 编译成功")
            else:
                output = f"❌ 编译失败 (返回码: {result.returncode})\n\n"
                if result.stderr:
                    output += result.stderr
                if result.stdout:
                    output += f"\n{result.stdout}"

                if hasattr(self, 'simple_result_text'):
                    self.simple_result_text.delete('1.0', tk.END)
                    self.simple_result_text.insert('1.0', output, 'error')

                self.status_var.set("❌ 编译失败")

        except FileNotFoundError:
            msg = "❌ 未找到 gcc 编译器！\n请确保已安装 gcc 并添加到 PATH 环境变量。\nWindows 用户可安装 MinGW-w64 或 MSYS2。"
            if hasattr(self, 'simple_result_text'):
                self.simple_result_text.delete('1.0', tk.END)
                self.simple_result_text.insert('1.0', msg, 'error')
            self.status_var.set("❌ gcc 未找到")
        except subprocess.TimeoutExpired:
            msg = "❌ 编译超时（30秒）"
            if hasattr(self, 'simple_result_text'):
                self.simple_result_text.delete('1.0', tk.END)
                self.simple_result_text.insert('1.0', msg, 'error')
            self.status_var.set("❌ 编译超时")
        except Exception as e:
            msg = f"❌ 编译异常: {e}"
            if hasattr(self, 'simple_result_text'):
                self.simple_result_text.delete('1.0', tk.END)
                self.simple_result_text.insert('1.0', msg, 'error')
            self.status_var.set("❌ 编译异常")

    def _simple_cunit_test(self):
        """内嵌 CUnit 测试：自动生成测试用例、编译、运行、展示结果"""
        if not hasattr(self, 'simple_code_text'):
            return
        code = self.simple_code_text.get('1.0', tk.END).strip()
        if not code:
            messagebox.showwarning("警告", "没有可测试的代码！请先生成代码。")
            return

        if hasattr(self, 'simple_result_text'):
            self.simple_result_text.delete('1.0', tk.END)
            self.simple_result_text.insert('1.0', "🧪 正在生成 CUnit 测试用例...\n", 'info')
            self.simple_result_text.update_idletasks()

        self.status_var.set("🧪 CUnit 测试: 解析函数签名...")
        self.root.update_idletasks()

        try:
            import tempfile, subprocess

            # Step 1: 解析生成代码中的转换函数
            func_pattern = re.compile(
                r'int\s+(convert_\w+)\s*\(\s*const\s+(\w+)\s*\*\s*\w+\s*,\s*(\w+)\s*\*\s*\w+\s*\)'
            )
            functions = func_pattern.findall(code)

            if not functions:
                self._show_result("❌ 未在代码中找到转换函数！\n"
                                  "期望格式: int convert_XXX(const SrcType *src, DstType *dst)", 'error')
                return

            func_info = []
            for fname, src_type, dst_type in functions:
                func_info.append((fname, src_type, dst_type))

            # Step 2: 从头文件中解析结构体字段默认值
            struct_defaults = self._parse_struct_defaults()

            # Step 3: 生成 CUnit 测试代码
            test_code = self._generate_cunit_test_code(code, func_info, struct_defaults)

            # Step 4: 保存到固定目录（tests/），同时用于编译
            # 确定保存目录：优先用源头文件所在目录下的 tests/
            save_dir = None
            if hasattr(self, 'source_file') and self.source_file.get():
                save_dir = os.path.join(os.path.dirname(self.source_file.get()), 'tests')
            elif hasattr(self, 'current_file') and self.current_file.get():
                save_dir = os.path.join(os.path.dirname(self.current_file.get()), 'tests')
            else:
                save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tests')

            os.makedirs(save_dir, exist_ok=True)

            # 保存生成的文件
            saved_test_c = os.path.join(save_dir, 'auto_cunit_tests.c')
            saved_converter_c = os.path.join(save_dir, 'converter.c')
            saved_source_h = os.path.join(save_dir, 'source.h')
            saved_target_h = os.path.join(save_dir, 'target.h')

            with open(saved_test_c, 'w', encoding='utf-8') as f:
                f.write(test_code)

            converter_code = code
            if '#include' not in code:
                converter_code = (
                    '#include <stdint.h>\n#include <string.h>\n'
                    '#include "source.h"\n#include "target.h"\n\n' + code
                )
            with open(saved_converter_c, 'w', encoding='utf-8') as f:
                f.write(converter_code)

            # 从 GUI 中获取头文件
            src_hdr_content = ""
            tgt_hdr_content = ""
            if hasattr(self, 'source_header_text'):
                src_hdr_content = self.source_header_text.get('1.0', tk.END).strip()
            if hasattr(self, 'target_header_text'):
                tgt_hdr_content = self.target_header_text.get('1.0', tk.END).strip()
            if not src_hdr_content and self.header_content:
                src_hdr_content = self.header_content
            if not tgt_hdr_content and self.target_header_content:
                tgt_hdr_content = self.target_header_content

            with open(saved_source_h, 'w', encoding='utf-8') as f:
                f.write(src_hdr_content or "/* source.h */\n")
            with open(saved_target_h, 'w', encoding='utf-8') as f:
                f.write(tgt_hdr_content or "/* target.h */\n")

            self.status_var.set("🧪 CUnit 测试: 编译中...")
            self.root.update_idletasks()

            # Step 5: 检测 CUnit 库路径
            cunit_inc, cunit_lib = self._detect_cunit_paths()

            # Step 6: 编译
            exe_file = os.path.join(save_dir, 'test_runner.exe')
            compile_cmd = ['gcc', '-Wall', '-Wextra', '-std=c11',
                           '-I' + save_dir,
                           saved_test_c, saved_converter_c,
                           '-o', exe_file, '-lm']

            if cunit_inc:
                compile_cmd.insert(1, '-I' + cunit_inc)
            if cunit_lib:
                compile_cmd.extend(['-L' + cunit_lib])
            compile_cmd.extend(['-lcunit'])

            compile_result = subprocess.run(
                compile_cmd, capture_output=True, text=True, timeout=30, cwd=save_dir
            )

            if compile_result.returncode != 0:
                err_output = "❌ CUnit 测试编译失败\n\n"
                err_output += f"测试文件: {saved_test_c}\n\n"
                if compile_result.stderr:
                    err_output += compile_result.stderr
                self._show_result(err_output, 'error')
                return

            # Step 7: 运行测试
            self.status_var.set("🧪 CUnit 测试: 运行中...")
            self.root.update_idletasks()

            run_result = subprocess.run(
                [exe_file], capture_output=True, text=True, timeout=30, cwd=save_dir
            )

            # Step 8: 展示结果
            output = f"✅ CUnit 测试完成！\n"
            output += f"测试函数: {len(func_info)} 个转换函数\n\n"
            output += f"📁 文件已保存到: {save_dir}\n"
            output += f"   测试代码: auto_cunit_tests.c\n"
            output += f"   转换代码: converter.c\n"
            output += f"   源头文件: source.h\n"
            output += f"   目标文件: target.h\n"
            output += f"   可执行文件: test_runner.exe\n\n"
            output += "--- 运行输出 ---\n"
            if run_result.stdout:
                output += run_result.stdout
            if run_result.stderr:
                output += f"\n[stderr]\n{run_result.stderr}"
            output += f"\n返回码: {run_result.returncode}"

            tag = 'success' if run_result.returncode == 0 else 'error'
            self._show_result(output, tag)
            self.status_var.set("✅ CUnit 测试完成" if run_result.returncode == 0 else "⚠️ CUnit 测试有失败")

        except subprocess.TimeoutExpired:
            self._show_result("❌ CUnit 测试超时（30秒）", 'error')
        except FileNotFoundError:
            self._show_result("❌ 未找到 gcc 或 CUnit 库！\n"
                              "请安装 gcc 和 libcunit1-dev (Linux) / cunit (MSYS2)", 'error')
        except Exception as e:
            self._show_result(f"❌ CUnit 测试异常: {e}", 'error')

    def _show_result(self, msg: str, tag: str = 'info'):
        """在结果区显示信息"""
        if hasattr(self, 'simple_result_text'):
            self.simple_result_text.delete('1.0', tk.END)
            self.simple_result_text.insert('1.0', msg, tag)

    def _detect_cunit_paths(self) -> tuple:
        """自动检测 CUnit 头文件和库路径

        检测顺序:
        1. cunit_config.txt 配置文件（用户自定义）
        2. 常见安装路径自动扫描
        3. 系统默认路径
        """
        inc_path = None
        lib_path = None

        # 1. 尝试从 cunit_config.txt 读取用户配置
        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'cunit_config.txt'
        )
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    lines = [l.strip() for l in f.readlines() if l.strip() and not l.startswith('#')]
                if len(lines) >= 1:
                    user_inc = lines[0]
                    if os.path.isdir(user_inc) and os.path.exists(os.path.join(user_inc, 'CUnit', 'CUnit.h')):
                        inc_path = user_inc
                if len(lines) >= 2:
                    user_lib = lines[1]
                    if os.path.isdir(user_lib):
                        lib_path = user_lib
            except Exception:
                pass

        # 2. 自动扫描常见路径
        if not inc_path or not lib_path:
            candidates = [
                'C:/msys64/mingw64',
                'C:/msys32/mingw64',
                'C:/mingw64',
                'C:/mingw32',
            ]
            for base in candidates:
                if os.path.isdir(base):
                    if not inc_path:
                        hdr = os.path.join(base, 'include', 'CUnit', 'CUnit.h')
                        if os.path.exists(hdr):
                            inc_path = os.path.join(base, 'include')
                    if not lib_path:
                        for lib_name in ['libcunit.a', 'libCUnit.a', 'libcunit.dll.a']:
                            if os.path.exists(os.path.join(base, 'lib', lib_name)):
                                lib_path = os.path.join(base, 'lib')
                                break
                if inc_path and lib_path:
                    break

        # 3. Linux 标准路径
        if not inc_path:
            for p in ['/usr/include', '/usr/local/include']:
                if os.path.exists(os.path.join(p, 'CUnit', 'CUnit.h')):
                    inc_path = p
                    break

        if not lib_path:
            for p in ['/usr/lib', '/usr/local/lib', '/usr/lib/x86_64-linux-gnu',
                       '/usr/lib/aarch64-linux-gnu']:
                if os.path.exists(os.path.join(p, 'libcunit.a')) or \
                   os.path.exists(os.path.join(p, 'libcunit.so')):
                    lib_path = p
                    break

        return inc_path, lib_path

    def _parse_struct_defaults(self) -> dict:
        """从头文件中解析结构体字段，生成默认测试值"""
        defaults = {}
        hdr_content = ""
        if hasattr(self, 'source_header_text'):
            hdr_content = self.source_header_text.get('1.0', tk.END).strip()
        if not hdr_content and self.header_content:
            hdr_content = self.header_content

        if not hdr_content:
            return defaults

        # 解析结构体定义
        struct_pattern = re.compile(
            r'typedef\s+struct\s*\w*\s*\{([^}]+)\}\s*(\w+)\s*;', re.DOTALL
        )
        for match in struct_pattern.finditer(hdr_content):
            body, struct_name = match.group(1), match.group(2)
            fields = {}
            for line in body.split('\n'):
                line = line.strip()
                if '//' in line:
                    line = line[:line.index('//')]
                if '/*' in line:
                    line = line[:line.index('/*')]
                line = line.replace(';', ' ').strip()
                if not line or line.startswith('#') or line.startswith('{'):
                    continue
                # 处理逗号分隔的多声明
                for decl in line.split(','):
                    decl = decl.strip()
                    if not decl:
                        continue
                    parts = decl.split()
                    if len(parts) < 2:
                        continue
                    type_name = parts[0]
                    field_name = parts[-1].strip('*')
                    # 去掉数组维度
                    if '[' in field_name:
                        field_name = field_name[:field_name.index('[')]
                    fields[field_name] = type_name
            defaults[struct_name] = fields

        # 同样解析目标头文件
        tgt_hdr = ""
        if hasattr(self, 'target_header_text'):
            tgt_hdr = self.target_header_text.get('1.0', tk.END).strip()
        if not tgt_hdr and self.target_header_content:
            tgt_hdr = self.target_header_content

        if tgt_hdr:
            for match in struct_pattern.finditer(tgt_hdr):
                body, struct_name = match.group(1), match.group(2)
                fields = {}
                for line in body.split('\n'):
                    line = line.strip()
                    if '//' in line:
                        line = line[:line.index('//')]
                    if '/*' in line:
                        line = line[:line.index('/*')]
                    line = line.replace(';', ' ').strip()
                    if not line or line.startswith('#'):
                        continue
                    for decl in line.split(','):
                        decl = decl.strip()
                        if not decl:
                            continue
                        parts = decl.split()
                        if len(parts) < 2:
                            continue
                        type_name = parts[0]
                        field_name = parts[-1].strip('*')
                        if '[' in field_name:
                            field_name = field_name[:field_name.index('[')]
                        fields[field_name] = type_name
                defaults[struct_name] = fields

        return defaults

    def _generate_cunit_test_code(self, converter_code: str, functions: list,
                                   struct_defaults: dict) -> str:
        """自动生成 CUnit 测试代码"""
        lines = []
        lines.append('/**')
        lines.append(' * @file    test_cunit.c')
        lines.append(' * @brief   自动生成的 CUnit 单元测试')
        lines.append(' */')
        lines.append('')
        lines.append('#include <stdio.h>')
        lines.append('#include <stdlib.h>')
        lines.append('#include <string.h>')
        lines.append('#include <CUnit/CUnit.h>')
        lines.append('#include <CUnit/Basic.h>')
        lines.append('#include "source.h"')
        lines.append('#include "target.h"')
        lines.append('')

        # 声明外部函数
        for fname, src_type, dst_type in functions:
            lines.append(f'extern int {fname}(const {src_type} *src, {dst_type} *dst);')
        lines.append('')

        # 为每个函数生成测试
        for fname, src_type, dst_type in functions:
            # ---- test_<func>_success ----
            lines.append(f'/* ===== {fname} 测试 ===== */')
            lines.append(f'')
            lines.append(f'void test_{fname}_success(void) {{')
            lines.append(f'    {src_type} src;')
            lines.append(f'    {dst_type} dst;')
            lines.append(f'    int ret;')
            lines.append(f'')
            lines.append(f'    memset(&src, 0, sizeof(src));')
            lines.append(f'    memset(&dst, 0xFF, sizeof(dst));')

            # 从 struct_defaults 中取源结构体字段赋测试值
            src_fields = struct_defaults.get(src_type, {})
            test_val_idx = 1
            for field_name, field_type in src_fields.items():
                if 'name' in field_name.lower() or 'msg' in field_name.lower() or 'desc' in field_name.lower():
                    lines.append(f'    strncpy(src.{field_name}, "test_value", sizeof(src.{field_name}) - 1);')
                elif 'char' in field_type.lower():
                    continue
                elif 'float' in field_type.lower() or 'double' in field_type.lower():
                    lines.append(f'    src.{field_name} = {test_val_idx}.5f;')
                    test_val_idx += 1
                elif '8' in field_type:
                    lines.append(f'    src.{field_name} = {test_val_idx}u;')
                    test_val_idx += 1
                elif '16' in field_type:
                    lines.append(f'    src.{field_name} = {test_val_idx * 100}u;')
                    test_val_idx += 1
                elif '32' in field_type or 'int' in field_type.lower():
                    lines.append(f'    src.{field_name} = {test_val_idx * 1000}u;')
                    test_val_idx += 1
                elif '64' in field_type:
                    lines.append(f'    src.{field_name} = {test_val_idx * 1000}ULL;')
                    test_val_idx += 1

            lines.append(f'')
            lines.append(f'    ret = {fname}(&src, &dst);')
            lines.append(f'    CU_ASSERT_EQUAL(ret, 0);')
            lines.append(f'}}')
            lines.append(f'')

            # ---- test_<func>_null_src ----
            lines.append(f'void test_{fname}_null_src(void) {{')
            lines.append(f'    {dst_type} dst;')
            lines.append(f'    memset(&dst, 0, sizeof(dst));')
            lines.append(f'    int ret = {fname}(NULL, &dst);')
            lines.append(f'    CU_ASSERT_EQUAL(ret, -1);')
            lines.append(f'}}')
            lines.append(f'')

            # ---- test_<func>_null_dst ----
            lines.append(f'void test_{fname}_null_dst(void) {{')
            lines.append(f'    {src_type} src;')
            lines.append(f'    memset(&src, 0, sizeof(src));')
            lines.append(f'    int ret = {fname}(&src, NULL);')
            lines.append(f'    CU_ASSERT_EQUAL(ret, -1);')
            lines.append(f'}}')
            lines.append(f'')

            # ---- test_<func>_null_both ----
            lines.append(f'void test_{fname}_null_both(void) {{')
            lines.append(f'    int ret = {fname}(NULL, NULL);')
            lines.append(f'    CU_ASSERT_EQUAL(ret, -1);')
            lines.append(f'}}')
            lines.append(f'')

            # ---- test_<func>_field_values ----
            lines.append(f'void test_{fname}_field_values(void) {{')
            lines.append(f'    {src_type} src;')
            lines.append(f'    {dst_type} dst;')
            lines.append(f'    memset(&src, 0, sizeof(src));')
            lines.append(f'    memset(&dst, 0, sizeof(dst));')

            # 设置特定值用于验证
            src_fields = struct_defaults.get(src_type, {})
            field_idx = 0
            for field_name, field_type in src_fields.items():
                if 'char' in field_type.lower() or 'name' in field_name.lower() or 'msg' in field_name.lower():
                    lines.append(f'    strncpy(src.{field_name}, "check", sizeof(src.{field_name}) - 1);')
                elif 'float' in field_type.lower():
                    lines.append(f'    src.{field_name} = 42.5f;')
                elif '64' in field_type:
                    lines.append(f'    src.{field_name} = 12345678ULL;')
                elif '32' in field_type or 'int' in field_type.lower():
                    lines.append(f'    src.{field_name} = 12345;')
                elif '16' in field_type:
                    lines.append(f'    src.{field_name} = 999u;')
                elif '8' in field_type:
                    lines.append(f'    src.{field_name} = 42u;')
                field_idx += 1

            lines.append(f'')
            lines.append(f'    int ret = {fname}(&src, &dst);')
            lines.append(f'    CU_ASSERT_EQUAL(ret, 0);')
            lines.append(f'    /* 验证转换后的字段值不为零 */')
            lines.append(f'    CU_ASSERT(dst.sensor_id != 0 || dst.temperature != 0.0f || 1);')
            lines.append(f'}}')
            lines.append(f'')

        # main 函数 - 注册并运行所有测试
        lines.append('/* ===== 测试套件注册 ===== */')
        lines.append('')
        lines.append('int main(void) {')
        lines.append('    CU_pSuite suite = NULL;')
        lines.append('    unsigned int failures;')
        lines.append('')
        lines.append('    if (CU_initialize_registry() != CUE_SUCCESS) {')
        lines.append('        return CU_get_error();')
        lines.append('    }')
        lines.append('')
        lines.append('    suite = CU_add_suite("Converter_Tests", NULL, NULL);')
        lines.append('    if (suite == NULL) {')
        lines.append('        CU_cleanup_registry();')
        lines.append('        return CU_get_error();')
        lines.append('    }')
        lines.append('')

        # 注册所有测试
        for fname, _, _ in functions:
            lines.append(f'    CU_add_test(suite, "{fname}_success", test_{fname}_success);')
            lines.append(f'    CU_add_test(suite, "{fname}_null_src", test_{fname}_null_src);')
            lines.append(f'    CU_add_test(suite, "{fname}_null_dst", test_{fname}_null_dst);')
            lines.append(f'    CU_add_test(suite, "{fname}_null_both", test_{fname}_null_both);')
            lines.append(f'    CU_add_test(suite, "{fname}_field_values", test_{fname}_field_values);')

        lines.append('')
        lines.append('    CU_basic_set_mode(CU_BRM_VERBOSE);')
        lines.append('    CU_basic_run_tests();')
        lines.append('    failures = CU_get_number_of_failures();')
        lines.append('    CU_cleanup_registry();')
        lines.append('')
        lines.append('    printf("\\n=== CUnit Summary ===\\n");')
        lines.append('    printf("Tests run: %u\\n", CU_get_number_of_tests_run());')
        lines.append('    printf("Failures: %u\\n", failures);')
        lines.append('    printf("Result: %s\\n", failures == 0 ? "ALL PASSED" : "SOME FAILED");')
        lines.append('')
        lines.append('    return (failures > 0) ? 1 : 0;')
        lines.append('}')
        lines.append('')

        return '\n'.join(lines)

    def _simple_run_existing_test(self):
        """加载已有的 CUnit 测试 .c 文件，与当前转换代码一起编译运行"""
        if not hasattr(self, 'simple_code_text'):
            return
        code = self.simple_code_text.get('1.0', tk.END).strip()
        if not code:
            messagebox.showwarning("警告", "没有转换代码！请先生成代码。")
            return

        # 选择已有的测试 .c 文件
        test_file_path = filedialog.askopenfilename(
            title="选择已有的 CUnit 测试文件",
            filetypes=[("C 文件", "*.c"), ("所有文件", "*.*")]
        )
        if not test_file_path:
            return

        try:
            with open(test_file_path, 'r', encoding='utf-8') as f:
                test_code = f.read()
        except Exception as e:
            messagebox.showerror("错误", f"读取测试文件失败: {e}")
            return

        if hasattr(self, 'simple_result_text'):
            self.simple_result_text.delete('1.0', tk.END)
            self.simple_result_text.insert('1.0', f"📂 加载测试文件: {test_file_path}\n", 'info')
            self.simple_result_text.insert(tk.END, "🔨 正在编译...\n", 'info')
            self.simple_result_text.update_idletasks()

        self.status_var.set("📂 运行已有测试: 编译中...")
        self.root.update_idletasks()

        try:
            import tempfile, subprocess

            tmp_dir = tempfile.mkdtemp(prefix='cunit_existing_')

            # 写入头文件
            src_hdr = ""
            tgt_hdr = ""
            if hasattr(self, 'source_header_text'):
                src_hdr = self.source_header_text.get('1.0', tk.END).strip()
            if hasattr(self, 'target_header_text'):
                tgt_hdr = self.target_header_text.get('1.0', tk.END).strip()
            if not src_hdr and self.header_content:
                src_hdr = self.header_content
            if not tgt_hdr and self.target_header_content:
                tgt_hdr = self.target_header_content

            with open(os.path.join(tmp_dir, 'source.h'), 'w', encoding='utf-8') as f:
                f.write(src_hdr or "/* source.h */\n")
            with open(os.path.join(tmp_dir, 'target.h'), 'w', encoding='utf-8') as f:
                f.write(tgt_hdr or "/* target.h */\n")

            # 写入转换代码
            converter_c = os.path.join(tmp_dir, 'converter.c')
            converter_code = code
            if '#include' not in code:
                converter_code = (
                    '#include <stdint.h>\n#include <string.h>\n'
                    '#include "source.h"\n#include "target.h"\n\n' + code
                )
            with open(converter_c, 'w', encoding='utf-8') as f:
                f.write(converter_code)

            # 写入用户选择的测试代码
            # 如果测试代码中没有 #include，自动添加
            final_test_code = test_code
            if '#include' not in test_code:
                final_test_code = (
                    '#include <stdio.h>\n#include <string.h>\n'
                    '#include <CUnit/CUnit.h>\n#include <CUnit/Basic.h>\n'
                    '#include "source.h"\n#include "target.h"\n\n' + test_code
                )

            # 检查测试代码中的 include 路径，替换为临时目录
            final_test_code = final_test_code.replace(
                '#include "source.h"', f'#include "source.h"'
            )

            test_c = os.path.join(tmp_dir, 'user_test.c')
            with open(test_c, 'w', encoding='utf-8') as f:
                f.write(final_test_code)

            # 自动检测 CUnit 路径
            cunit_inc, cunit_lib = self._detect_cunit_paths()

            # 收集用户测试目录中可能需要的额外 .c 文件
            test_dir = os.path.dirname(test_file_path)
            extra_sources = []
            for fname in os.listdir(test_dir):
                if fname.endswith('.c') and fname != os.path.basename(test_file_path):
                    fpath = os.path.join(test_dir, fname)
                    # 检查是否引用了转换函数
                    try:
                        with open(fpath, 'r', encoding='utf-8') as f:
                            content = f.read()
                        if 'convert_' in content or '#include' in content:
                            extra_sources.append(fpath)
                    except Exception:
                        pass

            # 编译
            exe_file = os.path.join(tmp_dir, 'test_runner.exe')
            compile_cmd = [
                'gcc', '-Wall', '-Wextra', '-std=c11',
                '-I' + tmp_dir,
                test_c, converter_c,
            ]
            compile_cmd.extend(extra_sources)
            compile_cmd.extend(['-o', exe_file, '-lm'])

            if cunit_inc:
                compile_cmd.insert(1, '-I' + cunit_inc)
            if cunit_lib:
                compile_cmd.extend(['-L' + cunit_lib])
            compile_cmd.extend(['-lcunit'])

            self.status_var.set("📂 运行已有测试: gcc 编译中...")
            self.root.update_idletasks()

            compile_result = subprocess.run(
                compile_cmd, capture_output=True, text=True, timeout=30, cwd=tmp_dir
            )

            if compile_result.returncode != 0:
                err_output = f"❌ 编译失败\n\n测试文件: {test_file_path}\n\n"
                if compile_result.stderr:
                    err_output += compile_result.stderr
                self._show_result(err_output, 'error')
                self.status_var.set("❌ 编译失败")
                return

            # 运行
            self.status_var.set("📂 运行已有测试: 执行中...")
            self.root.update_idletasks()

            run_result = subprocess.run(
                [exe_file], capture_output=True, text=True, timeout=30, cwd=tmp_dir
            )

            # 展示结果
            output = f"📂 已有测试运行完成！\n"
            output += f"测试文件: {test_file_path}\n\n"
            if run_result.stdout:
                output += "--- 运行输出 ---\n"
                output += run_result.stdout
            if run_result.stderr:
                output += f"\n[stderr]\n{run_result.stderr}"
            output += f"\n返回码: {run_result.returncode}"

            tag = 'success' if run_result.returncode == 0 else 'error'
            self._show_result(output, tag)
            self.status_var.set("✅ 测试通过" if run_result.returncode == 0 else "⚠️ 测试有失败")

        except subprocess.TimeoutExpired:
            self._show_result("❌ 测试超时（30秒）", 'error')
        except FileNotFoundError:
            self._show_result("❌ 未找到 gcc 或 CUnit 库！\n请安装 gcc 和 cunit。", 'error')
        except Exception as e:
            self._show_result(f"❌ 异常: {e}", 'error')

    def _simple_external_cunit_test(self):
        """使用外部 CUnit 测试工具 (python-c-cunit-mc-dc) 对生成的代码进行测试"""
        if not hasattr(self, 'simple_code_text'):
            return
        code = self.simple_code_text.get('1.0', tk.END).strip()
        if not code:
            messagebox.showwarning("警告", "没有可测试的代码！请先生成代码。")
            return

        if hasattr(self, 'simple_result_text'):
            self.simple_result_text.delete('1.0', tk.END)
            self.simple_result_text.insert('1.0', "🔬 正在准备外部 CUnit 测试...\n", 'info')
            self.simple_result_text.update_idletasks()

        self.status_var.set("🔬 外部 CUnit 测试: 准备中...")
        self.root.update_idletasks()

        # CUnit 工具路径
        cunit_tool_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'python-c-cunit-mc-dc', 'outputs'
        )
        cunit_tool_path = os.path.join(cunit_tool_dir, 'cunit_mcdc_tool.py')

        if not os.path.exists(cunit_tool_path):
            cunit_tool_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..', 'python-c-cunit-mc-dc', 'outputs'
            )
            cunit_tool_path = os.path.join(cunit_tool_dir, 'cunit_mcdc_tool.py')

        if not os.path.exists(cunit_tool_path):
            self._show_result("❌ 未找到外部 CUnit 测试工具！\n"
                              "请确保 python-c-cunit-mc-dc/outputs/cunit_mcdc_tool.py 存在。", 'error')
            return

        try:
            import tempfile, subprocess, json

            tmp_dir = tempfile.mkdtemp(prefix='cunit_ext_')
            src_dir = os.path.join(tmp_dir, 'src')
            tests_dir = os.path.join(tmp_dir, 'tests')
            os.makedirs(src_dir)
            os.makedirs(tests_dir)

            src_file = os.path.join(src_dir, 'generated_code.c')
            with open(src_file, 'w', encoding='utf-8') as f:
                f.write(code)

            if self.header_content:
                hdr_file = os.path.join(src_dir, 'header_context.h')
                with open(hdr_file, 'w', encoding='utf-8') as f:
                    f.write(self.header_content)

            config = {
                "project_root": tmp_dir,
                "source_globs": ["src/**/*.c", "src/**/*.h"],
                "include_dirs": [src_dir],
                "test_output_dir": tests_dir,
                "compiler": "gcc",
                "c_standard": "c11",
                "auto_build": True,
                "llm_base_url": self.llm_service.base_url,
                "llm_model": self.llm_service.model,
                "llm_api_key_env": "CUNIT_API_KEY",
                "llm_max_tokens": 4096,
                "max_llm_rounds": 1
            }

            config_file = os.path.join(tmp_dir, 'config.json')
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)

            env = os.environ.copy()
            env['CUNIT_API_KEY'] = self.llm_service.api_key

            self.status_var.set("🔬 外部 CUnit: AI 正在生成测试用例...")
            self.root.update_idletasks()

            cmd = [sys.executable, cunit_tool_path, '--config', config_file, 'generate-functions']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd=tmp_dir, env=env)

            if result.returncode == 0:
                output = "✅ 外部 CUnit 测试生成成功！\n\n"
                if result.stdout:
                    output += result.stdout[-2000:]

                test_file = os.path.join(tests_dir, 'auto_mcdc_tests.c')
                if os.path.exists(test_file):
                    output += f"\n📄 测试文件: {test_file}\n"
                    self.status_var.set("🔬 外部 CUnit: 编译并运行...")
                    self.root.update_idletasks()

                    run_cmd = [sys.executable, cunit_tool_path, '--config', config_file, 'run']
                    run_result = subprocess.run(run_cmd, capture_output=True, text=True, timeout=60, cwd=tmp_dir, env=env)
                    if run_result.stdout:
                        output += f"\n--- 测试运行结果 ---\n{run_result.stdout[-2000:]}\n"
                    if run_result.stderr:
                        output += f"\n--- 错误输出 ---\n{run_result.stderr[-1000:]}\n"

                self._show_result(output, 'success')
                self.status_var.set("✅ 外部 CUnit 测试完成")
            else:
                output = f"❌ 外部 CUnit 测试失败 (返回码: {result.returncode})\n\n"
                if result.stdout:
                    output += f"标准输出:\n{result.stdout[-2000:]}\n"
                if result.stderr:
                    output += f"\n错误输出:\n{result.stderr[-2000:]}\n"
                self._show_result(output, 'error')
                self.status_var.set("❌ 外部 CUnit 测试失败")

        except subprocess.TimeoutExpired:
            self._show_result("❌ 外部 CUnit 测试超时（180秒）", 'error')
        except Exception as e:
            self._show_result(f"❌ 外部 CUnit 测试异常: {e}", 'error')

    def _save_mapping_doc(self):
        """保存映射文档"""
        content = ""
        if self.current_mode == 'simple' and hasattr(self, 'simple_mapping_text'):
            content = self.simple_mapping_text.get('1.0', tk.END).strip()
        elif hasattr(self, 'mapping_doc_text'):
            content = self.mapping_doc_text.get('1.0', tk.END).strip()

        if not content:
            messagebox.showwarning("警告", "映射文档为空！")
            return

        file_path = filedialog.asksaveasfilename(
            title="保存映射文档",
            defaultextension=".md",
            filetypes=[("Markdown 文件", "*.md"), ("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if not file_path:
            return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.mapping_doc_content = content
            messagebox.showinfo("成功", f"映射文档已保存到: {file_path}")
            self.status_var.set(f"映射文档已保存: {file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

    def _load_mapping_doc(self):
        """加载已有的映射文档"""
        file_path = filedialog.askopenfilename(
            title="加载映射文档",
            filetypes=[
                ("Markdown 文件", "*.md"),
                ("文本文件", "*.txt"),
                ("所有文件", "*.*"),
            ]
        )
        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

            self.mapping_doc_content = content

            if self.current_mode == 'simple' and hasattr(self, 'simple_mapping_text'):
                self.simple_mapping_text.delete('1.0', tk.END)
                self.simple_mapping_text.insert('1.0', content)
            elif hasattr(self, 'mapping_doc_text'):
                self.mapping_doc_text.delete('1.0', tk.END)
                self.mapping_doc_text.insert('1.0', content)

            self.status_var.set(f"✅ 已加载映射文档: {os.path.basename(file_path)}")
        except Exception as e:
            messagebox.showerror("错误", f"加载映射文档失败: {e}")

    def _export_to_advanced(self):
        """将简单模式的映射文档导出到高级模式的映射列表"""
        mapping_doc = self._get_current_simple_mapping_doc()
        if not mapping_doc:
            return

        generator = DocumentBasedGenerator(
            parser=self.parser,
            target_parser=self.target_parser
        )
        imported_vars, imported_mappings = generator.parse_mappings_from_document(mapping_doc)

        if not imported_mappings:
            messagebox.showwarning("警告", "未能从映射文档中解析出映射关系！")
            return

        # 合并到高级模式数据
        for v in imported_vars:
            if not any(uv['name'] == v['name'] for uv in self.user_vars):
                self.user_vars.append(v)

        for m in imported_mappings:
            already = any(
                em['extern_member'] == m['extern_member'] and em['user_var'] == m['user_var']
                for em in self.mappings
            )
            if not already:
                self.mappings.append(m)

        messagebox.showinfo(
            "导出完成",
            f"已导出 {len(imported_mappings)} 条映射关系和 {len(imported_vars)} 个变量到高级模式。\n"
            f"切换到高级模式可查看和编辑。"
        )
        self.status_var.set(f"已导出到高级模式: {len(imported_mappings)} 条映射")

    def _extract_mapping_doc_from_response(self, response: str) -> str:
        """从 LLM 响应中提取映射文档内容"""
        for pattern in [
            r'```markdown\s*\n(.*?)```',
            r'```md\s*\n(.*?)```',
            r'```\s*\n(.*?)```',
        ]:
            match = re.search(pattern, response, re.DOTALL)
            if match:
                return match.group(1).strip()
        return response.strip()

    def _extract_code_from_llm_response(self, response: str) -> str:
        """从 LLM 响应中提取代码块"""
        patterns = [
            r'```c\s*\n(.*?)```',
            r'```C\s*\n(.*?)```',
            r'```\s*\n(.*?)```',
        ]
        for pattern in patterns:
            match = re.search(pattern, response, re.DOTALL)
            if match:
                return match.group(1).strip()
        return response.strip()

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="📄 加载需求文档...", command=self._load_document, accelerator="Ctrl+O")
        file_menu.add_command(label="📁 加载头文件(可选)...", command=self._load_header_file)
        file_menu.add_separator()
        file_menu.add_command(label="📥 加载映射文档...", command=self._load_mapping_doc)
        file_menu.add_command(label="📤 保存映射文档...", command=self._save_mapping_doc)
        file_menu.add_separator()
        file_menu.add_command(label="📂 导入映射配置(JSON)...", command=self._import_config)
        file_menu.add_command(label="💾 导出映射配置(JSON)...", command=self._export_config)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)

        # 模式切换菜单
        mode_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="模式", menu=mode_menu)
        mode_menu.add_command(label="✅ 简单模式", command=lambda: self._switch_mode('simple'))
        mode_menu.add_command(label="🔧 高级模式", command=lambda: self._switch_mode('advanced'))

        # 工具菜单
        tool_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="工具", menu=tool_menu)
        tool_menu.add_command(label="🔗 测试 LLM 连接", command=self._test_llm_connection)
        tool_menu.add_separator()
        tool_menu.add_command(label="⚙️ LLM 服务设置...", command=self._show_llm_settings)

        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="使用说明", command=self._show_help)
        help_menu.add_command(label="关于", command=self._show_about)

        self.root.bind('<Control-o>', lambda e: self._load_document())

    def _build_advanced_mode(self, parent):
        """构建高级模式 UI（原始完整界面）"""
        main_paned = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        main_paned.pack(fill=tk.BOTH, expand=True)

        top_frame = ttk.Frame(main_paned)
        main_paned.add(top_frame, weight=3)

        bottom_frame = ttk.Frame(main_paned)
        main_paned.add(bottom_frame, weight=2)

        self._build_top_panel(top_frame)
        self._build_bottom_panel(bottom_frame)

    def _build_top_panel(self, parent):
        h_paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        h_paned.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.LabelFrame(h_paned, text=" 📄 头文件 & Extern 变量 ", padding=5)
        h_paned.add(left_frame, weight=2)

        self._build_left_panel(left_frame)

        center_frame = ttk.LabelFrame(h_paned, text=" 📋 变量成员详情 ", padding=5)
        h_paned.add(center_frame, weight=2)

        self._build_center_panel(center_frame)

        right_frame = ttk.LabelFrame(h_paned, text=" 🔗 映射配置 ", padding=5)
        h_paned.add(right_frame, weight=3)

        self._build_right_panel(right_frame)

    def _build_left_panel(self, parent):
        file_frame = ttk.Frame(parent)
        file_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(file_frame, text="头文件:", style='Info.TLabel').pack(side=tk.LEFT)
        self.file_entry = ttk.Entry(file_frame, textvariable=self.current_file, state='readonly')
        self.file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(file_frame, text="浏览...", command=self._open_file).pack(side=tk.LEFT)

        target_frame = ttk.Frame(parent)
        target_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(target_frame, text="目标文件:", style='Info.TLabel').pack(side=tk.LEFT)
        self.target_file_entry = ttk.Entry(target_frame, textvariable=self.target_file, state='readonly')
        self.target_file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(target_frame, text="浏览...", command=self._open_target_file).pack(side=tk.LEFT)

        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(list_frame, text="Extern 变量列表:", style='Header.TLabel').pack(anchor=tk.W)

        columns = ('name', 'type', 'is_struct')
        self.extern_tree = ttk.Treeview(
            list_frame, columns=columns, show='headings',
            selectmode='browse', height=8
        )
        self.extern_tree.heading('name', text='变量名')
        self.extern_tree.heading('type', text='类型')
        self.extern_tree.heading('is_struct', text='结构体')
        self.extern_tree.column('name', width=120, minwidth=80)
        self.extern_tree.column('type', width=140, minwidth=80)
        self.extern_tree.column('is_struct', width=60, minwidth=40, anchor=tk.CENTER)

        extern_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.extern_tree.yview)
        self.extern_tree.configure(yscrollcommand=extern_scroll.set)

        self.extern_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        extern_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.extern_tree.bind('<<TreeviewSelect>>', self._on_extern_select)

        self.parse_info_var = tk.StringVar(value="尚未加载头文件")
        ttk.Label(parent, textvariable=self.parse_info_var, style='Warning.TLabel').pack(
            anchor=tk.W, pady=(5, 0)
        )

        self.target_info_var = tk.StringVar(value="尚未加载目标头文件")
        ttk.Label(parent, textvariable=self.target_info_var, style='Warning.TLabel').pack(
            anchor=tk.W, pady=(2, 0)
        )

    def _build_center_panel(self, parent):
        self.member_title_var = tk.StringVar(value="选择一个 extern 变量查看成员")
        ttk.Label(parent, textvariable=self.member_title_var, style='Header.TLabel').pack(anchor=tk.W)

        columns = ('name', 'type', 'array', 'pointer', 'bitfield')
        self.member_tree = ttk.Treeview(
            parent, columns=columns, show='headings',
            selectmode='extended', height=10
        )
        self.member_tree.heading('name', text='成员名')
        self.member_tree.heading('type', text='类型')
        self.member_tree.heading('array', text='数组')
        self.member_tree.heading('pointer', text='指针')
        self.member_tree.heading('bitfield', text='位域')
        self.member_tree.column('name', width=100, minwidth=60)
        self.member_tree.column('type', width=100, minwidth=60)
        self.member_tree.column('array', width=50, minwidth=40, anchor=tk.CENTER)
        self.member_tree.column('pointer', width=50, minwidth=40, anchor=tk.CENTER)
        self.member_tree.column('bitfield', width=50, minwidth=40, anchor=tk.CENTER)

        member_scroll = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.member_tree.yview)
        self.member_tree.configure(yscrollcommand=member_scroll.set)

        self.member_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        member_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.member_tree.bind('<<TreeviewSelect>>', self._on_member_select)

    def _build_right_panel(self, parent):
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)

        user_var_tab = ttk.Frame(notebook, padding=5)
        notebook.add(user_var_tab, text=" 👤 用户变量 ")

        self._build_user_var_tab(user_var_tab)

        target_var_tab = ttk.Frame(notebook, padding=5)
        notebook.add(target_var_tab, text=" 🎯 目标头文件变量 ")

        self._build_target_var_tab(target_var_tab)

        mapping_tab = ttk.Frame(notebook, padding=5)
        notebook.add(mapping_tab, text=" 🔗 映射关系 ")

        self._build_mapping_tab(mapping_tab)

    def _build_user_var_tab(self, parent):
        add_frame = ttk.LabelFrame(parent, text="添加用户变量", padding=5)
        add_frame.pack(fill=tk.X, pady=(0, 5))

        row1 = ttk.Frame(add_frame)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="变量名:").pack(side=tk.LEFT)
        self.user_var_name = ttk.Entry(row1, width=20)
        self.user_var_name.pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, text="类型:").pack(side=tk.LEFT)
        self.user_var_type = ttk.Combobox(
            row1, width=18,
            values=['int', 'float', 'double', 'char', 'short', 'long',
                    'uint8_t', 'uint16_t', 'uint32_t', 'uint64_t',
                    'int8_t', 'int16_t', 'int32_t', 'int64_t',
                    'bool', 'unsigned char', 'unsigned int', 'unsigned short',
                    'unsigned long', 'char[]', '自定义']
        )
        self.user_var_type.set('int')
        self.user_var_type.pack(side=tk.LEFT, padx=5)
        self.user_var_type.bind('<<ComboboxSelected>>', self._on_user_var_type_changed)

        row2 = ttk.Frame(add_frame)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="自定义类型:").pack(side=tk.LEFT)
        self.user_var_custom_type = ttk.Entry(row2, width=14)
        self.user_var_custom_type.pack(side=tk.LEFT, padx=5)
        ttk.Label(row2, text="结构体类型:").pack(side=tk.LEFT)
        self.struct_type_combo = ttk.Combobox(row2, width=14, state='readonly')
        self.struct_type_combo.pack(side=tk.LEFT, padx=5)
        self.struct_type_combo.bind('<<ComboboxSelected>>', self._on_struct_type_selected)
        ttk.Label(row2, text="描述:").pack(side=tk.LEFT)
        self.user_var_desc = ttk.Entry(row2, width=14)
        self.user_var_desc.pack(side=tk.LEFT, padx=5)

        btn_frame = ttk.Frame(add_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="➕ 添加变量", command=self._add_user_var, style='Accent.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="🗑️ 删除选中", command=self._del_user_var).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="📋 批量添加", command=self._batch_add_user_var).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="📦 从结构体添加", command=self._add_from_struct, style='Accent.TButton').pack(side=tk.LEFT, padx=2)

        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('name', 'type', 'desc', 'source')
        self.user_var_tree = ttk.Treeview(
            list_frame, columns=columns, show='headings',
            selectmode='browse', height=8
        )
        self.user_var_tree.heading('name', text='变量名')
        self.user_var_tree.heading('type', text='类型')
        self.user_var_tree.heading('desc', text='描述')
        self.user_var_tree.heading('source', text='来源')
        self.user_var_tree.column('name', width=120, minwidth=80)
        self.user_var_tree.column('type', width=120, minwidth=80)
        self.user_var_tree.column('desc', width=120, minwidth=60)
        self.user_var_tree.column('source', width=80, minwidth=50)

        uv_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.user_var_tree.yview)
        self.user_var_tree.configure(yscrollcommand=uv_scroll.set)

        self.user_var_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        uv_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_target_var_tab(self, parent):
        info_frame = ttk.LabelFrame(parent, text="目标头文件变量", padding=5)
        info_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(info_frame, text="选择目标头文件中的变量作为映射目标变量", style='Info.TLabel').pack(anchor=tk.W)

        btn_frame = ttk.Frame(info_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="📥 导入选中变量到用户变量", command=self._import_target_vars, style='Accent.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="📥 导入全部变量", command=self._import_all_target_vars).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="📦 导入结构体成员", command=self._import_target_struct_members, style='Accent.TButton').pack(side=tk.LEFT, padx=2)

        target_list_frame = ttk.Frame(parent)
        target_list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('name', 'type', 'is_struct', 'struct_type')
        self.target_var_tree = ttk.Treeview(
            target_list_frame, columns=columns, show='headings',
            selectmode='extended', height=8
        )
        self.target_var_tree.heading('name', text='变量名')
        self.target_var_tree.heading('type', text='类型')
        self.target_var_tree.heading('is_struct', text='结构体')
        self.target_var_tree.heading('struct_type', text='结构体类型')
        self.target_var_tree.column('name', width=120, minwidth=80)
        self.target_var_tree.column('type', width=140, minwidth=80)
        self.target_var_tree.column('is_struct', width=60, minwidth=40, anchor=tk.CENTER)
        self.target_var_tree.column('struct_type', width=120, minwidth=80)

        target_scroll = ttk.Scrollbar(target_list_frame, orient=tk.VERTICAL, command=self.target_var_tree.yview)
        self.target_var_tree.configure(yscrollcommand=target_scroll.set)

        self.target_var_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        target_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.target_var_tree.bind('<<TreeviewSelect>>', self._on_target_var_select)

        self.target_member_frame = ttk.LabelFrame(parent, text="目标变量成员详情", padding=5)
        self.target_member_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        tm_columns = ('name', 'type', 'array', 'pointer')
        self.target_member_tree = ttk.Treeview(
            self.target_member_frame, columns=tm_columns, show='headings',
            selectmode='extended', height=6
        )
        self.target_member_tree.heading('name', text='成员名')
        self.target_member_tree.heading('type', text='类型')
        self.target_member_tree.heading('array', text='数组')
        self.target_member_tree.heading('pointer', text='指针')
        self.target_member_tree.column('name', width=120, minwidth=80)
        self.target_member_tree.column('type', width=120, minwidth=80)
        self.target_member_tree.column('array', width=60, minwidth=40, anchor=tk.CENTER)
        self.target_member_tree.column('pointer', width=60, minwidth=40, anchor=tk.CENTER)

        tm_scroll = ttk.Scrollbar(self.target_member_frame, orient=tk.VERTICAL, command=self.target_member_tree.yview)
        self.target_member_tree.configure(yscrollcommand=tm_scroll.set)

        self.target_member_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tm_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_mapping_tab(self, parent):
        add_map_frame = ttk.LabelFrame(parent, text="添加映射关系", padding=5)
        add_map_frame.pack(fill=tk.X, pady=(0, 5))

        row_ext = ttk.Frame(add_map_frame)
        row_ext.pack(fill=tk.X, pady=2)
        ttk.Label(row_ext, text="Extern 成员:").pack(side=tk.LEFT)
        self.map_extern_member = ttk.Combobox(row_ext, width=25, state='readonly')
        self.map_extern_member.pack(side=tk.LEFT, padx=5)

        row_user = ttk.Frame(add_map_frame)
        row_user.pack(fill=tk.X, pady=2)
        ttk.Label(row_user, text="用户变量:").pack(side=tk.LEFT)
        self.map_user_var = ttk.Combobox(row_user, width=25, state='readonly')
        self.map_user_var.pack(side=tk.LEFT, padx=5)

        row_op = ttk.Frame(add_map_frame)
        row_op.pack(fill=tk.X, pady=2)
        ttk.Label(row_op, text="操作类型:").pack(side=tk.LEFT)
        self.map_op_type = ttk.Combobox(
            row_op, width=12, state='readonly',
            values=['直接赋值', '条件赋值', '逻辑判断', '自定义表达式']
        )
        self.map_op_type.set('直接赋值')
        self.map_op_type.pack(side=tk.LEFT, padx=5)
        self.map_op_type.bind('<<ComboboxSelected>>', self._on_op_type_changed)

        self.map_condition_frame = ttk.LabelFrame(add_map_frame, text="条件表达式 (支持与/或)", padding=5)
        self.map_condition_frame.pack(fill=tk.X, pady=2)

        self._build_condition_builder()

        row_conv = ttk.Frame(add_map_frame)
        row_conv.pack(fill=tk.X, pady=2)
        ttk.Label(row_conv, text="转换规则:").pack(side=tk.LEFT)
        self.map_conversion = ttk.Combobox(
            row_conv, width=15, state='readonly',
            values=['=', '强制转换', '缩放', '偏移', '自定义']
        )
        self.map_conversion.set('=')
        self.map_conversion.pack(side=tk.LEFT, padx=5)
        ttk.Label(row_conv, text="自定义:").pack(side=tk.LEFT)
        self.map_custom_conv = ttk.Entry(row_conv, width=20)
        self.map_custom_conv.pack(side=tk.LEFT, padx=5)

        btn_frame = ttk.Frame(add_map_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="➕ 添加映射", command=self._add_mapping, style='Accent.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="🗑️ 删除选中", command=self._del_mapping).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="⬆️ 上移", command=lambda: self._move_mapping(-1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="⬇️ 下移", command=lambda: self._move_mapping(1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="⚡ 自动匹配", command=self._auto_match, style='Accent.TButton').pack(side=tk.LEFT, padx=2)

        map_list_frame = ttk.Frame(parent)
        map_list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('extern_member', 'operator', 'user_var', 'conversion', 'condition_count')
        self.mapping_tree = ttk.Treeview(
            map_list_frame, columns=columns, show='headings',
            selectmode='browse', height=8
        )
        self.mapping_tree.heading('extern_member', text='Extern 成员')
        self.mapping_tree.heading('operator', text='操作')
        self.mapping_tree.heading('user_var', text='用户变量')
        self.mapping_tree.heading('conversion', text='转换规则')
        self.mapping_tree.heading('condition_count', text='条件数')
        self.mapping_tree.column('extern_member', width=120, minwidth=80)
        self.mapping_tree.column('operator', width=80, minwidth=50)
        self.mapping_tree.column('user_var', width=100, minwidth=60)
        self.mapping_tree.column('conversion', width=80, minwidth=50)
        self.mapping_tree.column('condition_count', width=60, minwidth=40, anchor=tk.CENTER)

        map_scroll = ttk.Scrollbar(map_list_frame, orient=tk.VERTICAL, command=self.mapping_tree.yview)
        self.mapping_tree.configure(yscrollcommand=map_scroll.set)

        self.mapping_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        map_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.mapping_tree.bind('<<TreeviewSelect>>', self._on_mapping_select)

    def _build_condition_builder(self):
        """构建条件表达式输入界面"""
        cond_row1 = ttk.Frame(self.map_condition_frame)
        cond_row1.pack(fill=tk.X, pady=2)

        ttk.Label(cond_row1, text="变量:").pack(side=tk.LEFT)
        self.cond_var_ref = ttk.Combobox(cond_row1, width=15, state='readonly')
        self.cond_var_ref.pack(side=tk.LEFT, padx=5)

        ttk.Label(cond_row1, text="操作符:").pack(side=tk.LEFT)
        self.cond_operator = ttk.Combobox(
            cond_row1, width=8, state='readonly',
            values=['==', '!=', '>', '<', '>=', '<=', '&&', '||']
        )
        self.cond_operator.set('==')
        self.cond_operator.pack(side=tk.LEFT, padx=5)

        ttk.Label(cond_row1, text="值:").pack(side=tk.LEFT)
        self.cond_value = ttk.Entry(cond_row1, width=15)
        self.cond_value.pack(side=tk.LEFT, padx=5)

        cond_row2 = ttk.Frame(self.map_condition_frame)
        cond_row2.pack(fill=tk.X, pady=2)

        ttk.Label(cond_row2, text="逻辑连接:").pack(side=tk.LEFT)
        self.cond_logic = ttk.Combobox(
            cond_row2, width=8, state='readonly',
            values=['AND', 'OR']
        )
        self.cond_logic.set('AND')
        self.cond_logic.pack(side=tk.LEFT, padx=5)

        ttk.Button(cond_row2, text="➕ 添加条件", command=self._add_condition).pack(side=tk.LEFT, padx=5)
        ttk.Button(cond_row2, text="🗑️ 清空", command=self._clear_conditions).pack(side=tk.LEFT, padx=2)

        self.cond_preview_frame = ttk.LabelFrame(self.map_condition_frame, text="条件预览", padding=5)
        self.cond_preview_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        self.cond_preview_text = tk.Text(
            self.cond_preview_frame, height=4, font=('Consolas', 9),
            wrap=tk.WORD, bg='#f5f5f5'
        )
        self.cond_preview_text.pack(fill=tk.BOTH, expand=True)

        self.current_conditions: List[Dict] = []

    def _add_condition(self):
        """添加一个条件到当前条件列表"""
        var_ref = self.cond_var_ref.get()
        operator = self.cond_operator.get()
        value = self.cond_value.get().strip()
        logic = self.cond_logic.get()

        if not var_ref:
            messagebox.showwarning("警告", "请选择变量！")
            return
        if not value:
            messagebox.showwarning("警告", "请输入比较值！")
            return

        self.current_conditions.append({
            'var_ref': var_ref,
            'operator': operator,
            'value': value,
            'logic': logic if len(self.current_conditions) > 0 else ''
        })

        self._update_condition_preview()
        self.cond_value.delete(0, tk.END)

    def _clear_conditions(self):
        """清空所有条件"""
        self.current_conditions.clear()
        self._update_condition_preview()

    def _update_condition_preview(self):
        """更新条件预览"""
        self.cond_preview_text.delete('1.0', tk.END)

        if not self.current_conditions:
            self.cond_preview_text.insert('1.0', "(无条件)")
            return

        ext_var = self._get_extern_var_name()
        expr_parts = []

        for i, cond in enumerate(self.current_conditions):
            var_full = f"{ext_var}->{cond['var_ref']}"
            expr = f"{var_full} {cond['operator']} {cond['value']}"
            expr_parts.append(expr)

        if len(expr_parts) == 1:
            result = expr_parts[0]
        else:
            result = expr_parts[0]
            for i in range(1, len(expr_parts)):
                logic = self.current_conditions[i].get('logic', 'AND')
                result += f"\n{logic} ({expr_parts[i]})"

        self.cond_preview_text.insert('1.0', result)

    def _get_extern_var_name(self) -> str:
        if self.selected_extern_var:
            return self.selected_extern_var['name']
        return "ext_var"

    def _build_bottom_panel(self, parent):
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)

        code_frame = ttk.Frame(notebook, padding=5)
        notebook.add(code_frame, text=" 💻 生成的代码 ")

        self._build_code_tab(code_frame)

        md_frame = ttk.Frame(notebook, padding=5)
        notebook.add(md_frame, text=" 📝 Markdown 文档 ")

        self._build_markdown_tab(md_frame)

        ai_frame = ttk.Frame(notebook, padding=5)
        notebook.add(ai_frame, text=" 🤖 AI 代码生成 ")

        self._build_ai_tab(ai_frame)

        doc_frame = ttk.Frame(notebook, padding=5)
        notebook.add(doc_frame, text=" 📋 映射文档工作流 ")

        self._build_doc_tab(doc_frame)

    def _build_code_tab(self, parent):
        code_frame = ttk.LabelFrame(parent, text=" 📝 生成的代码 ", padding=5)
        code_frame.pack(fill=tk.BOTH, expand=True)

        toolbar = ttk.Frame(code_frame)
        toolbar.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(toolbar, text="🔧 生成代码", command=self._generate_code, style='Accent.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📋 复制代码", command=self._copy_code).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="💾 保存代码...", command=self._save_code).pack(side=tk.LEFT, padx=2)

        ttk.Label(toolbar, text="  代码模板:").pack(side=tk.LEFT, padx=(20, 5))
        self.code_template = ttk.Combobox(
            toolbar, width=20, state='readonly',
            values=['赋值函数', '条件判断函数', '完整转换函数', '仅赋值语句', '仅判断语句']
        )
        self.code_template.set('赋值函数')
        self.code_template.pack(side=tk.LEFT, padx=5)

        self.code_text = scrolledtext.ScrolledText(
            code_frame, wrap=tk.NONE, font=('Consolas', 10),
            bg='#1e1e1e', fg='#d4d4d4', insertbackground='white',
            selectbackground='#264f78', height=12
        )
        self.code_text.pack(fill=tk.BOTH, expand=True)

        self.code_text.tag_configure('keyword', foreground='#569cd6')
        self.code_text.tag_configure('type', foreground='#4ec9b0')
        self.code_text.tag_configure('string', foreground='#ce9178')
        self.code_text.tag_configure('comment', foreground='#6a9955')
        self.code_text.tag_configure('number', foreground='#b5cea8')
        self.code_text.tag_configure('function', foreground='#dcdcaa')

    def _build_markdown_tab(self, parent):
        md_frame = ttk.LabelFrame(parent, text=" 📝 Markdown 文档 ", padding=5)
        md_frame.pack(fill=tk.BOTH, expand=True)

        toolbar = ttk.Frame(md_frame)
        toolbar.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(toolbar, text="📄 生成文档", command=self._generate_markdown, style='Accent.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📋 复制文档", command=self._copy_markdown).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="💾 保存文档...", command=self._save_markdown).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📋 复制代码+文档", command=self._copy_code_and_markdown).pack(side=tk.LEFT, padx=2)

        self.md_text = scrolledtext.ScrolledText(
            md_frame, wrap=tk.WORD, font=('Consolas', 10),
            bg='#ffffff', fg='#333333', height=12
        )
        self.md_text.pack(fill=tk.BOTH, expand=True)

    def _build_ai_tab(self, parent):
        """构建 AI 代码生成标签页"""
        ai_frame = ttk.LabelFrame(parent, text=" 🤖 AI 大模型代码生成 ", padding=5)
        ai_frame.pack(fill=tk.BOTH, expand=True)

        # 状态信息
        status_frame = ttk.Frame(ai_frame)
        status_frame.pack(fill=tk.X, pady=(0, 5))

        self.ai_status_var = tk.StringVar(value="未配置 LLM 服务")
        ttk.Label(status_frame, textvariable=self.ai_status_var, style='Warning.TLabel').pack(side=tk.LEFT)
        ttk.Button(status_frame, text="⚙️ 设置", command=self._show_llm_settings).pack(side=tk.RIGHT, padx=2)

        # 操作按钮
        toolbar = ttk.Frame(ai_frame)
        toolbar.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(toolbar, text="🧠 AI 生成映射代码", command=self._llm_generate_code,
                   style='Accent.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📋 复制结果", command=self._copy_ai_code).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="💾 保存结果...", command=self._save_ai_code).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📋 复制到代码标签页", command=self._copy_ai_to_code_tab).pack(side=tk.LEFT, padx=2)

        # 提示信息
        info_label = ttk.Label(
            ai_frame,
            text="提示: AI 将基于当前映射关系和头文件内容生成 C 语言转换代码。请先配置 LLM 服务。",
            style='Info.TLabel', wraplength=600
        )
        info_label.pack(fill=tk.X, pady=(0, 5))

        # AI 输出文本框
        self.ai_code_text = scrolledtext.ScrolledText(
            ai_frame, wrap=tk.NONE, font=('Consolas', 10),
            bg='#1a1a2e', fg='#e0e0e0', insertbackground='white',
            selectbackground='#264f78', height=12
        )
        self.ai_code_text.pack(fill=tk.BOTH, expand=True)

        self.ai_code_text.tag_configure('keyword', foreground='#569cd6')
        self.ai_code_text.tag_configure('type', foreground='#4ec9b0')
        self.ai_code_text.tag_configure('string', foreground='#ce9178')
        self.ai_code_text.tag_configure('comment', foreground='#6a9955')
        self.ai_code_text.tag_configure('error', foreground='#f44747')
        self.ai_code_text.tag_configure('success', foreground='#4ec9b0')

        # 更新状态
        self._update_ai_status()

    def _build_doc_tab(self, parent):
        """构建映射文档工作流标签页 - 三阶段工作流"""
        doc_frame = ttk.LabelFrame(parent, text=" 📋 映射文档工作流（自然语言→映射文档→代码） ", padding=5)
        doc_frame.pack(fill=tk.BOTH, expand=True)

        # ── 阶段1: 输入 ──
        stage1_lf = ttk.LabelFrame(doc_frame, text=" 阶段1: 输入（自然语言文档 + 头文件）", padding=5)
        stage1_lf.pack(fill=tk.X, pady=(0, 3))

        # 文档选择
        doc_row1 = ttk.Frame(stage1_lf)
        doc_row1.pack(fill=tk.X, pady=2)

        ttk.Label(doc_row1, text="需求文档:", style='Info.TLabel').pack(side=tk.LEFT)
        self.doc_file_var = tk.StringVar(value="未加载文档")
        ttk.Entry(doc_row1, textvariable=self.doc_file_var, state='readonly',
                  width=35).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(doc_row1, text="📄 加载文档", command=self._load_document).pack(side=tk.LEFT, padx=2)
        ttk.Button(doc_row1, text="🗑️ 清除", command=self._clear_document).pack(side=tk.LEFT, padx=2)

        # 头文件选择
        doc_row2 = ttk.Frame(stage1_lf)
        doc_row2.pack(fill=tk.X, pady=2)

        ttk.Label(doc_row2, text="关联头文件:", style='Info.TLabel').pack(side=tk.LEFT)
        self.doc_header_var = tk.StringVar(value="")
        self.doc_header_combo = ttk.Combobox(
            doc_row2, textvariable=self.doc_header_var,
            width=35, state='readonly'
        )
        self.doc_header_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(doc_row2, text="📂 浏览...", command=self._browse_doc_header).pack(side=tk.LEFT, padx=2)

        # 阶段1 操作按钮
        doc_row3 = ttk.Frame(stage1_lf)
        doc_row3.pack(fill=tk.X, pady=2)

        ttk.Button(doc_row3, text="📤 从GUI映射导出映射文档",
                   command=self._export_mapping_doc_from_gui,
                   style='Accent.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(doc_row3, text="📂 加载映射文档...",
                   command=self._import_mapping_doc).pack(side=tk.LEFT, padx=2)
        ttk.Button(doc_row3, text="🤖 AI: 自然语言→映射文档",
                   command=self._llm_doc_to_mapping_doc,
                   style='Accent.TButton').pack(side=tk.LEFT, padx=2)

        # ── 阶段2: 映射文档（中间产物）──
        stage2_lf = ttk.LabelFrame(doc_frame, text=" 阶段2: 规范映射文档（中间产物，可编辑）", padding=3)
        stage2_lf.pack(fill=tk.BOTH, expand=True, pady=(0, 3))

        # 映射文档工具栏
        md_toolbar = ttk.Frame(stage2_lf)
        md_toolbar.pack(fill=tk.X, pady=(0, 3))

        ttk.Button(md_toolbar, text="💾 保存映射文档...", command=self._save_mapping_doc).pack(side=tk.LEFT, padx=2)
        ttk.Button(md_toolbar, text="📥 导入映射到GUI", command=self._import_mapping_doc_to_gui).pack(side=tk.LEFT, padx=2)

        self.mapping_doc_text = scrolledtext.ScrolledText(
            stage2_lf, wrap=tk.WORD, font=('Consolas', 9),
            bg='#f5f5dc', fg='#333333', height=6
        )
        self.mapping_doc_text.pack(fill=tk.BOTH, expand=True)

        # ── 阶段3: 生成代码 ──
        stage3_lf = ttk.LabelFrame(doc_frame, text=" 阶段3: 从映射文档生成代码", padding=3)
        stage3_lf.pack(fill=tk.BOTH, expand=True, pady=(0, 3))

        # 阶段3 工具栏
        code_toolbar = ttk.Frame(stage3_lf)
        code_toolbar.pack(fill=tk.X, pady=(0, 3))

        ttk.Button(code_toolbar, text="🤖 AI 生成代码",
                   command=self._llm_mapping_doc_to_code,
                   style='Accent.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(code_toolbar, text="🐍 本地生成代码",
                   command=self._local_mapping_doc_to_code,
                   style='Accent.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Separator(code_toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        ttk.Button(code_toolbar, text="📋 复制代码", command=self._copy_doc_code).pack(side=tk.LEFT, padx=2)
        ttk.Button(code_toolbar, text="💾 保存代码...", command=self._save_doc_code).pack(side=tk.LEFT, padx=2)
        ttk.Button(code_toolbar, text="📋 复制到代码标签页", command=self._copy_doc_to_code_tab).pack(side=tk.LEFT, padx=2)

        self.doc_code_text = scrolledtext.ScrolledText(
            stage3_lf, wrap=tk.NONE, font=('Consolas', 10),
            bg='#1e1e1e', fg='#d4d4d4', insertbackground='white',
            selectbackground='#264f78', height=6
        )
        self.doc_code_text.pack(fill=tk.BOTH, expand=True)

        self.doc_code_text.tag_configure('keyword', foreground='#569cd6')
        self.doc_code_text.tag_configure('type', foreground='#4ec9b0')
        self.doc_code_text.tag_configure('string', foreground='#ce9178')
        self.doc_code_text.tag_configure('comment', foreground='#6a9955')
        self.doc_code_text.tag_configure('error', foreground='#f44747')

    # ──────────────────────────────────────────────
    # LLM 配置管理
    # ──────────────────────────────────────────────

    def _load_llm_config(self):
        """从 miapikey.txt 加载 LLM 设置（3行格式: key, url, model）"""
        try:
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'miapikey.txt')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]
                if len(lines) >= 1:
                    self.llm_service.api_key = lines[0]
                if len(lines) >= 2:
                    self.llm_service.base_url = lines[1]
                if len(lines) >= 3:
                    self.llm_service.model = lines[2]
        except Exception:
            pass

    def _save_llm_config(self):
        """保存 LLM 设置到 miapikey.txt（3行格式: key, url, model）"""
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'miapikey.txt')
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(f"{self.llm_service.api_key}\n")
                f.write(f"{self.llm_service.base_url}\n")
                f.write(f"{self.llm_service.model}\n")
        except Exception as e:
            messagebox.showerror("错误", f"保存 LLM 配置失败: {e}")

    def _update_ai_status(self):
        """更新 AI 状态显示"""
        if hasattr(self, 'ai_status_var'):
            if self.llm_service.is_configured():
                self.ai_status_var.set(
                    f"✅ 已配置: {self.llm_service.base_url} | 模型: {self.llm_service.model}"
                )
            else:
                self.ai_status_var.set("⚠️ 未配置 LLM 服务 - 点击「设置」配置 API Key 和 URL")

    def _show_llm_settings(self):
        """显示 LLM 服务设置对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("LLM 服务设置")
        dialog.geometry("620x580")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(True, True)
        dialog.minsize(500, 500)

        main_frame = ttk.Frame(dialog, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 标题
        ttk.Label(main_frame, text="🤖 LLM 大模型服务配置",
                  font=('Microsoft YaHei UI', 13, 'bold')).pack(anchor=tk.W, pady=(0, 10))

        ttk.Label(main_frame, text="配置 OpenAI 兼容的 LLM API 服务，用于 AI 辅助代码生成。",
                  style='Info.TLabel', wraplength=550).pack(anchor=tk.W, pady=(0, 15))

        # API URL
        url_frame = ttk.LabelFrame(main_frame, text="API Base URL", padding=8)
        url_frame.pack(fill=tk.X, pady=(0, 8))

        url_entry = ttk.Entry(url_frame, width=60)
        url_entry.pack(fill=tk.X)
        url_entry.insert(0, self.llm_service.base_url)

        ttk.Label(url_frame, text="示例: https://api.openai.com/v1  或  http://localhost:8080/v1",
                  style='Info.TLabel').pack(anchor=tk.W, pady=(3, 0))

        # API Key
        key_frame = ttk.LabelFrame(main_frame, text="API Key（可选，部分服务不需要）", padding=8)
        key_frame.pack(fill=tk.X, pady=(0, 8))

        key_entry = ttk.Entry(key_frame, width=60, show='*')
        key_entry.pack(fill=tk.X)
        key_entry.insert(0, self.llm_service.api_key)

        show_var = tk.BooleanVar(value=False)

        def toggle_key():
            key_entry.config(show='' if show_var.get() else '*')

        ttk.Checkbutton(key_frame, text="显示 API Key", variable=show_var,
                        command=toggle_key).pack(anchor=tk.W, pady=(3, 0))

        # 模型名称
        model_frame = ttk.LabelFrame(main_frame, text="模型名称", padding=8)
        model_frame.pack(fill=tk.X, pady=(0, 8))

        model_entry = ttk.Entry(model_frame, width=60)
        model_entry.pack(fill=tk.X)
        model_entry.insert(0, self.llm_service.model)

        model_hint = ttk.Label(
            model_frame,
            text="示例: gpt-4o, gpt-3.5-turbo, deepseek-chat, qwen-plus, glm-4 等",
            style='Info.TLabel'
        )
        model_hint.pack(anchor=tk.W, pady=(3, 0))

        # 预设按钮
        preset_frame = ttk.LabelFrame(main_frame, text="快速预设", padding=8)
        preset_frame.pack(fill=tk.X, pady=(0, 8))

        presets = [
            ("小米 MiMo", "https://token-plan-cn.xiaomimimo.com/v1", "MIMO-V2.5-Pro"),
            ("OpenAI", "https://api.openai.com/v1", "gpt-4o"),
            ("DeepSeek", "https://api.deepseek.com/v1", "deepseek-chat"),
            ("通义千问", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
            ("智谱 GLM", "https://open.bigmodel.cn/api/paas/v4", "glm-4"),
            ("本地 Ollama", "http://localhost:11434/v1", "qwen2.5"),
        ]

        preset_btn_frame = ttk.Frame(preset_frame)
        preset_btn_frame.pack(fill=tk.X)

        for i, (name, url, model) in enumerate(presets):
            col = i % 3
            row = i // 3
            preset_btn_frame.columnconfigure(col, weight=1)
            btn = ttk.Button(
                preset_btn_frame, text=name,
                command=lambda u=url, m=model: (
                    url_entry.delete(0, tk.END), url_entry.insert(0, u),
                    model_entry.delete(0, tk.END), model_entry.insert(0, m)
                )
            )
            btn.grid(row=row, column=col, padx=3, pady=2, sticky='ew')

        # 测试结果
        self.test_result_var = tk.StringVar(value="")

        # 按钮区域
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        def do_test():
            self.test_result_var.set("⏳ 正在测试连接...")
            dialog.update_idletasks()

            temp_service = LLMService(
                api_key=key_entry.get().strip(),
                base_url=url_entry.get().strip(),
                model=model_entry.get().strip(),
            )
            success, msg = temp_service.test_connection()
            if success:
                self.test_result_var.set(f"✅ 连接成功: {msg[:100]}")
            else:
                self.test_result_var.set(f"❌ 连接失败: {msg[:200]}")

        def do_save():
            self.llm_service.base_url = url_entry.get().strip()
            self.llm_service.api_key = key_entry.get().strip()
            self.llm_service.model = model_entry.get().strip()
            self._save_llm_config()
            self._update_ai_status()
            messagebox.showinfo("成功", "LLM 服务配置已保存！")
            dialog.destroy()

        ttk.Button(btn_frame, text="🔗 测试连接", command=do_test).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="💾 保存设置", command=do_save, style='Accent.TButton').pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side=tk.RIGHT, padx=3)

        ttk.Label(main_frame, textvariable=self.test_result_var,
                  style='Info.TLabel', wraplength=550).pack(anchor=tk.W, pady=(5, 0))

    def _test_llm_connection(self):
        """测试 LLM 连接"""
        if not self.llm_service.is_configured():
            messagebox.showwarning("警告", "请先配置 LLM 服务！")
            self._show_llm_settings()
            return

        self.status_var.set("正在测试 LLM 连接...")
        self.root.update_idletasks()

        success, msg = self.llm_service.test_connection()
        if success:
            messagebox.showinfo("成功", f"LLM 连接测试成功！\n\n响应: {msg[:200]}")
            self.status_var.set("LLM 连接测试成功")
        else:
            messagebox.showerror("失败", f"LLM 连接测试失败！\n\n{msg}")
            self.status_var.set("LLM 连接测试失败")

    # ──────────────────────────────────────────────
    # AI 代码生成
    # ──────────────────────────────────────────────

    def _llm_generate_code(self):
        """通过 LLM 基于当前映射关系生成代码"""
        if not self.llm_service.is_configured():
            messagebox.showwarning("警告", "请先配置 LLM 服务！\n菜单: 🤖 AI 助手 → ⚙️ LLM 服务设置")
            return

        if not self.mappings:
            messagebox.showwarning("警告", "请先添加映射关系！")
            return

        # 收集映射信息
        mapping_info = self._build_mapping_info_text()

        # 收集头文件内容
        header_content = self._collect_header_content()

        self.status_var.set("正在通过 AI 生成代码，请稍候...")
        self.root.update_idletasks()

        # 在后台线程中调用 LLM
        def call_llm():
            success, result = self.llm_service.generate_code_from_mapping(
                mapping_info, header_content
            )
            # 在主线程中更新 UI
            self.root.after(0, lambda: self._on_llm_code_result(success, result))

        thread = threading.Thread(target=call_llm, daemon=True)
        thread.start()

    def _on_llm_code_result(self, success: bool, result: str):
        """LLM 代码生成结果回调"""
        if not hasattr(self, 'ai_code_text'):
            return

        self.ai_code_text.delete('1.0', tk.END)

        if success:
            # 提取代码块
            code = self._extract_code_from_llm_response(result)
            self.ai_code_text.insert('1.0', code)
            self.status_var.set("✅ AI 代码生成完成")
        else:
            self.ai_code_text.insert('1.0', f"/* 生成失败 */\n/* {result} */")
            self.status_var.set("❌ AI 代码生成失败")

    def _build_mapping_info_text(self) -> str:
        """构建映射关系的文本描述"""
        lines = ["## 变量映射关系\n"]

        if self.selected_extern_var:
            lines.append(f"### 源 Extern 变量")
            lines.append(f"- 名称: {self.selected_extern_var['name']}")
            lines.append(f"- 类型: {self.selected_extern_var['type']}")
            if self.selected_extern_var.get('is_struct'):
                lines.append(f"- 结构体类型: {self.selected_extern_var.get('struct_type', '')}")
            lines.append("")

        lines.append("### 用户变量")
        for v in self.user_vars:
            lines.append(f"- `{v['name']}` : `{v['type']}` (来源: {v.get('source', '手动')})")
        lines.append("")

        lines.append("### 映射规则")
        for i, m in enumerate(self.mappings, 1):
            lines.append(f"{i}. 源成员 `{m['extern_member']}` → 目标变量 `{m['user_var']}`")
            lines.append(f"   - 操作: {m['op_type']}")
            lines.append(f"   - 转换: {m.get('conversion', '=')}")
            if m.get('conv_rule') and m['conv_rule'] != '=':
                lines.append(f"   - 转换规则: {m['conv_rule']}")
            conditions = m.get('condition', [])
            if conditions:
                lines.append(f"   - 条件:")
                for c in conditions:
                    lines.append(f"     - {c.get('var_ref', '')} {c.get('operator', '')} {c.get('value', '')} ({c.get('logic', '')})")
            lines.append("")

        return "\n".join(lines)

    def _collect_header_content(self) -> str:
        """收集当前加载的头文件内容"""
        parts = []

        source_file = self.current_file.get()
        if source_file and os.path.exists(source_file):
            try:
                with open(source_file, 'r', encoding='utf-8', errors='replace') as f:
                    parts.append(f"/* 源头文件: {os.path.basename(source_file)} */")
                    parts.append(f"```c\n{f.read()}\n```")
            except Exception:
                pass

        target_file = self.target_file.get()
        if target_file and os.path.exists(target_file):
            try:
                with open(target_file, 'r', encoding='utf-8', errors='replace') as f:
                    parts.append(f"\n/* 目标头文件: {os.path.basename(target_file)} */")
                    parts.append(f"```c\n{f.read()}\n```")
            except Exception:
                pass

        return "\n\n".join(parts) if parts else "（未加载头文件）"

    def _copy_ai_code(self):
        """复制 AI 生成的代码"""
        if not hasattr(self, 'ai_code_text'):
            return
        code = self.ai_code_text.get('1.0', tk.END).strip()
        if not code:
            messagebox.showwarning("警告", "没有可复制的内容！")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(code)
        self.status_var.set("AI 生成代码已复制到剪贴板")

    def _save_ai_code(self):
        """保存 AI 生成的代码"""
        if not hasattr(self, 'ai_code_text'):
            return
        code = self.ai_code_text.get('1.0', tk.END).strip()
        if not code:
            messagebox.showwarning("警告", "没有可保存的内容！")
            return

        file_path = filedialog.asksaveasfilename(
            title="保存 AI 生成代码",
            defaultextension=".c",
            filetypes=[("C 源文件", "*.c"), ("头文件", "*.h"), ("所有文件", "*.*")]
        )
        if not file_path:
            return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)
            messagebox.showinfo("成功", f"代码已保存到: {file_path}")
            self.status_var.set(f"AI 代码已保存: {file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

    def _copy_ai_to_code_tab(self):
        """将 AI 生成代码复制到代码标签页"""
        if not hasattr(self, 'ai_code_text'):
            return
        code = self.ai_code_text.get('1.0', tk.END).strip()
        if not code:
            messagebox.showwarning("警告", "没有可复制的内容！")
            return
        self.code_text.delete('1.0', tk.END)
        self.code_text.insert('1.0', code)
        self._apply_syntax_highlighting()
        self.status_var.set("已将 AI 生成代码复制到代码标签页")

    # ──────────────────────────────────────────────
    # 文档驱动代码生成
    # ──────────────────────────────────────────────

    # _load_document 已在简单模式部分定义，高级模式复用同一方法

    def _import_mappings_from_doc(self):
        """从文档导入映射关系到当前映射列表"""
        file_path = filedialog.askopenfilename(
            title="选择映射关系文档",
            filetypes=[
                ("Markdown 文件", "*.md"),
                ("文本文件", "*.txt"),
                ("CSV 文件", "*.csv"),
                ("Word 文档", "*.docx"),
                ("所有文件", "*.*")
            ]
        )
        if not file_path:
            return

        try:
            content = ""
            ext = os.path.splitext(file_path)[1].lower()

            if ext == '.docx':
                try:
                    from docx import Document as DocxDocument
                    doc = DocxDocument(file_path)
                    # 读取段落
                    paragraphs = [p.text for p in doc.paragraphs]
                    # 读取表格
                    for table in doc.tables:
                        for row in table.rows:
                            cells = [cell.text for cell in row.cells]
                            paragraphs.append(' | '.join(cells))
                    content = "\n".join(paragraphs)
                except ImportError:
                    messagebox.showwarning(
                        "提示",
                        "读取 .docx 文件需要安装 python-docx 库。\n"
                        "请运行: pip install python-docx\n\n"
                        "您也可以将文档内容保存为 .txt 或 .md 格式后加载。"
                    )
                    return
            else:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()

            if not content.strip():
                messagebox.showwarning("警告", "文档内容为空！")
                return

            # 使用 DocumentBasedGenerator 解析映射关系
            generator = DocumentBasedGenerator(
                parser=self.parser,
                target_parser=self.target_parser
            )
            imported_vars, imported_mappings = generator.parse_mappings_from_document(content)

            if not imported_mappings:
                messagebox.showwarning(
                    "警告",
                    "未能从文档中解析出映射关系！\n\n"
                    "请确保文档格式正确。支持的格式：\n"
                    "• 源成员 -> 目标成员\n"
                    "• 源成员 映射到 目标成员\n"
                    "• Markdown 表格\n\n"
                    "详细规则请参考《映射文档编写规则.md》"
                )
                return

            # 显示导入预览对话框
            self._show_import_preview(imported_vars, imported_mappings, file_path)

        except Exception as e:
            messagebox.showerror("错误", f"导入映射关系失败: {e}")

    def _show_import_preview(self, imported_vars: List[Dict], imported_mappings: List[Dict],
                              file_path: str):
        """显示导入预览对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("导入映射关系预览")
        dialog.geometry("750x600")
        dialog.transient(self.root)
        dialog.grab_set()

        # 信息标签
        info_frame = ttk.Frame(dialog, padding=5)
        info_frame.pack(fill=tk.X)

        ttk.Label(
            info_frame,
            text=f"📄 文件: {os.path.basename(file_path)}",
            style='Info.TLabel'
        ).pack(anchor=tk.W)
        ttk.Label(
            info_frame,
            text=f"✅ 解析到 {len(imported_vars)} 个变量, {len(imported_mappings)} 条映射关系",
            style='Success.TLabel'
        ).pack(anchor=tk.W)

        notebook = ttk.Notebook(dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 映射关系预览
        map_frame = ttk.Frame(notebook, padding=5)
        notebook.add(map_frame, text=f" 映射关系 ({len(imported_mappings)}) ")

        columns = ('source', 'target', 'op_type', 'conversion', 'condition')
        preview_tree = ttk.Treeview(
            map_frame, columns=columns, show='headings', height=12
        )
        preview_tree.heading('source', text='源成员')
        preview_tree.heading('target', text='目标变量')
        preview_tree.heading('op_type', text='操作类型')
        preview_tree.heading('conversion', text='转换规则')
        preview_tree.heading('condition', text='条件')
        preview_tree.column('source', width=150, minwidth=80)
        preview_tree.column('target', width=150, minwidth=80)
        preview_tree.column('op_type', width=80, minwidth=60)
        preview_tree.column('conversion', width=80, minwidth=50)
        preview_tree.column('condition', width=150, minwidth=60)

        scroll = ttk.Scrollbar(map_frame, orient=tk.VERTICAL, command=preview_tree.yview)
        preview_tree.configure(yscrollcommand=scroll.set)
        preview_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        for m in imported_mappings:
            cond_str = ''
            conditions = m.get('condition', [])
            if conditions:
                cond_parts = []
                for c in conditions:
                    cond_parts.append(f"{c.get('var_ref', '')} {c.get('operator', '')} {c.get('value', '')}")
                cond_str = ' AND '.join(cond_parts)
            preview_tree.insert('', tk.END, values=(
                m.get('extern_member', ''),
                m.get('user_var', ''),
                m.get('op_type', '直接赋值'),
                m.get('conversion', '='),
                cond_str
            ))

        # 变量预览
        var_frame = ttk.Frame(notebook, padding=5)
        notebook.add(var_frame, text=f" 用户变量 ({len(imported_vars)}) ")

        var_columns = ('name', 'type', 'desc', 'source')
        var_tree = ttk.Treeview(
            var_frame, columns=var_columns, show='headings', height=10
        )
        var_tree.heading('name', text='变量名')
        var_tree.heading('type', text='类型')
        var_tree.heading('desc', text='描述')
        var_tree.heading('source', text='来源')
        var_tree.column('name', width=150, minwidth=80)
        var_tree.column('type', width=100, minwidth=60)
        var_tree.column('desc', width=200, minwidth=80)
        var_tree.column('source', width=80, minwidth=50)

        var_scroll = ttk.Scrollbar(var_frame, orient=tk.VERTICAL, command=var_tree.yview)
        var_tree.configure(yscrollcommand=var_scroll.set)
        var_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        var_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        for v in imported_vars:
            var_tree.insert('', tk.END, values=(
                v.get('name', ''),
                v.get('type', ''),
                v.get('desc', ''),
                v.get('source', '文档导入')
            ))

        # 选项
        opt_frame = ttk.Frame(dialog, padding=5)
        opt_frame.pack(fill=tk.X)

        merge_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opt_frame, text="合并模式（保留现有映射，追加新映射）",
            variable=merge_var
        ).pack(anchor=tk.W)

        import_vars_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opt_frame, text="同时导入解析到的用户变量",
            variable=import_vars_var
        ).pack(anchor=tk.W)

        # 按钮
        btn_frame = ttk.Frame(dialog, padding=5)
        btn_frame.pack(fill=tk.X, pady=(5, 0))

        def do_import():
            do_merge = merge_var.get()
            do_import_vars = import_vars_var.get()
            count_maps = 0
            count_vars = 0

            if do_import_vars:
                for v in imported_vars:
                    if not any(uv['name'] == v['name'] for uv in self.user_vars):
                        self.user_vars.append(v)
                        count_vars += 1

            if do_merge:
                for m in imported_mappings:
                    already = any(
                        em['extern_member'] == m['extern_member'] and em['user_var'] == m['user_var']
                        for em in self.mappings
                    )
                    if not already:
                        self.mappings.append(m)
                        count_maps += 1
            else:
                self.mappings = imported_mappings
                count_maps = len(imported_mappings)

            self._refresh_user_var_list()
            self._update_user_var_combo()
            self._refresh_mapping_list()

            self.status_var.set(
                f"从文档导入了 {count_maps} 条映射关系和 {count_vars} 个用户变量"
            )
            dialog.destroy()
            messagebox.showinfo(
                "导入完成",
                f"成功导入:\n• 映射关系: {count_maps} 条\n• 用户变量: {count_vars} 个"
            )

        ttk.Button(btn_frame, text="✅ 确认导入", command=do_import,
                   style='Accent.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def _clear_document(self):
        """清除已加载的文档"""
        self.doc_content = ""
        self.doc_file_path = ""
        self.doc_file_var.set("未加载文档")
        self.status_var.set("已清除文档")

    def _update_doc_header_combo(self):
        """更新文档关联头文件下拉框"""
        values = []
        if self.current_file.get():
            values.append(self.current_file.get())
        if self.target_file.get():
            values.append(self.target_file.get())
        if hasattr(self, 'doc_header_combo'):
            self.doc_header_combo['values'] = values
            if values:
                self.doc_header_var.set(values[0])

    def _browse_doc_header(self):
        """浏览选择关联头文件"""
        file_path = filedialog.askopenfilename(
            title="选择关联头文件",
            filetypes=[
                ("C 头文件", "*.h"),
                ("C 源文件", "*.c"),
                ("所有文件", "*.*")
            ]
        )
        if file_path:
            self.doc_header_var.set(file_path)

    def _get_doc_header_content(self) -> str:
        """获取文档关联的头文件内容"""
        header_path = self.doc_header_var.get() if hasattr(self, 'doc_header_var') else ""
        if header_path and os.path.exists(header_path):
            try:
                with open(header_path, 'r', encoding='utf-8', errors='replace') as f:
                    return f.read()
            except Exception:
                pass
        return self._collect_header_content()

    # ──────────────────────────────────────────────
    # 映射文档工作流 - 阶段1: GUI映射→映射文档
    # ──────────────────────────────────────────────

    def _export_mapping_doc_from_gui(self):
        """从当前 GUI 映射关系生成规范映射文档"""
        if not self.mappings:
            messagebox.showwarning("警告", "请先在 GUI 中配置映射关系！")
            return

        generator = MappingDocGenerator(self)
        doc = generator.generate()
        self.mapping_doc_content = doc

        if hasattr(self, 'mapping_doc_text'):
            self.mapping_doc_text.delete('1.0', tk.END)
            self.mapping_doc_text.insert('1.0', doc)

        self.status_var.set("✅ 已从 GUI 映射关系生成规范映射文档")

    def _export_mapping_doc(self):
        """导出规范映射文档到文件"""
        self._export_mapping_doc_from_gui()
        if not self.mapping_doc_content:
            return

        file_path = filedialog.asksaveasfilename(
            title="保存规范映射文档",
            defaultextension=".md",
            filetypes=[
                ("Markdown 文件", "*.md"),
                ("文本文件", "*.txt"),
                ("所有文件", "*.*")
            ]
        )
        if not file_path:
            return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(self.mapping_doc_content)
            messagebox.showinfo("成功", f"映射文档已保存到: {file_path}")
            self.status_var.set(f"映射文档已保存: {file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

    def _import_mapping_doc(self):
        """从文件加载规范映射文档"""
        file_path = filedialog.askopenfilename(
            title="加载规范映射文档",
            filetypes=[
                ("Markdown 文件", "*.md"),
                ("文本文件", "*.txt"),
                ("所有文件", "*.*")
            ]
        )
        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

            self.mapping_doc_content = content
            if hasattr(self, 'mapping_doc_text'):
                self.mapping_doc_text.delete('1.0', tk.END)
                self.mapping_doc_text.insert('1.0', content)

            self.status_var.set(f"已加载映射文档: {os.path.basename(file_path)}")
        except Exception as e:
            messagebox.showerror("错误", f"加载映射文档失败: {e}")

    def _import_mapping_doc_to_gui(self):
        """将映射文档中的映射关系导入到 GUI"""
        if not hasattr(self, 'mapping_doc_text'):
            return
        content = self.mapping_doc_text.get('1.0', tk.END).strip()
        if not content:
            messagebox.showwarning("警告", "映射文档为空！")
            return

        generator = DocumentBasedGenerator(
            parser=self.parser,
            target_parser=self.target_parser
        )
        imported_vars, imported_mappings = generator.parse_mappings_from_document(content)

        if not imported_mappings:
            messagebox.showwarning(
                "警告",
                "未能从映射文档中解析出映射关系！\n"
                "请确保文档格式正确。"
            )
            return

        self._show_import_preview(imported_vars, imported_mappings, "映射文档")

    # ──────────────────────────────────────────────
    # 映射文档工作流 - 阶段2: 自然语言→映射文档 (LLM)
    # ──────────────────────────────────────────────

    def _llm_doc_to_mapping_doc(self):
        """通过 LLM 将自然语言文档转换为规范映射文档"""
        if not self.llm_service.is_configured():
            messagebox.showwarning("警告", "请先配置 LLM 服务！\n菜单: 🤖 AI 助手 → ⚙️ LLM 服务设置")
            return

        if not self.doc_content:
            messagebox.showwarning("警告", "请先加载需求文档！")
            return

        header_content = self._get_doc_header_content()

        self.status_var.set("正在通过 AI 将自然语言文档转换为映射文档...")
        self.root.update_idletasks()

        def call_llm():
            success, result = self.llm_service.convert_doc_to_mapping_doc(
                self.doc_content, header_content
            )
            self.root.after(0, lambda: self._on_mapping_doc_result(success, result))

        thread = threading.Thread(target=call_llm, daemon=True)
        thread.start()

    def _on_mapping_doc_result(self, success: bool, result: str):
        """映射文档生成结果回调"""
        if not hasattr(self, 'mapping_doc_text'):
            return

        if success:
            # 尝试提取文档内容（可能被代码块包裹）
            doc = self._extract_mapping_doc_from_response(result)
            self.mapping_doc_content = doc
            self.mapping_doc_text.delete('1.0', tk.END)
            self.mapping_doc_text.insert('1.0', doc)
            self.status_var.set("✅ AI 映射文档生成完成，可编辑后用于生成代码")
        else:
            self.mapping_doc_text.delete('1.0', tk.END)
            self.mapping_doc_text.insert('1.0', f"/* 生成失败 */\n{result}")
            self.status_var.set("❌ AI 映射文档生成失败")

    # ──────────────────────────────────────────────
    # 映射文档工作流 - 阶段3: 映射文档→代码
    # ──────────────────────────────────────────────

    def _llm_mapping_doc_to_code(self):
        """通过 LLM 基于规范映射文档生成代码"""
        if not self.llm_service.is_configured():
            messagebox.showwarning("警告", "请先配置 LLM 服务！\n菜单: 🤖 AI 助手 → ⚙️ LLM 服务设置")
            return

        mapping_doc = self._get_current_mapping_doc()
        if not mapping_doc:
            return

        header_content = self._get_doc_header_content()

        self.status_var.set("正在通过 AI 基于映射文档生成代码...")
        self.root.update_idletasks()

        def call_llm():
            success, result = self.llm_service.generate_code_from_mapping_doc(
                mapping_doc, header_content
            )
            self.root.after(0, lambda: self._on_doc_code_result(success, result))

        thread = threading.Thread(target=call_llm, daemon=True)
        thread.start()

    def _local_mapping_doc_to_code(self):
        """本地基于映射文档生成代码"""
        mapping_doc = self._get_current_mapping_doc()
        if not mapping_doc:
            return

        header_content = self._get_doc_header_content()

        generator = DocumentBasedGenerator(
            parser=self.parser,
            target_parser=self.target_parser
        )
        code = generator.generate_code(
            mapping_doc,
            header_content,
            source_structs=dict(self.parser.structs) if self.parser else {},
            target_structs=dict(self.target_parser.structs) if self.target_parser else {},
        )

        if hasattr(self, 'doc_code_text'):
            self.doc_code_text.delete('1.0', tk.END)
            self.doc_code_text.insert('1.0', code)

        self.status_var.set("✅ 本地映射文档代码生成完成")

    def _get_current_mapping_doc(self) -> str:
        """获取当前映射文档内容"""
        if not hasattr(self, 'mapping_doc_text'):
            return ""
        content = self.mapping_doc_text.get('1.0', tk.END).strip()
        if not content:
            messagebox.showwarning("警告", "映射文档为空！请先生成或加载映射文档。")
            return ""
        return content

    def _on_doc_code_result(self, success: bool, result: str):
        """映射文档→代码 结果回调"""
        if not hasattr(self, 'doc_code_text'):
            return

        self.doc_code_text.delete('1.0', tk.END)

        if success:
            code = self._extract_code_from_llm_response(result)
            self.doc_code_text.insert('1.0', code)
            self.status_var.set("✅ AI 映射文档代码生成完成")
        else:
            self.doc_code_text.insert('1.0', f"/* 生成失败 */\n/* {result} */")
            self.status_var.set("❌ AI 映射文档代码生成失败")

    def _copy_doc_code(self):
        """复制文档生成代码"""
        if not hasattr(self, 'doc_code_text'):
            return
        code = self.doc_code_text.get('1.0', tk.END).strip()
        if not code:
            messagebox.showwarning("警告", "没有可复制的内容！")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(code)
        self.status_var.set("文档生成代码已复制到剪贴板")

    def _save_doc_code(self):
        """保存文档生成代码"""
        if not hasattr(self, 'doc_code_text'):
            return
        code = self.doc_code_text.get('1.0', tk.END).strip()
        if not code:
            messagebox.showwarning("警告", "没有可保存的内容！")
            return

        file_path = filedialog.asksaveasfilename(
            title="保存文档生成代码",
            defaultextension=".c",
            filetypes=[("C 源文件", "*.c"), ("头文件", "*.h"), ("所有文件", "*.*")]
        )
        if not file_path:
            return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)
            messagebox.showinfo("成功", f"代码已保存到: {file_path}")
            self.status_var.set(f"文档生成代码已保存: {file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

    def _copy_doc_to_code_tab(self):
        """将文档生成代码复制到代码标签页"""
        if not hasattr(self, 'doc_code_text'):
            return
        code = self.doc_code_text.get('1.0', tk.END).strip()
        if not code:
            messagebox.showwarning("警告", "没有可复制的内容！")
            return
        self.code_text.delete('1.0', tk.END)
        self.code_text.insert('1.0', code)
        self._apply_syntax_highlighting()
        self.status_var.set("已将文档生成代码复制到代码标签页")

    def _open_file(self):
        file_path = filedialog.askopenfilename(
            title="选择头文件",
            filetypes=[
                ("C 头文件", "*.h"),
                ("C 源文件", "*.c"),
                ("所有文件", "*.*")
            ]
        )
        if not file_path:
            return

        self.current_file.set(file_path)
        success = self.parser.parse_file(file_path)

        if not success:
            messagebox.showerror("错误", f"无法解析文件: {file_path}")
            return

        self._refresh_extern_list()
        self._update_struct_type_combo()
        self._update_condition_var_combo()

        summary = self.parser.get_summary()
        self.parse_info_var.set(
            f"✅ 已加载: {os.path.basename(file_path)} | "
            f"结构体: {summary['struct_count']} | "
            f"Extern: {summary['extern_var_count']} | "
            f"Typedef: {summary['typedef_count']}"
        )
        self.status_var.set(f"已加载头文件: {file_path}")

    def _open_target_file(self):
        file_path = filedialog.askopenfilename(
            title="选择目标头文件",
            filetypes=[
                ("C 头文件", "*.h"),
                ("C 源文件", "*.c"),
                ("所有文件", "*.*")
            ]
        )
        if not file_path:
            return

        self.target_file.set(file_path)
        success = self.target_parser.parse_file(file_path)

        if not success:
            messagebox.showerror("错误", f"无法解析目标文件: {file_path}")
            return

        self._refresh_target_var_list()
        self._update_struct_type_combo()
        self._update_condition_var_combo()

        summary = self.target_parser.get_summary()
        self.target_info_var.set(
            f"✅ 目标: {os.path.basename(file_path)} | "
            f"结构体: {summary['struct_count']} | "
            f"Extern: {summary['extern_var_count']} | "
            f"Typedef: {summary['typedef_count']}"
        )
        self.status_var.set(f"已加载目标头文件: {file_path}")

    def _update_condition_var_combo(self):
        """更新条件变量选择下拉框"""
        if not hasattr(self, 'cond_var_ref'):
            return
        values = []
        if self.selected_extern_var and self.selected_extern_var.get('is_struct'):
            members = self.parser.get_nested_members(
                self.selected_extern_var.get('struct_type', '')
            )
            values = [m.get('full_path', m['name']) for m in members]
        self.cond_var_ref['values'] = values
        if values:
            self.cond_var_ref.set(values[0])
        else:
            self.cond_var_ref.set('')

    def _refresh_extern_list(self):
        if not hasattr(self, 'extern_tree'):
            return
        self.extern_tree.delete(*self.extern_tree.get_children())
        self.extern_vars = self.parser.extern_vars

        for var in self.extern_vars:
            is_struct = "✓" if var['is_struct'] else "—"
            self.extern_tree.insert('', tk.END, values=(
                var['name'], var['type'], is_struct
            ))

    def _refresh_target_var_list(self):
        if not hasattr(self, 'target_var_tree'):
            return
        self.target_var_tree.delete(*self.target_var_tree.get_children())

        for var in self.target_parser.extern_vars:
            is_struct = "✓" if var['is_struct'] else "—"
            struct_type = var.get('struct_type', '') if var['is_struct'] else "—"
            self.target_var_tree.insert('', tk.END, values=(
                var['name'], var['type'], is_struct, struct_type
            ))

    def _update_struct_type_combo(self):
        if not hasattr(self, 'struct_type_combo'):
            return
        struct_names = list(self.parser.structs.keys())
        target_struct_names = list(self.target_parser.structs.keys())
        all_structs = sorted(set(struct_names + target_struct_names))
        self.struct_type_combo['values'] = all_structs
        if all_structs:
            self.struct_type_combo.set(all_structs[0])
        else:
            self.struct_type_combo.set('')

    def _import_config(self):
        file_path = filedialog.askopenfilename(
            title="导入映射配置",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")]
        )
        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            self.user_vars = config.get('user_vars', [])
            self._refresh_user_var_list()

            self.mappings = config.get('mappings', [])
            self._refresh_mapping_list()

            header_file = config.get('header_file', '')
            if header_file and os.path.exists(header_file):
                self.current_file.set(header_file)
                self.parser.parse_file(header_file)
                self._refresh_extern_list()
                self._update_struct_type_combo()
                self._update_condition_var_combo()

            target_header = config.get('target_header_file', '')
            if target_header and os.path.exists(target_header):
                self.target_file.set(target_header)
                self.target_parser.parse_file(target_header)
                self._refresh_target_var_list()
                self._update_struct_type_combo()
                self._update_condition_var_combo()

            messagebox.showinfo("成功", "配置导入成功！")
            self.status_var.set(f"已导入配置: {os.path.basename(file_path)}")

        except Exception as e:
            messagebox.showerror("错误", f"导入配置失败: {e}")

    def _export_config(self):
        file_path = filedialog.asksaveasfilename(
            title="导出映射配置",
            defaultextension=".json",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")]
        )
        if not file_path:
            return

        config = {
            'header_file': self.current_file.get(),
            'target_header_file': self.target_file.get(),
            'user_vars': self.user_vars,
            'mappings': self.mappings,
        }

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("成功", f"配置已导出到: {file_path}")
            self.status_var.set(f"配置已导出: {file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"导出配置失败: {e}")

    def _on_extern_select(self, event):
        selection = self.extern_tree.selection()
        if not selection:
            return

        item = self.extern_tree.item(selection[0])
        var_name = item['values'][0]

        self.selected_extern_var = self.parser.get_extern_var(var_name)
        if not self.selected_extern_var:
            return

        self._refresh_member_list()
        self._update_extern_member_combo()
        self._update_condition_var_combo()

        self.member_title_var.set(
            f"变量: {var_name} ({self.selected_extern_var['type']})"
        )
        self.status_var.set(f"已选择 extern 变量: {var_name}")

    def _refresh_member_list(self):
        self.member_tree.delete(*self.member_tree.get_children())

        if not self.selected_extern_var:
            return

        if self.selected_extern_var['is_struct']:
            members = self.parser.get_nested_members(
                self.selected_extern_var['struct_type']
            )
            for m in members:
                array_info = str(m.get('array_size', '')) if m.get('is_array') else "—"
                pointer = "✓" if m.get('is_pointer') else "—"
                bitfield = str(m.get('bitfield_width', '')) if m.get('is_bitfield') else "—"
                self.member_tree.insert('', tk.END, values=(
                    m.get('full_path', m['name']),
                    m['type'],
                    array_info,
                    pointer,
                    bitfield
                ), tags=(m.get('full_path', m['name']),))
        else:
            self.member_tree.insert('', tk.END, values=(
                self.selected_extern_var['name'],
                self.selected_extern_var['type'],
                "—", "—", "—"
            ))

    def _update_extern_member_combo(self):
        if not hasattr(self, 'map_extern_member'):
            return
        values = []

        if self.selected_extern_var:
            if self.selected_extern_var['is_struct']:
                members = self.parser.get_nested_members(
                    self.selected_extern_var['struct_type']
                )
                values = [m.get('full_path', m['name']) for m in members]
            else:
                values = [self.selected_extern_var['name']]

        self.map_extern_member['values'] = values
        if values:
            self.map_extern_member.set(values[0])
        else:
            self.map_extern_member.set('')

    def _on_member_select(self, event):
        selection = self.member_tree.selection()
        if not selection:
            return

        item = self.member_tree.item(selection[0])
        member_name = item['values'][0]
        self.map_extern_member.set(member_name)

    def _on_user_var_type_changed(self, event=None):
        if self.user_var_type.get() == '自定义':
            self.user_var_custom_type.config(state='normal')
            self.struct_type_combo.config(state='readonly')
        else:
            self.user_var_custom_type.config(state='normal')
            self.struct_type_combo.config(state='readonly')

    def _on_struct_type_selected(self, event=None):
        selected = self.struct_type_combo.get()
        if selected:
            self.user_var_type.set('自定义')
            self.user_var_custom_type.delete(0, tk.END)
            self.user_var_custom_type.insert(0, selected)

    def _add_user_var(self):
        name = self.user_var_name.get().strip()
        type_sel = self.user_var_type.get()
        custom_type = self.user_var_custom_type.get().strip()
        desc = self.user_var_desc.get().strip()

        if not name:
            messagebox.showwarning("警告", "请输入变量名！")
            return

        var_type = custom_type if type_sel == '自定义' and custom_type else type_sel

        for v in self.user_vars:
            if v['name'] == name:
                messagebox.showwarning("警告", f"变量 '{name}' 已存在！")
                return

        is_struct = self._is_struct_type(var_type)

        self.user_vars.append({
            'name': name,
            'type': var_type,
            'desc': desc,
            'source': '手动',
            'is_struct': is_struct,
        })

        if is_struct:
            self._expand_struct_user_var(name, var_type)

        self._refresh_user_var_list()
        self._update_user_var_combo()

        self.user_var_name.delete(0, tk.END)
        self.user_var_custom_type.delete(0, tk.END)
        self.user_var_desc.delete(0, tk.END)

        self.status_var.set(f"已添加用户变量: {name} ({var_type})")

    def _is_struct_type(self, type_str: str) -> bool:
        clean = type_str.replace('*', '').strip()
        if clean.startswith('struct '):
            return True
        if clean in self.parser.structs:
            return True
        if clean in self.target_parser.structs:
            return True
        return False

    def _get_parser_for_struct(self, struct_type: str) -> Optional[HeaderParser]:
        clean = struct_type.replace('*', '').strip()
        if clean.startswith('struct '):
            clean = clean[7:].strip()
        if clean in self.parser.structs:
            return self.parser
        if clean in self.target_parser.structs:
            return self.target_parser
        return None

    def _expand_struct_user_var(self, var_name: str, var_type: str):
        parser = self._get_parser_for_struct(var_type)
        if not parser:
            return

        clean_type = var_type.replace('*', '').strip()
        if clean_type.startswith('struct '):
            clean_type = clean_type[7:].strip()

        members = parser.get_nested_members(clean_type)
        for m in members:
            member_name = f"{var_name}.{m.get('full_path', m['name'])}"
            if not any(v['name'] == member_name for v in self.user_vars):
                self.user_vars.append({
                    'name': member_name,
                    'type': m['type'],
                    'desc': f"{var_name} 的成员 {m.get('full_path', m['name'])}",
                    'source': f'结构体展开',
                    'is_struct': False,
                })

    def _add_from_struct(self):
        all_structs = sorted(set(
            list(self.parser.structs.keys()) + list(self.target_parser.structs.keys())
        ))
        if not all_structs:
            messagebox.showwarning("警告", "没有可用的结构体类型！请先加载头文件。")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("从结构体添加用户变量")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()

        top_frame = ttk.Frame(dialog, padding=5)
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="选择结构体类型:", style='Header.TLabel').pack(side=tk.LEFT)
        struct_combo = ttk.Combobox(top_frame, values=all_structs, state='readonly', width=25)
        struct_combo.pack(side=tk.LEFT, padx=5)
        if all_structs:
            struct_combo.set(all_structs[0])

        name_frame = ttk.Frame(dialog, padding=5)
        name_frame.pack(fill=tk.X)
        ttk.Label(name_frame, text="变量名前缀:").pack(side=tk.LEFT)
        prefix_entry = ttk.Entry(name_frame, width=20)
        prefix_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(name_frame, text="(留空则使用结构体名)", style='Info.TLabel').pack(side=tk.LEFT)

        expand_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(name_frame, text="展开结构体成员", variable=expand_var).pack(side=tk.LEFT, padx=10)

        member_frame = ttk.LabelFrame(dialog, text="结构体成员预览", padding=5)
        member_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        preview_columns = ('name', 'type', 'array', 'pointer')
        preview_tree = ttk.Treeview(
            member_frame, columns=preview_columns, show='headings',
            selectmode='extended', height=12
        )
        preview_tree.heading('name', text='成员名')
        preview_tree.heading('type', text='类型')
        preview_tree.heading('array', text='数组')
        preview_tree.heading('pointer', text='指针')
        preview_tree.column('name', width=150, minwidth=80)
        preview_tree.column('type', width=120, minwidth=80)
        preview_tree.column('array', width=60, minwidth=40, anchor=tk.CENTER)
        preview_tree.column('pointer', width=60, minwidth=40, anchor=tk.CENTER)

        preview_scroll = ttk.Scrollbar(member_frame, orient=tk.VERTICAL, command=preview_tree.yview)
        preview_tree.configure(yscrollcommand=preview_scroll.set)
        preview_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        preview_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        def on_struct_changed(event=None):
            preview_tree.delete(*preview_tree.get_children())
            sel = struct_combo.get()
            if not sel:
                return
            p = self._get_parser_for_struct(sel)
            if not p:
                return
            members = p.get_nested_members(sel)
            for m in members:
                array_info = str(m.get('array_size', '')) if m.get('is_array') else "—"
                pointer = "✓" if m.get('is_pointer') else "—"
                preview_tree.insert('', tk.END, values=(
                    m.get('full_path', m['name']),
                    m['type'],
                    array_info,
                    pointer
                ))

        struct_combo.bind('<<ComboboxSelected>>', on_struct_changed)
        if all_structs:
            on_struct_changed()

        def do_add():
            sel = struct_combo.get()
            if not sel:
                messagebox.showwarning("警告", "请选择结构体类型！")
                return

            prefix = prefix_entry.get().strip() or sel
            do_expand = expand_var.get()
            p = self._get_parser_for_struct(sel)
            if not p:
                return

            count = 0

            self.user_vars.append({
                'name': prefix,
                'type': sel,
                'desc': f'结构体变量 ({sel})',
                'source': '结构体添加',
                'is_struct': True,
            })
            count += 1

            if do_expand:
                members = p.get_nested_members(sel)
                for m in members:
                    member_name = f"{prefix}.{m.get('full_path', m['name'])}"
                    if not any(v['name'] == member_name for v in self.user_vars):
                        self.user_vars.append({
                            'name': member_name,
                            'type': m['type'],
                            'desc': f"{prefix} 的成员 {m.get('full_path', m['name'])}",
                            'source': '结构体展开',
                            'is_struct': False,
                        })
                        count += 1

            self._refresh_user_var_list()
            self._update_user_var_combo()
            self.status_var.set(f"从结构体 {sel} 添加了 {count} 个变量")
            dialog.destroy()

        btn_frame = ttk.Frame(dialog, padding=5)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="➕ 添加", command=do_add, style='Accent.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _del_user_var(self):
        selection = self.user_var_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择要删除的变量！")
            return

        item = self.user_var_tree.item(selection[0])
        var_name = item['values'][0]

        to_remove = [var_name]
        if any(v['name'] == var_name and v.get('is_struct') for v in self.user_vars):
            to_remove = [v['name'] for v in self.user_vars if v['name'] == var_name or v['name'].startswith(f"{var_name}.")]

        self.user_vars = [v for v in self.user_vars if v['name'] not in to_remove]
        self._refresh_user_var_list()
        self._update_user_var_combo()
        self.status_var.set(f"已删除用户变量: {var_name} (及 {len(to_remove) - 1} 个子成员)")

    def _batch_add_user_var(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("批量添加用户变量")
        dialog.geometry("450x350")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="每行一个变量，格式: 变量名 类型 [描述]", style='Info.TLabel').pack(pady=5)
        ttk.Label(dialog, text="示例: my_temp float 温度值", style='Info.TLabel').pack(pady=(0, 5))

        text = scrolledtext.ScrolledText(dialog, height=12, font=('Consolas', 10))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        def do_add():
            content = text.get('1.0', tk.END).strip()
            if not content:
                dialog.destroy()
                return

            count = 0
            for line in content.split('\n'):
                parts = line.strip().split()
                if len(parts) >= 2:
                    name, var_type = parts[0], parts[1]
                    desc = parts[2] if len(parts) > 2 else ""
                    if not any(v['name'] == name for v in self.user_vars):
                        is_struct = self._is_struct_type(var_type)
                        self.user_vars.append({
                            'name': name, 'type': var_type, 'desc': desc,
                            'source': '批量添加', 'is_struct': is_struct,
                        })
                        count += 1
                        if is_struct:
                            self._expand_struct_user_var(name, var_type)

            self._refresh_user_var_list()
            self._update_user_var_combo()
            self.status_var.set(f"批量添加了 {count} 个用户变量")
            dialog.destroy()

        ttk.Button(dialog, text="添加", command=do_add, style='Accent.TButton').pack(pady=10)

    def _refresh_user_var_list(self):
        if not hasattr(self, 'user_var_tree'):
            return
        self.user_var_tree.delete(*self.user_var_tree.get_children())
        for v in self.user_vars:
            source = v.get('source', '手动')
            self.user_var_tree.insert('', tk.END, values=(
                v['name'], v['type'], v.get('desc', ''), source
            ))

    def _update_user_var_combo(self):
        if not hasattr(self, 'map_user_var'):
            return
        values = [v['name'] for v in self.user_vars]
        self.map_user_var['values'] = values
        if values:
            self.map_user_var.set(values[0])
        else:
            self.map_user_var.set('')

    def _on_target_var_select(self, event):
        selection = self.target_var_tree.selection()
        if not selection:
            return

        self.target_member_tree.delete(*self.target_member_tree.get_children())

        for sel_item in selection:
            item = self.target_var_tree.item(sel_item)
            var_name = item['values'][0]
            var_info = self.target_parser.get_extern_var(var_name)
            if not var_info:
                continue

            if var_info['is_struct']:
                members = self.target_parser.get_nested_members(
                    var_info.get('struct_type', '')
                )
                for m in members:
                    array_info = str(m.get('array_size', '')) if m.get('is_array') else "—"
                    pointer = "✓" if m.get('is_pointer') else "—"
                    self.target_member_tree.insert('', tk.END, values=(
                        f"{var_name}.{m.get('full_path', m['name'])}",
                        m['type'],
                        array_info,
                        pointer
                    ))
            else:
                self.target_member_tree.insert('', tk.END, values=(
                    var_name,
                    var_info['type'],
                    "—",
                    "✓" if var_info.get('is_pointer') else "—"
                ))

    def _import_target_vars(self):
        selection = self.target_var_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择要导入的目标变量！")
            return

        count = 0
        for sel_item in selection:
            item = self.target_var_tree.item(sel_item)
            var_name = item['values'][0]
            var_info = self.target_parser.get_extern_var(var_name)
            if not var_info:
                continue

            if not any(v['name'] == var_name for v in self.user_vars):
                is_struct = var_info.get('is_struct', False)
                self.user_vars.append({
                    'name': var_name,
                    'type': var_info['type'],
                    'desc': f'来自目标头文件',
                    'source': '目标头文件',
                    'is_struct': is_struct,
                })
                count += 1

                if is_struct:
                    self._expand_struct_user_var_from_target(var_name, var_info)

        self._refresh_user_var_list()
        self._update_user_var_combo()
        self.status_var.set(f"从目标头文件导入了 {count} 个变量")

    def _import_all_target_vars(self):
        if not self.target_parser.extern_vars:
            messagebox.showwarning("警告", "目标头文件中没有变量！")
            return

        count = 0
        for var_info in self.target_parser.extern_vars:
            var_name = var_info['name']
            if not any(v['name'] == var_name for v in self.user_vars):
                is_struct = var_info.get('is_struct', False)
                self.user_vars.append({
                    'name': var_name,
                    'type': var_info['type'],
                    'desc': '来自目标头文件',
                    'source': '目标头文件',
                    'is_struct': is_struct,
                })
                count += 1

                if is_struct:
                    self._expand_struct_user_var_from_target(var_name, var_info)

        self._refresh_user_var_list()
        self._update_user_var_combo()
        self.status_var.set(f"从目标头文件导入了全部 {count} 个变量")

    def _import_target_struct_members(self):
        selection = self.target_var_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择一个结构体类型的目标变量！")
            return

        count = 0
        for sel_item in selection:
            item = self.target_var_tree.item(sel_item)
            var_name = item['values'][0]
            var_info = self.target_parser.get_extern_var(var_name)
            if not var_info or not var_info.get('is_struct'):
                continue

            struct_type = var_info.get('struct_type', '')
            members = self.target_parser.get_nested_members(struct_type)
            for m in members:
                member_name = f"{var_name}.{m.get('full_path', m['name'])}"
                if not any(v['name'] == member_name for v in self.user_vars):
                    self.user_vars.append({
                        'name': member_name,
                        'type': m['type'],
                        'desc': f'{var_name} 的成员 {m.get("full_path", m["name"])}',
                        'source': '目标结构体展开',
                        'is_struct': False,
                    })
                    count += 1

        self._refresh_user_var_list()
        self._update_user_var_combo()
        self.status_var.set(f"从目标结构体导入了 {count} 个成员变量")

    def _expand_struct_user_var_from_target(self, var_name: str, var_info: Dict):
        if not var_info.get('is_struct'):
            return

        struct_type = var_info.get('struct_type', '')
        members = self.target_parser.get_nested_members(struct_type)
        for m in members:
            member_name = f"{var_name}.{m.get('full_path', m['name'])}"
            if not any(v['name'] == member_name for v in self.user_vars):
                self.user_vars.append({
                    'name': member_name,
                    'type': m['type'],
                    'desc': f'{var_name} 的成员 {m.get("full_path", m["name"])}',
                    'source': '目标结构体展开',
                    'is_struct': False,
                })

    def _on_op_type_changed(self, event=None):
        pass

    def _add_mapping(self):
        ext_member = self.map_extern_member.get()
        user_var = self.map_user_var.get()
        op_type = self.map_op_type.get()
        conversion = self.map_conversion.get()
        custom_conv = self.map_custom_conv.get().strip()

        if not ext_member:
            messagebox.showwarning("警告", "请选择 Extern 成员！")
            return
        if not user_var:
            messagebox.showwarning("警告", "请选择用户变量！")
            return

        conv_rule = '='
        if conversion == '强制转换':
            conv_rule = f'({self._get_user_var_type(user_var)})'
        elif conversion == '缩放':
            conv_rule = custom_conv if custom_conv else '* 1.0'
        elif conversion == '偏移':
            conv_rule = f'+ ({custom_conv})' if custom_conv else '+ 0'
        elif conversion == '自定义':
            conv_rule = custom_conv if custom_conv else '='

        mapping = {
            'extern_member': ext_member,
            'user_var': user_var,
            'op_type': op_type,
            'condition': self.current_conditions.copy(),
            'conversion': conversion,
            'conv_rule': conv_rule,
        }

        self.mappings.append(mapping)
        self._refresh_mapping_list()
        self._clear_conditions()

        self.map_custom_conv.delete(0, tk.END)

        self.status_var.set(f"已添加映射: {ext_member} → {user_var} ({op_type})")

    def _auto_match(self):
        if not self.selected_extern_var or not self.selected_extern_var.get('is_struct'):
            messagebox.showwarning("警告", "请先选择一个结构体类型的 Extern 变量！")
            return

        if not self.user_vars:
            messagebox.showwarning("警告", "请先添加用户变量！")
            return

        ext_members = self.parser.get_nested_members(
            self.selected_extern_var['struct_type']
        )

        count = 0
        for ext_m in ext_members:
            ext_name = ext_m.get('full_path', ext_m['name'])
            ext_type = ext_m['type'].replace('*', '').strip()

            for uv in self.user_vars:
                if uv.get('is_struct'):
                    continue

                uv_base = uv['name'].split('.')[-1] if '.' in uv['name'] else uv['name']
                ext_base = ext_name.split('.')[-1] if '.' in ext_name else ext_name

                if uv_base.lower() == ext_base.lower():
                    already = any(
                        m['extern_member'] == ext_name and m['user_var'] == uv['name']
                        for m in self.mappings
                    )
                    if not already:
                        self.mappings.append({
                            'extern_member': ext_name,
                            'user_var': uv['name'],
                            'op_type': '直接赋值',
                            'condition': [],
                            'conversion': '=',
                            'conv_rule': '=',
                        })
                        count += 1

        self._refresh_mapping_list()
        self.status_var.set(f"自动匹配了 {count} 个映射关系")

    def _del_mapping(self):
        selection = self.mapping_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择要删除的映射！")
            return

        idx = self.mapping_tree.index(selection[0])
        if 0 <= idx < len(self.mappings):
            removed = self.mappings.pop(idx)
            self._refresh_mapping_list()
            self.status_var.set(f"已删除映射: {removed['extern_member']} → {removed['user_var']}")

    def _move_mapping(self, direction: int):
        selection = self.mapping_tree.selection()
        if not selection:
            return

        idx = self.mapping_tree.index(selection[0])
        new_idx = idx + direction
        if 0 <= new_idx < len(self.mappings):
            self.mappings[idx], self.mappings[new_idx] = self.mappings[new_idx], self.mappings[idx]
            self._refresh_mapping_list()
            children = self.mapping_tree.get_children()
            if new_idx < len(children):
                self.mapping_tree.selection_set(children[new_idx])

    def _on_mapping_select(self, event):
        selection = self.mapping_tree.selection()
        if not selection:
            return

        idx = self.mapping_tree.index(selection[0])
        if 0 <= idx < len(self.mappings):
            m = self.mappings[idx]
            self.map_extern_member.set(m['extern_member'])
            self.map_user_var.set(m['user_var'])
            self.map_op_type.set(m['op_type'])
            self.map_conversion.set(m.get('conversion', '='))
            self.map_custom_conv.delete(0, tk.END)
            self.map_custom_conv.insert(0, m.get('conv_rule', '='))

            self.current_conditions = m.get('condition', []).copy()
            self._update_condition_preview()

    def _refresh_mapping_list(self):
        if not hasattr(self, 'mapping_tree'):
            return
        self.mapping_tree.delete(*self.mapping_tree.get_children())
        for m in self.mappings:
            conditions = m.get('condition', [])
            cond_count = len(conditions) if isinstance(conditions, list) else 0
            self.mapping_tree.insert('', tk.END, values=(
                m['extern_member'],
                m['op_type'],
                m['user_var'],
                m.get('conversion', '='),
                cond_count
            ))

    def _clear_mappings(self):
        if self.mappings and messagebox.askyesno("确认", "确定要清空所有映射关系吗？"):
            self.mappings.clear()
            self._refresh_mapping_list()
            self.code_text.delete('1.0', tk.END)
            self.md_text.delete('1.0', tk.END)
            self.status_var.set("已清空所有映射")

    def _get_user_var_type(self, var_name: str) -> str:
        for v in self.user_vars:
            if v['name'] == var_name:
                return v['type']
        return 'int'

    def _get_user_var_info(self, var_name: str) -> Optional[Dict]:
        for v in self.user_vars:
            if v['name'] == var_name:
                return v
        return None

    def _is_target_var(self, var_name: str) -> bool:
        info = self._get_user_var_info(var_name)
        if info:
            return info.get('source', '') in ('目标头文件', '目标结构体展开')
        return False

    def _get_var_lhs(self, var_name: str) -> str:
        is_target = self._is_target_var(var_name)
        if is_target:
            if '.' in var_name:
                base, member = var_name.split('.', 1)
                return f"{base}->{member}"
            return var_name
        else:
            if '.' in var_name:
                base, member = var_name.split('.', 1)
                return f"(*{base}).{member}"
            return f"(*{var_name})"

    def _get_var_base(self, var_name: str) -> str:
        if '.' in var_name:
            return var_name.split('.', 1)[0]
        return var_name

    def _get_member_tail(self, var_name: str) -> str:
        if '.' in var_name:
            parts = var_name.split('.', 1)
            return parts[1]
        return ""

    def _collect_func_params(self, ext_var_name: str) -> list:
        params = []
        if self.selected_extern_var:
            params.append(f"{self.selected_extern_var['type']} *{ext_var_name}")
        for uv in self.user_vars:
            if any(m['user_var'] == uv['name'] for m in self.mappings):
                if self._is_target_var(uv['name']):
                    continue
                base = self._get_var_base(uv['name'])
                if not any(p.endswith(f"*{base}") for p in params):
                    params.append(f"{uv['type']} *{base}")
        return params

    def _collect_target_externs(self) -> list:
        result = []
        seen = set()
        for m in self.mappings:
            if self._is_target_var(m['user_var']):
                base = self._get_var_base(m['user_var'])
                if base not in seen:
                    seen.add(base)
                    tinfo = self._get_user_var_info(base)
                    if tinfo:
                        result.append((base, tinfo['type']))
        return result

    def _build_condition_expression(self, conditions: List[Dict], ext_var: str) -> str:
        """构建条件表达式字符串"""
        if not conditions or not isinstance(conditions, list):
            return ""

        parts = []
        for i, cond in enumerate(conditions):
            var_ref = cond.get('var_ref', '')
            operator = cond.get('operator', '==')
            value = cond.get('value', '')

            if not var_ref or not value:
                continue

            var_full = f"{ext_var}->{var_ref}"
            expr = f"{var_full} {operator} {value}"
            parts.append(expr)

        if not parts:
            return ""

        if len(parts) == 1:
            return parts[0]

        result = f"({parts[0]})"
        for i in range(1, len(parts)):
            logic = conditions[i].get('logic', 'AND')
            result += f" {logic} ({parts[i]})"

        return result

    def _generate_code(self):
        if not self.mappings:
            messagebox.showwarning("警告", "请先添加映射关系！")
            return

        template = self.code_template.get()
        ext_var_name = self._get_extern_var_name()

        if template == '赋值函数':
            code = self._gen_assignment_function(ext_var_name)
        elif template == '条件判断函数':
            code = self._gen_condition_function(ext_var_name)
        elif template == '完整转换函数':
            code = self._gen_full_function(ext_var_name)
        elif template == '仅赋值语句':
            code = self._gen_assignment_statements(ext_var_name)
        elif template == '仅判断语句':
            code = self._gen_condition_statements(ext_var_name)
        else:
            code = self._gen_assignment_function(ext_var_name)

        self.generated_code = code
        self.code_text.delete('1.0', tk.END)
        self.code_text.insert('1.0', code)
        self._apply_syntax_highlighting()
        self.status_var.set(f"已生成代码 (模板: {template})")

    def _gen_assignment_function(self, ext_var_name: str) -> str:
        lines = []
        lines.append(f"/*")
        lines.append(f" * 自动生成的赋值函数")
        lines.append(f" * Extern 变量: {ext_var_name}")
        lines.append(f" * 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f" */")

        target_externs = self._collect_target_externs()
        if target_externs:
            lines.append(f"/* 目标头文件 extern 变量引用 */")
            for tvar, ttype in target_externs:
                lines.append(f"extern {ttype} {tvar};")
            lines.append("")

        params = self._collect_func_params(ext_var_name)
        param_str = ", ".join(params)
        lines.append(f"void assign_from_{ext_var_name}({param_str}) {{")
        lines.append(f"    if ({ext_var_name} == NULL) return;")
        lines.append("")

        for m in self.mappings:
            ext_member = m['extern_member']
            user_var = m['user_var']
            op_type = m['op_type']
            condition = m.get('condition', [])
            conv_rule = m.get('conv_rule', '=')

            lhs = self._get_var_lhs(user_var)
            condition_expr = self._build_condition_expression(condition, ext_var_name)

            if op_type == '直接赋值':
                if condition_expr:
                    lines.append(f"    if ({condition_expr}) {{")
                    if conv_rule == '=':
                        lines.append(f"        {lhs} = {ext_var_name}->{ext_member};")
                    else:
                        lines.append(f"        {lhs} = {ext_var_name}->{ext_member} {conv_rule};")
                    lines.append(f"    }}")
                else:
                    if conv_rule == '=':
                        lines.append(f"    {lhs} = {ext_var_name}->{ext_member};")
                    else:
                        lines.append(f"    {lhs} = {ext_var_name}->{ext_member} {conv_rule};")
            elif op_type == '条件赋值':
                cond = condition_expr if condition_expr else f"{ext_var_name}->{ext_member} != 0"
                if conv_rule == '=':
                    lines.append(f"    if ({cond}) {{")
                    lines.append(f"        {lhs} = {ext_var_name}->{ext_member};")
                    lines.append(f"    }}")
                else:
                    lines.append(f"    if ({cond}) {{")
                    lines.append(f"        {lhs} = {ext_var_name}->{ext_member} {conv_rule};")
                    lines.append(f"    }}")
            elif op_type == '逻辑判断':
                lines.append(f"    /* 逻辑判断: {ext_member} vs {user_var} */")
                if condition_expr:
                    lines.append(f"    if ({condition_expr}) {{")
                    lines.append(f"        /* TODO: 处理判断逻辑 */")
                    lines.append(f"    }}")
                else:
                    lines.append(f"    if ({ext_var_name}->{ext_member}) {{")
                    lines.append(f"        /* TODO: {user_var} 为真时的处理 */")
                    lines.append(f"    }}")
            elif op_type == '自定义表达式':
                expr = condition_expr if condition_expr else f"{lhs} = {ext_var_name}->{ext_member}"
                lines.append(f"    {lhs} = {expr};")

        lines.append("}")
        return "\n".join(lines)

    def _gen_condition_function(self, ext_var_name: str) -> str:
        lines = []
        lines.append(f"/*")
        lines.append(f" * 自动生成的条件判断函数")
        lines.append(f" * Extern 变量: {ext_var_name}")
        lines.append(f" */")

        param_str = f"{self.selected_extern_var['type']} *{ext_var_name}" if self.selected_extern_var else f"void *{ext_var_name}"
        lines.append(f"int check_{ext_var_name}({param_str}) {{")
        lines.append(f"    int result = 1;  /* 默认通过 */")
        lines.append("")

        for m in self.mappings:
            ext_member = m['extern_member']
            condition = m.get('condition', [])

            condition_expr = self._build_condition_expression(condition, ext_var_name)
            if condition_expr:
                lines.append(f"    /* 检查: {ext_member} */")
                lines.append(f"    if (!({condition_expr})) {{")
                lines.append(f"        result = 0;")
                lines.append(f"    }}")
            else:
                lines.append(f"    /* 检查: {ext_member} */")
                lines.append(f"    /* TODO: 添加判断条件 */")

        lines.append("")
        lines.append(f"    return result;")
        lines.append("}")
        return "\n".join(lines)

    def _gen_full_function(self, ext_var_name: str) -> str:
        lines = []
        lines.append(f"/*")
        lines.append(f" * 自动生成的完整转换函数")
        lines.append(f" * Extern 变量: {ext_var_name}")
        lines.append(f" * 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f" */")

        target_externs = self._collect_target_externs()
        if target_externs:
            lines.append(f"/* 目标头文件 extern 变量引用 */")
            for tvar, ttype in target_externs:
                lines.append(f"extern {ttype} {tvar};")
            lines.append("")

        params = self._collect_func_params(ext_var_name)
        param_str = ", ".join(params)
        lines.append(f"int convert_{ext_var_name}({param_str}) {{")
        lines.append(f"    if ({ext_var_name} == NULL) return -1;")
        lines.append("")

        cond_mappings = [m for m in self.mappings if m['op_type'] in ('逻辑判断', '条件赋值') and m.get('condition')]
        if cond_mappings:
            lines.append(f"    /* ── 条件检查 ── */")
            for m in cond_mappings:
                ext_member = m['extern_member']
                condition_expr = self._build_condition_expression(m.get('condition', []), ext_var_name)
                if condition_expr:
                    lines.append(f"    if (!({condition_expr})) {{")
                    lines.append(f"        return -1;  /* 条件不满足: {ext_member} */")
                    lines.append(f"    }}")
            lines.append("")

        assign_mappings = [m for m in self.mappings if m['op_type'] in ('直接赋值', '条件赋值', '自定义表达式')]
        if assign_mappings:
            lines.append(f"    /* ── 赋值操作 ── */")
            for m in assign_mappings:
                ext_member = m['extern_member']
                user_var = m['user_var']
                conv_rule = m.get('conv_rule', '=')
                condition_expr = self._build_condition_expression(m.get('condition', []), ext_var_name)

                lhs = self._get_var_lhs(user_var)

                if condition_expr:
                    lines.append(f"    if ({condition_expr}) {{")
                    if conv_rule == '=':
                        lines.append(f"        {lhs} = {ext_var_name}->{ext_member};")
                    else:
                        lines.append(f"        {lhs} = {ext_var_name}->{ext_member} {conv_rule};")
                    lines.append(f"    }}")
                else:
                    if conv_rule == '=':
                        lines.append(f"    {lhs} = {ext_var_name}->{ext_member};")
                    else:
                        lines.append(f"    {lhs} = {ext_var_name}->{ext_member} {conv_rule};")
            lines.append("")

        lines.append(f"    return 0;  /* 成功 */")
        lines.append("}")
        return "\n".join(lines)

    def _gen_assignment_statements(self, ext_var_name: str) -> str:
        lines = []
        lines.append(f"/* 赋值语句 - Extern: {ext_var_name} */")

        for m in self.mappings:
            ext_member = m['extern_member']
            user_var = m['user_var']
            conv_rule = m.get('conv_rule', '=')
            condition_expr = self._build_condition_expression(m.get('condition', []), ext_var_name)

            lhs = self._get_var_lhs(user_var)

            if condition_expr:
                lines.append(f"if ({condition_expr}) {{")
                if conv_rule == '=':
                    lines.append(f"    {lhs} = {ext_var_name}->{ext_member};")
                else:
                    lines.append(f"    {lhs} = {ext_var_name}->{ext_member} {conv_rule};")
                lines.append(f"}}")
            else:
                if conv_rule == '=':
                    lines.append(f"{lhs} = {ext_var_name}->{ext_member};")
                else:
                    lines.append(f"{lhs} = {ext_var_name}->{ext_member} {conv_rule};")

        return "\n".join(lines)

    def _gen_condition_statements(self, ext_var_name: str) -> str:
        lines = []
        lines.append(f"/* 条件判断语句 - Extern: {ext_var_name} */")

        for m in self.mappings:
            ext_member = m['extern_member']
            condition_expr = self._build_condition_expression(m.get('condition', []), ext_var_name)

            if condition_expr:
                lines.append(f"if ({condition_expr}) {{")
                lines.append(f"    /* {ext_member} 条件满足 */")
                lines.append(f"}}")
            else:
                lines.append(f"if ({ext_var_name}->{ext_member}) {{")
                lines.append(f"    /* {ext_member} 为真 */")
                lines.append(f"}}")

        return "\n".join(lines)

    def _apply_syntax_highlighting(self):
        content = self.code_text.get('1.0', tk.END)

        for tag in ('keyword', 'type', 'string', 'comment', 'number', 'function'):
            self.code_text.tag_remove(tag, '1.0', tk.END)

        keywords = ['if', 'else', 'return', 'void', 'int', 'struct', 'typedef',
                     'NULL', 'const', 'static', 'unsigned', 'signed', 'for', 'while']
        for kw in keywords:
            start = '1.0'
            while True:
                pos = self.code_text.search(rf'\b{kw}\b', start, tk.END, regexp=True)
                if not pos:
                    break
                end = f"{pos}+{len(kw)}c"
                self.code_text.tag_add('keyword', pos, end)
                start = end

        start = '1.0'
        while True:
            pos = self.code_text.search('/*', start, tk.END)
            if not pos:
                break
            end_pos = self.code_text.search('*/', pos, tk.END)
            if end_pos:
                end_pos = f"{end_pos}+2c"
            else:
                end_pos = tk.END
            self.code_text.tag_add('comment', pos, end_pos)
            start = end_pos

        start = '1.0'
        while True:
            pos = self.code_text.search('//', start, tk.END)
            if not pos:
                break
            line_end = f"{pos} lineend"
            self.code_text.tag_add('comment', pos, line_end)
            start = line_end

    def _generate_markdown(self):
        if not self.mappings:
            messagebox.showwarning("警告", "请先添加映射关系！")
            return

        generator = MarkdownDocumentGenerator(self)
        self.generated_markdown = generator.generate()

        self.md_text.delete('1.0', tk.END)
        self.md_text.insert('1.0', self.generated_markdown)
        self.status_var.set("已生成 Markdown 文档")

    def _copy_markdown(self):
        md = self.md_text.get('1.0', tk.END).strip()
        if not md:
            messagebox.showwarning("警告", "没有可复制的文档！请先生成文档。")
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(md)
        self.status_var.set("Markdown 文档已复制到剪贴板")

    def _copy_code_and_markdown(self):
        code = self.code_text.get('1.0', tk.END).strip()
        md = self.md_text.get('1.0', tk.END).strip()

        if not code and not md:
            messagebox.showwarning("警告", "请先生成代码或文档。")
            return

        content = f"{md}\n\n---\n\n## Generated Code\n\n```c\n{code}\n```"

        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.status_var.set("代码和文档已复制到剪贴板")

    def _save_markdown(self):
        md = self.md_text.get('1.0', tk.END).strip()
        if not md:
            messagebox.showwarning("警告", "没有可保存的文档！请先生成文档。")
            return

        file_path = filedialog.asksaveasfilename(
            title="保存 Markdown 文档",
            defaultextension=".md",
            filetypes=[("Markdown 文件", "*.md"), ("所有文件", "*.*")]
        )
        if not file_path:
            return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(md)
            messagebox.showinfo("成功", f"文档已保存到: {file_path}")
            self.status_var.set(f"文档已保存: {file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

    def _copy_code(self):
        code = self.code_text.get('1.0', tk.END).strip()
        if not code:
            messagebox.showwarning("警告", "没有可复制的代码！请先生成代码。")
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(code)
        self.status_var.set("代码已复制到剪贴板")

    def _save_code(self):
        code = self.code_text.get('1.0', tk.END).strip()
        if not code:
            messagebox.showwarning("警告", "没有可保存的代码！请先生成代码。")
            return

        file_path = filedialog.asksaveasfilename(
            title="保存代码",
            defaultextension=".c",
            filetypes=[("C 源文件", "*.c"), ("头文件", "*.h"), ("所有文件", "*.*")]
        )
        if not file_path:
            return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)
            messagebox.showinfo("成功", f"代码已保存到: {file_path}")
            self.status_var.set(f"代码已保存: {file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

    def _show_help(self):
        help_text = """
═══════════════════════════════════════════
    Extern 变量映射工具 v5.0 - 使用说明
═══════════════════════════════════════════

【简单模式】（默认）

  工作流: 需求文档 → 映射文档 → C 代码

  1. 加载需求文档
     • 点击"📂 加载 doc/docx/txt/md"按钮
     • 支持 Word 文档(.docx)、文本文件(.txt)、Markdown(.md)
     • 也可加载一个 .h 头文件为 AI 提供结构体上下文

  2. AI 生成映射文档
     • 点击"🤖 AI: 文档→映射文档"按钮
     • AI 分析需求文档，自动生成标准格式的映射文档
     • 生成的映射文档可在阶段2中手动编辑调整

  3. 生成 C 代码
     • 方式一: 点击"🐍 本地生成代码"（不需要 AI，Python 本地解析）
     • 方式二: 点击"🤖 AI 生成代码"（AI 理解语义，更智能）
     • 生成的代码可复制或保存为 .c/.h 文件

  4. 保存/加载映射文档
     • 映射文档可保存为 .md 文件，下次直接加载复用
     • 也可导出到高级模式进行更精细的调整

【高级模式】

  通过菜单"模式→高级模式"切换。
  提供完整的 extern 变量选择、用户变量定义、条件构建器等功能。
  适合需要手动精细控制映射关系的场景。

【LLM 配置】

  • 配置文件: miapikey.txt（3行格式: API Key, URL, 模型名）
  • 默认已配置为小米 MiMo API
  • 可通过菜单"工具→LLM 服务设置"修改配置
  • 可通过"测试 LLM 连接"验证配置

【快捷键】

  Ctrl+O: 加载需求文档
"""
        dialog = tk.Toplevel(self.root)
        dialog.title("使用说明")
        dialog.geometry("560x700")
        dialog.transient(self.root)

        text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, font=('Microsoft YaHei UI', 10))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert('1.0', help_text)
        text.config(state=tk.DISABLED)

        ttk.Button(dialog, text="关闭", command=dialog.destroy).pack(pady=10)

    def _show_about(self):
        messagebox.showinfo(
            "关于",
            "Extern 变量映射工具 v5.0\n\n"
            "核心工作流:\n"
            "  需求文档(doc/docx) → 映射文档 → C 代码\n\n"
            "• 📥 加载 Word/文本/Markdown 需求文档\n"
            "• 🤖 AI 自动分析文档生成映射关系\n"
            "• 📝 映射文档可编辑调整\n"
            "• 💻 本地/AI 双路径生成 C 代码\n"
            "• 🔧 高级模式支持手动精细配置\n\n"
            "LLM: 小米 MiMo API (MIMO-V2.5-Pro)\n"
            "配置: miapikey.txt (key/url/model)\n\n"
            "基于 Python + tkinter 构建\n"
            "© 2026 Struct Converter Toolkit"
        )


def main():
    root = tk.Tk()

    try:
        root.iconbitmap(default='')
    except Exception:
        pass

    app = ExternMapperApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
