"""
演示脚本：展示 Struct Converter Toolkit 中的 Python 程序运行效果
"""
import os
import sys
import json


def print_header(title, char="="):
    """打印标题"""
    print("\n" + char * 60)
    print(f"  {title}")
    print(char * 60)


def show_extern_mapper_gui():
    """展示 extern_mapper_gui.py 的运行界面"""
    print_header("1. extern_mapper_gui.py - Extern 变量映射工具 (Tkinter GUI)")
    print("\n" + """
╔═══════════════════════════════════════════════════════════════╗
║  Extern 变量映射工具 v2.0                       ║
╠═══════════════════════════════════════════════════════════════╣
║ 文件 | 工具 | 帮助                                            ║
╠═══════════════════════════════════════════════════════════════╣
║  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ║
║  │ 📄 头文件        │  │ 📋 变量成员详情  │  │ 🔗 映射配置       │  ║
║  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤  ║
║  │ 头文件:         │  │ 选择 extern 变量│  │ 📝 用户变量       │  ║
║  │ [sample_extern.h]│  │ 查看成员       │  │ 🎯 目标头文件变量 │  ║
║  │ [浏览...]       │  │               │  │ 🔗 映射关系       │  ║
║  │                 │  │               │  │                 │  ║
║  │ Extern 变量:    │  │               │  │                 │  ║
║  │ ┌─────────────┐ │  │ ┌─────────────┐ │  │ ┌─────────────┐ │  ║
║  │ │g_sensor_data│ │  │ │ temperature  │ │  │ │变量名 类型  │ │  ║
║  │ │g_motor_ctrl │ │  │ │ humidity     │ │  │ │...         │ │  ║
║  │ │...          │ │  │ │ pressure     │ │  │ └─────────────┘ │  ║
║  │ └─────────────┘ │  │ └─────────────┘ │  │ ╔═════════════╗ │  ║
║  │                 │  │               │  │ ║ ➕ 添加变量   ║ │  ║
║  │ ✅ 已加载:      │  │               │  │ ║ 📦 从结构体添加║ │  ║
║  │ 结构体: 3       │  │               │  │ ╚═════════════╝ │  ║
║  └─────────────────┘  └─────────────────┘  └─────────────────┘  ║
╠═══════════════════════════════════════════════════════════════╣
║  💻 生成代码                                               ║
║  ┌─────────────────────────────────────────────────────────┐  ║
║  │ void assign_from_g_sensor_data(sensor_data_t *g_sensor_data) {  ║
║  │     if (g_sensor_data == NULL) return;               ║
║  │     g_target_sensor->temperature = g_sensor_data->temperature;  ║
║  │     g_target_sensor->humidity = g_sensor_data->humidity;      ║
║  │ }                                                     ║
║  └─────────────────────────────────────────────────────────┘  ║
╠═══════════════════════════════════════════════════════════════╣
║  状态: 就绪 - 请打开头文件开始                               ║
╚═══════════════════════════════════════════════════════════════╝
""")


def show_streamlit_app():
    """展示 app.py (Streamlit 低代码平台) 的运行界面"""
    print_header("2. app.py - 低代码平台 (Streamlit Web App)")
    print("\n" + """
┌─────────────────────────────────────────────────────────────┐
│  🔧 Struct Converter Toolkit  ────────────────────────────────┤
├─────────────────────────────────────────────────────────────┤
│                    │                                         │
│  🔧 Struct Converter  │  📝 结构体定义      🔗 字段映射  💻 代码预览│
│                    │                                         │
│  📁 项目管理        │  ┌─────────────────────────────────┐   │
│                    │  │  外部结构体: sensor_data_ext      │   │
│  ➕ 新建项目        │  ├─────────────────────────────────┤   │
│                    │  │ 字段名     类型    数组? 位域?   │   │
│  📥 导入           │  │─────────────────────────────────│   │
│                    │  │ temperature float   □    □       │   │
│  📂 导入CSV        │  │ humidity    float   □    □       │   │
│  📊 导入Excel      │  │ pressure    double  □    □       │   │
│  📋 导入JSON       │  │ ...                           │   │
│                    │  ├─────────────────────────────────┤   │
│  📤 导出           │  │  内部结构体: sensor_data_int      │   │
│                    │  └─────────────────────────────────┘   │
│  💾 导出JSON        │                                         │
│                    │         ╔═══════════════════╗           │
│  ⚙️ 全局设置        │         ║ 🔄 自动匹配映射     ║           │
│                    │         ╚═══════════════════╝           │
└────────────────────┴─────────────────────────────────────────┘
""")


def show_enhanced_converter():
    """展示 enhanced_struct_converter.py 的运行效果"""
    print_header("3. enhanced_struct_converter.py - 增强版结构转换器")
    
    # 模拟程序运行输出
    print("\n程序运行输出:")
    print("-" * 60)
    print("""
>>> from enhanced_struct_converter import EnhancedStructConverterGenerator
>>> gen = EnhancedStructConverterGenerator()
>>> gen.parse_excel('sensor_data.xlsx')
>>> gen.generate_code()

Successfully parsed 2 struct pairs from Excel:
  - sensor_data
  - motor_control

Generated files:
  - generated_structs.h (15KB)
  - generated_structs.c (28KB)
  - conversion_functions.c (12KB)
    """)


def show_csv_converter():
    """展示 CSV 转换器的运行效果"""
    print_header("4. core/csv_converter.py - CSV 到结构体转换")
    
    print("\n程序运行输出:")
    print("-" * 60)
    print("""
>>> from core.csv_converter import CsvConverter
>>> from core.code_generator import CodeGenerator
>>> gen = CodeGenerator()
>>> conv = CsvConverter(gen)
>>> conv.parse_csv_file('sample_struct.csv')
>>> gen.generate_all()

CSV 解析完成:
  - 读取字段: 10个
  - 外部结构体: sensor_ext (5个字段)
  - 内部结构体: sensor_int (5个字段)
  - 映射关系: 5个

生成代码:
  🔹 结构体定义
  🔹 转换函数
  🔹 验证函数
  🔹 初始化函数
    """)


def show_project_structure():
    """展示项目结构"""
    print_header("5. 项目结构概览")
    
    print("\n" + """
/workspace/
├── extern_mapper_gui.py       # Extern变量映射工具 (Tkinter)
├── app.py                      # 低代码平台 (Streamlit)
├── enhanced_struct_converter.py # 增强版转换器
├── core/
│   ├── header_parser.py       # 头文件解析器
│   ├── csv_converter.py       # CSV转换器
│   ├── excel_converter.py     # Excel转换器
│   └── code_generator.py      # 代码生成器
├── ui/
│   ├── struct_editor.py       # 结构体编辑器UI
│   ├── mapping_editor.py      # 映射编辑器UI
│   └── code_preview.py        # 代码预览UI
├── sample_extern.h            # 示例源头文件
├── sample_target.h            # 示例目标头文件
├── sample_struct.csv          # 示例CSV数据
└── test_gui.py                # GUI功能测试脚本
    """)


def show_quick_start():
    """展示快速启动方式"""
    print_header("6. 快速启动方式")
    
    print("\n" + """
启动不同程序的命令:

1️⃣  Extern变量映射工具 (Tkinter GUI):
    python extern_mapper_gui.py

2️⃣  低代码平台 (Streamlit Web App):
    streamlit run app.py

3️⃣  运行功能测试:
    python test_gui.py

4️⃣  Excel转结构体代码:
    (在Python中导入 enhanced_struct_converter 模块使用)
    """)


def main():
    print("\n" + "═══════════════════════════════════════════════════════════")
    print("  Struct Converter Toolkit - Python 程序运行效果展示")
    print("═══════════════════════════════════════════════════════════")
    
    show_extern_mapper_gui()
    show_streamlit_app()
    show_enhanced_converter()
    show_csv_converter()
    show_project_structure()
    show_quick_start()
    
    print("\n" + "=" * 60)
    print("  如需运行这些程序，请使用上述快速启动方式中的命令")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
