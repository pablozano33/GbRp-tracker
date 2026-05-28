import requests
import json
import os
import datetime
import re
import time

# Corrección menor 1: Identidad para evitar bloqueos al "entrar" al mod
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def ejecutar_tracker(GAME_ID, WEBHOOK_URL, DATA_FILE):

    def cargar_historial():
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def guardar_historial(datos):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=4)

    def limpiar_texto(html):
        if not html: return ""
        clean = re.compile('<.*?>')
        texto = re.sub(clean, '', html)
        texto = texto.replace('&nbsp;', ' ').strip()
        
        basura_ui = ["Manage Collections", "Files", "File Info", "Archived Files", "Comments", "Embed", "Credits", "THANKS FOR:"]
        for palabra in basura_ui:
            if palabra in texto:
                texto = texto.split(palabra)[0].strip()
                
        return (texto[:300] + '...') if len(texto) > 300 else texto

    def enviar_discord(mod_resumen, tipo, model_name="Mod"):
        mod_id = mod_resumen.get("_idRow")
        nombre_mod = mod_resumen.get("_sName", "Mod")
        version = mod_resumen.get("_sVersion", "")
        categoria_url = model_name.lower() + "s"
        link = f"https://gamebanana.com/{categoria_url}/{mod_id}"
        
        if tipo == "Publicado":
            ts_fecha = mod_resumen.get("_tsDateAdded") or mod_resumen.get("_tsDateUpdated")
        else:
            ts_fecha = mod_resumen.get("_tsDateUpdated") or mod_resumen.get("_tsDateAdded")
            
        if not ts_fecha:
            ts_fecha = int(time.time())
            
        fecha_formateada = datetime.datetime.fromtimestamp(ts_fecha).strftime('%d/%m/%Y %H:%M')

        mod_completo = {}
        try:
            time.sleep(1.0)
            perfil_url = f"https://gamebanana.com/apiv11/{model_name}/{mod_id}/Profile"

            res = requests.get(perfil_url, headers=HEADERS)
            res.raise_for_status()
            mod_completo = res.json()

        except Exception as e:
            if hasattr(e, 'response') and e.response is not None and e.response.status_code == 404:
                print(f"GameBanana bloqueó la lectura del {model_name} {mod_id}. Enviando datos básicos a Discord...")

        descripcion_real = ""

        if tipo == "Actualizado":
            try:
                updates_url = f"https://gamebanana.com/apiv11/{model_name}/{mod_id}/Updates"
                time.sleep(0.5)
                res_upd = requests.get(updates_url, headers=HEADERS)

                if res_upd.status_code == 200:
                    updates_data = res_upd.json()

                    lista_upd = updates_data.get("_aRecords", []) if isinstance(updates_data, dict) else updates_data

                    if isinstance(lista_upd, list) and len(lista_upd) > 0:

                        upd = lista_upd[0]

                        titulo_upd = (
                            upd.get("_sTitle", "")
                            or upd.get("_sName", "")
                        ).strip()

                        texto_upd = (
                            upd.get("_sText", "")
                            or upd.get("_sDescription", "")
                        ).strip()

                        texto_limpio = limpiar_texto(texto_upd)

                        if titulo_upd and texto_limpio:
                            descripcion_real = f"**{titulo_upd}**\n{texto_limpio}"

                        elif titulo_upd:
                            descripcion_real = f"**{titulo_upd}**"

                        elif texto_limpio:
                            descripcion_real = texto_limpio

            except Exception:
                pass

            if not descripcion_real:
                descripcion_real = "*El autor actualizó los archivos pero no dejó notas del parche.*"

        else:

            descripcion_raw = (
                mod_completo.get("_sText")
                or mod_completo.get("_sDescription")
                or mod_resumen.get("_sDescription", "")
            )

            descripcion_real = limpiar_texto(descripcion_raw)

            if not descripcion_real or len(descripcion_real) < 10:

                try:
                    res_web = requests.get(
                        link,
                        headers=HEADERS,
                        timeout=10
                    )

                    match = re.search(
                        r'<meta property="og:description" content="(.*?)"',
                        res_web.text
                    )

                    if match:
                        descripcion_real = match.group(1)[:300]

                except:
                    pass

            if not descripcion_real:
                descripcion_real = "*Sin descripción disponible en la portada.*"


        titulo_alerta = (
            f"✨ ¡Nuevo {model_name} Publicado! | ¡New {model_name} Released! ✨"
            if tipo == "Publicado"
            else f"🔄 ¡{model_name} Actualizado! | ¡{model_name} Updated! 🔄"
        )

        color = 3066993 if tipo == "Publicado" else 15844367

        imagenes = mod_resumen.get("_aPreviewMedia", {}).get("_aImages", [])

        if not imagenes:
            imagenes = mod_completo.get("_aPreviewMedia", {}).get("_aImages", [])

        imagen_url = ""

        if imagenes and len(imagenes) > 0:

            base_url = imagenes[0].get("_sBaseUrl", "")
            archivo = imagenes[0].get("_sFile", "")

            if base_url and archivo:
                imagen_url = f"{base_url}/{archivo}"


        embed = {
            "title": f"{nombre_mod} {'['+version+']' if version else ''}"[:256],
            "url": link,
            "description": descripcion_real[:4000],
            "color": color,
            "footer": {
                "text": f"ID: {mod_id} • Date: {fecha_formateada}"
            }
        }

        if imagen_url:
            embed["image"] = {"url": imagen_url}

        data = {
            "content": f"**{titulo_alerta}**",
            "embeds": [embed]
        }

        res_discord = requests.post(
            WEBHOOK_URL,
            json=data
        )

        if res_discord.status_code >= 400:
            print(
                f"❌ Error enviando {model_name} {mod_id}: "
                f"{res_discord.status_code}"
            )
            return False

        time.sleep(2)
        return True


    mods = []

    for tipo_orden in ["new", "updated"]:

        for page in range(1, 11):

            url = (
                f"https://gamebanana.com/apiv11/Game/{GAME_ID}/Subfeed"
                f"?_nPage={page}"
                f"&_nPerpage=50"
                f"&_sSort={tipo_orden}"
                f"&_csvModelInclusions=Mod,Tool,Sound"
            )

            try:
                time.sleep(1)

                response = requests.get(
                    url,
                    headers=HEADERS
                )

                response.raise_for_status()

                records = response.json().get(
                    "_aRecords",
                    []
                )

                if not records:
                    break

                mods.extend(records)

            except Exception as e:
                print(
                    f"Error en página {page} "
                    f"(Orden: {tipo_orden}): {e}"
                )
                break


    historial = cargar_historial()

    nuevos_datos = historial.copy()

    hubo_cambios = False

    inicio_mes = datetime.datetime(
        datetime.datetime.now().year,
        datetime.datetime.now().month,
        1
    ).timestamp()


    for mod in mods:

        mod_id = str(mod.get("_idRow"))

        fecha_upd = mod.get("_tsDateUpdated") or 0

        fecha_add = mod.get("_tsDateAdded") or 0

        model_name = mod.get(
            "_sModelName",
            "Mod"
        )

        tipo_evento = (
            "Publicado"
            if fecha_upd == 0
            or abs(fecha_upd - fecha_add) < 60
            else "Actualizado"
        )


        if (
            mod_id not in nuevos_datos
            or nuevos_datos[mod_id]
            < (fecha_upd or fecha_add)
        ):

            enviado = True

            if not historial:

                if (
                    (fecha_upd or fecha_add)
                    >= inicio_mes
                ):
                    enviado = enviar_discord(
                        mod,
                        tipo_evento,
                        model_name
                    )

            else:
                enviado = enviar_discord(
                    mod,
                    tipo_evento,
                    model_name
                )

            if enviado is not False:

                nuevos_datos[mod_id] = (
                    fecha_upd
                    or fecha_add
                )

                hubo_cambios = True


    if hubo_cambios:
        guardar_historial(
            nuevos_datos
        )


if __name__ == "__main__":

    ejecutar_tracker(
        "7886",
        os.environ.get("DISCORD_WEBHOOK_MEGAMIX"),
        "historial-megamix.json"
    )

    ejecutar_tracker(
        "16522",
        os.environ.get("DISCORD_WEBHOOK_MEGAMIXPLUS"),
        "historial-megamixplus.json"
    )

    ejecutar_tracker(
        "23911",
        os.environ.get("DISCORD_WEBHOOK_TOMODACHILTD"),
        "historial-tomodachi.json"
    )
