import os
import sys
import subprocess
import zipfile
import shutil
import json
from pathlib import Path

# --- Constantes ---
APPS_DIR = Path("apps")

def _find_system_python_executable():
    """Encuentra el ejecutable de Python 3 del sistema de forma robusta."""
    # (Esta función no ha cambiado)
    yield "-> Buscando el intérprete de Python del sistema..."
    candidates = ["/opt/homebrew/bin/python3", "/usr/local/bin/python3"]
    framework_path = Path("/Library/Frameworks/Python.framework/Versions")
    if framework_path.exists():
        versions = sorted(framework_path.glob("3.*/bin/python3"), reverse=True)
        if versions: candidates.append(str(versions[0]))
    candidates.append("/usr/bin/python3")
    yield f"   Orden de búsqueda: {candidates}"
    for path in candidates:
        if Path(path).exists():
            yield f"   Intérprete de Python preferido encontrado en: {path}"
            return path
    return None

def find_apps():
    # (Esta función no ha cambiado)
    if not APPS_DIR.exists(): APPS_DIR.mkdir()
    return sorted([d.name for d in APPS_DIR.iterdir() if d.is_dir()])

def get_app_metadata(app_name):
    # (Esta función no ha cambiado)
    metadata_path = APPS_DIR / app_name / "metadata.json"
    default_metadata = { "description": "No hay descripción disponible.", "author": "Desconocido", "version": "N/A" }
    if not metadata_path.exists(): return default_metadata
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for key in default_metadata:
                if key not in data: data[key] = default_metadata[key]
            return data
    except (json.JSONDecodeError, IOError): return default_metadata

def import_app_from_zip(zip_path_str, overwrite=False):
    # (Esta función no ha cambiado)
    zip_path = Path(zip_path_str)
    if not zip_path.exists() or not zipfile.is_zipfile(zip_path): return (False, "El archivo seleccionado no es un .zip válido.")
    required_files = {'script.py', 'requirements.txt'}
    with zipfile.ZipFile(zip_path, 'r') as zf:
        filenames_in_zip = {Path(p).name for p in zf.namelist() if not p.endswith('/')}
        if not required_files.issubset(filenames_in_zip):
            missing = required_files - filenames_in_zip
            return (False, f"El .zip debe contener al menos: {', '.join(missing)}")
    app_name = zip_path.stem
    dest_dir = APPS_DIR / app_name
    if dest_dir.exists() and not overwrite: return (False, f"La aplicación '{app_name}' ya existe.")
    if dest_dir.exists() and overwrite: shutil.rmtree(dest_dir)
    temp_extract_dir = APPS_DIR / f"__temp_{app_name}"
    try:
        if temp_extract_dir.exists(): shutil.rmtree(temp_extract_dir)
        with zipfile.ZipFile(zip_path, 'r') as zf: zf.extractall(temp_extract_dir)
        source_dir_with_files = temp_extract_dir
        script_path = list(temp_extract_dir.glob("**/script.py"))
        if script_path: source_dir_with_files = script_path[0].parent
        shutil.move(str(source_dir_with_files), str(dest_dir))
        if source_dir_with_files != temp_extract_dir: shutil.rmtree(temp_extract_dir)
        (dest_dir / "script.py").rename(dest_dir / "main.py")
    except Exception as e:
        if dest_dir.exists(): shutil.rmtree(dest_dir)
        if temp_extract_dir.exists(): shutil.rmtree(temp_extract_dir)
        return (False, f"Error durante la extracción: {e}")
    return (True, app_name)

# --- NUEVA LÓGICA DE VERIFICACIÓN Y LANZAMIENTO ---

def check_dependencies(app_name):
    """
    Verifica las dependencias de una app contra el entorno de Python encontrado.
    Devuelve (True, mensajes) si todo está OK, o (False, mensajes) si faltan paquetes.
    """
    app_dir = APPS_DIR / app_name
    requirements_file = app_dir / "requirements.txt"
    
    # 1. Encontrar el intérprete de Python
    python_interpreter = None
    search_generator = _find_system_python_executable()
    messages = []
    for message in search_generator:
        messages.append(message)
        if "encontrado en:" in message:
            python_interpreter = message.split("en: ")[1]
            
    if not python_interpreter:
        messages.append("ERROR: No se pudo encontrar un intérprete de Python 3 válido.")
        return False, messages, None

    # 2. Leer los requerimientos de la app
    if not requirements_file.exists() or requirements_file.stat().st_size == 0:
        messages.append("-> No se requieren dependencias específicas.")
        return True, messages, python_interpreter
    
    with open(requirements_file, 'r') as f:
        # Normalizar nombres: 'qrcode[pil]' -> 'qrcode'
        required_packages = {line.strip().lower().split('[')[0] for line in f if line.strip()}
    
    messages.append(f"-> Dependencias requeridas: {', '.join(required_packages)}")
    
    # 3. Obtener los paquetes instalados
    pip_executable = str(Path(python_interpreter).parent / "pip3")
    messages.append(f"-> Verificando paquetes instalados con: {pip_executable}")
    try:
        result = subprocess.run(
            [pip_executable, "list", "--format=json"],
            capture_output=True, text=True, check=True
        )
        installed_packages_data = json.loads(result.stdout)
        installed_packages = {pkg['name'].lower() for pkg in installed_packages_data}
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as e:
        messages.append(f"ERROR: No se pudo obtener la lista de paquetes instalados.")
        messages.append(f"   Detalle: {e}")
        return False, messages, python_interpreter

    # 4. Comparar y encontrar los paquetes que faltan
    missing_packages = required_packages - installed_packages
    
    if not missing_packages:
        messages.append("   ¡Todas las dependencias están cumplidas!")
        return True, messages, python_interpreter
    else:
        messages.append("   ¡ATENCIÓN! Faltan las siguientes dependencias:")
        for pkg in sorted(list(missing_packages)):
            messages.append(f"     - {pkg}")
        messages.append("   Por favor, instálalas usando la terminal antes de lanzar la app.")
        messages.append(f"   Ejemplo: {pip_executable} install {list(missing_packages)[0]}")
        return False, messages, python_interpreter

def launch_app_script(app_name, python_interpreter):
    """
    Función simple que solo lanza el script, asumiendo que las dependencias están OK.
    """
    app_dir = APPS_DIR / app_name
    main_script_file = app_dir / "main.py"
    
    try:
        subprocess.Popen([python_interpreter, str(main_script_file)])
        return "¡Aplicación lanzada!"
    except Exception as e:
        return f"ERROR al lanzar la aplicación: {e}"