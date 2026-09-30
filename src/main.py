import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, Menu
from tkinterdnd2 import TkinterDnD, DND_FILES
import os
import io
import pymupdf
from PIL import Image, ImageTk, ImageGrab
import threading

class DraggableImage:
    def __init__(self, manager, filepath, x, y, pil_image=None):
        self.manager = manager
        self.canvas = manager.canvas
        
        if pil_image:
            self.orig_image = pil_image.convert("RGBA")
        else:
            self.orig_image = Image.open(filepath).convert("RGBA")
        
        # Initial resize if too large
        w, h = self.orig_image.size
        if w > 400 or h > 400:
            ratio = min(400/w, 400/h)
            w, h = int(w*ratio), int(h*ratio)
            
        self.width = w
        self.height = h
        self.x = x
        self.y = y
        
        self.photo = None
        self.image_id = self.canvas.create_image(x, y, anchor="nw")
        
        self.canvas.tag_bind(self.image_id, '<ButtonPress-1>', self.on_press)
        self.canvas.tag_bind(self.image_id, '<B1-Motion>', self.on_drag)
        self.canvas.tag_bind(self.image_id, '<ButtonRelease-1>', self.on_release)
        self.canvas.tag_bind(self.image_id, '<Button-3>', self.on_right_click)
        
        self.update_image()
        
        self.selected = False
        self.border_id = None
        self.handle_ids = []
        
        self.drag_data = {"x": 0, "y": 0, "mode": "move", "handle": None}

    def update_image(self, high_quality=True):
        resample = Image.Resampling.LANCZOS if high_quality else Image.Resampling.NEAREST
        resized = self.orig_image.resize((self.width, self.height), resample)
        self.photo = ImageTk.PhotoImage(resized)
        self.canvas.itemconfig(self.image_id, image=self.photo)
        self.canvas.coords(self.image_id, self.x, self.y)

    def select(self):
        self.manager.deselect_all()
        self.selected = True
        self.draw_handles()
        self.raise_to_top()
        self.manager.selected_item = self

    def deselect(self):
        self.selected = False
        if self.border_id:
            self.canvas.delete(self.border_id)
            self.border_id = None
        for h in self.handle_ids:
            self.canvas.delete(h)
        self.handle_ids = []
        if self.manager.selected_item == self:
            self.manager.selected_item = None

    def raise_to_top(self):
        self.canvas.tag_raise(self.image_id)
        if self.selected:
            if self.border_id: self.canvas.tag_raise(self.border_id)
            for h in self.handle_ids: self.canvas.tag_raise(h)

    def send_to_back(self):
        self.canvas.tag_lower(self.image_id)
        if self.selected:
            self.raise_to_top()
            
    def remove(self):
        self.deselect()
        self.canvas.delete(self.image_id)
        if self in self.manager.items:
            self.manager.items.remove(self)

    def draw_handles(self):
        if self.border_id:
            self.update_handles_coords()
            return
            
        self.selected = True
        self.manager.selected_item = self
        
        self.border_id = self.canvas.create_rectangle(
            self.x, self.y, self.x + self.width, self.y + self.height,
            outline="#0078D7", width=2, dash=(4, 4)
        )
        
        r = 5
        corners = [
            ("nw", self.x, self.y),
            ("ne", self.x + self.width, self.y),
            ("sw", self.x, self.y + self.height),
            ("se", self.x + self.width, self.y + self.height)
        ]
        
        for pos, cx, cy in corners:
            h = self.canvas.create_rectangle(cx-r, cy-r, cx+r, cy+r, fill="white", outline="#0078D7", width=2)
            self.handle_ids.append(h)
            
            self.canvas.tag_bind(h, '<ButtonPress-1>', lambda e, p=pos: self.on_handle_press(e, p))
            self.canvas.tag_bind(h, '<B1-Motion>', self.on_handle_drag)
            self.canvas.tag_bind(h, '<ButtonRelease-1>', self.on_release)

    def update_handles_coords(self):
        if not self.border_id: return
        self.canvas.coords(self.border_id, self.x, self.y, self.x + self.width, self.y + self.height)
        
        r = 5
        corners = [
            (self.x, self.y),
            (self.x + self.width, self.y),
            (self.x, self.y + self.height),
            (self.x + self.width, self.y + self.height)
        ]
        for i, (cx, cy) in enumerate(corners):
            self.canvas.coords(self.handle_ids[i], cx-r, cy-r, cx+r, cy+r)

    def on_press(self, event):
        self.select()
        self.drag_data["mode"] = "move"
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def on_drag(self, event):
        if self.drag_data["mode"] != "move": return
        dx = event.x - self.drag_data["x"]
        dy = event.y - self.drag_data["y"]
        self.x += dx
        self.y += dy
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y
        self.canvas.coords(self.image_id, self.x, self.y)
        if self.selected:
            self.update_handles_coords()

    def on_handle_press(self, event, pos):
        self.drag_data["mode"] = "resize"
        self.drag_data["handle"] = pos
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y
        self.drag_data["start_w"] = self.width
        self.drag_data["start_h"] = self.height
        self.drag_data["start_x"] = self.x
        self.drag_data["start_y"] = self.y

    def on_handle_drag(self, event):
        if self.drag_data["mode"] != "resize": return
        
        dx = event.x - self.drag_data["x"]
        dy = event.y - self.drag_data["y"]
        pos = self.drag_data["handle"]
        
        new_w = self.drag_data["start_w"]
        new_h = self.drag_data["start_h"]
        new_x = self.drag_data["start_x"]
        new_y = self.drag_data["start_y"]
        
        aspect = self.drag_data["start_w"] / self.drag_data["start_h"]
        
        if pos == "se":
            new_w += dx
            new_h = int(new_w / aspect)
        elif pos == "sw":
            new_w -= dx
            new_h = int(new_w / aspect)
            new_x = self.drag_data["start_x"] + dx
        elif pos == "ne":
            new_w += dx
            new_h = int(new_w / aspect)
            new_y = self.drag_data["start_y"] + (self.drag_data["start_h"] - new_h)
        elif pos == "nw":
            new_w -= dx
            new_h = int(new_w / aspect)
            new_x = self.drag_data["start_x"] + dx
            new_y = self.drag_data["start_y"] + (self.drag_data["start_h"] - new_h)
            
        if new_w > 20 and new_h > 20:
            self.width = new_w
            self.height = new_h
            self.x = new_x
            self.y = new_y
            self.update_image(high_quality=False)
            self.update_handles_coords()

    def on_release(self, event):
        if self.drag_data["mode"] == "resize":
            self.update_image(high_quality=True)

    def on_right_click(self, event):
        self.select()
        menu = Menu(self.canvas, tearoff=0)
        menu.add_command(label="Bring to Front", command=self.raise_to_top)
        menu.add_command(label="Send to Back", command=self.send_to_back)
        menu.add_separator()
        menu.add_command(label="Remove", command=self.remove)
        menu.post(event.x_root, event.y_root)

class CanvasManager:
    def __init__(self, canvas):
        self.canvas = canvas
        self.items = []
        self.selected_item = None
        self.canvas.bind("<ButtonPress-1>", self.on_bg_click)
        
    def on_bg_click(self, event):
        # Only deselect if we clicked on the background, not on an item
        if not self.canvas.find_withtag("current"):
            self.deselect_all()
        
    def deselect_all(self):
        if self.selected_item:
            self.selected_item.deselect()

    def add_image(self, filepath=None, x=0, y=0, pil_image=None):
        try:
            item = DraggableImage(self, filepath, x, y, pil_image=pil_image)
            self.items.append(item)
            item.select()
        except Exception as e:
            print("Failed to load image:", e)
        
    def clear_all(self):
        for item in list(self.items):
            item.remove()

    def delete_selected(self):
        if self.selected_item:
            self.selected_item.remove()

class App(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)
        
        self.title("PDF Tools")
        self.geometry("900x950")
        self.resizable(False, False)
        
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(expand=True, fill="both", padx=10, pady=10)
        
        self.tab_compress = self.tabview.add("Compress PDF")
        self.tab_canvas = self.tabview.add("Image to PDF")
        
        self.setup_compress_tab()
        self.setup_canvas_tab()
        
        # Bind delete and paste keys globally (when canvas tab is active)
        self.bind("<Delete>", lambda e: self.canvas_manager.delete_selected() if self.tabview.get() == "Image to PDF" else None)
        self.bind("<Control-v>", lambda e: self.on_paste() if self.tabview.get() == "Image to PDF" else None)
        self.bind("<Control-V>", lambda e: self.on_paste() if self.tabview.get() == "Image to PDF" else None)
        
    # --- COMPRESS PDF TAB ---
    def setup_compress_tab(self):
        self.input_pdf_path = None
        self.compressed_bytes = None
        
        self.title_label = ctk.CTkLabel(self.tab_compress, text="PDF Compressor", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.pack(pady=(20, 10))
        
        self.file_frame = ctk.CTkFrame(self.tab_compress)
        self.file_frame.pack(pady=10, padx=20, fill="x")
        
        self.file_label = ctk.CTkLabel(self.file_frame, text="No file selected", width=300, anchor="w")
        self.file_label.pack(side="left", padx=10, pady=10)
        
        self.btn_browse = ctk.CTkButton(self.file_frame, text="Browse PDF", command=self.browse_file, width=100)
        self.btn_browse.pack(side="right", padx=10, pady=10)
        
        self.size_frame = ctk.CTkFrame(self.tab_compress)
        self.size_frame.pack(pady=10, padx=20, fill="x")
        
        self.lbl_target = ctk.CTkLabel(self.size_frame, text="Target Size:")
        self.lbl_target.pack(side="left", padx=10, pady=10)
        
        self.entry_size = ctk.CTkEntry(self.size_frame, width=100)
        self.entry_size.pack(side="left", padx=10, pady=10)
        
        self.combo_unit = ctk.CTkComboBox(self.size_frame, values=["MB", "KB"], width=70)
        self.combo_unit.set("MB")
        self.combo_unit.pack(side="left", padx=10, pady=10)
        
        self.btn_compress = ctk.CTkButton(self.tab_compress, text="Compress", command=self.start_compression, font=ctk.CTkFont(size=16, weight="bold"))
        self.btn_compress.pack(pady=20)
        
        self.status_label = ctk.CTkLabel(self.tab_compress, text="", text_color="gray")
        self.status_label.pack(pady=5)
        
        self.results_frame = ctk.CTkFrame(self.tab_compress)
        self.lbl_orig_size = ctk.CTkLabel(self.results_frame, text="Original Size: ")
        self.lbl_orig_size.pack(pady=5)
        
        self.lbl_comp_size = ctk.CTkLabel(self.results_frame, text="Compressed Size: ")
        self.lbl_comp_size.pack(pady=5)
        
        self.btn_save = ctk.CTkButton(self.results_frame, text="Save Compressed PDF", command=self.save_file)
        self.btn_save.pack(pady=10)

    def browse_file(self):
        filepath = filedialog.askopenfilename(title="Select PDF", filetypes=[("PDF Files", "*.pdf")])
        if filepath:
            self.input_pdf_path = filepath
            filename = os.path.basename(filepath)
            size_bytes = os.path.getsize(filepath)
            self.file_label.configure(text=f"{filename} ({self.format_size(size_bytes)})")
            self.results_frame.pack_forget()
            self.status_label.configure(text="")
            self.compressed_bytes = None
            
    def format_size(self, size_bytes):
        if size_bytes >= 1024 * 1024: return f"{size_bytes / (1024 * 1024):.2f} MB"
        else: return f"{size_bytes / 1024:.2f} KB"

    def get_target_size_bytes(self):
        try:
            val = float(self.entry_size.get())
            unit = self.combo_unit.get()
            return int(val * 1024 * 1024) if unit == "MB" else int(val * 1024)
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
            messagebox.showerror("Error", "The target size is larger than or equal to the current PDF size. Please enter a smaller target.")
            return
            
        self.results_frame.pack_forget()
        self.btn_compress.configure(state="disabled")
        self.status_label.configure(text="Compressing... Please wait.")
        threading.Thread(target=self.run_compression, args=(orig_bytes, target_bytes), daemon=True).start()

    def get_images_from_doc(self, doc):
        xrefs = set()
        for page in doc:
            for img in page.get_images(): xrefs.add(img[0])
        return list(xrefs)

    def compress_step(self, input_bytes, quality, scale_factor):
        doc = pymupdf.open("pdf", input_bytes)
        for xref in self.get_images_from_doc(doc):
            try:
                base_image = doc.extract_image(xref)
                img = Image.open(io.BytesIO(base_image["image"]))
                if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                if scale_factor < 1.0:
                    new_size = (int(img.width * scale_factor), int(img.height * scale_factor))
                    if new_size[0] > 0 and new_size[1] > 0:
                        img = img.resize(new_size, Image.Resampling.LANCZOS)
                out_stream = io.BytesIO()
                img.save(out_stream, format="JPEG", quality=quality)
                new_image_bytes = out_stream.getvalue()
                for page in doc:
                    if xref in [x[0] for x in page.get_images()]:
                        page.replace_image(xref, stream=new_image_bytes)
                        break
            except Exception: pass
        return doc.tobytes(garbage=4, deflate=True)

    def run_compression(self, orig_bytes_size, target_bytes):
        try:
            with open(self.input_pdf_path, "rb") as f: original_bytes = f.read()
            doc = pymupdf.open("pdf", original_bytes)
            current_bytes = doc.tobytes(garbage=4, deflate=True)
            
            best_bytes = current_bytes
            success = len(current_bytes) <= target_bytes
            
            if not success:
                for quality, scale in [(85, 1.0), (70, 1.0), (60, 0.8), (50, 0.6), (40, 0.5), (30, 0.4), (20, 0.3), (10, 0.2)]:
                    self.after(0, lambda q=quality: self.status_label.configure(text=f"Compressing... Trying quality {q}"))
                    compressed = self.compress_step(original_bytes, quality, scale)
                    best_bytes = compressed
                    if len(compressed) <= target_bytes:
                        success = True
                        break
            self.compressed_bytes = best_bytes
            self.after(0, lambda: self.finish_compression(orig_bytes_size, success))
        except Exception as e:
            self.after(0, lambda err=e: self.handle_compression_error(err))

    def handle_compression_error(self, err):
        self.btn_compress.configure(state="normal")
        self.status_label.configure(text="Compression failed!", text_color="red")
        messagebox.showerror("Error", f"An error occurred:\n{str(err)}")

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
            messagebox.showerror("Compression Failed", "The PDF could not be compressed to the requested target size.")

    def save_file(self):
        if not self.compressed_bytes: return
        orig_filename = os.path.basename(self.input_pdf_path)
        name, ext = os.path.splitext(orig_filename)
        filepath = filedialog.asksaveasfilename(title="Save Compressed PDF", initialfile=f"{name}_compressed{ext}", defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")])
        if filepath:
            try:
                with open(filepath, "wb") as f: f.write(self.compressed_bytes)
                messagebox.showinfo("Success", f"File saved successfully to:\n{filepath}")
            except Exception as e: messagebox.showerror("Error", f"Failed to save file:\n{str(e)}")

    # --- IMAGE TO PDF (CANVAS) TAB ---
    def setup_canvas_tab(self):
        self.tools_frame = ctk.CTkFrame(self.tab_canvas)
        self.tools_frame.pack(fill="x", padx=10, pady=(10, 0))
        
        self.btn_add_image = ctk.CTkButton(self.tools_frame, text="Add Image", command=self.add_image_dialog)
        self.btn_add_image.pack(side="left", padx=10, pady=10)

        self.btn_clear = ctk.CTkButton(self.tools_frame, text="Clear Canvas", fg_color="transparent", border_width=2, text_color=("gray10", "#DCE4EE"), command=self.clear_canvas)
        self.btn_clear.pack(side="left", padx=10, pady=10)
        
        self.btn_remove = ctk.CTkButton(self.tools_frame, text="Remove Selected", fg_color="transparent", border_width=2, text_color=("gray10", "#DCE4EE"), command=self.remove_selected)
        self.btn_remove.pack(side="left", padx=10, pady=10)
        
        self.btn_export = ctk.CTkButton(self.tools_frame, text="Download as PDF", font=ctk.CTkFont(weight="bold"), command=self.export_to_pdf)
        self.btn_export.pack(side="right", padx=10, pady=10)
        
        self.lbl_dnd_hint = ctk.CTkLabel(self.tools_frame, text="Drag & Drop or Ctrl+V to add images!", text_color="gray")
        self.lbl_dnd_hint.pack(side="right", padx=20, pady=10)
        
        self.canvas_container = tk.Frame(self.tab_canvas, bg="#cccccc")
        self.canvas_container.pack(pady=20)
        
        self.canvas_w = 595
        self.canvas_h = 842
        
        self.canvas = tk.Canvas(self.canvas_container, width=self.canvas_w, height=self.canvas_h, bg="white", highlightthickness=1, highlightbackground="gray")
        self.canvas.pack(padx=2, pady=2)
        
        self.canvas_manager = CanvasManager(self.canvas)
        
        self.canvas.drop_target_register(DND_FILES)
        self.canvas.dnd_bind('<<Drop>>', self.on_file_drop)
        
    def add_image_dialog(self):
        filepaths = filedialog.askopenfilenames(
            title="Select Images", 
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.gif")]
        )
        if filepaths:
            offset_x, offset_y = 50, 50
            for i, filepath in enumerate(filepaths):
                self.canvas_manager.add_image(filepath, offset_x + (i*20), offset_y + (i*20))

    def on_paste(self):
        try:
            clipboard = ImageGrab.grabclipboard()
            if isinstance(clipboard, list):
                offset_x, offset_y = 100, 100
                for i, filepath in enumerate(clipboard):
                    if isinstance(filepath, str) and filepath.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')):
                        self.canvas_manager.add_image(filepath, offset_x + (i*20), offset_y + (i*20))
            elif isinstance(clipboard, Image.Image):
                # Place at center approx
                center_x = (self.canvas_w / 2) - min(clipboard.width, 400)/2
                center_y = (self.canvas_h / 2) - min(clipboard.height, 400)/2
                self.canvas_manager.add_image(pil_image=clipboard, x=center_x, y=center_y)
        except Exception:
            pass
        
    def on_file_drop(self, event):
        files = self.split_dnd_files(event.data)
        offset_x, offset_y = event.x_root - self.canvas.winfo_rootx(), event.y_root - self.canvas.winfo_rooty()
        for i, filepath in enumerate(files):
            if filepath.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')):
                self.canvas_manager.add_image(filepath, offset_x + (i*20), offset_y + (i*20))

    def split_dnd_files(self, data):
        import shlex
        return shlex.split(data)

    def clear_canvas(self):
        if len(self.canvas_manager.items) == 0: return
        if messagebox.askyesno("Clear Canvas", "Are you sure you want to remove all images from the canvas?"):
            self.canvas_manager.clear_all()
            
    def remove_selected(self):
        self.canvas_manager.delete_selected()

    def export_to_pdf(self):
        if len(self.canvas_manager.items) == 0:
            messagebox.showinfo("Export", "The canvas is empty.")
            return
            
        filepath = filedialog.asksaveasfilename(title="Download as PDF", initialfile="Canvas_Export.pdf", defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")])
        if not filepath: return
        
        try:
            doc = pymupdf.open()
            page = doc.new_page(width=self.canvas_w, height=self.canvas_h)
            all_ids = self.canvas.find_all()
            id_to_item = {item.image_id: item for item in self.canvas_manager.items}
            
            for item_id in all_ids:
                if item_id in id_to_item:
                    item = id_to_item[item_id]
                    rect = pymupdf.Rect(item.x, item.y, item.x + item.width, item.y + item.height)
                    img_bytes = io.BytesIO()
                    resized = item.orig_image.resize((item.width, item.height), Image.Resampling.LANCZOS)
                    resized.save(img_bytes, format="PNG")
                    page.insert_image(rect, stream=img_bytes.getvalue())
                    
            doc.save(filepath)
            messagebox.showinfo("Success", f"PDF exported successfully to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"An error occurred while exporting:\n{str(e)}")


if __name__ == "__main__":
    app = App()
    app.mainloop()
