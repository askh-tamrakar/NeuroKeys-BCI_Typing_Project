# attendance_gui.py
"""
Simple Tkinter GUI to mark attendance into an Excel file.
- Enter file path (or use Browse)
- Enter names separated by comma (e.g. Alice, Bob, Charlie)
- Date defaults to today (YYYY-MM-DD) but is editable
- Click "Mark Attendance" to save

Dependencies:
    pip install pandas openpyxl
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import date
import pandas as pd


DATE_FORMAT = "%Y-%m-%d"


def normalize_name(n: str) -> str:
    return n.strip()


def load_or_create_df(path: Path, initial_members: list[str] | None = None) -> pd.DataFrame:
    """Load an attendance DataFrame or create a new one with initial_members."""
    if path.exists():
        df = pd.read_excel(path, index_col=0, engine="openpyxl")
        df.index = df.index.astype(str)
        return df
    else:
        # create empty df with provided members
        members = initial_members or []
        df = pd.DataFrame(index=members)
        df.index.name = "Member"
        return df


def save_df(path: Path, df: pd.DataFrame):
    df.to_excel(path, engine="openpyxl")


class AttendanceApp(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.parent.title("Attendance Marker")
        self.pack(fill="both", expand=True, padx=12, pady=12)

        # Variables
        self.file_var = tk.StringVar(value="attendance.xlsx")
        self.date_var = tk.StringVar(value=date.today().strftime(DATE_FORMAT))
        self.names_var = tk.StringVar(value="")  # comma-separated names

        # UI layout
        self._make_widgets()

    def _make_widgets(self):
        row = 0
        ttk.Label(self, text="Excel file:").grid(column=0, row=row, sticky="w")
        file_entry = ttk.Entry(self, textvariable=self.file_var, width=48)
        file_entry.grid(column=1, row=row, sticky="ew", padx=(6, 6))
        ttk.Button(self, text="Browse", command=self.browse_file).grid(column=2, row=row)
        row += 1

        ttk.Label(self, text="Date (YYYY-MM-DD):").grid(column=0, row=row, sticky="w", pady=(8, 0))
        ttk.Entry(self, textvariable=self.date_var, width=20).grid(column=1, row=row, sticky="w", pady=(8, 0))
        row += 1

        ttk.Label(self, text="Present (comma-separated):").grid(column=0, row=row, sticky="nw", pady=(8, 0))
        ttk.Entry(self, textvariable=self.names_var, width=48).grid(column=1, row=row, sticky="ew", padx=(6, 6), pady=(8, 0))
        ttk.Button(self, text="Mark Attendance", command=self.on_mark).grid(column=2, row=row, pady=(8, 0))
        row += 1

        # Feedback / preview
        ttk.Label(self, text="Status / Preview:").grid(column=0, row=row, sticky="nw", pady=(12, 0))
        self.preview = tk.Text(self, height=12, width=70, wrap="none")
        self.preview.grid(column=0, row=row+1, columnspan=3, sticky="nsew", pady=(6, 0))

        # Make grid expand
        self.columnconfigure(1, weight=1)
        self.rowconfigure(row+1, weight=1)

    def browse_file(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            title="Select attendance Excel file",
        )
        if path:
            self.file_var.set(path)

    def on_mark(self):
        path = Path(self.file_var.get()).expanduser()
        date_str = self.date_var.get().strip()
        try:
            # simple validation for date format
            _ = pd.to_datetime(date_str, format=DATE_FORMAT)
        except Exception as e:
            messagebox.showerror("Invalid date", f"Please use YYYY-MM-DD format.\n{e}")
            return

        names_raw = self.names_var.get().strip()
        if names_raw == "":
            messagebox.showwarning("No names", "Please enter at least one name (comma-separated).")
            return

        # parse names
        names = [normalize_name(n) for n in names_raw.split(",") if normalize_name(n)]
        if not names:
            messagebox.showwarning("No valid names", "No valid member names found after parsing.")
            return

        # Load or create df
        df = load_or_create_df(path, initial_members=names if not path.exists() else None)

        # Add any new members to df
        for m in names:
            if m not in df.index:
                # add new member with blanks for existing columns
                df.loc[m] = [""] * len(df.columns)

        # Ensure all existing members are strings
        df.index = df.index.astype(str)
        # Add date column if missing
        if date_str not in df.columns:
            df[date_str] = ""

        # Mark attendance: 'P' if in names else 'A'
        for member in df.index:
            df.at[member, date_str] = "P" if member in names else "A"

        # Save
        try:
            save_df(path, df)
        except Exception as e:
            messagebox.showerror("Save failed", f"Failed to save Excel file:\n{e}")
            return

        # Update preview and notify
        self.update_preview(df, date_str)
        messagebox.showinfo("Success", f"Marked attendance for {date_str} and saved to:\n{path}")

    def update_preview(self, df: pd.DataFrame, date_str: str):
        # Show the attendance column for the chosen date plus a small summary
        col = df[date_str].astype(str)
        present = col[col == "P"].index.tolist()
        absent = col[col == "A"].index.tolist()
        total = len(col)
        pcount = len(present)
        acount = len(absent)

        text = []
        text.append(f"Date: {date_str}")
        text.append(f"Total members: {total}")
        text.append(f"Present ({pcount}): {', '.join(present)}")
        text.append(f"Absent ({acount}): {', '.join(absent)}")
        text.append("\nFull column preview:\n")
        text.append(col.to_string())

        self.preview.delete("1.0", tk.END)
        self.preview.insert(tk.END, "\n".join(text))


def main():
    root = tk.Tk()
    root.geometry("780x420")
    app = AttendanceApp(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"X Error: {error}")
