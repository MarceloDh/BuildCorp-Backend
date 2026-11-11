from django.core.management.base import BaseCommand
from django.db import transaction

from inventario.models import Activo, Bodega, Obra, Servicio


class Command(BaseCommand):
    help = "Agrega dos unidades ficticias por servicio de equipo para practicar el flujo local."

    @transaction.atomic
    def handle(self, *args, **options):
        obra, _ = Obra.objects.get_or_create(nombre="Obra de demostración", defaults={"direccion": "Dirección de prueba"})
        bodega, _ = Bodega.objects.get_or_create(obra=obra, nombre="Bodega de demostración")
        creados = 0
        for servicio in Servicio.objects.exclude(categoria="Logística"):
            for unidad in (1, 2):
                _, nuevo = Activo.objects.get_or_create(
                    codigo=f"DEMO-{servicio.pk:03}-{unidad}",
                    defaults={"nombre": servicio.nombre, "bodega": bodega, "servicio": servicio},
                )
                creados += nuevo
        self.stdout.write(self.style.SUCCESS(f"{creados} unidades de demostración agregadas."))
