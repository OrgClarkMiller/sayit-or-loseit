# Read a list of objects from the screen, return one that hasn't been seen
# too often by the User

import pytesseract
from screen_io.screen_capture import capture_focused_window

def read_screen_text():
    wnd = capture_focused_window()
    if wnd is None: return []
    img = wnd.image
    if img is None: return []

    gray_image = img.convert("L")
    text: str = pytesseract.image_to_string(gray_image)
    text = text.replace("\x0c", "").strip() # Clean out junk from image
    return text.split()