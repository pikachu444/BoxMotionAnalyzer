from PIL import Image, ImageDraw

def create_tilted_box_icon(size=(64, 64), filename="images/box_icon.png"):
    """
    Creates a pixel art icon of a tilted box.
    """
    img = Image.new("RGBA", size, (0, 0, 0, 0))  # Transparent background
    draw = ImageDraw.Draw(img)

    # Define colors
    face_color = (139, 69, 19)  # Brown
    top_color = (160, 82, 45)   # Sienna
    line_color = (0, 0, 0)      # Black

    # Define tilted box coordinates
    # Top face
    top_face = [(20, 10), (44, 10), (54, 20), (30, 20)]
    draw.polygon(top_face, fill=top_color, outline=line_color)

    # Front face
    front_face = [(30, 20), (54, 20), (54, 44), (30, 44)]
    draw.polygon(front_face, fill=face_color, outline=line_color)

    # Side face
    side_face = [(20, 10), (30, 20), (30, 44), (20, 34)]
    draw.polygon(side_face, fill=face_color, outline=line_color)

    img.save(filename, "PNG")

if __name__ == "__main__":
    create_tilted_box_icon()
