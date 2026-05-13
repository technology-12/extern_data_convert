# Struct Converter Toolkit - 低代码平台

基于 Streamlit 构建的可视化结构体转换代码生成器。

## 快速启动

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动平台

**方式一：使用启动脚本（Windows）**
```bash
run_platform.bat
```

**方式二：命令行启动**
```bash
python -m streamlit run app.py
```

启动后浏览器会自动打开 `http://localhost:8501`。

## 功能说明

### 📝 结构体定义（Tab 1）
- 可视化添加/编辑/删除外部结构体和内部结构体的字段
- 支持字段类型下拉选择（预定义 C 类型）
- 支持数组大小、位域宽度、嵌套结构体等高级属性
- 支持验证字段设置

### 🔗 字段映射（Tab 2）
- 配置外部字段到内部字段的映射关系
- 设置转换规则（直接赋值 `=` 或自定义函数名）
- 添加验证逻辑条件表达式
- 可视化映射关系概览

### 💻 代码预览（Tab 3）
- 实时预览生成的 C 头文件 (.h) 和源文件 (.c)
- 语法高亮显示
- 一键下载生成的代码文件

### 📥 导入功能（侧边栏）
- **CSV 导入**：上传 CSV 文件，兼容现有命令行版本格式
- **Excel 导入**：上传 .xlsx 文件，每个 Sheet 代表一个结构体对
- **JSON 导入**：导入之前导出的配置文件

### 📤 导出功能（侧边栏）
- **JSON 导出**：将当前所有项目配置导出为 JSON 文件，方便保存和分享

## 项目结构

```
├── app.py                      # Streamlit 主应用入口
├── core/
│   ├── __init__.py
│   ├── code_generator.py       # 统一的 C 代码生成器
│   ├── csv_converter.py        # CSV 文件解析器
│   └── excel_converter.py      # Excel 文件解析器
├── ui/
│   ├── __init__.py
│   ├── struct_editor.py        # 结构体定义可视化编辑器
│   ├── mapping_editor.py       # 字段映射编辑器
│   └── code_preview.py         # 代码预览与下载
├── win7_struct_converter.py    # 原始命令行版本（Win7 兼容）
├── enhanced_struct_converter.py # 原始命令行版本（增强版）
├── csv_structs/                # CSV 输入目录
├── requirements.txt            # Python 依赖
└── run_platform.bat            # Windows 一键启动脚本
```

## CSV 文件格式

CSV 文件应包含以下列：

| 列名 | 说明 | 示例 |
|------|------|------|
| field_name | 字段名 | temperature |
| field_type | C 数据类型 | int32_t |
| struct_type | external 或 internal | external |
| external_field | 外部字段名（映射） | temperature |
| internal_field | 内部字段名（映射） | temp_val |
| conversion_rule | 转换规则 | = 或函数名 |
| validation_logic | 验证逻辑 | external->valid && recv_status |
| bitfield_width | 位域宽度 | 4 |
| nested_struct_def | 嵌套结构体定义 | struct_def |
| validation_field | 验证字段 | is_valid |
| array_size | 数组大小 | 10 |

## 兼容性

- 原始命令行脚本 `win7_struct_converter.py` 和 `enhanced_struct_converter.py` 保持不变
- 低代码平台是额外的可视化入口，不影响原有功能
- 核心代码生成逻辑通过 `core/code_generator.py` 统一管理
