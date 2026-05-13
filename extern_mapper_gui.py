"""
Extern 变量映射工具 - GUI 主程序
基于 tkinter 的可视化工具，用于读取头文件中的 extern 变量，
并允许用户将 extern 变量的成员与自定义变量进行对应赋值和逻辑判断。

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

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.header_parser import HeaderParser


class ExternMapperApp:
    """Extern 变量映射工具主窗口"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Extern 变量映射工具 v1.0")
        self.root.geometry("1280x820")
        self.root.minsize(1024, 680)

        # 设置主题样式
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self._configure_styles()

        # 解析器
        self.parser = HeaderParser()

        # 应用状态
        self.current_file = tk.StringVar(value="")
        self.extern_vars: List[Dict] = []  # 解析出的 extern 变量列表
        self.selected_extern_var = None  # 当前选中的 extern 变量
        self.user_vars: List[Dict] = []  # 用户自定义变量列表
        self.mappings: List[Dict] = []  # 映射关系列表
        self.generated_code = ""  # 生成的代码

        # 构建界面
        self._build_menu()
        self._build_ui()

        # 状态栏
        self.status_var = tk.StringVar(value="就绪 - 请打开一个头文件开始")
        self.status_bar = ttk.Label(
            self.root, textvariable=self.status_var,
            relief=tk.SUNKEN, anchor=tk.W, padding=(5, 2)
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # ── 样式配置 ──────────────────────────────────────────────────

    def _configure_styles(self):
        """配置 ttk 样式"""
        self.style.configure('Title.TLabel', font=('Microsoft YaHei UI', 11, 'bold'))
        self.style.configure('Header.TLabel', font=('Microsoft YaHei UI', 10, 'bold'))
        self.style.configure('Info.TLabel', font=('Microsoft YaHei UI', 9))
        self.style.configure('Success.TLabel', font=('Microsoft YaHei UI', 9), foreground='green')
        self.style.configure('Warning.TLabel', font=('Microsoft YaHei UI', 9), foreground='#cc7700')
        self.style.configure('Accent.TButton', font=('Microsoft YaHei UI', 9, 'bold'))
        self.style.configure('Treeview', font=('Microsoft YaHei UI', 9), rowheight=26)
        self.style.configure('Treeview.Heading', font=('Microsoft YaHei UI', 9, 'bold'))

    # ── 菜单栏 ────────────────────────────────────────────────────

    def _build_menu(self):
        """构建菜单栏"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="打开头文件...", command=self._open_file, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="导入映射配置...", command=self._import_config)
        file_menu.add_command(label="导出映射配置...", command=self._export_config)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)

        # 工具菜单
        tool_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="工具", menu=tool_menu)
        tool_menu.add_command(label="生成赋值代码", command=self._generate_code)
        tool_menu.add_command(label="复制生成的代码", command=self._copy_code)
        tool_menu.add_separator()
        tool_menu.add_command(label="清空所有映射", command=self._clear_mappings)

        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="使用说明", command=self._show_help)
        help_menu.add_command(label="关于", command=self._show_about)

        # 快捷键
        self.root.bind('<Control-o>', lambda e: self._open_file())

    # ── 主界面构建 ────────────────────────────────────────────────

    def _build_ui(self):
        """构建主界面"""
        # 主 PanedWindow（上下分割）
        main_paned = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 上半部分：文件选择 + 变量选择 + 映射配置
        top_frame = ttk.Frame(main_paned)
        main_paned.add(top_frame, weight=3)

        # 下半部分：代码预览
        bottom_frame = ttk.Frame(main_paned)
        main_paned.add(bottom_frame, weight=2)

        self._build_top_panel(top_frame)
        self._build_bottom_panel(bottom_frame)

    def _build_top_panel(self, parent):
        """构建上半部分面板"""
        # 使用 PanedWindow 水平分割
        h_paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        h_paned.pack(fill=tk.BOTH, expand=True)

        # ── 左侧面板：文件选择 + Extern 变量列表 ──
        left_frame = ttk.LabelFrame(h_paned, text=" 📄 头文件 & Extern 变量 ", padding=5)
        h_paned.add(left_frame, weight=2)

        self._build_left_panel(left_frame)

        # ── 中间面板：成员详情 ──
        center_frame = ttk.LabelFrame(h_paned, text=" 📋 变量成员详情 ", padding=5)
        h_paned.add(center_frame, weight=2)

        self._build_center_panel(center_frame)

        # ── 右侧面板：用户变量 + 映射配置 ──
        right_frame = ttk.LabelFrame(h_paned, text=" 🔗 映射配置 ", padding=5)
        h_paned.add(right_frame, weight=3)

        self._build_right_panel(right_frame)

    def _build_left_panel(self, parent):
        """构建左侧面板：文件选择和 extern 变量列表"""
        # 文件选择区域
        file_frame = ttk.Frame(parent)
        file_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(file_frame, text="头文件:", style='Info.TLabel').pack(side=tk.LEFT)
        self.file_entry = ttk.Entry(file_frame, textvariable=self.current_file, state='readonly')
        self.file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(file_frame, text="浏览...", command=self._open_file).pack(side=tk.LEFT)

        # Extern 变量列表
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(list_frame, text="Extern 变量列表:", style='Header.TLabel').pack(anchor=tk.W)

        # Treeview 显示 extern 变量
        columns = ('name', 'type', 'is_struct')
        self.extern_tree = ttk.Treeview(
            list_frame, columns=columns, show='headings',
            selectmode='browse', height=10
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

        # 解析信息
        self.parse_info_var = tk.StringVar(value="尚未加载头文件")
        ttk.Label(parent, textvariable=self.parse_info_var, style='Warning.TLabel').pack(
            anchor=tk.W, pady=(5, 0)
        )

    def _build_center_panel(self, parent):
        """构建中间面板：变量成员详情"""
        # 成员详情标题
        self.member_title_var = tk.StringVar(value="选择一个 extern 变量查看成员")
        ttk.Label(parent, textvariable=self.member_title_var, style='Header.TLabel').pack(anchor=tk.W)

        # 成员 Treeview
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
        """构建右侧面板：用户变量定义和映射配置"""
        # 使用 Notebook 分页
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)

        # ── Tab 1: 用户变量定义 ──
        user_var_tab = ttk.Frame(notebook, padding=5)
        notebook.add(user_var_tab, text=" 👤 用户变量 ")

        self._build_user_var_tab(user_var_tab)

        # ── Tab 2: 映射配置 ──
        mapping_tab = ttk.Frame(notebook, padding=5)
        notebook.add(mapping_tab, text=" 🔗 映射关系 ")

        self._build_mapping_tab(mapping_tab)

    def _build_user_var_tab(self, parent):
        """构建用户变量定义标签页"""
        # 添加用户变量区域
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

        row2 = ttk.Frame(add_frame)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="自定义类型:").pack(side=tk.LEFT)
        self.user_var_custom_type = ttk.Entry(row2, width=20)
        self.user_var_custom_type.pack(side=tk.LEFT, padx=5)
        ttk.Label(row2, text="描述:").pack(side=tk.LEFT)
        self.user_var_desc = ttk.Entry(row2, width=20)
        self.user_var_desc.pack(side=tk.LEFT, padx=5)

        btn_frame = ttk.Frame(add_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="➕ 添加变量", command=self._add_user_var, style='Accent.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="🗑️ 删除选中", command=self._del_user_var).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="📋 批量添加", command=self._batch_add_user_var).pack(side=tk.LEFT, padx=2)

        # 用户变量列表
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('name', 'type', 'desc')
        self.user_var_tree = ttk.Treeview(
            list_frame, columns=columns, show='headings',
            selectmode='browse', height=8
        )
        self.user_var_tree.heading('name', text='变量名')
        self.user_var_tree.heading('type', text='类型')
        self.user_var_tree.heading('desc', text='描述')
        self.user_var_tree.column('name', width=120, minwidth=80)
        self.user_var_tree.column('type', width=120, minwidth=80)
        self.user_var_tree.column('desc', width=150, minwidth=80)

        uv_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.user_var_tree.yview)
        self.user_var_tree.configure(yscrollcommand=uv_scroll.set)

        self.user_var_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        uv_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_mapping_tab(self, parent):
        """构建映射配置标签页"""
        # 添加映射区域
        add_map_frame = ttk.LabelFrame(parent, text="添加映射关系", padding=5)
        add_map_frame.pack(fill=tk.X, pady=(0, 5))

        # 第一行：选择 extern 成员
        row_ext = ttk.Frame(add_map_frame)
        row_ext.pack(fill=tk.X, pady=2)
        ttk.Label(row_ext, text="Extern 成员:").pack(side=tk.LEFT)
        self.map_extern_member = ttk.Combobox(row_ext, width=25, state='readonly')
        self.map_extern_member.pack(side=tk.LEFT, padx=5)

        # 第二行：选择用户变量
        row_user = ttk.Frame(add_map_frame)
        row_user.pack(fill=tk.X, pady=2)
        ttk.Label(row_user, text="用户变量:").pack(side=tk.LEFT)
        self.map_user_var = ttk.Combobox(row_user, width=25, state='readonly')
        self.map_user_var.pack(side=tk.LEFT, padx=5)

        # 第三行：赋值/判断
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

        # 第四行：条件/表达式
        self.map_condition_frame = ttk.Frame(add_map_frame)
        self.map_condition_frame.pack(fill=tk.X, pady=2)
        ttk.Label(self.map_condition_frame, text="条件/表达式:").pack(side=tk.LEFT)
        self.map_condition = ttk.Entry(self.map_condition_frame, width=40)
        self.map_condition.pack(side=tk.LEFT, padx=5)

        # 第五行：转换规则
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

        # 添加按钮
        btn_frame = ttk.Frame(add_map_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="➕ 添加映射", command=self._add_mapping, style='Accent.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="🗑️ 删除选中", command=self._del_mapping).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="⬆️ 上移", command=lambda: self._move_mapping(-1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="⬇️ 下移", command=lambda: self._move_mapping(1)).pack(side=tk.LEFT, padx=2)

        # 映射列表
        map_list_frame = ttk.Frame(parent)
        map_list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('extern_member', 'operator', 'user_var', 'conversion', 'condition')
        self.mapping_tree = ttk.Treeview(
            map_list_frame, columns=columns, show='headings',
            selectmode='browse', height=8
        )
        self.mapping_tree.heading('extern_member', text='Extern 成员')
        self.mapping_tree.heading('operator', text='操作')
        self.mapping_tree.heading('user_var', text='用户变量')
        self.mapping_tree.heading('conversion', text='转换规则')
        self.mapping_tree.heading('condition', text='条件/表达式')
        self.mapping_tree.column('extern_member', width=120, minwidth=80)
        self.mapping_tree.column('operator', width=80, minwidth=50)
        self.mapping_tree.column('user_var', width=100, minwidth=60)
        self.mapping_tree.column('conversion', width=80, minwidth=50)
        self.mapping_tree.column('condition', width=150, minwidth=80)

        map_scroll = ttk.Scrollbar(map_list_frame, orient=tk.VERTICAL, command=self.mapping_tree.yview)
        self.mapping_tree.configure(yscrollcommand=map_scroll.set)

        self.mapping_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        map_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.mapping_tree.bind('<<TreeviewSelect>>', self._on_mapping_select)

    def _build_bottom_panel(self, parent):
        """构建下半部分面板：代码预览"""
        code_frame = ttk.LabelFrame(parent, text=" 📝 生成的代码 ", padding=5)
        code_frame.pack(fill=tk.BOTH, expand=True)

        # 工具栏
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

        # 代码预览区
        self.code_text = scrolledtext.ScrolledText(
            code_frame, wrap=tk.NONE, font=('Consolas', 10),
            bg='#1e1e1e', fg='#d4d4d4', insertbackground='white',
            selectbackground='#264f78', height=12
        )
        self.code_text.pack(fill=tk.BOTH, expand=True)

        # 添加行号和语法高亮标签
        self.code_text.tag_configure('keyword', foreground='#569cd6')
        self.code_text.tag_configure('type', foreground='#4ec9b0')
        self.code_text.tag_configure('string', foreground='#ce9178')
        self.code_text.tag_configure('comment', foreground='#6a9955')
        self.code_text.tag_configure('number', foreground='#b5cea8')
        self.code_text.tag_configure('function', foreground='#dcdcaa')

    # ── 文件操作 ──────────────────────────────────────────────────

    def _open_file(self):
        """打开头文件"""
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

        # 更新 extern 变量列表
        self._refresh_extern_list()

        summary = self.parser.get_summary()
        self.parse_info_var.set(
            f"✅ 已加载: {os.path.basename(file_path)} | "
            f"结构体: {summary['struct_count']} | "
            f"Extern: {summary['extern_var_count']} | "
            f"Typedef: {summary['typedef_count']}"
        )
        self.status_var.set(f"已加载头文件: {file_path}")

    def _refresh_extern_list(self):
        """刷新 extern 变量列表"""
        self.extern_tree.delete(*self.extern_tree.get_children())
        self.extern_vars = self.parser.extern_vars

        for var in self.extern_vars:
            is_struct = "✓" if var['is_struct'] else "—"
            self.extern_tree.insert('', tk.END, values=(
                var['name'], var['type'], is_struct
            ))

    def _import_config(self):
        """导入映射配置"""
        file_path = filedialog.askopenfilename(
            title="导入映射配置",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")]
        )
        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 恢复用户变量
            self.user_vars = config.get('user_vars', [])
            self._refresh_user_var_list()

            # 恢复映射
            self.mappings = config.get('mappings', [])
            self._refresh_mapping_list()

            # 如果有关联的头文件，尝试加载
            header_file = config.get('header_file', '')
            if header_file and os.path.exists(header_file):
                self.current_file.set(header_file)
                self.parser.parse_file(header_file)
                self._refresh_extern_list()

            messagebox.showinfo("成功", "配置导入成功！")
            self.status_var.set(f"已导入配置: {os.path.basename(file_path)}")

        except Exception as e:
            messagebox.showerror("错误", f"导入配置失败: {e}")

    def _export_config(self):
        """导出映射配置"""
        file_path = filedialog.asksaveasfilename(
            title="导出映射配置",
            defaultextension=".json",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")]
        )
        if not file_path:
            return

        config = {
            'header_file': self.current_file.get(),
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

    # ── Extern 变量选择 ───────────────────────────────────────────

    def _on_extern_select(self, event):
        """当选择 extern 变量时"""
        selection = self.extern_tree.selection()
        if not selection:
            return

        item = self.extern_tree.item(selection[0])
        var_name = item['values'][0]

        # 查找变量信息
        self.selected_extern_var = self.parser.get_extern_var(var_name)
        if not self.selected_extern_var:
            return

        # 更新成员列表
        self._refresh_member_list()

        # 更新映射面板中的 extern 成员下拉框
        self._update_extern_member_combo()

        self.member_title_var.set(
            f"变量: {var_name} ({self.selected_extern_var['type']})"
        )
        self.status_var.set(f"已选择 extern 变量: {var_name}")

    def _refresh_member_list(self):
        """刷新成员列表"""
        self.member_tree.delete(*self.member_tree.get_children())

        if not self.selected_extern_var:
            return

        if self.selected_extern_var['is_struct']:
            # 展示结构体成员（包括嵌套展开）
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
            # 基本类型变量，没有成员
            self.member_tree.insert('', tk.END, values=(
                self.selected_extern_var['name'],
                self.selected_extern_var['type'],
                "—", "—", "—"
            ))

    def _update_extern_member_combo(self):
        """更新映射面板中的 extern 成员下拉框"""
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
        """当选择成员时，自动设置到映射面板"""
        selection = self.member_tree.selection()
        if not selection:
            return

        item = self.member_tree.item(selection[0])
        member_name = item['values'][0]
        self.map_extern_member.set(member_name)

    # ── 用户变量管理 ──────────────────────────────────────────────

    def _add_user_var(self):
        """添加用户自定义变量"""
        name = self.user_var_name.get().strip()
        type_sel = self.user_var_type.get()
        custom_type = self.user_var_custom_type.get().strip()
        desc = self.user_var_desc.get().strip()

        if not name:
            messagebox.showwarning("警告", "请输入变量名！")
            return

        # 确定类型
        var_type = custom_type if type_sel == '自定义' and custom_type else type_sel

        # 检查重复
        for v in self.user_vars:
            if v['name'] == name:
                messagebox.showwarning("警告", f"变量 '{name}' 已存在！")
                return

        self.user_vars.append({
            'name': name,
            'type': var_type,
            'desc': desc,
        })

        self._refresh_user_var_list()
        self._update_user_var_combo()

        # 清空输入
        self.user_var_name.delete(0, tk.END)
        self.user_var_desc.delete(0, tk.END)

        self.status_var.set(f"已添加用户变量: {name} ({var_type})")

    def _del_user_var(self):
        """删除选中的用户变量"""
        selection = self.user_var_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择要删除的变量！")
            return

        item = self.user_var_tree.item(selection[0])
        var_name = item['values'][0]

        self.user_vars = [v for v in self.user_vars if v['name'] != var_name]
        self._refresh_user_var_list()
        self._update_user_var_combo()
        self.status_var.set(f"已删除用户变量: {var_name}")

    def _batch_add_user_var(self):
        """批量添加用户变量"""
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
                    # 检查重复
                    if not any(v['name'] == name for v in self.user_vars):
                        self.user_vars.append({
                            'name': name, 'type': var_type, 'desc': desc
                        })
                        count += 1

            self._refresh_user_var_list()
            self._update_user_var_combo()
            self.status_var.set(f"批量添加了 {count} 个用户变量")
            dialog.destroy()

        ttk.Button(dialog, text="添加", command=do_add, style='Accent.TButton').pack(pady=10)

    def _refresh_user_var_list(self):
        """刷新用户变量列表"""
        self.user_var_tree.delete(*self.user_var_tree.get_children())
        for v in self.user_vars:
            self.user_var_tree.insert('', tk.END, values=(
                v['name'], v['type'], v.get('desc', '')
            ))

    def _update_user_var_combo(self):
        """更新映射面板中的用户变量下拉框"""
        values = [v['name'] for v in self.user_vars]
        self.map_user_var['values'] = values
        if values:
            self.map_user_var.set(values[0])
        else:
            self.map_user_var.set('')

    # ── 映射管理 ──────────────────────────────────────────────────

    def _on_op_type_changed(self, event=None):
        """操作类型改变时的回调"""
        pass

    def _add_mapping(self):
        """添加映射关系"""
        ext_member = self.map_extern_member.get()
        user_var = self.map_user_var.get()
        op_type = self.map_op_type.get()
        condition = self.map_condition.get().strip()
        conversion = self.map_conversion.get()
        custom_conv = self.map_custom_conv.get().strip()

        if not ext_member:
            messagebox.showwarning("警告", "请选择 Extern 成员！")
            return
        if not user_var:
            messagebox.showwarning("警告", "请选择用户变量！")
            return

        # 确定转换规则
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
            'condition': condition,
            'conversion': conversion,
            'conv_rule': conv_rule,
        }

        self.mappings.append(mapping)
        self._refresh_mapping_list()

        # 清空条件输入
        self.map_condition.delete(0, tk.END)
        self.map_custom_conv.delete(0, tk.END)

        self.status_var.set(f"已添加映射: {ext_member} → {user_var} ({op_type})")

    def _del_mapping(self):
        """删除选中的映射"""
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
        """移动映射顺序"""
        selection = self.mapping_tree.selection()
        if not selection:
            return

        idx = self.mapping_tree.index(selection[0])
        new_idx = idx + direction
        if 0 <= new_idx < len(self.mappings):
            self.mappings[idx], self.mappings[new_idx] = self.mappings[new_idx], self.mappings[idx]
            self._refresh_mapping_list()
            # 重新选中
            children = self.mapping_tree.get_children()
            if new_idx < len(children):
                self.mapping_tree.selection_set(children[new_idx])

    def _on_mapping_select(self, event):
        """当选择映射时"""
        selection = self.mapping_tree.selection()
        if not selection:
            return

        idx = self.mapping_tree.index(selection[0])
        if 0 <= idx < len(self.mappings):
            m = self.mappings[idx]
            self.map_extern_member.set(m['extern_member'])
            self.map_user_var.set(m['user_var'])
            self.map_op_type.set(m['op_type'])
            self.map_condition.delete(0, tk.END)
            self.map_condition.insert(0, m.get('condition', ''))
            self.map_conversion.set(m.get('conversion', '='))
            self.map_custom_conv.delete(0, tk.END)
            self.map_custom_conv.insert(0, m.get('conv_rule', '='))

    def _refresh_mapping_list(self):
        """刷新映射列表"""
        self.mapping_tree.delete(*self.mapping_tree.get_children())
        for m in self.mappings:
            self.mapping_tree.insert('', tk.END, values=(
                m['extern_member'],
                m['op_type'],
                m['user_var'],
                m.get('conversion', '='),
                m.get('condition', '')
            ))

    def _clear_mappings(self):
        """清空所有映射"""
        if self.mappings and messagebox.askyesno("确认", "确定要清空所有映射关系吗？"):
            self.mappings.clear()
            self._refresh_mapping_list()
            self.code_text.delete('1.0', tk.END)
            self.status_var.set("已清空所有映射")

    # ── 代码生成 ──────────────────────────────────────────────────

    def _get_user_var_type(self, var_name: str) -> str:
        """获取用户变量的类型"""
        for v in self.user_vars:
            if v['name'] == var_name:
                return v['type']
        return 'int'

    def _get_extern_var_name(self) -> str:
        """获取当前选中的 extern 变量名"""
        if self.selected_extern_var:
            return self.selected_extern_var['name']
        return "ext_var"

    def _generate_code(self):
        """生成代码"""
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
        """生成赋值函数"""
        lines = []
        lines.append(f"/*")
        lines.append(f" * 自动生成的赋值函数")
        lines.append(f" * Extern 变量: {ext_var_name}")
        lines.append(f" * 生成时间: {self._get_timestamp()}")
        lines.append(f" */")

        # 生成函数签名
        params = [f"{ext_var_name}"]  # extern 变量作为参数
        # 添加用户变量参数
        for uv in self.user_vars:
            if any(m['user_var'] == uv['name'] for m in self.mappings):
                params.append(f"{uv['type']} *{uv['name']}")

        param_str = ", ".join(params)
        if self.selected_extern_var:
            param_str = f"{self.selected_extern_var['type']} *{ext_var_name}, " + ", ".join(
                f"{uv['type']} *{uv['name']}" for uv in self.user_vars
                if any(m['user_var'] == uv['name'] for m in self.mappings)
            )

        lines.append(f"void assign_from_{ext_var_name}({param_str}) {{")
        lines.append(f"    if ({ext_var_name} == NULL) return;")
        lines.append("")

        for m in self.mappings:
            ext_member = m['extern_member']
            user_var = m['user_var']
            op_type = m['op_type']
            condition = m.get('condition', '')
            conv_rule = m.get('conv_rule', '=')

            if op_type == '直接赋值':
                if conv_rule == '=':
                    lines.append(f"    (*{user_var}) = {ext_var_name}->{ext_member};")
                else:
                    lines.append(f"    (*{user_var}) = {ext_var_name}->{ext_member} {conv_rule};")
            elif op_type == '条件赋值':
                cond = condition if condition else f"{ext_var_name}->{ext_member} != 0"
                if conv_rule == '=':
                    lines.append(f"    if ({cond}) {{")
                    lines.append(f"        (*{user_var}) = {ext_var_name}->{ext_member};")
                    lines.append(f"    }}")
                else:
                    lines.append(f"    if ({cond}) {{")
                    lines.append(f"        (*{user_var}) = {ext_var_name}->{ext_member} {conv_rule};")
                    lines.append(f"    }}")
            elif op_type == '逻辑判断':
                lines.append(f"    /* 逻辑判断: {ext_member} vs {user_var} */")
                if condition:
                    lines.append(f"    if ({condition}) {{")
                    lines.append(f"        /* TODO: 处理判断逻辑 */")
                    lines.append(f"    }}")
                else:
                    lines.append(f"    if ({ext_var_name}->{ext_member}) {{")
                    lines.append(f"        /* TODO: {user_var} 为真时的处理 */")
                    lines.append(f"    }}")
            elif op_type == '自定义表达式':
                expr = condition if condition else f"(*{user_var}) = {ext_var_name}->{ext_member}"
                lines.append(f"    {expr};")

        lines.append("}")
        return "\n".join(lines)

    def _gen_condition_function(self, ext_var_name: str) -> str:
        """生成条件判断函数"""
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
            condition = m.get('condition', '')

            if condition:
                lines.append(f"    /* 检查: {ext_member} */")
                lines.append(f"    if (!({condition})) {{")
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
        """生成完整转换函数（包含赋值和判断）"""
        lines = []
        lines.append(f"/*")
        lines.append(f" * 自动生成的完整转换函数")
        lines.append(f" * Extern 变量: {ext_var_name}")
        lines.append(f" * 生成时间: {self._get_timestamp()}")
        lines.append(f" */")

        # 函数签名
        params = []
        if self.selected_extern_var:
            params.append(f"{self.selected_extern_var['type']} *{ext_var_name}")
        for uv in self.user_vars:
            if any(m['user_var'] == uv['name'] for m in self.mappings):
                params.append(f"{uv['type']} *{uv['name']}")

        param_str = ", ".join(params)
        lines.append(f"int convert_{ext_var_name}({param_str}) {{")
        lines.append(f"    if ({ext_var_name} == NULL) return -1;")
        lines.append("")

        # 条件判断部分
        cond_mappings = [m for m in self.mappings if m['op_type'] in ('逻辑判断', '条件赋值')]
        if cond_mappings:
            lines.append(f"    /* ── 条件检查 ── */")
            for m in cond_mappings:
                ext_member = m['extern_member']
                condition = m.get('condition', '')
                if condition:
                    lines.append(f"    if (!({condition})) {{")
                    lines.append(f"        return -1;  /* 条件不满足: {ext_member} */")
                    lines.append(f"    }}")
            lines.append("")

        # 赋值部分
        assign_mappings = [m for m in self.mappings if m['op_type'] in ('直接赋值', '条件赋值', '自定义表达式')]
        if assign_mappings:
            lines.append(f"    /* ── 赋值操作 ── */")
            for m in assign_mappings:
                ext_member = m['extern_member']
                user_var = m['user_var']
                conv_rule = m.get('conv_rule', '=')

                if conv_rule == '=':
                    lines.append(f"    (*{user_var}) = {ext_var_name}->{ext_member};")
                else:
                    lines.append(f"    (*{user_var}) = {ext_var_name}->{ext_member} {conv_rule};")
            lines.append("")

        lines.append(f"    return 0;  /* 成功 */")
        lines.append("}")
        return "\n".join(lines)

    def _gen_assignment_statements(self, ext_var_name: str) -> str:
        """生成仅赋值语句"""
        lines = []
        lines.append(f"/* 赋值语句 - Extern: {ext_var_name} */")

        for m in self.mappings:
            ext_member = m['extern_member']
            user_var = m['user_var']
            conv_rule = m.get('conv_rule', '=')

            if conv_rule == '=':
                lines.append(f"(*{user_var}) = {ext_var_name}->{ext_member};")
            else:
                lines.append(f"(*{user_var}) = {ext_var_name}->{ext_member} {conv_rule};")

        return "\n".join(lines)

    def _gen_condition_statements(self, ext_var_name: str) -> str:
        """生成仅判断语句"""
        lines = []
        lines.append(f"/* 条件判断语句 - Extern: {ext_var_name} */")

        for m in self.mappings:
            ext_member = m['extern_member']
            condition = m.get('condition', '')

            if condition:
                lines.append(f"if ({condition}) {{")
                lines.append(f"    /* {ext_member} 条件满足 */")
                lines.append(f"}}")
            else:
                lines.append(f"if ({ext_var_name}->{ext_member}) {{")
                lines.append(f"    /* {ext_member} 为真 */")
                lines.append(f"}}")

        return "\n".join(lines)

    def _apply_syntax_highlighting(self):
        """应用简单的语法高亮"""
        content = self.code_text.get('1.0', tk.END)

        # 清除现有标签
        for tag in ('keyword', 'type', 'string', 'comment', 'number', 'function'):
            self.code_text.tag_remove(tag, '1.0', tk.END)

        # 高亮关键字
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

        # 高亮注释
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

        # 高亮单行注释
        start = '1.0'
        while True:
            pos = self.code_text.search('//', start, tk.END)
            if not pos:
                break
            line_end = f"{pos} lineend"
            self.code_text.tag_add('comment', pos, line_end)
            start = line_end

    def _copy_code(self):
        """复制生成的代码到剪贴板"""
        code = self.code_text.get('1.0', tk.END).strip()
        if not code:
            messagebox.showwarning("警告", "没有可复制的代码！请先生成代码。")
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(code)
        self.status_var.set("代码已复制到剪贴板")

    def _save_code(self):
        """保存生成的代码到文件"""
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

    # ── 辅助方法 ──────────────────────────────────────────────────

    @staticmethod
    def _get_timestamp() -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _show_help(self):
        """显示帮助信息"""
        help_text = """
═══════════════════════════════════════════
        Extern 变量映射工具 - 使用说明
═══════════════════════════════════════════

1. 打开头文件
   • 点击"浏览..."或菜单"文件→打开头文件"
   • 选择包含 extern 声明的 .h 文件
   • 工具会自动解析 extern 变量和结构体定义

2. 选择 Extern 变量
   • 在左侧列表中点击选择一个 extern 变量
   • 中间面板会显示该变量的成员（如果是结构体）

3. 定义用户变量
   • 在右侧"用户变量"标签页中添加自定义变量
   • 支持单个添加和批量添加

4. 配置映射关系
   • 在"映射关系"标签页中选择 extern 成员和用户变量
   • 选择操作类型：直接赋值、条件赋值、逻辑判断、自定义表达式
   • 可设置转换规则和条件表达式

5. 生成代码
   • 点击"生成代码"按钮
   • 选择代码模板（赋值函数、条件判断函数等）
   • 可复制或保存生成的代码

6. 导入/导出
   • 支持将映射配置导出为 JSON 文件
   • 可导入之前保存的配置

快捷键:
   Ctrl+O: 打开文件
"""
        dialog = tk.Toplevel(self.root)
        dialog.title("使用说明")
        dialog.geometry("520x580")
        dialog.transient(self.root)

        text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, font=('Microsoft YaHei UI', 10))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert('1.0', help_text)
        text.config(state=tk.DISABLED)

        ttk.Button(dialog, text="关闭", command=dialog.destroy).pack(pady=10)

    def _show_about(self):
        """显示关于信息"""
        messagebox.showinfo(
            "关于",
            "Extern 变量映射工具 v1.0\n\n"
            "用于读取C语言头文件中的 extern 变量声明，\n"
            "并将 extern 变量的成员与用户自定义变量\n"
            "进行对应赋值和逻辑判断的代码生成工具。\n\n"
            "基于 Python + tkinter 构建\n"
            "© 2026 Struct Converter Toolkit"
        )


# ── 入口 ──────────────────────────────────────────────────────────

def main():
    root = tk.Tk()

    # 设置窗口图标（如果有的话）
    try:
        root.iconbitmap(default='')
    except Exception:
        pass

    app = ExternMapperApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
