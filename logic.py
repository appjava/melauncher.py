import os
import sys
import subprocess
import zipfile
import shutil
import json
from pathlib import Path

# --- Constantes ---
APPS_DIR = Path("apps")

def get_venv_python_path(venv_dir):
    """Obtiene la ruta al ejecutable de Python dentro de un venv para macOS/Linux."""
    return Path(venv_dir) / "bin" / "python"

def find_apps():
    """Encuentra todas las carpetas de aplicaciones en el directorio 'apps'."""
    if not APPS_DIR.exists():
        APPS_DIR.mkdir()
    return sorted([d.name for d in APPS_DIR.iterdir() if d.is_dir()])

def get_app_metadata(app_name):
    """
    Lee el archivo metadata.json de una app.
    Devuelve valores por defecto si el archivo no existe o es inválido.
    """
    metadata_path = APPS_DIR / app_name / "metadata.json"
    default_metadata = {
        "description": "No hay descripción disponible.",
        "author": "Desconocido",
        "version": "N/A"
    }
    if not metadata_path.exists():
        return default_metadata
    
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Rellenar con valores por defecto si faltan claves en el JSON
            for key in default_metadata:
                if key not in data:
                    data[key] = default_metadata[key]
            return data
    except (json.JSONDecodeError, IOError):
        return default_metadata

def import_app_from_zip(zip_path_str, overwrite=False):
    """
    Valida y extrae una app desde un .zip.
    'cover.png' y 'metadata.json' son ahora opcionales.
    """
    zip_path = Path(zip_path_str)
    
    if not zip_path.exists() or not zipfile.is_zipfile(zip_path):
        return (False, "El archivo seleccionado no es un .zip válido.")

    # --- MODIFICADO: 'cover.png' y 'metadata.json' ahora son opcionales. ---
    # Solo requerimos los archivos esenciales para que la app funcione.
    required_files = {'script.py', 'requirements.txt'}
    
    with zipfile.ZipFile(zip_path, 'r') as zf:
        filenames_in_zip = {Path(p).name for p in zf.namelist() if not p.endswith('/')}
        if not required_files.issubset(filenames_in_zip):
            missing = required_files - filenames_in_zip
            return (False, f"El .zip debe contener al menos: {', '.join(missing)}")

    app_name = zip_path.stem
    dest_dir = APPS_DIR / app_name
    
    if dest_dir.exists() and not overwrite:
        return (False, f"La aplicación '{app_name}' ya existe.")
    
    if dest_dir.exists() and overwrite:
        shutil.rmtree(dest_dir)

    temp_extract_dir = APPS_DIR / f"__temp_{app_name}"
    
    try:
        if temp_extract_dir.exists():
            shutil.rmtree(temp_extract_dir)
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(temp_extract_dir)

        source_dir_with_files = temp_extract_dir
        script_path = list(temp_extract_dir.glob("**/script.py"))
        if script_path:
            source_dir_with_files = script_path[0].parent
        
        shutil.move(str(source_dir_with_files), str(dest_dir))
        
        if source_dir_with_files != temp_extract_dir:
            shutil.rmtree(temp_extract_dir)
        
        (dest_dir / "script.py").rename(dest_dir / "main.py")

    except Exception as e:
        if dest_dir.exists(): shutil.rmtree(dest_dir)
        if temp_extract_dir.exists(): shutil.rmtree(temp_extract_dir)
        return (False, f"Error durante la extracción: {e}")
        
    return (True, app_name)

def launch_app(app_name):
    """
    Gestiona el venv y lanza la aplicación. Usa 'yield' para devolver el progreso.
    """
    app_dir = APPS_DIR / app_name
    venv_dir = app_dir / "venv"
    requirements_file = app_dir / "requirements.txt"
    main_script_file = app_dir / "main.py"

    if not main_script_file.exists():
        yield f"ERROR: No se encontró 'main.py' en {app_dir}."
        return

    python_executable = get_venv_python_path(venv_dir)

    if not python_executable.exists():
        yield f"-> Creando entorno virtual para '{app_name}'..."
        try:
            subprocess.run(
                [sys.executable, "-m", "venv", str(venv_dir)],
                check=True, capture_output=True, text=True, timeout=120
            )
            yield "   Entorno virtual creado."
        except subprocess.CalledProcessError as e:
            yield f"ERROR al crear venv: {e.stderr}"
            return

    if requirements_file.exists() and requirements_file.stat().st_size > 0:
        yield f"-> Instalando dependencias..."
        try:
            pip_executable = python_executable.parent / "pip"
            subprocess.run(
                [str(pip_executable), "install", "-r", str(requirements_file)],
                check=True, capture_output=True, text=True, timeout=300
            )
            yield "   Dependencias instaladas."
        except subprocess.CalledProcessError as e:
            yield f"ERROR al instalar dependencias: {e.stderr}"
            return
    else:
        yield "-> No hay dependencias que instalar."

    yield f"\n==> LANZANDO '{app_name}'..."
    try:
        subprocess.Popen([str(python_executable), str(main_script_file)])
        yield "   ¡Aplicación lanzada!"
    except Exception as e:
        yield f"ERROR al lanzar la aplicación: {e}"