"""
Utility to generate authentic-looking scanned Land Record (7/12 Extract) images
for Hackathon demonstration, testing, and offline OCR.
"""

import os
from PIL import Image, ImageDraw, ImageFont


def create_land_document_image(output_path, survey_no, owner_name, area_str, village="Pune", taluka="Haveli", district="Pune", date_str="12/04/2023"):
    """
    Renders a realistic scanned document style image of a Maharashtra 7/12 Land Record.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Document dimensions (standard A4-ish ratio)
    width, height = 900, 1200
    # Slightly off-white / parchment background to simulate paper
    image = Image.new("RGB", (width, height), color=(250, 249, 245))
    draw = ImageDraw.Draw(image)

    # Load default or fallback font
    try:
        font_title = ImageFont.truetype("arial.ttf", 26)
        font_header = ImageFont.truetype("arial.ttf", 20)
        font_bold = ImageFont.truetype("arialbd.ttf", 18)
        font_body = ImageFont.truetype("arial.ttf", 17)
        font_stamp = ImageFont.truetype("arialbd.ttf", 22)
    except Exception:
        font_title = ImageFont.load_default()
        font_header = ImageFont.load_default()
        font_bold = ImageFont.load_default()
        font_body = ImageFont.load_default()
        font_stamp = ImageFont.load_default()

    # Outer border
    draw.rectangle([(40, 40), (width - 40, height - 40)], outline=(60, 60, 60), width=3)
    draw.rectangle([(45, 45), (width - 45, height - 45)], outline=(120, 120, 120), width=1)

    # Header
    draw.text((width // 2, 70), "GOVERNMENT OF MAHARASHTRA", fill=(20, 20, 20), font=font_title, anchor="mm")
    draw.text((width // 2, 105), "REVENUE AND FOREST DEPARTMENT", fill=(50, 50, 50), font=font_header, anchor="mm")
    draw.text((width // 2, 140), "VILLAGE FORM VII-XII (RECORD OF RIGHTS / 7/12 EXTRACT)", fill=(10, 10, 10), font=font_bold, anchor="mm")

    # Dividing line
    draw.line([(60, 165), (width - 60, 165)], fill=(80, 80, 80), width=2)

    # Administrative Metadata Box
    y_start = 185
    draw.rectangle([(60, y_start), (width - 60, y_start + 85)], outline=(100, 100, 100), width=1)
    
    draw.text((80, y_start + 15), f"District: {district}", fill=(20, 20, 20), font=font_body)
    draw.text((360, y_start + 15), f"Taluka: {taluka}", fill=(20, 20, 20), font=font_body)
    draw.text((640, y_start + 15), f"Village: {village}", fill=(20, 20, 20), font=font_body)
    
    draw.text((80, y_start + 50), f"Record Date: {date_str}", fill=(20, 20, 20), font=font_body)
    draw.text((360, y_start + 50), "Jurisdiction: Revenue Circle-3", fill=(20, 20, 20), font=font_body)
    draw.text((640, y_start + 50), "Tenure: Occupant Class-1", fill=(20, 20, 20), font=font_body)

    # Main Land Record Grid
    table_top = 295
    table_bottom = 680
    draw.rectangle([(60, table_top), (width - 60, table_bottom)], outline=(40, 40, 40), width=2)

    # Column headers
    draw.rectangle([(60, table_top), (width - 60, table_top + 45)], fill=(235, 233, 225), outline=(40, 40, 40), width=2)
    draw.line([(320, table_top), (320, table_bottom)], fill=(80, 80, 80), width=1)
    draw.line([(580, table_top), (580, table_bottom)], fill=(80, 80, 80), width=1)

    draw.text((190, table_top + 22), "PARCEL ATTRIBUTE", fill=(10, 10, 10), font=font_bold, anchor="mm")
    draw.text((450, table_top + 22), "RECORDED SPECIFICATION", fill=(10, 10, 10), font=font_bold, anchor="mm")
    draw.text((730, table_top + 22), "STATUS / NOTES", fill=(10, 10, 10), font=font_bold, anchor="mm")

    # Table rows
    rows = [
        ("Survey / Gat Number:", f"{survey_no}", "Primary Cadastral ID"),
        ("Khata / Account No:", "408 / B", "Revenue Ledger Page"),
        ("Owner / Occupant Name:", f"{owner_name}", "Verified Title Holder"),
        ("Total Land Area:", f"{area_str}", "Gross Cultivable Parcel"),
        ("Cultivable Area:", f"{area_str}", "Class A Agricultural"),
        ("Land Revenue Assessment:", "Rs. 18.50 per annum", "Settlement Current"),
        ("Irrigation Details:", "Well / Seasonal Canal", "Source: Neera Canal"),
        ("Encumbrances / Mortgages:", "NIL", "No active charge recorded"),
    ]

    curr_y = table_top + 45
    row_height = (table_bottom - (table_top + 45)) // len(rows)

    for i, (col1, col2, col3) in enumerate(rows):
        y_center = curr_y + (row_height // 2)
        # Alternate subtle shading
        if i % 2 == 1:
            draw.rectangle([(61, curr_y), (width - 61, curr_y + row_height)], fill=(245, 244, 238))
        
        # Horizontal row divider
        draw.line([(60, curr_y), (width - 60, curr_y)], fill=(150, 150, 150), width=1)
        
        draw.text((80, y_center), col1, fill=(50, 50, 50), font=font_bold, anchor="lm")
        draw.text((340, y_center), col2, fill=(10, 10, 10), font=font_bold, anchor="lm")
        draw.text((600, y_center), col3, fill=(70, 70, 70), font=font_body, anchor="lm")
        
        curr_y += row_height

    # Re-draw vertical column lines over shaded rows
    draw.line([(320, table_top), (320, table_bottom)], fill=(80, 80, 80), width=1)
    draw.line([(580, table_top), (580, table_bottom)], fill=(80, 80, 80), width=1)

    # Watermark / Official Seal simulation
    draw.ellipse([(width - 260, 730), (width - 100, 890)], outline=(180, 40, 40), width=3)
    draw.ellipse([(width - 250, 740), (width - 110, 880)], outline=(180, 40, 40), width=1)
    draw.text((width - 180, 790), "TAHSILDAR", fill=(180, 40, 40), font=font_stamp, anchor="mm")
    draw.text((width - 180, 830), "HAVELI, PUNE", fill=(180, 40, 40), font=font_body, anchor="mm")

    # Bottom Official Declaration
    draw.text((70, 740), "Digitally Certified Record of Rights extracted from State Land Portal.", fill=(80, 80, 80), font=font_body)
    draw.text((70, 770), "Barcode / Hash: e712-4091-8892-A9F1", fill=(80, 80, 80), font=font_body)
    draw.text((70, 800), "Officer Signature: Authorized Revenue Officer (Talathi / Tahsildar)", fill=(30, 30, 30), font=font_bold)

    # Noise & texture simulation (subtle scanner lines)
    for y_line in range(50, height - 50, 120):
        draw.line([(40, y_line), (width - 40, y_line)], fill=(235, 233, 228), width=1)

    image.save(output_path, "PNG", quality=95)
    return output_path
