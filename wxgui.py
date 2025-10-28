import wx
from pathlib import Path
from PIL import Image

from logic import find_apps, get_app_metadata, import_app_from_zip, check_dependencies, launch_app_script

COVER_SIZE = (250, 250)

class AppLauncherFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Python App Launcher (wxPython)", size=(600, 600))
        
        self.python_interpreter_path = None # Almacenará la ruta al Python encontrado
        
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        
        self.app_listbox = wx.ListBox(panel, style=wx.LB_SINGLE)
        log_label = wx.StaticText(panel, label="Log de Actividad:")
        self.log_console = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH)
        left_sizer.Add(wx.StaticText(panel, label="Aplicaciones:"), 0, wx.ALL | wx.EXPAND, 5)
        left_sizer.Add(self.app_listbox, 1, wx.EXPAND | wx.ALL, 5)
        left_sizer.Add(log_label, 0, wx.ALL | wx.EXPAND, 5)
        left_sizer.Add(self.log_console, 1, wx.EXPAND | wx.ALL, 5)
        
        self.cover_bitmap = wx.StaticBitmap(panel)
        self.cover_bitmap.SetMinSize(COVER_SIZE)
        metadata_box = wx.StaticBox(panel, label="Información de la App")
        metadata_sizer = wx.StaticBoxSizer(metadata_box, wx.VERTICAL)
        self.desc_text = wx.StaticText(panel, label="Descripción: N/A", style=wx.ST_NO_AUTORESIZE)
        self.author_text = wx.StaticText(panel, label="Autor: N/A")
        self.version_text = wx.StaticText(panel, label="Versión: N/A")
        metadata_sizer.Add(self.desc_text, 1, wx.EXPAND | wx.ALL, 5)
        metadata_sizer.Add(self.author_text, 0, wx.EXPAND | wx.ALL, 5)
        metadata_sizer.Add(self.version_text, 0, wx.EXPAND | wx.ALL, 5)

        self.launch_button = wx.Button(panel, label="Lanzar Aplicación")
        self.import_button = wx.Button(panel, label="Importar App (.zip)")
        
        right_sizer.Add(self.cover_bitmap, 0, wx.ALL | wx.CENTER, 5)
        right_sizer.Add(metadata_sizer, 1, wx.EXPAND | wx.ALL, 5)
        right_sizer.Add(self.launch_button, 0, wx.EXPAND | wx.ALL, 5)
        right_sizer.Add(self.import_button, 0, wx.EXPAND | wx.ALL, 5)
        
        main_sizer.Add(left_sizer, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(right_sizer, 1, wx.EXPAND | wx.ALL, 5)
        panel.SetSizer(main_sizer)
        
        self.Bind(wx.EVT_LISTBOX, self.on_app_select, self.app_listbox)
        self.Bind(wx.EVT_BUTTON, self.on_launch, self.launch_button)
        self.Bind(wx.EVT_BUTTON, self.on_import, self.import_button)
        
        self.populate_app_list()
        self.Centre()
        self.Show()

    def add_log(self, message):
        self.log_console.AppendText(message + "\n")
        wx.Yield()

    def on_launch(self, event):
        """Manejador del botón Lanzar. Solo se ejecuta si el botón está habilitado."""
        selection_index = self.app_listbox.GetSelection()
        if selection_index == wx.NOT_FOUND or self.python_interpreter_path is None:
            return
        
        app_name = self.app_listbox.GetString(selection_index)
        self.add_log(f"\n==> LANZANDO '{app_name}'...")
        message = launch_app_script(app_name, self.python_interpreter_path)
        self.add_log(f"   {message}")

    def on_app_select(self, event):
        """Al seleccionar una app, se actualiza la UI y se verifican las dependencias."""
        selection_index = self.app_listbox.GetSelection()
        if selection_index == wx.NOT_FOUND: return
        
        app_name = self.app_listbox.GetString(selection_index)
        
        # 1. Actualizar UI (portada y metadatos)
        cover_path = Path("apps") / app_name / "cover.png"
        bitmap = wx.Bitmap(*COVER_SIZE); dc = wx.MemoryDC(bitmap); dc.SetBackground(wx.Brush(wx.BLACK)); dc.Clear(); del dc
        if cover_path.exists():
            try:
                pil_img = Image.open(cover_path); pil_img.thumbnail(COVER_SIZE, Image.Resampling.LANCZOS)
                wx_image = wx.Image(pil_img.width, pil_img.height, pil_img.convert("RGB").tobytes())
                bitmap = wx.Bitmap(wx_image)
            except Exception as e: self.add_log(f"Error al cargar imagen: {e}")
        self.cover_bitmap.SetBitmap(bitmap)
        
        metadata = get_app_metadata(app_name)
        self.desc_text.SetLabel(f"Descripción: {metadata['description']}")
        self.desc_text.Wrap(self.GetClientSize().width // 2 - 50) 
        self.author_text.SetLabel(f"Autor: {metadata['author']}")
        self.version_text.SetLabel(f"Versión: {metadata['version']}")
        self.Layout()

        # 2. Verificar dependencias y actualizar el log y el botón
        self.log_console.Clear()
        self.launch_button.Disable() # Deshabilitar por defecto
        self.python_interpreter_path = None
        
        all_ok, messages, python_path = check_dependencies(app_name)
        for msg in messages:
            self.add_log(msg)
        
        if all_ok:
            self.launch_button.Enable()
            self.python_interpreter_path = python_path
            
    def on_import(self, event):
        # (Función sin cambios)
        with wx.FileDialog(self, "Seleccionar .zip", wildcard="*.zip", style=wx.FD_OPEN) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL: return
            filepath = dlg.GetPath()
        app_name = Path(filepath).stem
        overwrite = False
        if app_name in find_apps():
            with wx.MessageDialog(self, f"La app '{app_name}' ya existe. Sobreescribir?", "Confirmar", wx.YES_NO) as mdlg:
                if mdlg.ShowModal() != wx.ID_YES:
                    self.add_log(f"Importación de '{app_name}' cancelada.")
                    return
                overwrite = True
        self.add_log(f"Importando '{Path(filepath).name}'...")
        success, message = import_app_from_zip(filepath, overwrite)
        if success: self.add_log(f"¡Éxito! App '{message}' importada."); self.populate_app_list()
        else: self.add_log(f"ERROR: {message}")

    def populate_app_list(self):
        # (Función sin cambios)
        self.app_listbox.Clear()
        apps = find_apps()
        if not apps: self.app_listbox.Append("No hay apps instaladas."); self.app_listbox.Disable(); self.launch_button.Disable()
        else:
            self.app_listbox.Enable(); self.app_listbox.Set(apps)
            self.app_listbox.SetSelection(0); self.on_app_select(None)

if __name__ == '__main__':
    app = wx.App(False)
    frame = AppLauncherFrame()
    app.MainLoop()