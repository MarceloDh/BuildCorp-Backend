import re
from itertools import cycle

from django.core.exceptions import ValidationError


def rut_normalizado(valor):
    rut = str(valor).upper().replace(".", "").replace(" ", "")
    if not re.fullmatch(r"[0-9]{7,8}-?[0-9K]", rut):
        raise ValidationError("Escribe un RUT válido, por ejemplo 12.345.678-5.")
    cuerpo, verificador = rut.replace("-", "")[:-1], rut[-1]
    suma = sum(int(digito) * peso for digito, peso in zip(reversed(cuerpo), cycle(range(2, 8))))
    resto = 11 - suma % 11
    esperado = {11: "0", 10: "K"}.get(resto, str(resto))
    if verificador != esperado:
        raise ValidationError("El dígito verificador del RUT no es correcto.")
    return f"{cuerpo}-{verificador}"
