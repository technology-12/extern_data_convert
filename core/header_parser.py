"""
C语言头文件解析器
解析 .h 头文件中的 extern 变量声明、typedef struct 定义、struct 定义等。
"""
import re
import os
from typing import Dict, List, Any, Optional, Tuple


class HeaderParser:
    """
    解析C语言头文件，提取 extern 变量声明和结构体定义。
    
    支持的功能：
    - 解析 extern 变量声明（包括基本类型和结构体类型）
    - 解析 typedef struct 定义
    - 解析 struct 定义
    - 解析结构体成员（包括基本类型、数组、嵌套结构体）
    - 处理注释和预处理指令
    """

    # 常见C语言基本类型
    BASIC_TYPES = {
        'char', 'short', 'int', 'long', 'float', 'double',
        'signed char', 'unsigned char', 'unsigned short',
        'unsigned int', 'unsigned long', 'long long',
        'unsigned long long', 'bool', 'void',
        'int8_t', 'int16_t', 'int32_t', 'int64_t',
        'uint8_t', 'uint16_t', 'uint32_t', 'uint64_t',
        'size_t', 'ptrdiff_t', 'int8', 'int16', 'int32', 'int64',
        'uint8', 'uint16', 'uint32', 'uint64',
        'BOOL', 'BYTE', 'WORD', 'DWORD', 'UINT8', 'UINT16', 'UINT32', 'UINT64',
        'INT8', 'INT16', 'INT32', 'INT64',
        'U8', 'U16', 'U32', 'U64', 'S8', 'S16', 'S32', 'S64',
        'boolean', 'u8', 'u16', 'u32', 'u64', 's8', 's16', 's32', 's64',
    }

    def __init__(self):
        self.structs: Dict[str, List[Dict[str, Any]]] = {}
        self.extern_vars: List[Dict[str, Any]] = []
        self.typedefs: Dict[str, str] = {}  # typedef alias -> original type
        self.enums: Dict[str, List[Dict[str, Any]]] = {}
        self.raw_content: str = ""
        self.file_path: str = ""

    def clear(self):
        """清除所有已解析的数据"""
        self.structs.clear()
        self.extern_vars.clear()
        self.typedefs.clear()
        self.enums.clear()
        self.raw_content = ""
        self.file_path = ""

    def parse_file(self, file_path: str) -> bool:
        """
        解析指定的头文件。
        
        Args:
            file_path: 头文件路径
            
        Returns:
            解析是否成功
        """
        if not os.path.exists(file_path):
            return False

        self.clear()
        self.file_path = file_path

        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                self.raw_content = f.read()
        except Exception:
            try:
                with open(file_path, 'r', encoding='gbk', errors='replace') as f:
                    self.raw_content = f.read()
            except Exception:
                return False

        self._parse_content()
        return True

    def parse_string(self, content: str) -> bool:
        """
        解析头文件内容字符串。
        
        Args:
            content: 头文件内容
            
        Returns:
            解析是否成功
        """
        self.clear()
        self.raw_content = content
        self._parse_content()
        return True

    def _parse_content(self):
        """执行解析流程"""
        # 1. 预处理：移除注释
        cleaned = self._remove_comments(self.raw_content)
        
        # 2. 解析 typedef 定义
        self._parse_typedefs(cleaned)
        
        # 3. 解析 enum 定义
        self._parse_enums(cleaned)
        
        # 4. 解析 struct 定义
        self._parse_structs(cleaned)
        
        # 5. 解析 extern 变量声明
        self._parse_extern_vars(cleaned)

    def _remove_comments(self, content: str) -> str:
        """移除C语言注释（单行和多行）"""
        # 移除多行注释 /* ... */
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        # 移除单行注释 //
        content = re.sub(r'//[^\n]*', '', content)
        return content

    def _parse_typedefs(self, content: str):
        """解析 typedef 声明（非结构体的）"""
        # 匹配 typedef old_type new_name;
        # 例如: typedef unsigned char UINT8;
        pattern = r'typedef\s+([\w\s\*]+?)\s+(\w+)\s*;'
        for match in re.finditer(pattern, content):
            original_type = match.group(1).strip()
            alias = match.group(2).strip()
            if alias not in self.structs and original_type:
                self.typedefs[alias] = original_type

    def _parse_enums(self, content: str):
        """解析 enum 定义"""
        # 匹配 typedef enum { ... } name; 或 enum name { ... };
        pattern = r'(?:typedef\s+)?enum\s*(\w*)\s*\{([^}]*)\}\s*(\w+)?\s*;'
        for match in re.finditer(pattern, content):
            enum_name = match.group(1) or match.group(3) or ""
            members_str = match.group(2)
            members = []
            for item in members_str.split(','):
                item = item.strip()
                if item:
                    # 处理带初始值的枚举成员
                    parts = item.split('=')
                    name = parts[0].strip()
                    value = parts[1].strip() if len(parts) > 1 else ""
                    if name:
                        members.append({'name': name, 'value': value})
            if enum_name and members:
                self.enums[enum_name] = members

    def _parse_structs(self, content: str):
        """解析 struct 定义"""
        # 匹配 typedef struct { ... } name; 或 typedef struct tag { ... } name;
        # 或 struct name { ... };
        
        # 模式1: typedef struct [tag] { ... } name [, name2]*;
        pattern1 = r'typedef\s+struct\s*(\w*)\s*\{([^}]*)\}\s*([\w\s,]+)\s*;'
        for match in re.finditer(pattern1, content):
            tag = match.group(1).strip()
            body = match.group(2)
            names_str = match.group(3).strip()
            members = self._parse_struct_body(body)
            
            # 可能有多个别名
            names = [n.strip() for n in names_str.split(',') if n.strip()]
            for name in names:
                self.structs[name] = members
            if tag:
                self.structs[tag] = members

        # 模式2: struct name { ... }; (非 typedef)
        pattern2 = r'(?<!typedef\s)struct\s+(\w+)\s*\{([^}]*)\}\s*;'
        for match in re.finditer(pattern2, content):
            name = match.group(1).strip()
            body = match.group(2)
            members = self._parse_struct_body(body)
            if name:
                self.structs[name] = members

    def _parse_struct_body(self, body: str) -> List[Dict[str, Any]]:
        """解析结构体体中的成员变量"""
        members = []
        lines = body.split(';')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 尝试解析成员变量
            member = self._parse_member(line)
            if member:
                members.append(member)
        
        return members

    def _parse_member(self, line: str) -> Optional[Dict[str, Any]]:
        """
        解析单个结构体成员声明。
        
        支持格式：
        - type name;
        - type name[N];
        - type name:N; (位域)
        - type *name;
        - struct type name;
        """
        line = line.strip()
        if not line:
            return None

        # 移除行内注释
        if '/*' in line:
            line = re.sub(r'/\*.*?\*/', '', line)
        if '//' in line:
            line = line.split('//')[0]

        # 处理位域: type name : N
        bitfield_match = re.match(r'([\w\s\*]+?)\s*(\w+)\s*:\s*(\d+)', line)
        if bitfield_match:
            type_str = bitfield_match.group(1).strip()
            name = bitfield_match.group(2).strip()
            bitfield_width = int(bitfield_match.group(3))
            return {
                'name': name,
                'type': type_str,
                'is_array': False,
                'array_size': None,
                'is_pointer': '*' in type_str,
                'is_bitfield': True,
                'bitfield_width': bitfield_width,
                'is_nested_struct': self._is_struct_type(type_str),
            }

        # 处理数组: type name[N]
        array_match = re.match(r'([\w\s\*]+?)\s*(\w+)\s*\[(\d+)\]', line)
        if array_match:
            type_str = array_match.group(1).strip()
            name = array_match.group(2).strip()
            array_size = int(array_match.group(3))
            return {
                'name': name,
                'type': type_str,
                'is_array': True,
                'array_size': array_size,
                'is_pointer': '*' in type_str,
                'is_bitfield': False,
                'bitfield_width': None,
                'is_nested_struct': self._is_struct_type(type_str),
            }

        # 处理多维数组: type name[N][M]
        multi_array_match = re.match(r'([\w\s\*]+?)\s*(\w+)\s*(\[[\d\w]+\])+', line)
        if multi_array_match:
            type_str = multi_array_match.group(1).strip()
            name = multi_array_match.group(2).strip()
            dims = re.findall(r'\[(\d+)\]', line)
            return {
                'name': name,
                'type': type_str,
                'is_array': True,
                'array_size': 'x'.join(dims),
                'is_pointer': '*' in type_str,
                'is_bitfield': False,
                'bitfield_width': None,
                'is_nested_struct': self._is_struct_type(type_str),
            }

        # 处理普通变量: type name 或 type *name
        # 也处理 struct type name
        simple_match = re.match(r'([\w\s\*]+?)\s*(\w+)\s*$', line)
        if simple_match:
            type_str = simple_match.group(1).strip()
            name = simple_match.group(2).strip()
            
            # 过滤掉一些不合法的情况
            if name in ('struct', 'union', 'enum', 'unsigned', 'signed'):
                return None
            
            return {
                'name': name,
                'type': type_str,
                'is_array': False,
                'array_size': None,
                'is_pointer': '*' in type_str,
                'is_bitfield': False,
                'bitfield_width': None,
                'is_nested_struct': self._is_struct_type(type_str),
            }

        return None

    def _is_struct_type(self, type_str: str) -> bool:
        """判断类型是否为结构体类型"""
        type_str = type_str.strip()
        if type_str.startswith('struct '):
            return True
        # 检查是否是已知的结构体类型名
        clean_type = type_str.replace('*', '').strip()
        if clean_type in self.structs:
            return True
        # 检查是否是已知的 typedef 别名
        if clean_type in self.typedefs:
            original = self.typedefs[clean_type]
            return self._is_struct_type(original)
        return False

    def _parse_extern_vars(self, content: str):
        """解析 extern 变量声明"""
        # 匹配 extern 声明
        # extern type name;
        # extern type name[N];
        # extern type *name;
        # extern struct type name;
        # extern const type name;
        
        pattern = r'extern\s+(?:(const|volatile)\s+)?([\w\s\*]+?)\s*(\w+)(\[[\d\w]*\])?\s*;'
        
        for match in re.finditer(pattern, content):
            qualifier = match.group(1) or ""
            type_str = match.group(2).strip()
            name = match.group(3).strip()
            array_suffix = match.group(4) or ""
            
            # 清理类型字符串
            type_str = re.sub(r'\s+', ' ', type_str).strip()
            
            # 判断是否是数组
            is_array = bool(array_suffix)
            array_size = None
            if is_array:
                size_match = re.search(r'\[(\d+)\]', array_suffix)
                array_size = int(size_match.group(1)) if size_match else None

            # 判断是否是指针
            is_pointer = '*' in type_str
            
            # 获取纯净的类型名（去掉指针符号）
            clean_type = type_str.replace('*', '').strip()
            
            # 判断是否是结构体类型
            is_struct = self._is_struct_type(type_str)
            
            # 获取结构体成员
            struct_members = []
            if is_struct:
                struct_type = clean_type
                if struct_type.startswith('struct '):
                    struct_type = struct_type[7:].strip()
                struct_members = self.structs.get(struct_type, [])

            var_info = {
                'name': name,
                'type': type_str,
                'clean_type': clean_type,
                'qualifier': qualifier,
                'is_array': is_array,
                'array_size': array_size,
                'is_pointer': is_pointer,
                'is_struct': is_struct,
                'struct_members': struct_members,
                'struct_type': clean_type if is_struct else None,
            }
            
            self.extern_vars.append(var_info)

    def get_extern_var(self, var_name: str) -> Optional[Dict[str, Any]]:
        """根据名称获取 extern 变量信息"""
        for var in self.extern_vars:
            if var['name'] == var_name:
                return var
        return None

    def get_struct_members(self, struct_type: str) -> List[Dict[str, Any]]:
        """获取结构体类型的成员列表"""
        clean_type = struct_type.replace('*', '').strip()
        if clean_type.startswith('struct '):
            clean_type = clean_type[7:].strip()
        return self.structs.get(clean_type, [])

    def get_nested_members(self, struct_type: str, prefix: str = "") -> List[Dict[str, Any]]:
        """
        获取结构体的所有成员，包括嵌套结构体的成员（展开）。
        
        Args:
            struct_type: 结构体类型名
            prefix: 成员前缀（用于嵌套展开）
            
        Returns:
            展开后的成员列表，每个成员包含 'full_path' 字段
        """
        members = self.get_struct_members(struct_type)
        result = []
        
        for member in members:
            full_name = f"{prefix}.{member['name']}" if prefix else member['name']
            
            if member.get('is_nested_struct') and not member.get('is_pointer'):
                # 递归展开嵌套结构体
                nested_type = member['type'].replace('struct ', '').strip()
                nested_members = self.get_nested_members(nested_type, full_name)
                result.extend(nested_members)
            else:
                member_copy = dict(member)
                member_copy['full_path'] = full_name
                result.append(member_copy)
        
        return result

    def resolve_type(self, type_name: str) -> str:
        """解析 typedef 别名，返回原始类型"""
        visited = set()
        current = type_name
        while current in self.typedefs and current not in visited:
            visited.add(current)
            current = self.typedefs[current]
        return current

    def get_summary(self) -> Dict[str, Any]:
        """获取解析结果的摘要信息"""
        return {
            'file_path': self.file_path,
            'struct_count': len(self.structs),
            'extern_var_count': len(self.extern_vars),
            'typedef_count': len(self.typedefs),
            'enum_count': len(self.enums),
            'struct_names': list(self.structs.keys()),
            'extern_var_names': [v['name'] for v in self.extern_vars],
            'enum_names': list(self.enums.keys()),
        }
