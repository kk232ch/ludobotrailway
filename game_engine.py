from PIL import Image, ImageDraw
import io

# --- CONFIGURATION ---
# Adjust these to fit your specific bg_theme.jpg
BOARD_IMAGE_PATH = "templates/bg_theme.jpg" 

# If your image is 1000x1000, a 15x15 grid means each cell is roughly 66px.
# You might need to tweak these 3 numbers until the tokens land exactly in the boxes.
CELL_SIZE = 66      # Size of one square in pixels
START_X = 50        # X pixel where the first left column starts
START_Y = 50        # Y pixel where the top row starts

# Token Colors
COLORS = {
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "yellow": (255, 215, 0),
    "blue": (0, 0, 255)
}

# --- COORDINATE MAPPING (The Hard Part) ---
# This maps "Step 1" of the path to a specific (Grid_X, Grid_Y) location.
# This is a SIMPLIFIED example path for Red. 
# You will eventually need to map all 52 steps for a perfect board.
PATH_MAP = {
    0: (1, 6), 1: (2, 6), 2: (3, 6), 3: (4, 6), 4: (5, 6), # ... straight line
    # ... You would fill this out for the full loop
}

# --- HOME POSITIONS (Where tokens sit before starting) ---
HOME_POSITIONS = {
    "red":   [(2, 2), (2, 3), (3, 2), (3, 3)],
    "green": [(11, 2), (11, 3), (12, 2), (12, 3)],
    # ... add yellow/blue
}

def get_pixel_coords(grid_x, grid_y):
    """Converts a grid number (0-14) to real pixels on your JPG."""
    real_x = START_X + (grid_x * CELL_SIZE)
    real_y = START_Y + (grid_y * CELL_SIZE)
    return real_x, real_y

def draw_board(game_state):
    """
    Generates an image based on the current game state.
    game_state example: {'red': [0, 5, 'home', 'home'], 'green': [22, 'home', 'home', 'home']}
    """
    try:
        # 1. Load the background
        base = Image.open(BOARD_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(base)
        
        # 2. Draw Tokens
        for color, positions in game_state.items():
            for i, pos in enumerate(positions):
                
                # A. Determine Grid Coordinates
                if pos == 'home':
                    # Get the home coordinates for this specific token index
                    gx, gy = HOME_POSITIONS[color][i]
                else:
                    # Get coordinates from the path map (Handle invalid path keys safely)
                    gx, gy = PATH_MAP.get(pos, (7, 7)) # Default to center if unknown

                # B. Convert to Pixels
                px, py = get_pixel_coords(gx, gy)
                
                # C. Draw the Token (Circle)
                radius = int(CELL_SIZE * 0.3) # Token is 30% size of the cell
                
                # Slight offset if multiple tokens are on same spot (prevents total overlap)
                # (Simple logic: just shift slightly based on token index)
                offset = i * 5 
                
                draw.ellipse(
                    [px - radius + offset, py - radius + offset, px + radius + offset, py + radius + offset], 
                    fill=COLORS[color], 
                    outline="black", 
                    width=2
                )

        # 3. Save to memory (RAM) instead of disk (Faster)
        bio = io.BytesIO()
        base.save(bio, 'JPEG')
        bio.seek(0)
        return bio

    except Exception as e:
        print(f"Error generating image: {e}")
        return None
