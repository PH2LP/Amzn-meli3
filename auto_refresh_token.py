import os
import requests
from dotenv import dotenv_values

# ======================================================
# 🔄 AUTO REFRESH TOKEN MERCADO LIBRE
# ======================================================

def refresh_token():
    print("🔄 Renovando access token de Mercado Libre...")

    env_path = ".env"
    env = dotenv_values(env_path)

    client_id = env.get("ML_CLIENT_ID")
    client_secret = env.get("ML_CLIENT_SECRET")
    refresh_token = env.get("ML_REFRESH_TOKEN")

    if not client_id or not client_secret or not refresh_token:
        print("❌ Faltan credenciales en el archivo .env")
        return

    url = "https://api.mercadolibre.com/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token
    }

    try:
        r = requests.post(url, data=payload, timeout=10)
        r.raise_for_status()
        data = r.json()

        new_access_token = data["access_token"]
        new_refresh_token = data.get("refresh_token", refresh_token)

        # === Actualizar el archivo .env ===
        with open(env_path, "r") as f:
            lines = f.readlines()
        new_lines = []
        for line in lines:
            if line.startswith("ML_ACCESS_TOKEN="):
                new_lines.append(f"ML_ACCESS_TOKEN={new_access_token}\n")
            elif line.startswith("ML_REFRESH_TOKEN="):
                new_lines.append(f"ML_REFRESH_TOKEN={new_refresh_token}\n")
            else:
                new_lines.append(line)
        with open(env_path, "w") as f:
            f.writelines(new_lines)

        print("✅ Token renovado correctamente.")
        print(f"🆕 Nuevo access_token: {new_access_token[:40]}...")
        print(f"♻️ Nuevo refresh_token: {new_refresh_token[:40]}...")
        print("💾 Archivo .env actualizado automáticamente.")

        # === Exportar automáticamente las variables al entorno ===
        print("🌎 Exportando nuevas variables de entorno...")
        os.environ["ML_ACCESS_TOKEN"] = new_access_token
        os.environ["ML_REFRESH_TOKEN"] = new_refresh_token

        # También actualiza las variables del shell actual (solo si usás bash/zsh)
        shell = os.getenv("SHELL", "")
        if "bash" in shell or "zsh" in shell:
            os.system("export $(grep -v '^#' .env | xargs)")
            print("✅ Variables exportadas al entorno del shell.")
        else:
            print("⚠️ Entorno no interactivo, export omitido (solo memoria Python).")

    except Exception as e:
        print(f"❌ Error al renovar token: {e}")


if __name__ == "__main__":
    refresh_token()