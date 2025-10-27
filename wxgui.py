import wx
import threading
from wx.lib.newevent import NewEvent
from pathlib import Path
from PIL import Image

# Importamos nuestra lógica central.
from launcher_logic import find_apps, launch_app, import_app_from_zip, get_app_metadata

# --- Constantes y Eventos Personalizados ---
COVER_SIZE = (250, 250)

UpdateLogEvent, EVT_UPDATE_LOG = NewEvent()
ThreadFinishedEvent, EVT_THREAD_FINISHED = NewEvent()

# --- Hilo de Trabajo (Worker Thread) ---
class WorkerThread(threading.Thread):
    def __init__(self, wx_window, app_name):
        super().__init__()
        self._wx_window = wx_window
        self._app_name = app_name
        self.daemon = True

    def run(self):
        for message in launch_app(self._app_name):
            evt = UpdateLogEvent(message=message)
            wx.PostEvent(self._wx_window, evt)
        wx.PostEvent(self._wx_window, ThreadFinishedEvent())

# --- Ventana Principal de la Aplicación ---
class AppLauncherFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Python App Launcher (wxPython)", size=(800, 600))
        
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # --- Columna Izquierda ---
        self.app_listbox = wx.ListBox(panel, style=wx.LB_SINGLE)
        log_label = wx.StaticText(panel, label="Log de Actividad:")
        self.log_console = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH)
        
        left_sizer.Add(wx.StaticText(panel, label="Aplicaciones:"), 0, wx.ALL | wx.EXPAND, 5)
        left_sizer.Add(self.app_listbox, 1, wx.EXPAND | wx.ALL, 5)
        left_sizer.Add(log_label, 0, wx.ALL | wx.EXPAND, 5)
        left_sizer.Add(self.log_console, 1, wx.EXPAND | wx.ALL, 5)
        
        # --- Columna Derecha ---
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
        
        # --- Binds de Eventos ---
        self.Bind(wx.EVT_LISTBOX, self.on_app_select, self.app_listbox)
        self.Bind(wx.EVT_BUTTON, self.on_launch, self.launch_button)
        self.Bind(wx.EVT_BUTTON, self.on_import, self.import_button)
        self.Bind(EVT_UPDATE_LOG, self.on_update_log)
        self.Bind(EVT_THREAD_FINISHED, self.on_thread_finished)
        
        self.worker = None
        
        # --- Carga Inicial ---
        self.populate_app_list()
        self.Centre()
        self.Show()

    def on_update_log(self, event):
        self.log_console.AppendText(event.message + "\n")

    def on_thread_finished(self, event):
        self.launch_button.Enable()
        self.import_button.Enable()
        self.worker = None

    def on_launch(self, event):
        selection_index = self.app_listbox.GetSelection()
        if selection_index == wx.NOT_FOUND:
            self.add_log_directo("AVISO: Por favor, selecciona una aplicación.")
            return

        if self.worker is not None:
            wx.MessageBox("Ya hay un proceso de instalación en curso.", "Proceso Ocupado", wx.OK | wx.ICON_INFORMATION)
            return

        app_name = self.app_listbox.GetString(selection_index)
        self.log_console.Clear()
        self.log_console.AppendText(f"Iniciando proceso para: {app_name}\n")
        
        self.launch_button.Disable()
        self.import_button.Disable()
        
        self.worker = WorkerThread(self, app_name)
        self.worker.start()

    def on_app_select(self, event):
        selection_index = self.app_listbox.GetSelection()
        if selection_index == wx.NOT_FOUND: return
        app_name = self.app_listbox.GetString(selection_index)
        
        cover_path = Path("apps") / app_name / "cover.png"
        bitmap = wx.Bitmap(*COVER_SIZE); dc = wx.MemoryDC(bitmap); dc.SetBackground(wx.Brush(wx.BLACK)); dc.Clear(); del dc
        if cover_path.exists():
            try:
                pil_img = Image.open(cover_path); pil_img.thumbnail(COVER_SIZE, Image.Resampling.LANCZOS)
                wx_image = wx.Image(pil_img.width, pil_img.height, pil_img.convert("RGB").tobytes())
                bitmap = wx.Bitmap(wx_image)
            except Exception as e: self.add_log_directo(f"Error al cargar imagen: {e}")
        self.cover_bitmap.SetBitmap(bitmap)
        
        metadata = get_app_metadata(app_name)
        self.desc_text.SetLabel(f"Descripción: {metadata['description']}")
        # El wrap es importante para que el texto se ajuste al cambiarlo
        self.desc_text.Wrap(self.GetClientSize().width // 2 - 50) 
        self.author_text.SetLabel(f"Autor: {metadata['author']}")
        self.version_text.SetLabel(f"Versión: {metadata['version']}")
        
        self.Layout()

    def on_import(self, event):
        with wx.FileDialog(self, "Seleccionar .zip de la aplicación", wildcard="Archivos Zip (*.zip)|*.zip", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL: return
            filepath = fileDialog.GetPath()

        app_name = Path(filepath).stem; overwrite = False
        if app_name in find_apps():
            dlg = wx.MessageDialog(self, f"La app '{app_name}' ya existe. ¿Desea sobreescribirla?", "Confirmar Sobreescritura", wx.YES_NO | wx.ICON_QUESTION)
            if dlg.ShowModal() != wx.ID_YES:
                self.add_log_directo(f"Importación de '{app_name}' cancelada."); return
            overwrite = True
        
        self.add_log_directo(f"Importando '{Path(filepath).name}'...")
        success, message = import_app_from_zip(filepath, overwrite)
        if success:
            self.add_log_directo(f"¡Éxito! App '{message}' importada."); self.populate_app_list()
        else:
            self.add_log_directo(f"ERROR: {message}")

    def populate_app_list(self):
        self.app_listbox.Clear()
        apps = find_apps()
        if not apps:
            self.app_listbox.Append("No hay apps instaladas."); self.app_listbox.Disable()
        else:
            self.app_listbox.Enable(); self.app_listbox.Set(apps)
            self.app_listbox.SetSelection(0); self.on_app_select(None)

    def add_log_directo(self, message):
        self.log_console.AppendText(message + "\n")

if __name__ == '__main__':
    app = wx.App(False)
    frame = AppLauncherFrame()
    app.MainLoop()