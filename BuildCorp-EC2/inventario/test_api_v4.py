from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import identify_hasher
from django.contrib.auth.models import Group
from django.test import override_settings
from rest_framework.test import APITestCase
from unittest.mock import patch

from .access import OPERADOR, SUPERVISOR
from .models import Activo, Mantenimiento, Obra


@override_settings(SIMPLE_JWT={"SIGNING_KEY": "clave-exclusiva-para-pruebas-automatizadas"})
class InventarioV4Tests(APITestCase):
    base = "/api/v4/"
    password = "BuildCorp_Prueba_410!"

    @classmethod
    def setUpTestData(cls):
        for nombre, rol in (("supervision", SUPERVISOR), ("bodega", OPERADOR), ("sin_rol", None)):
            usuario = get_user_model().objects.create_user(nombre, password=cls.password)
            if rol:
                usuario.groups.add(Group.objects.create(name=rol))

    def autenticar(self, nombre="supervision"):
        self.client.credentials()
        respuesta = self.client.post(self.base + "token/", {"username": nombre, "password": self.password})
        self.assertEqual(respuesta.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + respuesta.data["access"])
        return respuesta.data

    def crear(self, recurso, datos):
        respuesta = self.client.post(self.base + recurso + "/", datos, format="json")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(respuesta["Content-Type"], "application/json")
        return respuesta.data["id"]

    def test_crud_retiene_las_relaciones_y_verifica_persistencia(self):
        self.autenticar()
        obra = self.crear("obras", {"nombre": "Obra central", "direccion": "Santiago"})
        bodega = self.crear("bodegas", {"nombre": "Bodega norte", "obra": obra})
        activo = self.crear("herramientas", {"codigo": "E4-001", "nombre": "Taladro", "bodega": bodega})
        mantencion = self.crear("mantenimientos", {"activo": activo, "tarea": "Inspección", "horas_limite": 60})
        for recurso, pk, modificacion in (
            ("obras", obra, {"direccion": "Providencia"}),
            ("bodegas", bodega, {"nombre": "Bodega A"}),
            ("herramientas", activo, {"nombre": "Taladro industrial", "horas_uso": 900}),
            ("mantenimientos", mantencion, {"observaciones": "Revisar brocas"}),
        ):
            url = f"{self.base}{recurso}/{pk}/"
            self.assertEqual(self.client.patch(url, modificacion, format="json").status_code, 200)
            resultado = self.client.get(url)
            self.assertEqual(resultado.status_code, 200)
            campo = next(iter(modificacion))
            self.assertEqual(resultado.data[campo], modificacion[campo])
        resultado = self.client.put(f"{self.base}obras/{obra}/", {"nombre": "Obra A", "direccion": "Santiago"})
        self.assertEqual(resultado.status_code, 200)
        self.assertEqual(Obra.objects.get(pk=obra).nombre, "Obra A")
        self.assertEqual(Activo.objects.get(pk=activo).horas_uso, 0)
        self.assertEqual(Mantenimiento.objects.get(pk=mantencion).activo_id, activo)
        self.assertEqual(self.client.delete(f"{self.base}obras/{obra}/").status_code, 409)
        for recurso, pk in (("mantenimientos", mantencion), ("herramientas", activo), ("bodegas", bodega), ("obras", obra)):
            self.assertEqual(self.client.delete(f"{self.base}{recurso}/{pk}/").status_code, 204)
            self.assertEqual(self.client.get(f"{self.base}{recurso}/{pk}/").status_code, 404)

    def test_jwt_roles_renovacion_y_hash(self):
        url = self.base + "obras/"
        self.assertEqual(self.client.get(url).status_code, 401)
        tokens = self.autenticar("bodega")
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url, {}).status_code, 403)
        self.autenticar("sin_rol")
        self.assertEqual(self.client.get(url).status_code, 403)
        renovacion = self.client.post(self.base + "token/refresh/", {"refresh": tokens["refresh"]})
        self.assertEqual(renovacion.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + renovacion.data["access"])
        self.assertEqual(self.client.get(self.base + "perfil/").data["usuario"], "bodega")
        usuario = get_user_model().objects.get(username="bodega")
        self.assertNotEqual(usuario.password, self.password)
        self.assertEqual(identify_hasher(usuario.password).algorithm, "pbkdf2_sha256")
        self.assertTrue(usuario.check_password(self.password))

    def test_validaciones_y_recurso_s3(self):
        self.autenticar()
        self.assertEqual(self.client.post(self.base + "obras/", {"nombre": "Incompleta"}).status_code, 400)
        obra = self.crear("obras", {"nombre": "Obra A", "direccion": "Santiago"})
        bodega = self.crear("bodegas", {"nombre": "Bodega A", "obra": obra})
        activo = self.crear("herramientas", {"codigo": "E4-001", "nombre": "Taladro", "bodega": bodega})
        url = self.base + "mantenimientos/"
        self.assertEqual(self.client.post(url, {"activo": activo, "tarea": "Sin umbral"}).status_code, 400)
        self.assertEqual(self.client.post(url, {"activo": activo, "tarea": "Umbral erróneo", "horas_limite": 0}).status_code, 400)
        mantencion = self.crear("mantenimientos", {"activo": activo, "tarea": "Inspección", "horas_limite": 50})
        Mantenimiento.objects.filter(pk=mantencion).update(estado=Mantenimiento.Estado.COMPLETADO)
        url += f"{mantencion}/"
        self.assertEqual(self.client.patch(url, {"tarea": "Cambio"}, format="json").status_code, 400)
        self.assertEqual(self.client.delete(url).status_code, 409)
        guia = self.base + "recursos/guia/"
        self.assertEqual(self.client.get(guia).status_code, 503)
        with self.settings(RECURSOS_BUCKET="bucket-pruebas"), patch("inventario.api_v4.boto3.client") as cliente:
            firma = cliente.return_value.generate_presigned_url
            firma.return_value = "https://example.com/guia"
            self.assertEqual(self.client.get(guia).status_code, 200)
            firma.assert_called_once_with(
                "get_object", Params={"Bucket": "bucket-pruebas", "Key": "recursos/guia-inventario.txt"}, ExpiresIn=120,
            )

    @override_settings(CORS_ALLOWED_ORIGINS=["http://127.0.0.1:5173"])
    def test_cors_restringido_al_frontend(self):
        for origen, esperado in (("http://127.0.0.1:5173", "http://127.0.0.1:5173"), ("https://otro.example", None)):
            respuesta = self.client.options(
                self.base + "obras/", HTTP_ORIGIN=origen, HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            )
            self.assertEqual(respuesta.get("Access-Control-Allow-Origin"), esperado)

    def test_portada_solo_acepta_metodos_de_lectura(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.head("/").status_code, 200)
        self.assertEqual(self.client.post("/").status_code, 405)

    def test_clientes_prestamos_y_traslados_v4(self):
        self.autenticar()
        obra = self.crear("obras", {"nombre": "Obra Sur", "direccion": "Av. Matta 100"})
        bod1 = self.crear("bodegas", {"nombre": "Bodega 1", "obra": obra})
        bod2 = self.crear("bodegas", {"nombre": "Bodega 2", "obra": obra})
        herr = self.crear("herramientas", {"codigo": "CLI-01", "nombre": "Taladro", "bodega": bod1})
        cli = self.crear("clientes", {"nombre": "Constructora Sur", "identificador": "76.123.456-7"})

        tr = self.client.post(self.base + "traslados/", {"activo": herr, "destino": bod2}, format="json")
        self.assertEqual(tr.status_code, 201)
        self.assertEqual(Activo.objects.get(pk=herr).bodega_id, bod2)

        pr = self.client.post(self.base + "prestamos/", {
            "activo": herr, "contratista": cli, "vence_en": "2099-01-01T18:00:00Z",
            "responsable_entrega": "Juan Pérez", "firma_entrega": "JP",
        }, format="json")
        self.assertEqual(pr.status_code, 201)
        self.assertEqual(Activo.objects.get(pk=herr).estado, Activo.Estado.EN_USO)

        dev = self.client.post(f"{self.base}prestamos/{pr.data['id']}/devolver/", {
            "horas_utilizadas": 12, "responsable_devolucion": "Juan Pérez", "firma_devolucion": "JP",
        }, format="json")
        self.assertEqual(dev.status_code, 200)
        self.assertEqual(Activo.objects.get(pk=herr).estado, Activo.Estado.DISPONIBLE)
        self.assertEqual(Activo.objects.get(pk=herr).horas_uso, 12)
