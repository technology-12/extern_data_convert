"""测试脚本 - 验证 GUI 工具的核心功能"""
import tkinter as tk
from tkinter import ttk
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

root = tk.Tk()
root.withdraw()

from extern_mapper_gui import ExternMapperApp
app = ExternMapperApp(root)

# Test 1: 解析头文件
app.parser.parse_file('sample_extern.h')
app._refresh_extern_list()
print('Test 1 - Extern vars loaded: %d' % len(app.parser.extern_vars))
assert len(app.parser.extern_vars) == 11, "Should have 11 extern vars"

# Test 2: 选择 extern 变量
children = app.extern_tree.get_children()
app.extern_tree.selection_set(children[0])
app._on_extern_select(None)
print('Test 2 - Selected var: %s' % app.selected_extern_var['name'])
assert app.selected_extern_var['name'] == 'g_sensor_data', "First var should be g_sensor_data"

# Test 3: 添加用户变量
app.user_vars = [
    {'name': 'my_temp', 'type': 'float', 'desc': '温度'},
    {'name': 'my_humidity', 'type': 'float', 'desc': '湿度'},
    {'name': 'my_pressure', 'type': 'double', 'desc': '压力'},
    {'name': 'is_valid', 'type': 'bool', 'desc': '有效标志'},
]
app._refresh_user_var_list()
app._update_user_var_combo()
print('Test 3 - User vars: %d' % len(app.user_vars))
assert len(app.user_vars) == 4, "Should have 4 user vars"

# Test 4: 添加映射
app.mappings = [
    {'extern_member': 'temperature', 'user_var': 'my_temp', 'op_type': '直接赋值', 'condition': '', 'conversion': '=', 'conv_rule': '='},
    {'extern_member': 'humidity', 'user_var': 'my_humidity', 'op_type': '直接赋值', 'condition': '', 'conversion': '=', 'conv_rule': '='},
    {'extern_member': 'pressure', 'user_var': 'my_pressure', 'op_type': '直接赋值', 'condition': '', 'conversion': '=', 'conv_rule': '='},
    {'extern_member': 'valid', 'user_var': 'is_valid', 'op_type': '条件赋值', 'condition': 'g_sensor_data->valid == true', 'conversion': '=', 'conv_rule': '='},
]
app._refresh_mapping_list()
print('Test 4 - Mappings: %d' % len(app.mappings))
assert len(app.mappings) == 4, "Should have 4 mappings"

# Test 5: 生成代码
app._generate_code()
code = app.code_text.get('1.0', tk.END)
print('Test 5 - Generated code length: %d' % len(code))
assert len(code) > 100, "Generated code should not be empty"
print()
print('=== Generated Code ===')
print(code)

root.destroy()
print()
print('All tests passed!')
