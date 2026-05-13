# Struct Converter Toolkit - User Guide

## Table of Contents
1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [System Requirements](#system-requirements)
4. [Quick Start Guide](#quick-start-guide)
5. [File Formats](#file-formats)
6. [Advanced Features](#advanced-features)
7. [Troubleshooting](#troubleshooting)

## Overview

The Struct Converter Toolkit is a Python-based utility that generates C code for converting between external and internal structures based on configuration files. The toolkit includes two versions:
- **Enhanced Version**: Full-featured with Excel support (requires pandas and openpyxl)
- **Windows 7 Compatible Version**: Works with basic Python (only built-in libraries)

## System Requirements

### Windows 7 Compatible Version (Recommended):
- Python 2.7+ or Python 3.x
- No additional packages required
- Works on Windows 7, 8, 10, 11, or compatible systems

### Enhanced Version:
- Python 3.x
- pandas (version 1.4.4 or compatible with your Python version)
- openpyxl (for Excel file support)
- Works on modern systems

## Getting Started

### For Windows 7 Users:
1. Ensure Python is installed on your system (Python 3.8.10 is recommended for Windows 7)
2. Copy the entire `struct_converter_toolkit` folder to your desired location
3. Place your CSV configuration files in the `csv_structs` subfolder
4. Double-click `win7_struct_converter.py` to run with default settings, or run from command line

### For Modern Systems:
1. Install required packages: `pip install pandas openpyxl`
2. Run `python enhanced_struct_converter.py` with or without parameters

## Quick Start Guide

### Method 1: Direct Execution (Easiest)
Double-click either Python file to run with default settings:
- `win7_struct_converter.py` → Uses CSV files from `csv_structs/` folder, outputs to `generated_structs.h` and `generated_structs.c`
- `enhanced_struct_converter.py` → Tries to read from `sample.xlsx`, outputs to `enhanced_structs.h` and `enhanced_structs.c`

### Method 2: Command Line with Custom Parameters
```
# Windows 7 compatible version
python win7_struct_converter.py <csv_directory> <output_header> <output_source>

# Example:
python win7_struct_converter.py my_csv_folder my_header.h my_source.c

# Enhanced version
python enhanced_struct_converter.py <input_excel> <output_header> <output_source>

# Example:
python enhanced_struct_converter.py my_structs.xlsx my_header.h my_source.c
```

### Method 3: Using the Demo Batch File
Run `run_demo.bat` for a quick demonstration of the Windows 7 compatible version.

## File Formats

### CSV Format (for Windows 7 Compatible Version)
Create CSV files in the `csv_structs` folder with the following columns:

| Column | Description | Example |
|--------|-------------|---------|
| field_name | Name of the field | temperature |
| field_type | C data type | int32_t |
| struct_type | "external" or "internal" | external |
| external_field | Name of external field (for mapping) | temperature |
| internal_field | Name of internal field (for mapping) | temp_val |
| conversion_rule | Conversion function or "=" for direct | = or temp_convert_func |
| validation_logic | Validation condition | external->valid && recv_status |
| bitfield_width | Width for bitfields | 4 |
| nested_struct_def | Definition for nested structs | struct_def |
| validation_field | Field to validate | is_valid |
| array_size | Array size | 10 |

### Excel Format (for Enhanced Version)
Create sheets in your Excel file with the same column headers as the CSV format above.

## Advanced Features

### Bitfields
To define a bitfield, specify the `bitfield_width` column with a numeric value:
```
field_name: status_flag
field_type: int
bitfield_width: 4
```
This generates: `int status_flag : 4;`

### Nested Structures
Use the `nested_struct_def` column to define nested structures.

### Validation Logic
The `validation_logic` column allows complex validation conditions. For example:
- `external->valid && recv_status` - Valid only if external is valid AND receive status is true
- `recv_status == 1` - Valid only if receive status equals 1

### Receive Status Parameter
When validation logic includes `recv_status`, the generated functions will include this parameter for validation purposes.

## Troubleshooting

### Common Issues

**Issue**: "No such file or directory" error
**Solution**: Ensure your CSV/Excel file exists at the specified path. For Windows 7 version, check that CSV files are in the correct directory.

**Issue**: "Module not found" error (pandas/openpyxl)
**Solution**: Install required packages with `pip install pandas openpyxl` (for enhanced version only)

**Issue**: Python script doesn't run when double-clicked
**Solution**: 
- Check that Python is installed and associated with .py files
- Or run from command line using `python win7_struct_converter.py`

**Issue**: Generated code doesn't compile
**Solution**: Check your configuration files for syntax errors, particularly in data types and field names

### For Windows 7 Users
- Use the Windows 7 compatible version (it doesn't require pandas or openpyxl)
- If you get encoding errors, ensure your CSV files are saved in UTF-8 format
- Make sure your Python version is compatible with Windows 7 (Python 3.8.10 is recommended)

## Examples

### Sample CSV Structure
```csv
field_name,field_type,struct_type,external_field,internal_field,conversion_rule,validation_logic,bitfield_width,nested_struct_def,validation_field,array_size
temperature,int32_t,external,temperature,temp_val,=,external->valid && recv_status,,,,,
humidity,float,external,humidity,humid_val,=,recv_status == 1,,,,,
status_flag,int,external,status,status_flag,,,"status : 4",,,,
temp_val,float,internal,,,,,,,,,
humid_val,float,internal,,,,,,,,,
is_valid,bool,internal,,,,,,,,is_valid,,
```

This configuration generates:
- External struct with temperature (int32_t), humidity (float), status_flag (int:4 bitfield), and valid (bool)
- Internal struct with temp_val (float), humid_val (float), and is_valid (bool)
- Conversion functions with validation based on external validity and receive status
- Bitfield definition for status flag (4 bits)

## Support

If you encounter issues:
1. Check that your configuration files follow the correct format
2. Ensure all required fields are present
3. For the enhanced version, verify that pandas and openpyxl are installed
4. For Windows 7, use the compatible version which requires no additional packages