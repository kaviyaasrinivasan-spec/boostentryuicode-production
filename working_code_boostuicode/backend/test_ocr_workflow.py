#!/usr/bin/env python3
"""
Test script to verify OCR text layer workflow works correctly.
Run this to test if the image -> PDF -> OCR text layer pipeline works.
"""
import os
import io
import subprocess
import tempfile

# Test with PIL
try:
    from PIL import Image, ImageOps, ImageEnhance, ImageFilter
    print("✅ PIL/Pillow imported successfully")
except ImportError as e:
    print(f"❌ PIL import failed: {e}")
    exit(1)

# Test reportlab
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    print("✅ reportlab imported successfully")
except ImportError as e:
    print(f"❌ reportlab import failed: {e}")
    exit(1)

# Create a simple test image
print("\n📝 Creating test image...")
test_img = Image.new("RGB", (800, 600), color=(255, 255, 255))
# Add some text-like patterns
from PIL import ImageDraw
draw = ImageDraw.Draw(test_img)
draw.text((50, 50), "Invoice No: 123456", fill=(0, 0, 0))
draw.text((50, 100), "Date: 19/12/2025", fill=(0, 0, 0))
draw.text((50, 150), "Consignee: Test Company Ltd", fill=(0, 0, 0))
draw.text((50, 200), "Amount: Rs. 50,000", fill=(0, 0, 0))
print("✅ Test image created (800x600)")

# Convert to grayscale
print("\n📝 Converting to grayscale...")
img = test_img.convert("L")
img = ImageOps.autocontrast(img, cutoff=2)
img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=150, threshold=2))
enhancer = ImageEnhance.Contrast(img)
img = enhancer.enhance(1.8)
img = img.convert("RGB")
print("✅ Grayscale processing done")

# Create PDF with reportlab
print("\n📝 Creating PDF with reportlab...")
pdf_buffer = io.BytesIO()
w, h = img.size
c = canvas.Canvas(pdf_buffer, pagesize=(w, h))

img_buffer = io.BytesIO()
img.save(img_buffer, format='JPEG', quality=85, optimize=True)
img_buffer.seek(0)

c.drawImage(ImageReader(img_buffer), 0, 0, width=w, height=h)
c.save()
pdf_bytes = pdf_buffer.getvalue()
print(f"✅ PDF created ({len(pdf_bytes)} bytes)")

# Test OCR text layer with ocrmypdf
print("\n📝 Adding OCR text layer with ocrmypdf...")

# Save temp PDF
with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_in:
    tmp_in.write(pdf_bytes)
    tmp_in_path = tmp_in.name

tmp_out_path = tmp_in_path.replace('.pdf', '_ocr.pdf')

# Run ocrmypdf
try:
    result = subprocess.run([
        'ocrmypdf',
        '--language', 'eng',
        '--deskew',
        '--skip-text',
        '--optimize', '0',
        '--jobs', '1',
        '--tesseract-timeout', '60',
        '--tesseract-config', '--psm 6',
        tmp_in_path,
        tmp_out_path
    ], capture_output=True, text=True, timeout=120)
    
    if result.returncode == 0 and os.path.exists(tmp_out_path):
        with open(tmp_out_path, 'rb') as f:
            ocr_pdf_bytes = f.read()
        print(f"✅ OCR text layer added! New size: {len(ocr_pdf_bytes)} bytes")
        
        # Save final PDF for inspection
        with open("test_output_with_ocr.pdf", "wb") as f:
            f.write(ocr_pdf_bytes)
        print(f"✅ Saved test_output_with_ocr.pdf for inspection")
        
    else:
        print(f"❌ OCR failed (exit code {result.returncode})")
        print(f"   stderr: {result.stderr}")
        
except FileNotFoundError:
    print("❌ ocrmypdf not found! Install it with: pip install ocrmypdf")
except subprocess.TimeoutExpired:
    print("❌ OCR timed out after 120 seconds")
except Exception as e:
    print(f"❌ OCR error: {e}")

# Cleanup
try:
    os.unlink(tmp_in_path)
except:
    pass
try:
    os.unlink(tmp_out_path)
except:
    pass

# Test PyMuPDF text extraction (what extractor uses)
print("\n📝 Testing PyMuPDF text extraction from OCR'd PDF...")
try:
    import fitz  # PyMuPDF
    
    if os.path.exists("test_output_with_ocr.pdf"):
        doc = fitz.open("test_output_with_ocr.pdf")
        text = ""
        for page in doc:
            text += page.get_text("text")
        doc.close()
        
        if len(text.strip()) > 10:
            print(f"✅ Extracted {len(text)} chars from PDF text layer:")
            print(f"   First 200 chars: {text[:200]}")
        else:
            print("❌ No text layer found or text too short")
    else:
        print("❌ test_output_with_ocr.pdf not found")
        
except ImportError:
    print("⚠️ PyMuPDF not installed (run: pip install pymupdf)")
except Exception as e:
    print(f"❌ PyMuPDF error: {e}")

print("\n" + "="*60)
print("TEST COMPLETE")
print("="*60)
