"""
Excel file parser for the Struct Converter Toolkit.
Reads Excel files and loads them into the CodeGenerator.
"""
from typing import Dict, List, Any
from .code_generator import CodeGenerator


class ExcelConverter:
    """
    Parses Excel files containing struct definitions and conversion rules,
    then loads them into a CodeGenerator instance.
    Each sheet in the Excel file represents one struct pair (external/internal).
    """

    def __init__(self, generator: CodeGenerator = None):
        self.generator = generator or CodeGenerator()

    def parse_file(self, excel_file: str):
        """Parse an Excel file from a file path."""
        import pandas as pd
        xl_file = pd.ExcelFile(excel_file)
        sheets: Dict[str, List[Dict[str, str]]] = {}
        for sheet_name in xl_file.sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            sheets[sheet_name] = self._dataframe_to_rows(df)
        self.generator.load_from_csv_dict(sheets)

    def parse_uploaded_file(self, uploaded_file):
        """Parse a Streamlit UploadedFile object (Excel format)."""
        import pandas as pd
        import io

        content = uploaded_file.getvalue()
        xl_file = pd.ExcelFile(io.BytesIO(content))
        sheets: Dict[str, List[Dict[str, str]]] = {}
        for sheet_name in xl_file.sheet_names:
            df = pd.read_excel(xl_file, sheet_name=sheet_name)
            sheets[sheet_name] = self._dataframe_to_rows(df)
        self.generator.load_from_csv_dict(sheets)

    @staticmethod
    def _dataframe_to_rows(df) -> List[Dict[str, str]]:
        """Convert a pandas DataFrame to a list of row dicts with string values."""
        import pandas as pd
        rows = []
        for _, row in df.iterrows():
            clean_row = {}
            for col in df.columns:
                val = row.get(col, '')
                if pd.isna(val):
                    clean_row[col] = ''
                else:
                    clean_row[col] = str(val)
            rows.append(clean_row)
        return rows
