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
from typing import Dict, List, Any, Optional
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.header_parser import HeaderParser


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


class ExternMapperApp:
    """Extern 变量映射工具主窗口"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Extern 变量映射工具 v2.1")
        self.root.geometry("1500x920")
        self.root.minsize(1200, 760)

        self.style = ttk.Style()
        self.style.theme_use('clam')
        self._configure_styles()

        self.parser = HeaderParser()
        self.target_parser = HeaderParser()

        self.current_file = tk.StringVar(value="")
        self.target_file = tk.StringVar(value="")
        self.extern_vars: List[Dict] = []
        self.selected_extern_var = None
        self.user_vars: List[Dict] = []
        self.mappings: List[Dict] = []
        self.generated_code = ""
        self.generated_markdown = ""

        self._build_menu()
        self._build_ui()

        self.status_var = tk.StringVar(value="就绪 - 请打开一个头文件开始")
        self.status_bar = ttk.Label(
            self.root, textvariable=self.status_var,
            relief=tk.SUNKEN, anchor=tk.W, padding=(5, 2)
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _configure_styles(self):
        self.style.configure('Title.TLabel', font=('Microsoft YaHei UI', 11, 'bold'))
        self.style.configure('Header.TLabel', font=('Microsoft YaHei UI', 10, 'bold'))
        self.style.configure('Info.TLabel', font=('Microsoft YaHei UI', 9))
        self.style.configure('Success.TLabel', font=('Microsoft YaHei UI', 9), foreground='green')
        self.style.configure('Warning.TLabel', font=('Microsoft YaHei UI', 9), foreground='#cc7700')
        self.style.configure('Accent.TButton', font=('Microsoft YaHei UI', 9, 'bold'))
        self.style.configure('Treeview', font=('Microsoft YaHei UI', 9), rowheight=26)
        self.style.configure('Treeview.Heading', font=('Microsoft YaHei UI', 9, 'bold'))

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="打开头文件...", command=self._open_file, accelerator="Ctrl+O")
        file_menu.add_command(label="打开目标头文件...", command=self._open_target_file, accelerator="Ctrl+T")
        file_menu.add_separator()
        file_menu.add_command(label="导入映射配置...", command=self._import_config)
        file_menu.add_command(label="导出映射配置...", command=self._export_config)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)

        tool_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="工具", menu=tool_menu)
        tool_menu.add_command(label="生成赋值代码", command=self._generate_code)
        tool_menu.add_command(label="复制生成的代码", command=self._copy_code)
        tool_menu.add_separator()
        tool_menu.add_command(label="生成 Markdown 文档", command=self._generate_markdown)
        tool_menu.add_command(label="复制 Markdown 文档", command=self._copy_markdown)
        tool_menu.add_command(label="保存 Markdown 文档...", command=self._save_markdown)
        tool_menu.add_separator()
        tool_menu.add_command(label="清空所有映射", command=self._clear_mappings)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="使用说明", command=self._show_help)
        help_menu.add_command(label="关于", command=self._show_about)

        self.root.bind('<Control-o>', lambda e: self._open_file())
        self.root.bind('<Control-t>', lambda e: self._open_target_file())

    def _build_ui(self):
        main_paned = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

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
        self.extern_tree.delete(*self.extern_tree.get_children())
        self.extern_vars = self.parser.extern_vars

        for var in self.extern_vars:
            is_struct = "✓" if var['is_struct'] else "—"
            self.extern_tree.insert('', tk.END, values=(
                var['name'], var['type'], is_struct
            ))

    def _refresh_target_var_list(self):
        self.target_var_tree.delete(*self.target_var_tree.get_children())

        for var in self.target_parser.extern_vars:
            is_struct = "✓" if var['is_struct'] else "—"
            struct_type = var.get('struct_type', '') if var['is_struct'] else "—"
            self.target_var_tree.insert('', tk.END, values=(
                var['name'], var['type'], is_struct, struct_type
            ))

    def _update_struct_type_combo(self):
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
        self.user_var_tree.delete(*self.user_var_tree.get_children())
        for v in self.user_vars:
            source = v.get('source', '手动')
            self.user_var_tree.insert('', tk.END, values=(
                v['name'], v['type'], v.get('desc', ''), source
            ))

    def _update_user_var_combo(self):
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
        Extern 变量映射工具 - 使用说明
═══════════════════════════════════════════

1. 打开头文件
   • 点击"浏览..."或菜单"文件→打开头文件"
   • 选择包含 extern 声明的 .h 文件
   • 工具会自动解析 extern 变量和结构体定义

2. 条件表达式与/或操作（新增）
   • 在映射配置中选择 Extern 成员和用户变量
   • 在条件表达式区域添加多个条件
   • 每个条件包含: 变量引用、操作符(=、!=、>、<等)、比较值
   • 多条件之间可通过"逻辑连接"(AND/OR)组合
   • 预览区域实时显示组合后的完整表达式

3. 选择 Extern 变量
   • 在左侧列表中点击选择一个 extern 变量
   • 中间面板会显示该变量的成员（如果是结构体）

4. 定义用户变量
   • 在右侧"用户变量"标签页中添加自定义变量
   • 支持单个添加、批量添加
   • 【新增】从结构体添加：选择结构体类型，一键添加所有成员
   • 【新增】结构体类型下拉框：快速选择已解析的结构体类型

5. 目标头文件变量（新增功能）
   • 在左侧面板选择目标头文件
   • 目标头文件包含转换后的变量定义和 extern 声明
   • 在"目标头文件变量"标签页中查看和选择变量
   • 可导入选中变量、全部变量、或结构体成员作为映射目标

6. 配置映射关系
   • 在"映射关系"标签页中选择 extern 成员和用户变量
   • 选择操作类型：直接赋值、条件赋值、逻辑判断、自定义表达式
   • 【新增】添加多个条件表达式，支持与/或逻辑组合
   • 可设置转换规则和条件表达式
   • 【新增】自动匹配：按名称自动匹配 extern 成员和用户变量

7. 生成代码和文档
   • 点击"生成代码"按钮生成 C 代码
   • 【新增】点击"生成文档"按钮生成 Markdown 文档
   • 【新增】可复制代码+文档组合，方便大模型处理
   • 可复制或保存生成的代码/文档

8. 导入/导出
   • 支持将映射配置导出为 JSON 文件
   • 可导入之前保存的配置（包含目标头文件路径）

快捷键:
   Ctrl+O: 打开源头文件
   Ctrl+T: 打开目标头文件
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
            "Extern 变量映射工具 v2.1\n\n"
            "用于读取C语言头文件中的 extern 变量声明，\n"
            "并将 extern 变量的成员与用户自定义变量\n"
            "进行对应赋值和逻辑判断的代码生成工具。\n\n"
            "v2.1 新增功能:\n"
            "• Markdown 文档生成 - 清晰描述变量映射关系\n"
            "• 条件表达式与/或操作 - 支持多条件组合判断\n"
            "• 代码+文档组合复制 - 方便大模型处理\n\n"
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
