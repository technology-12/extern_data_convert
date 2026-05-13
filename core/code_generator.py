"""
Unified C code generator for struct conversion.
Extracted from win7_struct_converter.py and enhanced_struct_converter.py.
Used by both CLI tools and the Streamlit low-code platform.
"""
import json
from typing import Dict, List, Any, Optional


class CodeGenerator:
    """
    Unified code generator that produces C header and source files
    for converting between external and internal structures.
    """

    DEFAULT_C_TYPES = [
        'char', 'short', 'int', 'long', 'float', 'double',
        'signed char', 'unsigned char', 'unsigned short',
        'unsigned int', 'unsigned long', 'long long',
        'unsigned long long', 'bool', 'int8_t', 'int16_t',
        'int32_t', 'int64_t', 'uint8_t', 'uint16_t',
        'uint32_t', 'uint64_t', 'size_t', 'ptrdiff_t'
    ]

    def __init__(self):
        self.struct_pairs: Dict[str, Dict] = {}
        self.all_structs: Dict[str, List[Dict]] = {}

    def clear(self):
        """Clear all loaded data."""
        self.struct_pairs.clear()
        self.all_structs.clear()

    # ── Data Loading ──────────────────────────────────────────────

    def add_struct(self, struct_name: str, fields: List[Dict[str, Any]]):
        """Add or replace a struct definition."""
        self.all_structs[struct_name] = fields

    def add_struct_pair(self, pair_name: str, external_name: str,
                        internal_name: str, mappings: List[Dict[str, str]]):
        """Add or replace a struct pair with field mappings."""
        self.struct_pairs[pair_name] = {
            'external_name': external_name,
            'internal_name': internal_name,
            'mappings': mappings
        }

    def load_from_dict(self, data: Dict[str, Any]):
        """
        Load configuration from a dictionary (e.g. parsed from JSON).
        Expected format:
        {
            "projects": {
                "sensor_data": {
                    "external_struct_name": "sensor_data_ext",
                    "internal_struct_name": "sensor_data_int",
                    "external_fields": [ {...}, ... ],
                    "internal_fields": [ {...}, ... ],
                    "mappings": [ {...}, ... ]
                }
            }
        }
        """
        self.clear()
        projects = data.get('projects', {})
        for pair_name, project in projects.items():
            ext_name = project.get('external_struct_name', f'{pair_name}_ext')
            int_name = project.get('internal_struct_name', f'{pair_name}_int')

            ext_fields = project.get('external_fields', [])
            int_fields = project.get('internal_fields', [])
            mappings = project.get('mappings', [])

            self.add_struct(ext_name, ext_fields)
            self.add_struct(int_name, int_fields)
            self.add_struct_pair(pair_name, ext_name, int_name, mappings)

    def export_to_dict(self) -> Dict[str, Any]:
        """Export current configuration to a dictionary (for JSON serialization)."""
        projects = {}
        for pair_name, pair_info in self.struct_pairs.items():
            ext_name = pair_info['external_name']
            int_name = pair_info['internal_name']
            projects[pair_name] = {
                'external_struct_name': ext_name,
                'internal_struct_name': int_name,
                'external_fields': self.all_structs.get(ext_name, []),
                'internal_fields': self.all_structs.get(int_name, []),
                'mappings': pair_info['mappings']
            }
        return {'projects': projects}

    def load_from_csv_dict(self, sheets: Dict[str, List[Dict[str, str]]]):
        """
        Load from CSV-parsed data (dict of sheet_name -> list of row dicts).
        Compatible with the CSV format used by win7_struct_converter.py.
        """
        self.clear()
        for sheet_name, rows in sheets.items():
            self._parse_struct_pair_rows(rows, sheet_name)

    def _parse_struct_pair_rows(self, rows: List[Dict[str, str]], sheet_name: str):
        """Parse rows containing struct definitions and mappings (CSV format)."""
        if not rows:
            return

        has_field_name = any(row.get('field_name', '').strip() for row in rows)
        has_field_type = any(row.get('field_type', '').strip() for row in rows)

        if has_field_name and has_field_type:
            ext_name = f"{sheet_name}_ext"
            int_name = f"{sheet_name}_int"

            ext_fields = []
            int_fields = []

            for row in rows:
                field_name = row.get('field_name', '').strip()
                field_type = row.get('field_type', '').strip()
                struct_type = row.get('struct_type', 'external').lower()

                if field_name and field_type:
                    field_info = {
                        'name': field_name,
                        'type': field_type,
                        'size': row.get('field_size', '').strip(),
                        'is_array': bool(row.get('field_size', '').strip()),
                        'is_bitfield': bool(row.get('bitfield_width', '').strip()),
                        'bitfield_width': row.get('bitfield_width', '').strip() or None,
                        'nested_struct_def': row.get('nested_struct_def', '').strip(),
                        'validation_field': row.get('validation_field', '').strip(),
                        'array_size': row.get('array_size', '').strip()
                    }

                    if struct_type == 'internal':
                        int_fields.append(field_info)
                    else:
                        ext_fields.append(field_info)

            if ext_fields:
                self.add_struct(ext_name, ext_fields)
            if int_fields:
                self.add_struct(int_name, int_fields)

            # Process mappings
            has_mapping = any(row.get('external_field', '').strip() for row in rows)
            has_internal = any(row.get('internal_field', '').strip() for row in rows)

            if has_mapping and has_internal:
                mappings = []
                for row in rows:
                    ef = row.get('external_field', '').strip()
                    inf = row.get('internal_field', '').strip()
                    if ef and inf:
                        mappings.append({
                            'external_field': ef,
                            'internal_field': inf,
                            'conversion_rule': row.get('conversion_rule', '=').strip() or '=',
                            'validation_logic': row.get('validation_logic', '').strip(),
                            'bitfield_info': row.get('bitfield_info', '').strip(),
                            'nested_struct': row.get('nested_struct', '').strip()
                        })
                self.add_struct_pair(sheet_name, ext_name, int_name, mappings)
        else:
            # Legacy format: only mappings
            ext_name = f"{sheet_name}_ext"
            int_name = f"{sheet_name}_int"

            if rows and 'external_struct' in rows[0]:
                ext_name = rows[0].get('external_struct', ext_name)
                int_name = rows[0].get('internal_struct', int_name)

            mappings = []
            for row in rows:
                ef = row.get('external_field', '').strip()
                inf = row.get('internal_field', '').strip()
                if ef and inf:
                    mappings.append({
                        'external_field': ef,
                        'internal_field': inf,
                        'conversion_rule': row.get('conversion_rule', '=').strip() or '=',
                        'validation_logic': row.get('validation_logic', '').strip(),
                        'bitfield_info': row.get('bitfield_info', '').strip(),
                        'nested_struct': row.get('nested_struct', '').strip()
                    })
            self.add_struct_pair(sheet_name, ext_name, int_name, mappings)

    # ── Validation Helpers ────────────────────────────────────────

    def _has_validation_field(self, struct_name: str) -> bool:
        """Check if a struct has validation fields."""
        if struct_name in self.all_structs:
            for field in self.all_structs[struct_name]:
                if field.get('validation_field'):
                    return True
        return False

    def _find_validity_field(self, struct_name: str) -> Optional[str]:
        """Find a field in the struct that indicates validity."""
        if struct_name in self.all_structs:
            for field in self.all_structs[struct_name]:
                if 'valid' in field['name'].lower() or 'status' in field['name'].lower():
                    return field['name']
        return None

    def _has_recv_status_logic(self, mappings: List[Dict]) -> bool:
        """Check if any mapping uses recv_status in validation logic."""
        return any('recv_status' in m.get('validation_logic', '') for m in mappings)

    # ── Code Generation ───────────────────────────────────────────

    def generate_header_code(self, header_guard: str = "GENERATED_STRUCTS_H",
                             include_guard_prefix: str = "") -> str:
        """
        Generate C header file with struct definitions and function declarations.

        Args:
            header_guard: Name for the include guard macro.
            include_guard_prefix: Optional prefix (e.g. "WIN7") for backward compat.
        """
        if include_guard_prefix:
            guard = f"{include_guard_prefix}_STRUCT_CONVERTER_H"
        else:
            guard = header_guard

        lines = [
            "/* Generated by Struct Converter Toolkit - Low-Code Platform */",
            f"#ifndef {guard}",
            f"#define {guard}",
            "",
            "#include <stdint.h>",
            "#include <stdbool.h>",
            ""
        ]

        # Struct definitions
        for struct_name, fields in self.all_structs.items():
            lines.append("typedef struct {")
            for field in fields:
                line = self._generate_field_declaration(field)
                lines.append(f"    {line}")
            lines.append(f"}} {struct_name}_t;")
            lines.append("")

        # Function declarations
        for pair_name, pair_info in self.struct_pairs.items():
            ext_name = pair_info['external_name']
            int_name = pair_info['internal_name']
            mappings = pair_info['mappings']

            needs_recv = (self._has_validation_field(ext_name) or
                          self._has_validation_field(int_name) or
                          self._has_recv_status_logic(mappings))

            lines.append(f"// Conversion functions for {pair_name}")
            if needs_recv:
                lines.append(
                    f"int convert_{ext_name}_to_{int_name}"
                    f"({ext_name}_t *external, {int_name}_t *internal, int recv_status);"
                )
                lines.append(
                    f"int convert_{int_name}_to_{ext_name}"
                    f"({int_name}_t *internal, {ext_name}_t *external, int recv_status);"
                )
            else:
                lines.append(
                    f"int convert_{ext_name}_to_{int_name}"
                    f"({ext_name}_t *external, {int_name}_t *internal);"
                )
                lines.append(
                    f"int convert_{int_name}_to_{ext_name}"
                    f"({int_name}_t *internal, {ext_name}_t *external);"
                )
            lines.append("")

        lines.extend([
            f"#endif /* {guard} */",
            ""
        ])

        return "\n".join(lines)

    def _generate_field_declaration(self, field: Dict) -> str:
        """Generate a single field declaration line (without leading whitespace)."""
        ftype = field.get('type', 'int')
        fname = field.get('name', 'unknown')

        if field.get('is_array') and field.get('size'):
            return f"{ftype} {fname}[{field['size']}];"
        elif field.get('is_bitfield') and field.get('bitfield_width'):
            return f"{ftype} {fname} : {field['bitfield_width']};"
        elif field.get('nested_struct_def'):
            return f"{field['nested_struct_def']}_t {fname};"
        else:
            return f"{ftype} {fname};"

    def generate_source_code(self, header_file: str = "generated_structs.h") -> str:
        """
        Generate C source file with conversion function implementations.

        Args:
            header_file: Name of the header file to include.
        """
        lines = [
            "/* Generated by Struct Converter Toolkit - Low-Code Platform */",
            f'#include "{header_file}"',
            "",
            "// Conversion functions"
        ]

        for pair_name, pair_info in self.struct_pairs.items():
            ext_name = pair_info['external_name']
            int_name = pair_info['internal_name']
            mappings = pair_info['mappings']

            ext_has_val = self._has_validation_field(ext_name)
            int_has_val = self._has_validation_field(int_name)
            needs_recv = ext_has_val or int_has_val or self._has_recv_status_logic(mappings)

            # ── External → Internal ──
            if needs_recv:
                sig = (f"int convert_{ext_name}_to_{int_name}"
                       f"({ext_name}_t *external, {int_name}_t *internal, int recv_status)")
            else:
                sig = (f"int convert_{ext_name}_to_{int_name}"
                       f"({ext_name}_t *external, {int_name}_t *internal)")

            lines.extend(["", sig, "{"])
            lines.append("    if (!external || !internal) return -1;")
            lines.append("")

            for mapping in mappings:
                ef = mapping['external_field']
                inf = mapping['internal_field']
                rule = mapping.get('conversion_rule', '=')
                vlogic = mapping.get('validation_logic', '')

                if vlogic:
                    lines.append(f"    // Apply validation logic: {vlogic}")
                    lines.append(f"    if ({vlogic}) {{")
                    if rule == '=':
                        lines.append(f"        internal->{inf} = external->{ef};")
                    else:
                        lines.append(f"        internal->{inf} = {rule}(external->{ef});")
                    lines.append("    } else {")
                    lines.append(f"        internal->{inf} = 0;  // Default value on validation failure")
                    lines.append("    }")
                elif rule == '=':
                    lines.append(f"    internal->{inf} = external->{ef};")
                else:
                    lines.append(f"    internal->{inf} = {rule}(external->{ef});")

            # Validation field updates
            if int_has_val:
                for field in self.all_structs.get(int_name, []):
                    if field.get('validation_field'):
                        ext_val_field = self._find_validity_field(ext_name)
                        if ext_val_field:
                            lines.append(
                                f"    internal->{field['validation_field']} = "
                                f"external->{ext_val_field} && recv_status;  "
                                f"// Combine external validity and receive status"
                            )
                        else:
                            lines.append(
                                f"    internal->{field['validation_field']} = "
                                f"recv_status;  // Use receive status as validity"
                            )

            lines.extend(["    return 0;", "}", ""])

            # ── Internal → External ──
            if needs_recv:
                sig = (f"int convert_{int_name}_to_{ext_name}"
                       f"({int_name}_t *internal, {ext_name}_t *external, int recv_status)")
            else:
                sig = (f"int convert_{int_name}_to_{ext_name}"
                       f"({int_name}_t *internal, {ext_name}_t *external)")

            lines.extend([sig, "{"])
            lines.append("    if (!internal || !external) return -1;")
            lines.append("")

            for mapping in mappings:
                ef = mapping['external_field']
                inf = mapping['internal_field']
                rule = mapping.get('conversion_rule', '=')

                if rule == '=':
                    lines.append(f"    external->{ef} = internal->{inf};")
                else:
                    lines.append(f"    external->{ef} = {rule}(internal->{inf});")

            lines.extend(["    return 0;", "}", ""])

        return "\n".join(lines)

    # ── File Output ───────────────────────────────────────────────

    def generate_files(self, output_header: str, output_source: str,
                       header_guard: str = "GENERATED_STRUCTS_H"):
        """Generate and write header and source files to disk."""
        header_code = self.generate_header_code(header_guard=header_guard)
        with open(output_header, 'w', encoding='utf-8') as f:
            f.write(header_code)

        source_code = self.generate_source_code(header_file=output_header)
        with open(output_source, 'w', encoding='utf-8') as f:
            f.write(source_code)

        return header_code, source_code
