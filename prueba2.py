import tkinter as tk
from tkinter import filedialog, scrolledtext
from PIL import Image, ImageTk
from ultralytics import YOLO
import requests

# ==================== API NEXAR ====================
CLIENT_ID = '2ec98ebb-9c17-4128-b28a-35e95a4f338c'
CLIENT_SECRET = 'V-9IAEDOARvKAa3s57QeVy1NIbfL-lbZoXr3'

def obtener_token():
    url = "https://identity.nexar.com/connect/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "supply.domain"
    }
    response = requests.post(url, data=data)
    return response.json().get("access_token", None)

def buscar_componente(nombre, token):
    url = "https://api.nexar.com/graphql"
    headers = {"Authorization": f"Bearer {token}"}
    query = """
    query BuscarComponente($busqueda: String!) {
      supSearch(q: $busqueda, limit: 1) {
        results {
          part {
            mpn
            manufacturer { name }
            shortDescription
            specs {
              attribute { name }
              displayValue
            }
          }
        }
      }
    }
    """
    variables = {"busqueda": nombre}
    response = requests.post(url, json={"query": query, "variables": variables}, headers=headers)
    return response.json().get("data", {}).get("supSearch", {}).get("results", [])

# ==================== MODELO IA ====================
model = YOLO("best.pt")  # Asegúrate de que esté en tu carpeta o da ruta completa

# ==================== INTERFAZ TKINTER ====================
def cargar_imagen():
    ruta = filedialog.askopenfilename(filetypes=[("Imágenes", "*.jpg;*.png")])
    if ruta:
        detectar_y_consultar(ruta)

def detectar_y_consultar(ruta_imagen):
    result = model(ruta_imagen)[0]
    result.save(filename="resultado.jpg")

    nombres_detectados = list(set([model.names[int(box.cls)] for box in result.boxes]))

    mostrar_resultado("resultado.jpg")

    # Mostrar resultados de API
    token = obtener_token()
    salida_texto.delete("1.0", tk.END)

    if not token:
        salida_texto.insert(tk.END, "❌ No se pudo obtener token de Nexar.")
        return

    for nombre in nombres_detectados:
        salida_texto.insert(tk.END, f"\n🔍 Resultados para: {nombre}\n")
        componentes = buscar_componente(nombre, token)
        if not componentes:
            salida_texto.insert(tk.END, "  ⚠️ No se encontró información.\n")
        else:
            parte = componentes[0]["part"]
            salida_texto.insert(tk.END, f"  🧩 MPN: {parte.get('mpn')}\n")
            salida_texto.insert(tk.END, f"  🏭 Fabricante: {parte['manufacturer']['name']}\n")
            salida_texto.insert(tk.END, f"  📝 Descripción: {parte.get('shortDescription')}\n")
            salida_texto.insert(tk.END, "  📊 Especificaciones:\n")
            for spec in parte.get("specs", [])[:3]:
                salida_texto.insert(tk.END, f"    • {spec['attribute']['name']}: {spec['displayValue']}\n")

def mostrar_resultado(ruta_imagen):
    img = Image.open(ruta_imagen).resize((500, 400))
    img_tk = ImageTk.PhotoImage(img)
    panel_imagen.config(image=img_tk)
    panel_imagen.image = img_tk

# ==================== GUI ====================
root = tk.Tk()
root.title("Detector de Componentes con IA + API")
root.geometry("700x700")

btn_cargar = tk.Button(root, text="📷 Subir Imagen", command=cargar_imagen)
btn_cargar.pack(pady=10)

panel_imagen = tk.Label(root)
panel_imagen.pack()

salida_texto = scrolledtext.ScrolledText(root, width=80, height=15)
salida_texto.pack(pady=10)

root.mainloop()
