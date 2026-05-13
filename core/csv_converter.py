"""
CSV file parser for the Struct Converter Toolkit.
Reads CSV files and loads them into the CodeGenerator.
"""
import csv
import os
from typing import Dict, List
from io import StringIO
from .code_generator import CodeGenerator


class CsvConverter:
    """
    Parses CSV files containing struct definitions and conversion rules,
    then loads them into a CodeGenerator instance.
    Each CSV file in a directory represents one struct pair (external/internal).
    """

    def __init__(self, generator: CodeGenerator = None):
        self.generator = generator or CodeGenerator()

    @staticmethod
    def _csv_to_dict_list(file_path: str) -> List[Dict[str, str]]:
        """Read a CSV file and return a list of row dictionaries."""
        rows = []
        with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
            content = csvfile.read()
            if not content.strip():
                return []
            string_io = StringIO(content)
            csv_reader = csv.DictReader(string_io)
            for row in csv_reader:
                clean_row = {k: (v if v is not None else '') for k, v in row.items()}
                rows.append(clean_row)
        return rows

    def parse_directory(self, csv_directory: str):
        """Parse all CSV files in a directory."""
        sheets: Dict[str, List[Dict[str, str]]] = {}
        for filename in sorted(os.listdir(csv_directory)):
            if filename.lower().endswith('.csv'):
                file_path = os.path.join(csv_directory, filename)
                sheet_name = os.path.splitext(filename)[0]
                sheets[sheet_name] = self._csv_to_dict_list(file_path)
        self.generator.load_from_csv_dict(sheets)

    def parse_file(self, file_path: str, sheet_name: str = None):
        """Parse a single CSV file."""
        if sheet_name is None:
            sheet_name = os.path.splitext(os.path.basename(file_path))[0]
        rows = self._csv_to_dict_list(file_path)
        self.generator.load_from_csv_dict({sheet_name: rows})

    def parse_uploaded_files(self, uploaded_files: list):
        """
        Parse Streamlit UploadedFile objects.
        Each file is treated as a separate struct pair.
        """
        sheets: Dict[str, List[Dict[str, str]]] = {}
        for uploaded_file in uploaded_files:
            sheet_name = os.path.splitext(uploaded_file.name)[0]
            content = uploaded_file.getvalue().decode('utf-8')
            if not content.strip():
                continue
            string_io = StringIO(content)
            csv_reader = csv.DictReader(string_io)
            rows = []
            for row in csv_reader:
                clean_row = {k: (v if v is not None else '') for k, v in row.items()}
                rows.append(clean_row)
            sheets[sheet_name] = rows
        self.generator.load_from_csv_dict(sheets)
