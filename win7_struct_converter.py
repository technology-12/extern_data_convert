# Windows 7 compatible version of the struct converter
# Uses only built-in Python libraries to ensure compatibility
import re
import csv
import os
from typing import Dict, List, Any, Tuple
from io import StringIO

class Win7StructConverterGenerator:
    """
    A tool to generate C code for converting between external and internal structures
    based on CSV-specified relationships (compatible with Windows 7).
    This version uses only built-in Python libraries.
    """
    
    def __init__(self):
        self.struct_pairs = {}  # Stores pairs of external/internal structs
        self.all_structs = {}   # Stores all struct definitions
        self.global_types = self._get_default_types()
        
    def _get_default_types(self):
        """Define default C types"""
        return {
            'char', 'short', 'int', 'long', 'float', 'double',
            'signed char', 'unsigned char', 'unsigned short', 
            'unsigned int', 'unsigned long', 'long long', 
            'unsigned long long', 'bool', 'int8_t', 'int16_t', 
            'int32_t', 'int64_t', 'uint8_t', 'uint16_t', 
            'uint32_t', 'uint64_t', 'size_t', 'ptrdiff_t'
        }
    
    def _csv_to_dict_list(self, file_path: str) -> List[Dict[str, str]]:
        """Convert CSV file to list of dictionaries (similar to pandas DataFrame)"""
        rows = []
        with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
            # Read the entire file to check for empty content
            content = csvfile.read()
            if not content.strip():
                return []
            
            # Use StringIO to process the content again
            string_io = StringIO(content)
            csv_reader = csv.DictReader(string_io)
            for row in csv_reader:
                # Replace None values with empty strings
                clean_row = {}
                for key, value in row.items():
                    clean_row[key] = value if value is not None else ''
                rows.append(clean_row)
        return rows
    
    def parse_csv(self, csv_directory: str):
        """
        Parse CSV files in a directory where each CSV represents a struct pair (external/internal)
        """
        for filename in os.listdir(csv_directory):
            if filename.lower().endswith('.csv'):
                file_path = os.path.join(csv_directory, filename)
                sheet_name = os.path.splitext(filename)[0]
                df = self._csv_to_dict_list(file_path)
                self._parse_struct_pair_sheet(df, sheet_name)
    
    def _parse_struct_pair_sheet(self, rows: List[Dict], sheet_name: str):
        """
        Parse a CSV sheet containing a pair of external/internal structs and their mappings
        """
        if not rows:
            return
            
        # Determine if this sheet has mapping information or struct definitions
        has_field_name = any('field_name' in row and row['field_name'] for row in rows)
        has_field_type = any('field_type' in row and row['field_type'] for row in rows)
        
        if has_field_name and has_field_type:
            # This sheet contains struct definitions
            external_struct_name = f"{sheet_name}_ext"
            internal_struct_name = f"{sheet_name}_int"
            
            # Separate external and internal struct definitions
            external_fields = []
            internal_fields = []
            
            for row in rows:
                field_name = row.get('field_name', '')
                field_type = row.get('field_type', '')
                struct_type = row.get('struct_type', 'external').lower()  # 'external' or 'internal'
                
                if field_name and field_type:
                    field_info = {
                        'name': field_name,
                        'type': field_type,
                        'size': row.get('field_size', ''),
                        'is_array': bool(row.get('field_size', '').strip()),
                        'is_bitfield': bool(row.get('bitfield_width', '').strip()),
                        'bitfield_width': row.get('bitfield_width', None),
                        'nested_struct_def': row.get('nested_struct_def', ''),
                        'validation_field': row.get('validation_field', ''),
                        'array_size': row.get('array_size', '')  # For arrays
                    }
                    
                    if struct_type == 'internal':
                        internal_fields.append(field_info)
                    else:
                        external_fields.append(field_info)
            
            # Store the struct definitions
            if external_fields:
                self.all_structs[external_struct_name] = external_fields
            if internal_fields:
                self.all_structs[internal_struct_name] = internal_fields
            
            # Process mappings if they exist
            has_mapping = any('external_field' in row and row.get('external_field', '') for row in rows)
            has_internal_field = any('internal_field' in row and row.get('internal_field', '') for row in rows)
            
            if has_mapping and has_internal_field:
                # Create mapping entry
                if sheet_name not in self.struct_pairs:
                    self.struct_pairs[sheet_name] = {
                        'external_name': external_struct_name,
                        'internal_name': internal_struct_name,
                        'mappings': []
                    }
                    
                # Process mapping rows  
                for row in rows:
                    external_field = row.get('external_field', '')
                    internal_field = row.get('internal_field', '')
                    if external_field.strip() and internal_field.strip():
                        mapping = {
                            'external_field': external_field,
                            'internal_field': internal_field,
                            'conversion_rule': row.get('conversion_rule', '='), 
                            'validation_logic': row.get('validation_logic', ''),
                            'bitfield_info': row.get('bitfield_info', ''),
                            'nested_struct': row.get('nested_struct', '')
                        }
                        self.struct_pairs[sheet_name]['mappings'].append(mapping)
        else:
            # This sheet contains only mappings (legacy format)
            external_struct_name = sheet_name + "_ext"  # Try to infer from sheet name
            internal_struct_name = sheet_name + "_int"
            
            # Check if external_struct column exists
            if rows and 'external_struct' in rows[0]:
                external_struct_name = rows[0].get('external_struct', external_struct_name)
                internal_struct_name = rows[0].get('internal_struct', internal_struct_name)
            
            # Store the mapping
            if sheet_name not in self.struct_pairs:
                self.struct_pairs[sheet_name] = {
                    'external_name': external_struct_name,
                    'internal_name': internal_struct_name,
                    'mappings': []
                }
                
            for row in rows:
                external_field = row.get('external_field', '')
                internal_field = row.get('internal_field', '')
                if external_field.strip() and internal_field.strip():
                    mapping = {
                        'external_field': external_field,
                        'internal_field': internal_field,
                        'conversion_rule': row.get('conversion_rule', '='), 
                        'validation_logic': row.get('validation_logic', ''),
                        'bitfield_info': row.get('bitfield_info', ''),
                        'nested_struct': row.get('nested_struct', '')
                    }
                    self.struct_pairs[sheet_name]['mappings'].append(mapping)
    
    def generate_header_code(self) -> str:
        """
        Generate header file with struct definitions
        """
        header_code = [
            "/* Generated by Windows 7 Compatible Struct Converter Tool */",
            "#ifndef WIN7_STRUCT_CONVERTER_H",
            "#define WIN7_STRUCT_CONVERTER_H",
            "",
            "#include <stdint.h>",
            "#include <stdbool.h>",
            ""
        ]
        
        # Add all struct definitions
        for struct_name, fields in self.all_structs.items():
            header_code.append(f"typedef struct {{")
            for field in fields:
                if field['is_array'] and field['size']:
                    header_code.append(f"    {field['type']} {field['name']}[{field['size']}];")
                elif field['is_bitfield'] and field['bitfield_width']:
                    header_code.append(f"    {field['type']} {field['name']} : {field['bitfield_width']};")
                elif field['nested_struct_def']:
                    # For nested structs, add the struct reference
                    header_code.append(f"    {field['nested_struct_def']}_t {field['name']};")
                else:
                    header_code.append(f"    {field['type']} {field['name']};")
            header_code.append(f"}} {struct_name}_t;")
            header_code.append("")
        
        # Add function declarations for each struct pair
        for pair_name, pair_info in self.struct_pairs.items():
            external_name = pair_info['external_name']
            internal_name = pair_info['internal_name']
            mappings = pair_info['mappings']
            
            # Check if any mapping has validation logic that uses recv_status
            has_recv_status_logic = any('recv_status' in mapping.get('validation_logic', '') for mapping in mappings)
            
            # Add validation fields if needed
            external_has_validation = self._has_validation_field(external_name)
            internal_has_validation = self._has_validation_field(internal_name)
            
            # Add conversion function declarations
            header_code.append(f"// Conversion functions for {pair_name}")
            if external_has_validation or internal_has_validation or has_recv_status_logic:
                header_code.append(f"int convert_{external_name}_to_{internal_name}({external_name}_t *external, {internal_name}_t *internal, int recv_status);")
                header_code.append(f"int convert_{internal_name}_to_{external_name}({internal_name}_t *internal, {external_name}_t *external, int recv_status);")
            else:
                header_code.append(f"int convert_{external_name}_to_{internal_name}({external_name}_t *external, {internal_name}_t *internal);")
                header_code.append(f"int convert_{internal_name}_to_{external_name}({internal_name}_t *internal, {external_name}_t *external);")
            header_code.append("")
        
        header_code.extend([
            "#endif /* WIN7_STRUCT_CONVERTER_H */",
            ""
        ])
        
        return "\n".join(header_code)
    
    def _has_validation_field(self, struct_name: str) -> bool:
        """Check if a struct has validation fields"""
        if struct_name in self.all_structs:
            for field in self.all_structs[struct_name]:
                if field.get('validation_field'):
                    return True
        return False
    
    def _find_validity_field(self, struct_name: str) -> str:
        """Find a field in the struct that indicates validity"""
        if struct_name in self.all_structs:
            for field in self.all_structs[struct_name]:
                if 'valid' in field['name'].lower() or 'status' in field['name'].lower():
                    return field['name']
        return None
    
    def generate_source_code(self) -> str:
        """
        Generate source file with conversion functions
        """
        source_code = [
            "/* Generated by Windows 7 Compatible Struct Converter Tool */",
            '#include "win7_struct_converter.h"',
            "",
            "// Conversion functions"
        ]
        
        for pair_name, pair_info in self.struct_pairs.items():
            external_name = pair_info['external_name']
            internal_name = pair_info['internal_name']
            mappings = pair_info['mappings']
            
            # Generate external to internal conversion function
            external_has_validation = self._has_validation_field(external_name)
            internal_has_validation = self._has_validation_field(internal_name)
            
            # Check if any mapping has validation logic that uses recv_status
            has_recv_status_logic = any('recv_status' in mapping.get('validation_logic', '') for mapping in mappings)
            
            if external_has_validation or internal_has_validation or has_recv_status_logic:
                func_signature = f"int convert_{external_name}_to_{internal_name}({external_name}_t *external, {internal_name}_t *internal, int recv_status)"
            else:
                func_signature = f"int convert_{external_name}_to_{internal_name}({external_name}_t *external, {internal_name}_t *internal)"
            
            source_code.extend([
                f"",
                f"{func_signature}",
                f"{{"
            ])
            
            # Add validation
            source_code.append(f"    if (!external || !internal) return -1;")
            source_code.append(f"")
            
            # Add conversion logic for each field
            for mapping in mappings:
                external_field = mapping['external_field']
                internal_field = mapping['internal_field']
                conv_rule = mapping['conversion_rule']
                validation_logic = mapping['validation_logic']
                
                if validation_logic:
                    # Apply validation logic
                    source_code.append(f"    // Apply validation logic: {validation_logic}")
                    source_code.append(f"    if ({validation_logic}) {{")
                    if conv_rule == '=':
                        source_code.append(f"        internal->{internal_field} = external->{external_field};")
                    else:
                        source_code.append(f"        internal->{internal_field} = {conv_rule}(external->{external_field});")
                    source_code.append(f"    }} else {{")
                    # Set default value if validation fails
                    source_code.append(f"        internal->{internal_field} = 0;  // Default value on validation failure")
                    source_code.append(f"    }}")
                elif conv_rule == '=':
                    source_code.append(f"    internal->{internal_field} = external->{external_field};")
                else:
                    source_code.append(f"    internal->{internal_field} = {conv_rule}(external->{external_field});")
            
            # Handle validation field updates if needed
            if internal_has_validation:
                for field in self.all_structs[internal_name]:
                    if field.get('validation_field'):
                        # Determine validation based on external status and other factors
                        # Look for validity field in external struct
                        external_validity_field = self._find_validity_field(external_name)
                        if external_validity_field:
                            source_code.append(f"    internal->{field['validation_field']} = external->{external_validity_field} && recv_status;  // Combine external validity and receive status")
                        else:
                            source_code.append(f"    internal->{field['validation_field']} = recv_status;  // Use receive status as validity")
            
            source_code.extend([
                f"    return 0;",
                f"}}",
                f""
            ])
            
            # Generate internal to external conversion function
            if external_has_validation or internal_has_validation or has_recv_status_logic:
                func_signature = f"int convert_{internal_name}_to_{external_name}({internal_name}_t *internal, {external_name}_t *external, int recv_status)"
            else:
                func_signature = f"int convert_{internal_name}_to_{external_name}({internal_name}_t *internal, {external_name}_t *external)"
            
            source_code.extend([
                f"{func_signature}",
                f"{{"
            ])
            
            # Add validation
            source_code.append(f"    if (!internal || !external) return -1;")
            source_code.append(f"")
            
            # Add reverse conversion logic
            for mapping in mappings:
                external_field = mapping['external_field']
                internal_field = mapping['internal_field']
                conv_rule = mapping['conversion_rule']
                
                if conv_rule == '=':
                    source_code.append(f"    external->{external_field} = internal->{internal_field};")
                else:
                    # For reverse, we may need to invert the conversion rule
                    source_code.append(f"    external->{external_field} = {conv_rule}(internal->{internal_field});")
            
            source_code.extend([
                f"    return 0;",
                f"}}",
                f""
            ])
        
        return "\n".join(source_code)
    
    def generate_code(self, csv_directory: str, output_header: str, output_source: str):
        """
        Main function to generate header and source files from CSV directory
        """
        self.parse_csv(csv_directory)
        
        header_code = self.generate_header_code()
        with open(output_header, 'w', encoding='utf-8') as f:
            f.write(header_code)
        
        source_code = self.generate_source_code()
        with open(output_source, 'w', encoding='utf-8') as f:
            f.write(source_code)
        
        print(f"Generated {output_header} and {output_source}")


def main():
    """
    Example usage
    """
    import sys

    if len(sys.argv) == 4:
        csv_directory = sys.argv[1]
        output_header = sys.argv[2]
        output_source = sys.argv[3]
    elif len(sys.argv) == 1:
        # Default values for direct execution
        print("Running with default values...")
        print("Usage: python win7_struct_converter.py <csv_directory> <output_header> <output_source>")
        print("Using defaults:")
        print("  CSV Directory: csv_structs")
        print("  Output Header: generated_structs.h")
        print("  Output Source: generated_structs.c")
        print("Place CSV files with struct definitions in the 'csv_structs' directory.")
        print("Each CSV file represents one struct pair (external/internal).")
        print("")

        csv_directory = "csv_structs"
        output_header = "generated_structs.h"
        output_source = "generated_structs.c"
    else:
        print("Usage: python win7_struct_converter.py <csv_directory> <output_header> <output_source>")
        print("Example: python win7_struct_converter.py csv_structs win7_structs.h win7_structs.c")
        print("")
        print("For direct execution without arguments, the script will use default values.")
        print("Place CSV files with struct definitions in the 'csv_structs' directory.")
        print("Each CSV file represents one struct pair (external/internal).")
        return

    converter = Win7StructConverterGenerator()
    converter.generate_code(csv_directory, output_header, output_source)


if __name__ == "__main__":
    main()