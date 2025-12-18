import sys
print(f"Python executable: {sys.executable}")
try:
    import openpyxl
    print(f"openpyxl file: {openpyxl.__file__}")
    print(f"openpyxl version: {openpyxl.__version__}")
    from openpyxl.styles import PatternFill
    print("openpyxl.styles imported successfully")
except ImportError as e:
    print(f"Error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
