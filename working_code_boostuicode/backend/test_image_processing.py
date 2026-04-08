#!/usr/bin/env python3
"""Test image processing with color output and OCR text layer."""

import io
import os
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

# Test image path
TEST_IMAGE = r"C:\Users\avin4\.gemini\antigravity\brain\b37b3bb4-b7d3-4d29-a298-914b37c937f6\uploaded_image_1766081337082.png"
OUTPUT_PDF = r"C:\Users\avin4\Desktop\boostentryai ui code\automation_ui_code\boosterentryai-ui\test_output.pdf"

def process_image_to_pdf(image_path):
    """Process image with new color-preserving settings."""
    
    print(f"Loading image: {image_path}")
    img = Image.open(image_path)
    
    # Fix rotation
    try:
        img = ImageOps.exif_transpose(img)
    except:
        pass
    
    w, h = img.size
    print(f"Original size: {w}x{h}, mode: {img.mode}")
    
    # 1. Resize to max 1600px
    MAX_DIMENSION = 1600
    if max(w, h) > MAX_DIMENSION:
        scale = MAX_DIMENSION / max(w, h)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        img = img.resize((new_w, new_h), Image.LANCZOS)
        w, h = img.size
        print(f"Resized to: {w}x{h}")
    
    # 2. Keep COLOR
    if img.mode == "RGBA":
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")
    print(f"Mode after convert: {img.mode}")
    
    # 3. Minimal processing
    img = ImageOps.autocontrast(img, cutoff=1)
    img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=80, threshold=2))
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.2)
    
    # 4. Create PDF
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=(w, h))
    
    # Save as JPEG
    TARGET_SIZE_BYTES = 300 * 1024
    quality = 90
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='JPEG', quality=quality, optimize=True)
    
    while img_buffer.tell() > TARGET_SIZE_BYTES and quality > 50:
        quality -= 5
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG', quality=quality, optimize=True)
    
    print(f"JPEG quality: {quality}, size: {img_buffer.tell() / 1024:.1f} KB")
    
    img_buffer.seek(0)
    img_reader = ImageReader(img_buffer)
    c.drawImage(img_reader, 0, 0, width=w, height=h)
    c.save()
    
    pdf_bytes = pdf_buffer.getvalue()
    print(f"PDF size (before OCR): {len(pdf_bytes) / 1024:.1f} KB")
    
    # 5. Add OCR text layer
    try:
        import ocrmypdf
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_in:
            tmp_in.write(pdf_bytes)
            tmp_in_path = tmp_in.name
        
        tmp_out_path = tmp_in_path.replace('.pdf', '_ocr.pdf')
        
        print("Running OCR (this may take 5-15 seconds)...")
        ocrmypdf.ocr(
            tmp_in_path,
            tmp_out_path,
            language='eng',
            deskew=False,
            clean=False,
            rotate_pages=False,
            remove_background=False,
            force_ocr=True,
            optimize=1,
            jobs=4,
            progress_bar=True,
            tesseract_timeout=120,
            tesseract_config=['--psm', '1', '-c', 'preserve_interword_spaces=1'],
        )
        
        with open(tmp_out_path, 'rb') as f:
            pdf_bytes = f.read()
        
        os.unlink(tmp_in_path)
        os.unlink(tmp_out_path)
        print(f"✅ OCR complete! PDF size: {len(pdf_bytes) / 1024:.1f} KB")
        
    except Exception as e:
        print(f"⚠️ OCR failed: {e}")
    
    return pdf_bytes

if __name__ == "__main__":
    pdf_bytes = process_image_to_pdf(TEST_IMAGE)
    
    # Save output
    with open(OUTPUT_PDF, 'wb') as f:
        f.write(pdf_bytes)
    print(f"✅ Saved to: {OUTPUT_PDF}")
    print(f"Final size: {len(pdf_bytes) / 1024:.1f} KB")
