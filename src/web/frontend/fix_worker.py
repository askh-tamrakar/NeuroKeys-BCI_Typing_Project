import sys

def remove_lines(filepath, start_line, end_line):
    # 1-based indexing for arguments
    start_index = start_line - 1
    end_index = end_line # Slice is exclusive at end, so this cuts up to end_index (which is end_line - 1 in 0-based)
                         # Wait, if I want to delete lines 485 to 775 (inclusive).
                         # I want to keep indices 0 to 483.
                         # And indices 775 to end.
                         # lines[:484] gives indices 0..483.
                         # lines[775:] gives indices 775..end.
                         # The deleted range is indices 484..774.
                         # Length of deleted range = 774 - 484 + 1 = 291 lines.
                         # 775 - 485 + 1 = 291. Correct.
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    current_len = len(lines)
    print(f"Original line count: {current_len}")
    
    if end_line > current_len:
        print("End line out of bounds")
        return

    # Keep lines before start_line and after end_line
    new_lines = lines[:start_index] + lines[end_line:]
    
    print(f"New line count: {len(new_lines)}")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

if __name__ == "__main__":
    remove_lines(r"i:\Neuroscience\Brain-To-Brain-Telepathic-Communication-System\frontend\src\workers\game.worker.js", 485, 775)
