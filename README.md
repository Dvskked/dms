# The Diamonds League

Portal web de The Diamonds League: sitio público (liga, pubs, museo, noticias,
live de fútbol, alianzas, redes, equipo y donación) y panel de administración
completo sobre Flask + SQLAlchemy.

## Requisitos

- Python 3.11 o superior
- `pip install -r requirements.txt`

## Puesta en marcha

```bash
python seed.py --force     # crea el esquema y carga los datos iniciales
python app.py              # http://127.0.0.1:5000
```

Cuenta inicial: `admin` / `adminmascapito`.

La configuración se lee de `.env` (plantilla en `.env.example`).

## Base de datos

SQLite por defecto en `instance/diamonds_league.db`. Para MySQL o PostgreSQL solo
hay que definir `DATABASE_URL`:

```bash
DATABASE_URL=mysql+pymysql://usuario:clave@127.0.0.1:3306/diamonds_league?charset=utf8mb4
DATABASE_URL=postgresql+psycopg://usuario:clave@127.0.0.1:5432/diamonds_league
```

### Migraciones (Flask-Migrate)

Mientras `AUTO_CREATE_TABLES=1` la app crea sola las tablas que falten, útil en
desarrollo. Con migraciones se trabaja con `AUTO_CREATE_TABLES=0`, de modo que el
esquema solo cambia por versiones:

```bash
# 1. Desactivar el autocompletado y apuntar a la base que se quiere migrar
set AUTO_CREATE_TABLES=0
set DATABASE_URL=sqlite:///C:/ruta/vacia/diamonds_league.db

# 2. Detectar los cambios del modelo y crear la revisión
flask --app app db migrate -m "descripcion del cambio"
flask --app app db upgrade

# 3. Si la base ya tenia las tablas (creadas con db.create_all) y coincide con
#    la revisión generada, marcarla sin volver a ejecutarla:
flask --app app db stamp head
```

Comandos disponibles: `db init`, `db migrate`, `db upgrade`, `db downgrade`,
`db current`, `db history`, `db stamp`.

Las revisiones viven en `migrations/versions/`. La revisión inicial cubre las
24 tablas del modelo.

### Comandos CLI

```bash
flask --app app init-db               # crea las tablas y el admin por defecto
flask --app app seed                  # carga los datos si la base esta vacia
flask --app app seed --force          # recarga los datos de la temporada
flask --app app create-admin usuario clave   # alta de otro administrador
```

## Estructura

| Ruta | Contenido |
| --- | --- |
| `app.py` | application factory, CLI, manejo de errores y filtros Jinja |
| `config.py` | configuración por entorno (`development`, `testing`, `production`) |
| `models.py` | modelos SQLAlchemy (24 tablas) |
| `forms.py` | formularios de auth y administración |
| `blueprints/site.py` | sitio público |
| `blueprints/auth.py` | registro, login, perfil, contraseña y Google |
| `blueprints/admin.py` | panel de administración (19 recursos) |
| `seed.py` | datos iniciales de la temporada |
| `migrations/` | revisiones de Alembic |
| `templates/`, `static/` | vistas, estilos y JavaScript |

## Verificación

```bash
python -m compileall -q .    # sintaxis
python smoke_test.py         # end-to-end sobre el cliente de pruebas
python http_test.py          # servidor WSGI real y rutas publicas
python html_check.py         # ids duplicados y balance de etiquetas
python check_css.py          # clases HTML sin regla CSS y balance de llaves
```

`smoke_test.py` crea, edita, duplica y elimina registros de prueba, y limpia
todos sus residuos al terminar.

## Contraseñas

`STORE_PASSWORDS_PLAINTEXT=1` guarda las contraseñas en texto plano porque es un
requisito explícito del cliente. Con `STORE_PASSWORDS_PLAINTEXT=0` se almacenan
como hash `pbkdf2:sha256` sin cambiar el modelo ni las vistas.
