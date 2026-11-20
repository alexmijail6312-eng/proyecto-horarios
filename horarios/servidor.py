"""
Interfaz visual local. Servidor HTTP con la biblioteca estandar y una pagina en web/index.html.
No requiere instalar nada: python main.py gui
"""
import json
import mimetypes
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import datos, experimentos
from .agentes import Orquestador

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(RAIZ, "web")
RES = os.path.join(RAIZ, "resultados")


class Estado:
    lock = threading.Lock()
    orq = None
    exp = {"corriendo": False, "mensaje": "", "resultado": None}


def nuevo_entorno(materias=20, semilla=1, tension=False):
    Estado.orq = Orquestador(datos.generar_entorno(int(materias), int(semilla), bool(tension)), int(semilla))


def _experimento(repeticiones):
    Estado.exp = {"corriendo": True, "mensaje": "Iniciando", "resultado": None}
    try:
        def cb(m):
            Estado.exp["mensaje"] = m
        res = experimentos.correr(repeticiones=repeticiones, salida=RES, callback=cb)
        Estado.exp = {"corriendo": False, "mensaje": "Experimentacion finalizada",
                      "resultado": {k: res[k] for k in ("calidad", "psr", "sorpresa", "repeticiones")}}
    except Exception as e:                                       # se informa a la interfaz
        Estado.exp = {"corriendo": False, "mensaje": f"Error: {e}", "resultado": None}


class Manejador(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, codigo=200):
        cuerpo = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _archivo(self, ruta):
        if not os.path.isfile(ruta):
            return self._json({"error": "No encontrado"}, 404)
        with open(ruta, "rb") as f:
            datos_ = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(ruta)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(datos_)))
        self.end_headers()
        self.wfile.write(datos_)

    def do_GET(self):
        ruta = self.path.split("?")[0]
        if ruta == "/":
            return self._archivo(os.path.join(WEB, "index.html"))
        if ruta == "/api/estado":
            with Estado.lock:
                return self._json(Estado.orq.estado())
        if ruta == "/api/experimento":
            return self._json(Estado.exp)
        if ruta.startswith("/resultados/"):
            nombre = os.path.basename(ruta)
            return self._archivo(os.path.join(RES, nombre))
        return self._json({"error": "No encontrado"}, 404)

    def do_POST(self):
        largo = int(self.headers.get("Content-Length") or 0)
        p = json.loads(self.rfile.read(largo) or b"{}")
        ruta = self.path
        try:
            if ruta == "/api/experimento":
                if Estado.exp["corriendo"]:
                    return self._json({"error": "Ya hay una experimentacion en curso"}, 400)
                threading.Thread(target=_experimento, args=(int(p.get("repeticiones", 3)),), daemon=True).start()
                return self._json({"ok": True})
            with Estado.lock:
                if ruta == "/api/generar":
                    nuevo_entorno(p.get("materias", 20), p.get("semilla", 1), p.get("tension", False))
                elif ruta == "/api/planificar":
                    ok = Estado.orq.planificar(p.get("metodo_local", "sa"), int(p.get("generaciones", 80)))
                    if not ok:
                        return self._json({"error": "El PSR no encontro un horario completo con estos datos"}, 400)
                elif ruta == "/api/evento":
                    tipo = p.pop("tipo")
                    Estado.orq.aplicar_evento(tipo, **p)
                elif ruta == "/api/sorpresa":
                    Estado.orq.aplicar_evento(**Estado.orq.sugerir_sorpresa())
                elif ruta == "/api/exportar":
                    os.makedirs(RES, exist_ok=True)
                    destino = os.path.join(RES, "horario.csv")
                    datos.guardar_horario(Estado.orq.ent, Estado.orq.g, destino)
                    return self._json({"ok": True, "ruta": destino})
                else:
                    return self._json({"error": "Ruta desconocida"}, 404)
                return self._json(Estado.orq.estado())
        except (ValueError, KeyError) as e:
            return self._json({"error": str(e)}, 400)


def servir(puerto=8000, abrir=True):
    nuevo_entorno()
    srv = ThreadingHTTPServer(("127.0.0.1", puerto), Manejador)
    url = f"http://127.0.0.1:{puerto}"
    print(f"Interfaz disponible en {url} (Ctrl+C para salir)")
    if abrir:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido")
        srv.server_close()
