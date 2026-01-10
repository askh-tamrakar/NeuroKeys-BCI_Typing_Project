from PIL import Image, ImageDraw

# Config
VARIANT_COUNT = 8
SPRITE_W = 20  # Width of one bush sprite
SPRITE_H = 20  # Height of one bush sprite
SHEET_W = SPRITE_W * VARIANT_COUNT
SHEET_H = SPRITE_H

# Colors
TRANSPARENT = (0, 0, 0, 0)
YELLOW = (240, 200, 50, 255) # Yellow-ish Gold

# Create Image
img = Image.new('RGBA', (SHEET_W, SHEET_H), TRANSPARENT)
pixels = img.load()

# Bush definitions (1 = pixel, 0 = empty)
# 10x10 grid logic scaled up or just mapped
# Let's define a simple 10x10 matrix for the "Standard" bush and modify it


STANDARD_BUSH = [
    [0,0,0,0,1,0,0,0,0,0],
    [0,0,0,1,1,0,0,0,0,0],
    [0,0,1,1,1,1,0,1,0,0],
    [0,1,1,1,1,1,1,1,0,0],
    [0,1,1,1,1,1,1,1,0,0],
    [0,0,1,1,1,1,1,0,0,0],
    [0,0,1,1,1,1,1,0,0,0],
    [0,0,0,1,1,1,0,0,0,0],
    [0,0,0,1,1,1,0,0,0,0],
    [0,0,0,1,1,1,0,0,1,0], # Little root
]

# Helper to draw a matrix at offset
def draw_matrix(matrix, offset_x, offset_y, scale=2):
    for r, row in enumerate(matrix):
        for c, val in enumerate(row):
            if val:
                # Draw 2x2 block for 'pixel' look
                for dy in range(scale):
                    for dx in range(scale):
                        px = offset_x + c * scale + dx
                        py = offset_y + r * scale + dy
                        if 0 <= px < SHEET_W and 0 <= py < SHEET_H:
                            pixels[px, py] = YELLOW

# --- Variants ---

# 1. Standard
draw_matrix(STANDARD_BUSH, 0, 0)

# 2. Small (Crop edges)
SMALL_BUSH = [row[1:9] for row in STANDARD_BUSH[2:]] # smaller
draw_matrix(SMALL_BUSH, SPRITE_W + 2, 4)

# 3. Large (Add width/height)
LARGE_BUSH = [
    [0,0,0,1,1,1,0,0],
    [0,0,1,1,1,1,1,0],
    [0,1,1,1,1,1,1,1],
    [1,1,1,1,1,1,1,1],
    [1,1,1,1,1,1,1,1],
    [0,1,1,1,1,1,1,1],
    [0,0,1,1,1,1,1,0],
    [0,0,0,1,1,1,0,0],
    [0,0,0,1,1,1,0,0],
    [0,0,0,1,1,1,0,0],
]
draw_matrix(LARGE_BUSH, SPRITE_W * 2 + 1, -2, scale=2)

# 4. Two-Branch (Split top)
TWO_BRANCH = [
    [1,0,0,0,0,0,1,0,0,0],
    [1,1,0,0,0,0,1,1,0,0],
    [0,1,1,0,0,1,1,0,0,0],
    [0,0,1,1,1,1,0,0,0,0],
    [0,0,1,1,1,1,0,0,0,0],
    [0,0,1,1,1,1,0,0,0,0],
    [0,0,1,1,1,1,0,0,0,0],
    [0,0,0,1,1,0,0,0,0,0],
    [0,0,0,1,1,0,0,0,0,0],
    [0,0,0,1,1,0,0,0,0,0],
]
draw_matrix(TWO_BRANCH, SPRITE_W * 3 + 2, 0)

# 5. No Right (Left half of standard)
NO_RIGHT = [
    [0,0,0,0,1,0],
    [0,1,0,1,1,0],
    [1,1,0,1,1,0],
    [1,1,0,1,1,0],
    [1,1,0,1,1,0],
    [0,1,1,1,1,0],
    [0,0,1,1,0,0],
    [0,0,1,1,0,0],
    [0,0,1,1,0,0],
    [0,0,1,1,0,0],
]
draw_matrix(NO_RIGHT, SPRITE_W * 4 + 4, 0)

# 6. No Right Flipped (Mirror of 5)
# Manually flip logic or just draw
draw_matrix([row[::-1] for row in NO_RIGHT], SPRITE_W * 5 + 4, 0)

# 7. No Left (Right half of standard)
NO_LEFT = [
    [0,1,0,0,0,0],
    [0,1,1,0,1,0],
    [0,1,1,0,1,1],
    [0,1,1,0,1,1],
    [0,1,1,0,1,1],
    [0,1,1,1,1,0],
    [0,0,1,1,0,0],
    [0,0,1,1,0,0],
    [0,0,1,1,0,0],
    [0,0,1,1,0,0],
]
draw_matrix(NO_LEFT, SPRITE_W * 6 + 4, 0)

# 8. No Left Flipped
draw_matrix([row[::-1] for row in NO_LEFT], SPRITE_W * 7 + 4, 0)

# Save
OUT_PATH = 'i:/Neuroscience/Brain-To-Brain-Telepathic-Communication-System/frontend/public/Resources/Dino/bushes.png'
img.save(OUT_PATH)
print(f"Generated sprite sheet at {OUT_PATH}")
