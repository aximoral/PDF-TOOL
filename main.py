import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import io
import pymupdf
from PIL import Image
import threading

class PDFCompressorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("PDF Compressor")
        self.geometry("500x450")
        self.resizable(False, False)
        
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        
        self.input_pdf_path = None
        self.compressed_bytes = None
        
        self.create_widgets()
        
    def create_widgets(self):
        # Title
        self.title_label = ctk.CTkLabel(self, text="PDF Compressor", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.pack(pady=(20, 10))
        
        # File Selection
        self.file_frame = ctk.CTkFrame(self)
        self.file_frame.pack(pady=10, padx=20, fill="x")
        
        self.file_label = ctk.CTkLabel(self.file_frame, text="No file selected", width=300, anchor="w")
        self.file_label.pack(side="left", padx=10, pady=10)
        
        self.btn_browse = ctk.CTkButton(self.file_frame, text="Browse PDF", command=self.browse_file, width=100)
        self.btn_browse.pack(side="right", padx=10, pady=10)
        
        # Target Size
        self.size_frame = ctk.CTkFrame(self)
        self.size_frame.pack(pady=10, padx=20, fill="x")
        
        self.lbl_target = ctk.CTkLabel(self.size_frame, text="Target Size:")
        self.lbl_target.pack(side="left", padx=10, pady=10)
        
        self.entry_size = ctk.CTkEntry(self.size_frame, width=100)
        self.entry_size.pack(side="left", padx=10, pady=10)
        
        self.combo_unit = ctk.CTkComboBox(self.size_frame, values=["MB", "KB"], width=70)
        self.combo_unit.set("MB")
        self.combo_unit.pack(side="left", padx=10, pady=10)
        
        # Compress Button
        self.btn_compress = ctk.CTkButton(self, text="Compress", command=self.start_compression, font=ctk.CTkFont(size=16, weight="bold"))
        self.btn_compress.pack(pady=20)
        
        # Status Label
        self.status_label = ctk.CTkLabel(self, text="", text_color="gray")
        self.status_label.pack(pady=5)
        
        # Results Frame
        self.results_frame = ctk.CTkFrame(self)
        
        self.lbl_orig_size = ctk.CTkLabel(self.results_frame, text="Original Size: ")
        self.lbl_orig_size.pack(pady=5)
        
        self.lbl_comp_size = ctk.CTkLabel(self.results_frame, text="Compressed Size: ")
        self.lbl_comp_size.pack(pady=5)
        
        self.btn_save = ctk.CTkButton(self.results_frame, text="Save Compressed PDF", command=self.save_file)
        self.btn_save.pack(pady=10)
        
    def browse_file(self):
        filepath = filedialog.askopenfilename(
            title="Select PDF",
            filetypes=[("PDF Files", "*.pdf")]
        )
        if filepath:
            self.input_pdf_path = filepath
            filename = os.path.basename(filepath)
            size_bytes = os.path.getsize(filepath)
            size_str = self.format_size(size_bytes)
            self.file_label.configure(text=f"{filename} ({size_str})")
            
            # Hide results frame if it was shown
            self.results_frame.pack_forget()
            self.status_label.configure(text="")
            self.compressed_bytes = None
            
    def format_size(self, size_bytes):
        if size_bytes >= 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
        else:
            return f"{size_bytes / 1024:.2f} KB"

    def get_target_size_bytes(self):
        try:
            val = float(self.entry_size.get())
            unit = self.combo_unit.get()
            if unit == "MB":
                return int(val * 1024 * 1024)
            else:
                return int(val * 1024)
        except ValueError:
            return None

    def start_compression(self):
        if not self.input_pdf_path:
            messagebox.showerror("Error", "Please select a PDF file first.")
            return
            
        target_bytes = self.get_target_size_bytes()
        if target_bytes is None or target_bytes <= 0:
            messagebox.showerror("Error", "Please enter a valid target size.")
            return
            
        orig_bytes = os.path.getsize(self.input_pdf_path)
        
        if target_bytes >= orig_bytes:
            messagebox.showerror(
                "Error",
                "The target size is larger than or equal to the current PDF size. Please enter a smaller target."
            )
            return
            
        # Hide results frame before starting
        self.results_frame.pack_forget()
        self.btn_compress.configure(state="disabled")
        self.status_label.configure(text="Compressing... Please wait.")
        
        # Run compression in a separate thread to keep UI responsive
        threading.Thread(target=self.run_compression, args=(orig_bytes, target_bytes), daemon=True).start()
        
    def get_images_from_doc(self, doc):
        xrefs = set()
        for page in doc:
            for img in page.get_images():
                xref = img[0]
                xrefs.add(xref)
        return list(xrefs)

    def compress_step(self, input_bytes, quality, scale_factor):
        doc = pymupdf.open("pdf", input_bytes)
        xrefs = self.get_images_from_doc(doc)
        
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
            except Exception:
                pass
                
        return doc.tobytes(garbage=4, deflate=True)

    def run_compression(self, orig_bytes_size, target_bytes):
        try:
            with open(self.input_pdf_path, "rb") as f:
                original_bytes = f.read()
                
            # First try basic optimization
            doc = pymupdf.open("pdf", original_bytes)
            current_bytes = doc.tobytes(garbage=4, deflate=True)
            
            best_bytes = current_bytes
            success = False
            
            if len(current_bytes) <= target_bytes:
                success = True
            else:
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
                
                for quality, scale in strategies:
                    # Update status safely from thread
                    self.after(0, lambda q=quality: self.status_label.configure(text=f"Compressing... Trying quality {q}"))
                    
                    compressed = self.compress_step(original_bytes, quality, scale)
                    best_bytes = compressed
                    if len(compressed) <= target_bytes:
                        success = True
                        break
            
            self.compressed_bytes = best_bytes
            
            # Update UI on main thread
            self.after(0, lambda: self.finish_compression(orig_bytes_size, success))
            
        except Exception as e:
            self.after(0, lambda err=e: self.handle_compression_error(err))

    def handle_compression_error(self, err):
        self.btn_compress.configure(state="normal")
        self.status_label.configure(text="Compression failed!")
        messagebox.showerror("Error", f"An error occurred during compression:\n{str(err)}")

    def finish_compression(self, orig_bytes_size, success):
        self.btn_compress.configure(state="normal")
        
        comp_size = len(self.compressed_bytes)
        
        if success:
            self.status_label.configure(text="Compression successful!", text_color="green")
            self.lbl_orig_size.configure(text=f"Original Size: {self.format_size(orig_bytes_size)}")
            self.lbl_comp_size.configure(text=f"Compressed Size: {self.format_size(comp_size)}")
            self.results_frame.pack(pady=10, fill="x")
        else:
            self.status_label.configure(text="Error: Could not compress the PDF below the target size.", text_color="red")
            self.compressed_bytes = None
            messagebox.showerror("Compression Failed", "The PDF could not be compressed to the requested target size. The images are already at minimum quality or the file mostly consists of text/objects that cannot be compressed further. Please enter a larger target size.")


    def save_file(self):
        if not self.compressed_bytes:
            return
            
        orig_filename = os.path.basename(self.input_pdf_path)
        name, ext = os.path.splitext(orig_filename)
        default_name = f"{name}_compressed{ext}"
        
        filepath = filedialog.asksaveasfilename(
            title="Save Compressed PDF",
            initialfile=default_name,
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")]
        )
        
        if filepath:
            try:
                with open(filepath, "wb") as f:
                    f.write(self.compressed_bytes)
                messagebox.showinfo("Success", f"File saved successfully to:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file:\n{str(e)}")

if __name__ == "__main__":
    app = PDFCompressorApp()
    app.mainloop()
