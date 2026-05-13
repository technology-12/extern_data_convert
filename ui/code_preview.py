"""
Code preview and download component for the Streamlit low-code platform.
Displays generated C header and source code with syntax highlighting.
"""
import streamlit as st
from typing import Dict, Any, Optional
from core.code_generator import CodeGenerator


def render_code_preview():
    """Render the code preview and download page."""
    project = _get_current_project()
    if project is None:
        st.warning("请先在侧边栏创建或选择一个项目。")
        return

    # Build a CodeGenerator from current session state
    generator = _build_generator()

    if not generator.struct_pairs:
        st.warning("暂无结构体对配置。请先在「结构体定义」和「字段映射」页面完成配置。")
        return

    # Settings
    settings = st.session_state.get('settings', {
        'output_header': 'generated_structs.h',
        'output_source': 'generated_structs.c',
        'header_guard': 'GENERATED_STRUCTS_H'
    })

    header_file = settings.get('output_header', 'generated_structs.h')
    source_file = settings.get('output_source', 'generated_structs.c')
    header_guard = settings.get('header_guard', 'GENERATED_STRUCTS_H')

    # Generate code
    header_code = generator.generate_header_code(header_guard=header_guard)
    source_code = generator.generate_source_code(header_file=header_file)

    # Display tabs for header and source
    h_tab, s_tab = st.tabs(["📄 头文件 (.h)", "📄 源文件 (.c)"])

    with h_tab:
        st.markdown(f"### `{header_file}`")
        st.code(header_code, language="c")

        st.download_button(
            label="⬇️ 下载头文件",
            data=header_code,
            file_name=header_file,
            mime="text/plain",
            use_container_width=True
        )

    with s_tab:
        st.markdown(f"### `{source_file}`")
        st.code(source_code, language="c")

        st.download_button(
            label="⬇️ 下载源文件",
            data=source_code,
            file_name=source_file,
            mime="text/plain",
            use_container_width=True
        )

    # Download both files
    st.markdown("---")
    st.markdown("### 打包下载")

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="📦 下载头文件 (.h)",
            data=header_code,
            file_name=header_file,
            mime="text/plain"
        )
    with col2:
        st.download_button(
            label="📦 下载源文件 (.c)",
            data=source_code,
            file_name=source_file,
            mime="text/plain"
        )


def _build_generator() -> CodeGenerator:
    """
    Build a CodeGenerator instance from the current session state.
    Syncs the UI state (fields, mappings) into the generator.
    """
    generator = CodeGenerator()

    if 'projects' not in st.session_state:
        return generator

    for pair_name, project in st.session_state.projects.items():
        ext_name = project.get('external_struct_name', f'{pair_name}_ext')
        int_name = project.get('internal_struct_name', f'{pair_name}_int')

        # Get fields from session state (may have been edited in UI)
        ext_key = f"project_{pair_name}_ext_fields"
        int_key = f"project_{pair_name}_int_fields"
        mappings_key = f"project_{pair_name}_mappings"

        ext_fields = st.session_state.get(ext_key, project.get('external_fields', []))
        int_fields = st.session_state.get(int_key, project.get('internal_fields', []))
        mappings = st.session_state.get(mappings_key, project.get('mappings', []))

        generator.add_struct(ext_name, ext_fields)
        generator.add_struct(int_name, int_fields)
        generator.add_struct_pair(pair_name, ext_name, int_name, mappings)

    return generator


def _get_current_project() -> Optional[Dict[str, Any]]:
    """Get the current project data from session state."""
    if 'projects' not in st.session_state:
        st.session_state.projects = {}
    current = st.session_state.get('current_project')
    if current and current in st.session_state.projects:
        return st.session_state.projects[current]
    return None
