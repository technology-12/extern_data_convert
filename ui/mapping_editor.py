"""
Field mapping and conversion rule editor for the Streamlit low-code platform.
Provides forms for configuring external-to-internal field mappings.
"""
import streamlit as st
from typing import List, Dict, Any


def render_mapping_editor():
    """Render the mapping editor page for the current project."""
    project = _get_current_project()
    if project is None:
        st.warning("请先在侧边栏创建或选择一个项目。")
        return

    pair_name = st.session_state.current_project
    mappings_key = f"project_{pair_name}_mappings"

    # Initialize mappings in session state
    if mappings_key not in st.session_state:
        st.session_state[mappings_key] = project.get('mappings', [])

    mappings = st.session_state[mappings_key]

    ext_fields = project.get('external_fields', [])
    int_fields = project.get('internal_fields', [])

    ext_field_names = [f['name'] for f in ext_fields if f.get('name')]
    int_field_names = [f['name'] for f in int_fields if f.get('name')]

    if not ext_field_names and not int_field_names:
        st.warning("请先在「结构体定义」页面添加外部和内部结构体字段。")
        return

    st.subheader("字段映射配置")

    # Mapping visualization
    if mappings:
        st.markdown("### 映射关系概览")
        _render_mapping_overview(mappings, ext_field_names, int_field_names)
        st.markdown("---")

    # Edit mappings
    st.markdown("### 编辑映射关系")

    for i, mapping in enumerate(mappings):
        with st.container(border=True):
            m_cols = st.columns([3, 1, 3, 3, 1])

            with m_cols[0]:
                # External field
                current_ext = mapping.get('external_field', '')
                ext_options = [''] + ext_field_names
                ext_idx = ext_options.index(current_ext) if current_ext in ext_options else 0
                mapping['external_field'] = st.selectbox(
                    "外部字段", ext_options, index=ext_idx,
                    key=f"{mappings_key}_ext_{i}", label_visibility="collapsed"
                )

            with m_cols[1]:
                st.markdown("<div style='text-align:center; padding-top:28px;'>→</div>",
                           unsafe_allow_html=True)

            with m_cols[2]:
                # Internal field
                current_int = mapping.get('internal_field', '')
                int_options = [''] + int_field_names
                int_idx = int_options.index(current_int) if current_int in int_options else 0
                mapping['internal_field'] = st.selectbox(
                    "内部字段", int_options, index=int_idx,
                    key=f"{mappings_key}_int_{i}", label_visibility="collapsed"
                )

            with m_cols[3]:
                # Conversion rule
                current_rule = mapping.get('conversion_rule', '=')
                rule = st.text_input(
                    "转换规则", value=current_rule,
                    key=f"{mappings_key}_rule_{i}",
                    placeholder="= 或自定义函数名",
                    label_visibility="collapsed"
                )
                mapping['conversion_rule'] = rule if rule.strip() else '='

            with m_cols[4]:
                if st.button("🗑️", key=f"{mappings_key}_del_{i}", help="删除此映射"):
                    mappings.pop(i)
                    st.session_state[mappings_key] = mappings
                    _sync_to_project(pair_name, mappings)
                    st.rerun()

            # Validation logic (expandable)
            current_vlogic = mapping.get('validation_logic', '')
            vlogic = st.text_input(
                "验证逻辑 (可选)",
                value=current_vlogic,
                key=f"{mappings_key}_vlogic_{i}",
                placeholder="例如: external->valid && recv_status",
                help="输入验证条件表达式，如 external->valid && recv_status"
            )
            mapping['validation_logic'] = vlogic.strip()

            # Bitfield info and nested struct (advanced)
            with st.expander("高级选项", expanded=False):
                bf_info = mapping.get('bitfield_info', '')
                mapping['bitfield_info'] = st.text_input(
                    "位域信息", value=bf_info,
                    key=f"{mappings_key}_bf_{i}",
                    placeholder="可选"
                )

                ns_info = mapping.get('nested_struct', '')
                mapping['nested_struct'] = st.text_input(
                    "嵌套结构体", value=ns_info,
                    key=f"{mappings_key}_ns_{i}",
                    placeholder="可选"
                )

            mappings[i] = mapping

    st.session_state[mappings_key] = mappings

    # Add new mapping
    st.markdown("---")
    st.markdown("### 添加新映射")

    add_cols = st.columns([3, 1, 3, 3, 1])

    with add_cols[0]:
        new_ext = st.selectbox(
            "外部字段", [''] + ext_field_names,
            key=f"{mappings_key}_new_ext"
        )

    with add_cols[1]:
        st.markdown("<div style='text-align:center; padding-top:28px;'>→</div>",
                    unsafe_allow_html=True)

    with add_cols[2]:
        new_int = st.selectbox(
            "内部字段", [''] + int_field_names,
            key=f"{mappings_key}_new_int"
        )

    with add_cols[3]:
        new_rule = st.text_input(
            "转换规则", value="=",
            key=f"{mappings_key}_new_rule",
            placeholder="= 或自定义函数名"
        )

    with add_cols[4]:
        st.write("")
        if st.button("➕ 添加", key=f"{mappings_key}_add"):
            if new_ext and new_int:
                new_mapping = {
                    'external_field': new_ext,
                    'internal_field': new_int,
                    'conversion_rule': new_rule.strip() or '=',
                    'validation_logic': '',
                    'bitfield_info': '',
                    'nested_struct': ''
                }
                mappings.append(new_mapping)
                st.session_state[mappings_key] = mappings
                _sync_to_project(pair_name, mappings)
                st.rerun()

    # Sync back
    _sync_to_project(pair_name, mappings)


def _render_mapping_overview(mappings: List[Dict], ext_names: List[str], int_names: List[str]):
    """Render a visual overview of the mapping relationships."""
    # Build a simple text-based visualization
    lines = []
    for m in mappings:
        ef = m.get('external_field', '?')
        inf = m.get('internal_field', '?')
        rule = m.get('conversion_rule', '=')
        vlogic = m.get('validation_logic', '')

        if rule == '=':
            arrow = "───"
        else:
            arrow = f"─[{rule}]─"

        line = f"`{ef}` {arrow}→ `{inf}`"
        if vlogic:
            line += f"  *(条件: `{vlogic}`)*"
        lines.append(line)

    st.markdown("\n\n".join(lines))


def _sync_to_project(pair_name: str, mappings: List[Dict]):
    """Sync mappings back to the project data in session state."""
    if pair_name in st.session_state.projects:
        st.session_state.projects[pair_name]['mappings'] = mappings


def _get_current_project() -> Dict[str, Any] | None:
    """Get the current project data from session state."""
    if 'projects' not in st.session_state:
        st.session_state.projects = {}
    current = st.session_state.get('current_project')
    if current and current in st.session_state.projects:
        return st.session_state.projects[current]
    return None
