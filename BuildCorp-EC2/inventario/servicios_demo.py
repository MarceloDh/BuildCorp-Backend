import unicodedata


def pesos(monto):
    return "$" + f"{monto:,}".replace(",", ".")


def normalizar(texto):
    return "".join(
        letra for letra in unicodedata.normalize("NFD", texto.casefold())
        if not unicodedata.combining(letra)
    )


CATEGORIAS_SERVICIOS = (
    {"codigo": "herramientas", "categoria": "Herramientas"},
    {"codigo": "maquinaria", "categoria": "Maquinaria"},
    {"codigo": "traslado", "categoria": "Logística"},
)

