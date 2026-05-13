"""
Struct Converter Toolkit - 低代码平台主应用
基于 Streamlit 构建的可视化结构体转换代码生成器

启动方式:
    streamlit run app.py
"""
import streamlit as st
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.code_generator import CodeGenerator
from core.csv_converter import CsvConverter
from ui.struct_editor import render_struct_editor_page
from ui.mapping_editor import render_mapping_editor
from ui.code_preview import render_code_preview


# ── Page Configuration ────────────────────────────────────────────

st.set_page_config(
    page_title="Struct Converter Toolkit",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ── Session State Initialization ──────────────────────────────────

def init_session_state():
    """Initialize session state with default values."""
    if 'projects' not in st.session_state:
        st.session_state.projects = {}
    if 'current_project' not in st.session_state:
        st.session_state.current_project = None
    if 'settings' not in st.session_state:
        st.session_state.settings = {
            'output_header': 'generated_structs.h',
            'output_source': 'generated_structs.c',
            'header_guard': 'GENERATED_STRUCTS_H'
        }


# ── Sidebar ───────────────────────────────────────────────────────

def render_sidebar():
    """Render the sidebar with project management, import/export, and settings."""
    with st.sidebar:
        st.title("🔧 Struct Converter")
        st.caption("结构体转换代码生成器 · 低代码平台")

        # ── Project Management ──
        st.markdown("---")
        st.subheader("📁 项目管理")

        # Create new project
        with st.expander("➕ 新建项目", expanded=False):
            new_name = st.text_input(
                "项目名称",
                placeholder="例如: sensor_data",
                key="new_project_name"
            )
            if st.button("创建", use_container_width=True):
                if new_name.strip():
                    name = new_name.strip()
                    if name in st.session_state.projects:
                        st.error(f"项目 '{name}' 已存在！")
                    else:
                        st.session_state.projects[name] = {
                            'external_struct_name': f'{name}_ext',
                            'internal_struct_name': f'{name}_int',
                            'external_fields': [],
                            'internal_fields': [],
                            'mappings': []
                        }
                        st.session_state.current_project = name
                        st.rerun()
                else:
                    st.error("请输入项目名称")

        # Project list
        project_names = list(st.session_state.projects.keys())
        if project_names:
            selected = st.selectbox(
                "当前项目",
                options=project_names,
                index=project_names.index(st.session_state.current_project)
                if st.session_state.current_project in project_names else 0,
                key="project_selector"
            )
            if selected != st.session_state.current_project:
                st.session_state.current_project = selected
                st.rerun()

            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗑️ 删除项目", use_container_width=True):
                    del st.session_state.projects[selected]
                    # Clean up related session state keys
                    keys_to_remove = [k for k in st.session_state
                                      if k.startswith(f"project_{selected}_")]
                    for k in keys_to_remove:
                        del st.session_state[k]
                    if st.session_state.projects:
                        st.session_state.current_project = list(st.session_state.projects.keys())[0]
                    else:
                        st.session_state.current_project = None
                    st.rerun()

            with col2:
                # Quick info
                proj = st.session_state.projects[selected]
                ext_count = len(proj.get('external_fields', []))
                int_count = len(proj.get('internal_fields', []))
                map_count = len(proj.get('mappings', []))
                st.metric("字段/映射", f"{ext_count}+{int_count}/{map_count}")
        else:
            st.info("暂无项目，请创建新项目或导入配置。")

        # ── Import ──
        st.markdown("---")
        st.subheader("📥 导入")

        with st.expander("📂 导入 CSV 文件"):
            csv_files = st.file_uploader(
                "选择 CSV 文件",
                type=['csv'],
                accept_multiple_files=True,
                key="csv_uploader"
            )
            if csv_files and st.button("导入 CSV", key="import_csv_btn"):
                try:
                    generator = CodeGenerator()
                    converter = CsvConverter(generator)
                    converter.parse_uploaded_files(csv_files)
                    data = generator.export_to_dict()
                    for name, proj in data['projects'].items():
                        st.session_state.projects[name] = proj
                    if data['projects']:
                        first_name = list(data['projects'].keys())[0]
                        st.session_state.current_project = first_name
                    st.success(f"成功导入 {len(data['projects'])} 个结构体对！")
                    st.rerun()
                except Exception as e:
                    st.error(f"导入 CSV 失败: {e}")

        with st.expander("📊 导入 Excel 文件"):
            excel_file = st.file_uploader(
                "选择 Excel 文件",
                type=['xlsx', 'xls'],
                accept_multiple_files=False,
                key="excel_uploader"
            )
            if excel_file and st.button("导入 Excel", key="import_excel_btn"):
                try:
                    generator = CodeGenerator()
                    converter = ExcelConverter(generator)
                    converter.parse_uploaded_file(excel_file)
                    data = generator.export_to_dict()
                    for name, proj in data['projects'].items():
                        st.session_state.projects[name] = proj
                    if data['projects']:
                        first_name = list(data['projects'].keys())[0]
                        st.session_state.current_project = first_name
                    st.success(f"成功导入 {len(data['projects'])} 个结构体对！")
                    st.rerun()
                except Exception as e:
                    st.error(f"导入 Excel 失败: {e}")

        with st.expander("📋 导入 JSON 配置"):
            json_file = st.file_uploader(
                "选择 JSON 文件",
                type=['json'],
                accept_multiple_files=False,
                key="json_uploader"
            )
            if json_file and st.button("导入 JSON", key="import_json_btn"):
                try:
                    content = json_file.getvalue().decode('utf-8')
                    data = json.loads(content)
                    for name, proj in data.get('projects', {}).items():
                        st.session_state.projects[name] = proj
                    if data.get('projects'):
                        first_name = list(data['projects'].keys())[0]
                        st.session_state.current_project = first_name
                    st.success(f"成功导入 {len(data.get('projects', {}))} 个项目！")
                    st.rerun()
                except Exception as e:
                    st.error(f"导入 JSON 失败: {e}")

        # ── Export ──
        st.markdown("---")
        st.subheader("📤 导出")

        if st.session_state.projects:
            if st.button("💾 导出 JSON 配置", use_container_width=True):
                # Sync UI state to projects before export
                _sync_ui_to_projects()
                export_data = {'projects': st.session_state.projects}
                json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
                st.download_button(
                    label="⬇️ 下载 JSON 文件",
                    data=json_str,
                    file_name="struct_converter_config.json",
                    mime="application/json",
                    use_container_width=True
                )

        # ── Settings ──
        st.markdown("---")
        st.subheader("⚙️ 全局设置")

        settings = st.session_state.settings

        settings['output_header'] = st.text_input(
            "输出头文件名",
            value=settings.get('output_header', 'generated_structs.h'),
            key="setting_header"
        )
        settings['output_source'] = st.text_input(
            "输出源文件名",
            value=settings.get('output_source', 'generated_structs.c'),
            key="setting_source"
        )
        settings['header_guard'] = st.text_input(
            "头文件保护宏",
            value=settings.get('header_guard', 'GENERATED_STRUCTS_H'),
            key="setting_guard"
        )

        st.session_state.settings = settings


def _sync_ui_to_projects():
    """Sync UI editing state back to project data before export."""
    for pair_name, project in st.session_state.projects.items():
        ext_key = f"project_{pair_name}_ext_fields"
        int_key = f"project_{pair_name}_int_fields"
        mappings_key = f"project_{pair_name}_mappings"

        if ext_key in st.session_state:
            project['external_fields'] = st.session_state[ext_key]
        if int_key in st.session_state:
            project['internal_fields'] = st.session_state[int_key]
        if mappings_key in st.session_state:
            project['mappings'] = st.session_state[mappings_key]


# ── Main Area ─────────────────────────────────────────────────────

def render_main():
    """Render the main content area with tabs."""
    tab1, tab2, tab3 = st.tabs([
        "📝 结构体定义",
        "🔗 字段映射",
        "💻 代码预览"
    ])

    with tab1:
        render_struct_editor_page()

    with tab2:
        render_mapping_editor()

    with tab3:
        render_code_preview()


# ── Entry Point ───────────────────────────────────────────────────

def main():
    init_session_state()
    render_sidebar()
    render_main()


if __name__ == "__main__":
    main()
