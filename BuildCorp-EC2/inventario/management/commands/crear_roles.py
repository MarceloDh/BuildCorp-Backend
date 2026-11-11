from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from inventario.access import OPERADOR, SUPERVISOR


class Command(BaseCommand):
    help = "Crea los grupos Bodega y Supervisión para asignarlos a cuentas de personal."

    def handle(self, *args, **options):
        for nombre in (OPERADOR, SUPERVISOR):
            Group.objects.get_or_create(name=nombre)
        self.stdout.write(self.style.SUCCESS("Grupos disponibles: Bodega y Supervisión."))
