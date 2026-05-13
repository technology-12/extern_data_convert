"""
Structure definition visual editor for the Streamlit low-code platform.
Provides forms for adding/editing/removing struct fields.
"""
import streamlit as st
from typing import List, Dict, Any


# Predefined C types for the dropdown
C_TYPES = [
    'char', 'short', 'int', 'long', 'float', 'double',
    'signed char', 'unsigned char', 'unsigned short',
    'unsigned int', 'unsigned long', 'long long',
    'unsigned long long', 'bool',
    'int8_t', 'int16_t', 'int32_t', 'int64_t',
    'uint8_t', 'uint16_t', 'uint32_t', 'uint64_t',
    'size_t', 'ptrdiff_t'
]


def _field_to_row(field: Dict[str, Any], idx: int) -> Dict[str, Any]:
    """Ensure a field dict has all expected keys."""
    return {
        'name': field.get('name', ''),
        'type': field.get('type', 'int'),
        'size': field.get('size', ''),
        'is_array': field.get('is_array', False),
        'is_bitfield': field.get('is_bitfield', False),
        'bitfield_width': field.get('bitfield_width', None),
        'nested_struct_def': field.get('nested_struct_def', ''),
        'validation_field': field.get('validation_field', ''),
        'array_size': field.get('array_size', '')
    }


def _new_field(name: str = '', ftype: str = 'int') -> Dict[str, Any]:
    """Create a new empty field dict."""
    return {
        'name': name,
        'type': ftype,
        'size': '',
        'is_array': False,
        'is_bitfield': False,
        'bitfield_width': None,
        'nested_struct_def': '',
        'validation_field': '',
        'array_size': ''
    }


def render_struct_editor(struct_name: str, fields_key: str, label: str):
    """
    Render an editable struct definition section.

    Args:
        struct_name: Display name for the struct (e.g. "sensor_data_ext")
        fields_key: session_state key for the fields list
        label: Section label (e.g. "外部结构体" or "内部结构体")
    """
    fields = st.session_state.get(fields_key, [])

    st.subheader(f"{label}: `{struct_name}_t`")

    if not fields:
        st.info(f"暂无字段，请点击下方「添加字段」按钮添加。")
    else:
        # Display fields in a compact table-like format
        for i, field in enumerate(fields):
            field = _field_to_row(field, i)
            cols = st.columns([3, 3, 2, 2, 2, 1])

            with cols[0]:
                field['name'] = st.text_input(
                    "字段名", value=field['name'],
                    key=f"{fields_key}_name_{i}", label_visibility="collapsed"
                )

            with cols[1]:
                current_type = field['type']
                type_index = C_TYPES.index(current_type) if current_type in C_TYPES else 0
                field['type'] = st.selectbox(
                    "类型", C_TYPES, index=type_index,
                    key=f"{fields_key}_type_{i}", label_visibility="collapsed"
                )

            with cols[2]:
                field['size'] = st.text_input(
                    "数组大小", value=field['size'],
                    key=f"{fields_key}_size_{i}",
                    placeholder="无",
                    label_visibility="collapsed"
                )
                field['is_array'] = bool(field['size'].strip())

            with cols[3]:
                bw = field.get('bitfield_width') or ''
                field['bitfield_width'] = st.text_input(
                    "位域宽度", value=bw,
                    key=f"{fields_key}_bw_{i}",
                    placeholder="无",
                    label_visibility="collapsed"
                )
                field['is_bitfield'] = bool(str(field['bitfield_width']).strip())

            with cols[4]:
                field['nested_struct_def'] = st.text_input(
                    "嵌套结构体", value=field.get('nested_struct_def', ''),
                    key=f"{fields_key}_nested_{i}",
                    placeholder="无",
                    label_visibility="collapsed"
                )

            with cols[5]:
                # Delete button
                if st.button("🗑️", key=f"{fields_key}_del_{i}", help="删除此字段"):
                    fields.pop(i)
                    st.session_state[fields_key] = fields
                    st.rerun()

            # Update the field in the list
            fields[i] = field

        st.session_state[fields_key] = fields

    # Add field form
    st.markdown("---")
    add_cols = st.columns([3, 3, 2, 2, 2, 1])

    with add_cols[0]:
        new_name = st.text_input("新字段名", key=f"{fields_key}_new_name",
                                  placeholder="输入字段名", label_visibility="collapsed")

    with add_cols[1]:
        new_type = st.selectbox("类型", C_TYPES, index=C_TYPES.index('int'),
                                 key=f"{fields_key}_new_type", label_visibility="collapsed")

    with add_cols[2]:
        new_size = st.text_input("数组大小", key=f"{fields_key}_new_size",
                                  placeholder="无", label_visibility="collapsed")

    with add_cols[3]:
        new_bw = st.text_input("位域宽度", key=f"{fields_key}_new_bw",
                                placeholder="无", label_visibility="collapsed")

    with add_cols[4]:
        new_nested = st.text_input("嵌套结构体", key=f"{fields_key}_new_nested",
                                    placeholder="无", label_visibility="collapsed")

    with add_cols[5]:
        st.write("")  # spacer
        if st.button("➕", key=f"{fields_key}_add", help="添加字段"):
            if new_name.strip():
                new_f = _new_field(new_name.strip(), new_type)
                new_f['size'] = new_size.strip()
                new_f['is_array'] = bool(new_size.strip())
                new_f['bitfield_width'] = new_bw.strip() or None
                new_f['is_bitfield'] = bool(new_bw.strip())
                new_f['nested_struct_def'] = new_nested.strip()
                fields.append(new_f)
                st.session_state[fields_key] = fields
                st.rerun()

    # Validation field setting
    st.markdown("---")
    val_cols = st.columns([3, 3])
    with val_cols[0]:
        st.caption("验证字段设置")
    with val_cols[1]:
        if fields:
            field_names = [f['name'] for f in fields]
            current_val = ''
            for f in fields:
                if f.get('validation_field'):
                    current_val = f['validation_field']
                    break
            val_field = st.selectbox(
                "验证字段",
                options=[''] + field_names,
                index=([''] + field_names).index(current_val) if current_val in ([''] + field_names) else 0,
                key=f"{fields_key}_val_field",
                help="选择用于验证逻辑的字段"
            )
            # Update validation_field for the selected field
            for f in fields:
                f['validation_field'] = ''
            if val_field:
                for f in fields:
                    if f['name'] == val_field:
                        f['validation_field'] = val_field
                        break
            st.session_state[fields_key] = fields


def render_struct_editor_page():
    """Render the full struct editor page with external and internal sections."""
    project = _get_current_project()
    if project is None:
        st.warning("请先在侧边栏创建或选择一个项目。")
        return

    pair_name = st.session_state.current_project
    ext_name = project.get('external_struct_name', f'{pair_name}_ext')
    int_name = project.get('internal_struct_name', f'{pair_name}_int')

    ext_key = f"project_{pair_name}_ext_fields"
    int_key = f"project_{pair_name}_int_fields"

    # Initialize fields in session state if not present
    if ext_key not in st.session_state:
        st.session_state[ext_key] = project.get('external_fields', [])
    if int_key not in st.session_state:
        st.session_state[int_key] = project.get('internal_fields', [])

    col1, col2 = st.columns(2)

    with col1:
        with st.container(border=True):
            render_struct_editor(ext_name, ext_key, "外部结构体 (External)")

    with col2:
        with st.container(border=True):
            render_struct_editor(int_name, int_key, "内部结构体 (Internal)")

    # Sync back to project data
    project['external_fields'] = st.session_state[ext_key]
    project['internal_fields'] = st.session_state[int_key]
    st.session_state.projects[pair_name] = project


def _get_current_project() -> Dict[str, Any] | None:
    """Get the current project data from session state."""
    if 'projects' not in st.session_state:
        st.session_state.projects = {}
    current = st.session_state.get('current_project')
    if current and current in st.session_state.projects:
        return st.session_state.projects[current]
    return None
