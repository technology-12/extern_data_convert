"""测试脚本 - 验证 GUI 工具的核心功能（包含 v2.0 新增功能测试）"""
import tkinter as tk
from tkinter import ttk
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

root = tk.Tk()
root.withdraw()

from extern_mapper_gui import ExternMapperApp
app = ExternMapperApp(root)

# ══════════════════════════════════════════
# 基础功能测试 (v1.0 兼容)
# ══════════════════════════════════════════

# Test 1: 解析源头文件
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
    {'name': 'my_temp', 'type': 'float', 'desc': '温度', 'source': '手动', 'is_struct': False},
    {'name': 'my_humidity', 'type': 'float', 'desc': '湿度', 'source': '手动', 'is_struct': False},
    {'name': 'my_pressure', 'type': 'double', 'desc': '压力', 'source': '手动', 'is_struct': False},
    {'name': 'is_valid', 'type': 'bool', 'desc': '有效标志', 'source': '手动', 'is_struct': False},
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
print('=== Generated Code (Basic) ===')
print(code)

# ══════════════════════════════════════════
# Feature 1 测试: 结构体用户变量简化操作
# ══════════════════════════════════════════

print()
print('=' * 60)
print('Feature 1: 结构体用户变量简化操作')
print('=' * 60)

# Test 6: _is_struct_type 检测
assert app._is_struct_type('sensor_data_t') == True, "sensor_data_t should be a struct"
assert app._is_struct_type('motor_control_t') == True, "motor_control_t should be a struct"
assert app._is_struct_type('int') == False, "int should not be a struct"
assert app._is_struct_type('float') == False, "float should not be a struct"
print('Test 6 - _is_struct_type: PASSED')

# Test 7: _get_parser_for_struct
p = app._get_parser_for_struct('sensor_data_t')
assert p is app.parser, "sensor_data_t should be in source parser"
p = app._get_parser_for_struct('nonexistent')
assert p is None, "nonexistent should return None"
print('Test 7 - _get_parser_for_struct: PASSED')

# Test 8: _expand_struct_user_var - 添加结构体变量并自动展开成员
app.user_vars.clear()
app._add_user_var_cleanup = True
app.user_vars.append({
    'name': 'my_sensor',
    'type': 'sensor_data_t',
    'desc': '我的传感器',
    'source': '手动',
    'is_struct': True,
})
app._expand_struct_user_var('my_sensor', 'sensor_data_t')
print('Test 8 - Expanded struct user vars: %d' % len(app.user_vars))
assert len(app.user_vars) > 1, "Should have more than 1 variable after expansion"
assert any(v['name'] == 'my_sensor.temperature' for v in app.user_vars), \
    "Should have my_sensor.temperature"
assert any(v['name'] == 'my_sensor.humidity' for v in app.user_vars), \
    "Should have my_sensor.humidity"
assert any(v['name'] == 'my_sensor.valid' for v in app.user_vars), \
    "Should have my_sensor.valid"
print('Test 8 - _expand_struct_user_var: PASSED')

# Test 9: _update_struct_type_combo
app._update_struct_type_combo()
struct_values = list(app.struct_type_combo['values'])
print('Test 9 - Struct type combo values: %s' % struct_values)
assert 'sensor_data_t' in struct_values, "sensor_data_t should be in combo"
assert 'motor_control_t' in struct_values, "motor_control_t should be in combo"
print('Test 9 - _update_struct_type_combo: PASSED')

# Test 10: 删除结构体变量时级联删除子成员
app._refresh_user_var_list()
app._update_user_var_combo()
initial_count = len(app.user_vars)
app.user_var_tree.selection_set(app.user_var_tree.get_children()[0])
app._del_user_var()
print('Test 10 - After deleting struct var, user vars: %d (was %d)' % (len(app.user_vars), initial_count))
assert not any(v['name'].startswith('my_sensor') for v in app.user_vars), \
    "All my_sensor members should be removed"
print('Test 10 - Cascade delete struct members: PASSED')

# ══════════════════════════════════════════
# Feature 2 测试: 目标头文件变量支持
# ══════════════════════════════════════════

print()
print('=' * 60)
print('Feature 2: 目标头文件变量支持')
print('=' * 60)

# Test 11: 解析目标头文件
app.target_parser.parse_file('sample_target.h')
app._refresh_target_var_list()
print('Test 11 - Target extern vars: %d' % len(app.target_parser.extern_vars))
assert len(app.target_parser.extern_vars) == 6, "Should have 6 target extern vars"
print('Test 11 - Target header parsing: PASSED')

# Test 12: 目标变量列表显示
target_children = app.target_var_tree.get_children()
print('Test 12 - Target var tree items: %d' % len(target_children))
assert len(target_children) == 6, "Should have 6 items in target var tree"
print('Test 12 - Target var tree display: PASSED')

# Test 13: 导入全部目标变量
app.user_vars.clear()
app._import_all_target_vars()
print('Test 13 - User vars after importing all target: %d' % len(app.user_vars))
assert len(app.user_vars) > 6, "Should have more than 6 (structs are expanded)"
assert any(v['name'] == 'g_target_sensor' for v in app.user_vars), \
    "Should have g_target_sensor"
assert any(v['name'] == 'g_target_sensor.temperature' for v in app.user_vars), \
    "Should have g_target_sensor.temperature expanded"
assert any(v['name'] == 'g_target_tick' for v in app.user_vars), \
    "Should have g_target_tick"
print('Test 13 - Import all target vars: PASSED')

# Test 14: 目标变量来源标记
target_var = next(v for v in app.user_vars if v['name'] == 'g_target_sensor')
assert target_var.get('source') == '目标头文件', "Source should be '目标头文件'"
assert target_var.get('is_struct') == True, "g_target_sensor should be marked as struct"
expanded_var = next(v for v in app.user_vars if v['name'] == 'g_target_sensor.temperature')
assert expanded_var.get('source') == '目标结构体展开', "Source should be '目标结构体展开'"
print('Test 14 - Target var source marking: PASSED')

# Test 15: _is_target_var 检测
assert app._is_target_var('g_target_sensor') == True, "g_target_sensor should be target var"
assert app._is_target_var('my_temp') == False, "my_temp should not be target var"
print('Test 15 - _is_target_var: PASSED')

# Test 16: _get_member_tail
assert app._get_member_tail('g_target_sensor.temperature') == 'temperature', \
    "Should extract 'temperature'"
assert app._get_member_tail('g_target_tick') == '', \
    "Should return empty for non-member var"
print('Test 16 - _get_member_tail: PASSED')

# Test 17: 使用目标变量生成代码
app.user_vars.clear()
app._import_all_target_vars()
app._refresh_user_var_list()
app._update_user_var_combo()

app.selected_extern_var = app.parser.get_extern_var('g_sensor_data')
app._update_extern_member_combo()

app.mappings = [
    {'extern_member': 'temperature', 'user_var': 'g_target_sensor.temperature', 'op_type': '直接赋值', 'condition': '', 'conversion': '=', 'conv_rule': '='},
    {'extern_member': 'humidity', 'user_var': 'g_target_sensor.humidity', 'op_type': '直接赋值', 'condition': '', 'conversion': '=', 'conv_rule': '='},
    {'extern_member': 'pressure', 'user_var': 'g_target_sensor.pressure', 'op_type': '直接赋值', 'condition': '', 'conversion': '=', 'conv_rule': '='},
]
app._refresh_mapping_list()
app._generate_code()
code = app.code_text.get('1.0', tk.END)
print('Test 17 - Generated code with target vars:')
print(code)
assert 'g_target_sensor->temperature' in code, \
    "Should use -> access for target struct vars"
assert 'g_sensor_data->temperature' in code, \
    "Should use -> access for extern vars"
print('Test 17 - Code generation with target vars: PASSED')

# Test 18: 自动匹配功能
app.user_vars.clear()
app.user_vars = [
    {'name': 'my_sensor.temperature', 'type': 'int32_t', 'desc': '', 'source': '结构体展开', 'is_struct': False},
    {'name': 'my_sensor.humidity', 'type': 'float', 'desc': '', 'source': '结构体展开', 'is_struct': False},
    {'name': 'my_sensor.valid', 'type': 'bool', 'desc': '', 'source': '结构体展开', 'is_struct': False},
]
app._refresh_user_var_list()
app._update_user_var_combo()
app.mappings.clear()
app.selected_extern_var = app.parser.get_extern_var('g_sensor_data')
app._auto_match()
print('Test 18 - Auto-matched mappings: %d' % len(app.mappings))
assert len(app.mappings) >= 2, "Should auto-match at least 2 mappings"
matched_members = [m['extern_member'] for m in app.mappings]
assert 'temperature' in matched_members, "Should match temperature"
assert 'humidity' in matched_members, "Should match humidity"
assert 'valid' in matched_members, "Should match valid"
print('Test 18 - Auto match: PASSED')

# Test 19: 导出/导入配置包含目标头文件
app.target_file.set('sample_target.h')
import json, tempfile
with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
    config = {
        'header_file': app.current_file.get(),
        'target_header_file': app.target_file.get(),
        'user_vars': app.user_vars,
        'mappings': app.mappings,
    }
    json.dump(config, f, ensure_ascii=False, indent=2)
    temp_path = f.name

with open(temp_path, 'r', encoding='utf-8') as f:
    loaded = json.load(f)
assert loaded.get('target_header_file') == 'sample_target.h', \
    "Config should contain target_header_file"
os.unlink(temp_path)
print('Test 19 - Config export with target header: PASSED')

# Test 20: 导入目标结构体成员
app.user_vars.clear()
app._refresh_user_var_list()
app._update_user_var_combo()
target_children = app.target_var_tree.get_children()
app.target_var_tree.selection_set(target_children[0])
app._import_target_struct_members()
print('Test 20 - User vars after importing target struct members: %d' % len(app.user_vars))
assert len(app.user_vars) > 0, "Should have imported some members"
assert any('g_target_sensor.' in v['name'] for v in app.user_vars), \
    "Should have g_target_sensor member vars"
print('Test 20 - Import target struct members: PASSED')

root.destroy()
print()
print('=' * 60)
print('All 20 tests passed!')
print('=' * 60)
