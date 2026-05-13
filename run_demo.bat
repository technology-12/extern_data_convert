@echo off
echo **********************************************
echo Welcome to the Struct Converter Toolkit!
echo **********************************************
echo.
echo This toolkit provides two Python scripts for generating C structure conversion code:
echo.
echo 1. enhanced_struct_converter.py - Full-featured version (requires pandas and openpyxl)
echo 2. win7_struct_converter.py - Windows 7 compatible version (uses only built-in libraries)
echo.
echo **********************************************
echo Running Windows 7 compatible version directly...
echo **********************************************
echo.
python win7_struct_converter.py
echo.
echo **********************************************
echo Check the generated files: generated_structs.h and generated_structs.c
echo **********************************************
pause