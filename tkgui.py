import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox, font
from PIL import Image, ImageTk
from pathlib import Path
from launcher_logic import find_apps, launch_app, import_app_from_zip

COVER_SIZE = (200, 200)

class AppLauncherTk(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Python App Launcher")
        self.geometry("800x500")

        # --- Estilo ---
        self.default_font = font.nametofont("TkDefaultFont")
        self.default_font.configure(family="Helvetica", size=12)
        self.configure(bg="#3c3c3c")

        # --- Layout ---
        self.grid_columnconfigure(0, weight=1, minsize=200)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        # --- Frames ---
        left_frame = tk.Frame(self, bg="#4f4f4f")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        right_frame = tk.Frame(self, bg="#3c3c3c")
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)

        # --- Widgets del Frame Izquierdo ---
        left_frame.grid_rowconfigure(1, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)
        
        tk.Label(left_frame, text="Aplicaciones", fg="white", bg="#4f4f4f", font=("Helvetica", 16)).grid(row=0, column=0, pady=5)
        self.app_listbox = tk.Listbox(left_frame, bg="#2b2b2b", fg="white", selectbackground="#0078d7", borderwidth=0, highlightthickness=0)
        self.app_listbox.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.app_listbox.bind("<<ListboxSelect>>", self.on_app_select)
        
        # --- Widgets del Frame Derecho ---
        right_frame.grid_rowconfigure(1, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)
        
        self.cover_label = tk.Label(right_frame, text="Selecciona una App", bg="#2b2b2b", fg="grey")
        self.cover_label.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)

        self.launch_button = tk.Button(right_frame, text="Lanzar", command=self.launch_selected_app)
        self.launch_button.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        
        self.import_button = tk.Button(right_frame, text="Importar (.zip)", command=self.import_app)
        self.import_button.grid(row=1, column=1, sticky="ew", padx=5, pady=5)

        # --- Consola de Log (abajo) ---
        self.log_console = scrolledtext.ScrolledText(self, state='disabled', wrap=tk.WORD, height=10, bg="#1e1e1e", fg="#d4d4d4")
        self.log_console.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")

        # --- Carga Inicial ---
        self.populate_app_list()

    def add_log(self, message):
        self.log_console.config(state='normal')
        self.log_console.insert(tk.END, message + "\n")
        self.log_console.config(state='disabled')
        self.log_console.see(tk.END)
        self.update_idletasks()

    def populate_app_list(self):
        self.app_listbox.delete(0, tk.END)
        apps = find_apps()
        if not apps:
            self.app_listbox.insert(tk.END, "No hay apps instaladas.")
            self.app_listbox.config(state="disabled")
            self.on_app_select(None) # Limpiar portada
        else:
            self.app_listbox.config(state="normal")
            for app_name in apps:
                self.app_listbox.insert(tk.END, app_name)
            self.app_listbox.select_set(0) # Seleccionar el primer elemento
            self.app_listbox.event_generate("<<ListboxSelect>>")

    def on_app_select(self, event):
        selection_indices = self.app_listbox.curselection()
        if not selection_indices:
            self.cover_label.config(image='', text="Selecciona una App")
            return
            
        app_name = self.app_listbox.get(selection_indices[0])
        cover_path = Path("apps") / app_name / "cover.png"
        
        if cover_path.exists():
            try:
                img = Image.open(cover_path)
                img.thumbnail(COVER_SIZE, Image.Resampling.LANCZOS)
                self.cover_photo = ImageTk.PhotoImage(img)
                self.cover_label.config(image=self.cover_photo, text="")
            except Exception as e:
                self.cover_label.config(image='', text=f"Error al cargar\n{cover_path.name}")
        else:
            self.cover_label.config(image='', text="Portada no encontrada")

    def import_app(self):
        filepath = filedialog.askopenfilename(title="Seleccionar .zip", filetypes=(("Archivos Zip", "*.zip"),))
        if not filepath: return

        app_name = Path(filepath).stem
        overwrite = False
        if app_name in find_apps():
            if not messagebox.askyesno("Confirmar", f"La app '{app_name}' ya existe. ¿Sobreescribir?"):
                self.add_log(f"Importación de '{app_name}' cancelada.")
                return
            overwrite = True
        
        self.add_log(f"Importando '{Path(filepath).name}'...")
        success, message = import_app_from_zip(filepath, overwrite)

        if success:
            self.add_log(f"Éxito: App '{message}' importada.")
            self.populate_app_list()
        else:
            self.add_log(f"ERROR: {message}")

    def launch_selected_app(self):
        selection_indices = self.app_listbox.curselection()
        if not selection_indices:
            self.add_log("AVISO: Selecciona una aplicación.")
            return

        app_name = self.app_listbox.get(selection_indices[0])
        self.log_console.config(state='normal')
        self.log_console.delete(1.0, tk.END)
        self.log_console.config(state='disabled')
        self.add_log(f"Iniciando: {app_name}")

        self.launch_button.config(state="disabled")
        self.import_button.config(state="disabled")

        for message in launch_app(app_name):
            self.add_log(message)

        self.launch_button.config(state="normal")
        self.import_button.config(state="normal")

if __name__ == "__main__":
    app = AppLauncherTk()
    app.mainloop()