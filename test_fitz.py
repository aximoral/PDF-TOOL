import pymupdf
import io
import os
from PIL import Image

def get_images_from_doc(doc):
    xrefs = set()
    for page in doc:
        for img in page.get_images():
            xref = img[0]
            xrefs.add(xref)
    return list(xrefs)

def compress_step(input_bytes, quality, scale_factor):
    doc = pymupdf.open("pdf", input_bytes)
    xrefs = get_images_from_doc(doc)
    
    for xref in xrefs:
        try:
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            
            img = Image.open(io.BytesIO(image_bytes))
            
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            if scale_factor < 1.0:
                new_size = (int(img.width * scale_factor), int(img.height * scale_factor))
                if new_size[0] > 0 and new_size[1] > 0:
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            out_stream = io.BytesIO()
            img.save(out_stream, format="JPEG", quality=quality)
            new_image_bytes = out_stream.getvalue()
            
            for page in doc:
                page_xrefs = [x[0] for x in page.get_images()]
                if xref in page_xrefs:
                    page.replace_image(xref, stream=new_image_bytes)
                    break
        except Exception as e:
            print("Error compressing image:", e)
            pass
            
    return doc.tobytes(garbage=4, deflate=True)

def compress_pdf(input_path, output_path, target_size):
    with open(input_path, "rb") as f:
        original_bytes = f.read()
        
    doc = pymupdf.open("pdf", original_bytes)
    current_bytes = doc.tobytes(garbage=4, deflate=True)
    if len(current_bytes) <= target_size:
        with open(output_path, "wb") as f:
            f.write(current_bytes)
        return True
        
    strategies = [
        (85, 1.0),
        (70, 1.0),
        (60, 0.8),
        (50, 0.6),
        (40, 0.5),
        (30, 0.4),
        (20, 0.3),
        (10, 0.2)
    ]
    
    best_bytes = current_bytes
    for quality, scale in strategies:
        print(f"Trying quality={quality}, scale={scale}")
        compressed_bytes = compress_step(original_bytes, quality, scale)
        print("Size:", len(compressed_bytes))
        best_bytes = compressed_bytes
        if len(compressed_bytes) <= target_size:
            with open(output_path, "wb") as f:
                f.write(compressed_bytes)
            return True
            
    with open(output_path, "wb") as f:
        f.write(best_bytes)
    return False

print("Compressing large.pdf to 30000 bytes...")
compress_pdf("large.pdf", "compressed.pdf", 30000)
print("Compressed size:", os.path.getsize("compressed.pdf"))

