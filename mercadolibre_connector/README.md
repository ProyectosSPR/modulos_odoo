# Mercado Libre Connector - Odoo 16

Módulo de integración completa con Mercado Libre para Odoo 16 con soporte multi-empresa y multi-tienda.

## 🚀 Características

### ✅ Autenticación OAuth 2.0
- Flujo completo de autorización OAuth
- Refresh automático de tokens cada 30 minutos
- Auto-retry en errores 401 (token expirado)
- Health status de tokens (healthy, warning, critical)

### ✅ Multi-Empresa y Multi-Tienda
- Múltiples configuraciones por empresa
- Múltiples cuentas de ML por empresa
- Soporte para todos los sitios de ML (MLM, MLA, MLB, etc.)

### ✅ Sistema de Invitaciones por Email
- Envío de invitaciones para conectar cuentas
- Tracking completo (enviada, abierta, completada)
- Emails de confirmación automáticos
- Expiración automática de invitaciones

### ✅ Sistema de Logs Robusto
- 6 tipos de logs (auth, api_request, api_response, error, email, cron, system)
- 5 niveles (debug, info, warning, error, critical)
- Registro de requests/responses completos
- Stack traces en errores
- Limpieza automática de logs antiguos (90+ días)

### ✅ API Playground
- Editor interactivo para probar endpoints de ML
- Soporte para GET, POST, PUT, DELETE
- Headers, Body y Query Params personalizables
- Autorización automática
- Historial de ejecuciones
- Templates predefinidos

### ✅ Seguridad
- 3 niveles de permisos (Usuario, Manager, Admin)
- Reglas multi-company
- Campos sensibles protegidos (password)
- Tokens encriptados en grupos específicos

## 📦 Instalación

### 1. Copiar el módulo
```bash
cp -r mercadolibre_connector /path/to/odoo/addons/
```

### 2. Actualizar lista de módulos
```bash
# Desde Odoo
Aplicaciones > Actualizar Lista de Aplicaciones

# O desde línea de comandos
odoo-bin -u mercadolibre_connector -d tu_base_datos
```

### 3. Instalar el módulo
```
Aplicaciones > Buscar "Mercado Libre" > Instalar
```

### 4. Dependencias Python
```bash
pip install requests
```

## ⚙️ Configuración Inicial

### 1. Crear Aplicación en Mercado Libre

1. Ve a https://developers.mercadolibre.com/
2. Crea una nueva aplicación
3. Configura la URL de redirección: `https://tudominio.com/mercadolibre/callback`
4. Obtén tu `Client ID` y `Client Secret`

### 2. Configurar en Odoo

1. Ve a: **Mercado Libre > Configuración > Aplicaciones ML**
2. Crea un nuevo registro:
   - **Nombre**: ML México - Producción
   - **Empresa**: Selecciona tu empresa
   - **Sitio ML**: MLM (México)
   - **Client ID**: Pega tu App ID
   - **Client Secret**: Pega tu Secret
   - **Redirect URI**: `https://tudominio.com/mercadolibre/callback`

## 📱 Conectar Cuentas de Mercado Libre

### Método 1: Invitación por Email (Recomendado)

1. Ve a: **Mercado Libre > Invitaciones**
2. Click en **Crear**
3. Completa:
   - **Configuración**: Selecciona la configuración creada
   - **Email**: Email del destinatario
   - **Nombre Destinatario**: Nombre de la persona
   - **Expira el**: Fecha de expiración (default: 7 días)
4. Click en **Enviar Invitación**
5. El destinatario recibirá un email con un link
6. Al hacer click, será redirigido a Mercado Libre para autorizar
7. Una vez autorizado, la cuenta se conectará automáticamente

### Método 2: Directo (Para Administradores)

1. Ve a: **Mercado Libre > Mis Cuentas**
2. Click en **Crear**
3. Selecciona la configuración
4. Click en **Conectar Cuenta**
5. Serás redirigido a Mercado Libre
6. Autoriza la aplicación
7. Tu cuenta quedará conectada

## 🔄 Gestión de Tokens

### Refresh Automático

- **Cron ejecuta cada 30 minutos**
- Busca tokens que expiren en menos de 30 minutos
- Refresca automáticamente usando `refresh_token`
- Logs completos en cada refresh
- Notificaciones en el chatter de la cuenta

### Refresh Manual

1. Ve a la cuenta: **Mercado Libre > Mis Cuentas > [Cuenta]**
2. Click en **Refrescar Token**

### Health Status

- 🟢 **Healthy**: Token válido, sin errores
- 🟡 **Warning**: Próximo a expirar (<30 min) o errores recientes
- 🔴 **Critical**: Expirado o múltiples errores consecutivos
- ⚫ **Disabled**: Auto-refresh desactivado

## 🎮 Usar API Playground

1. Ve a: **Mercado Libre > Herramientas > API Playground**
2. Click en **Crear**
3. Completa:
   - **Nombre**: Obtener mis órdenes
   - **Cuenta**: Selecciona tu cuenta
   - **Método HTTP**: GET
   - **Endpoint**: `/orders/search`
   - **Query Params** (pestaña):
     ```json
     {
       "seller": "TU_USER_ID",
       "sort": "date_desc",
       "limit": 50
     }
     ```
4. Click en **Ejecutar Request**
5. La respuesta aparecerá en la pestaña **Response**

### Templates Disponibles

El playground incluye templates para:
- Obtener info de usuario (`/users/me`)
- Buscar órdenes (`/orders/search`)
- Obtener producto (`/items/{id}`)
- Buscar preguntas (`/questions/search`)

## 📊 Ver Logs

### Logs en Tiempo Real

1. Ve a: **Mercado Libre > Herramientas > Logs**
2. Usa los filtros:
   - **Hoy**: Logs de hoy
   - **Errores**: Solo errores y críticos
   - **Advertencias**: Solo warnings
   - **API Requests**: Requests a ML API
   - **Token Refresh**: Refreshes de tokens

### Logs de una Cuenta Específica

1. Ve a: **Mercado Libre > Mis Cuentas > [Cuenta]**
2. Click en **Ver Logs**

## 🔐 Grupos de Seguridad

### Usuario
- Ver y gestionar sus propias cuentas
- Usar el playground
- Ver logs

### Manager
- Todo lo de Usuario
- Ver/gestionar todas las cuentas de su empresa
- Crear y enviar invitaciones
- Ver tokens (sin Client Secret)
- Refrescar tokens manualmente

### Administrador
- Acceso total
- Crear/editar configuraciones
- Ver Client Secrets
- Acceso a todas las empresas

## 🛠️ Uso Programático

### Hacer Requests a ML API

```python
# Desde cualquier modelo

# GET simple
http = self.env['mercadolibre.http']
result = http.get(
    account_id=account.id,
    endpoint='/users/me'
)

if result['success']:
    user_data = result['data']
    print(f"Nickname: {user_data['nickname']}")
else:
    print(f"Error: {result['error']}")

# POST con body
result = http.post(
    account_id=account.id,
    endpoint='/items',
    body={
        'title': 'Producto nuevo',
        'price': 100,
        'category_id': 'MLM1234',
        # ...
    }
)

# Request completo
result = http._request(
    account_id=account.id,
    endpoint='/items',
    method='PUT',
    body={'price': 150},
    params={'item_id': 'MLM123'},
    retry_on_401=True,  # Auto-retry si token expirado
    log_request=True    # Guardar en logs
)
```

### Crear Logs Manualmente

```python
self.env['mercadolibre.log'].create({
    'account_id': account.id,
    'log_type': 'system',
    'level': 'info',
    'operation': 'sync_orders',
    'message': 'Sincronizadas 10 órdenes nuevas',
    'company_id': account.company_id.id,
    'user_id': self.env.user.id,
})

# O usar el helper
self.env['mercadolibre.log'].log_api_call(
    account_id=account.id,
    endpoint='/orders/search',
    method='GET',
    response_data=orders_data,
    status_code=200,
    response_time=0.5
)
```

## 🔧 Crons Configurados

### 1. Refresh Tokens
- **Frecuencia**: Cada 30 minutos
- **Modelo**: `mercadolibre.token`
- **Método**: `_cron_refresh_tokens()`

### 2. Expirar Invitaciones
- **Frecuencia**: Cada día
- **Modelo**: `mercadolibre.invitation`
- **Método**: `_cron_expire_invitations()`

### 3. Limpiar Logs Antiguos
- **Frecuencia**: Cada semana
- **Modelo**: `mercadolibre.log`
- **Método**: `_cron_clean_old_logs()`

## 📝 Estructura del Módulo

```
mercadolibre_connector/
├── __manifest__.py
├── models/
│   ├── mercadolibre_config.py         # Configuración de apps ML
│   ├── mercadolibre_account.py        # Cuentas conectadas
│   ├── mercadolibre_token.py          # Tokens OAuth
│   ├── mercadolibre_invitation.py     # Invitaciones por email
│   ├── mercadolibre_log.py            # Sistema de logs
│   ├── mercadolibre_api_playground.py # Playground
│   └── mercadolibre_http.py           # HTTP Wrapper
├── controllers/
│   └── main.py                         # OAuth callbacks
├── views/
│   ├── mercadolibre_config_views.xml
│   ├── mercadolibre_account_views.xml
│   ├── mercadolibre_invitation_views.xml
│   ├── mercadolibre_log_views.xml
│   ├── mercadolibre_playground_views.xml
│   ├── mercadolibre_menus.xml
│   └── templates.xml
├── security/
│   ├── mercadolibre_security.xml       # Grupos
│   ├── ir.model.access.csv            # Permisos
│   └── mercadolibre_rules.xml         # Reglas multi-company
└── data/
    ├── ir_cron.xml
    ├── mail_template_invitation.xml
    ├── mail_template_connected.xml
    └── mercadolibre_playground_templates.xml
```

## 🐛 Troubleshooting

### Error: "Invitación no encontrada"
- Verifica que el link no haya expirado
- Verifica que la invitación no haya sido cancelada

### Error 401 en API Requests
- El token está expirado
- Click en "Refrescar Token" manualmente
- Verifica que el cron esté activo

### El cron no ejecuta
- Verifica que el cron esté activo: Configuración > Acciones Programadas
- Busca "ML: Refresh Tokens"
- Verifica que no haya errores en logs

### No llegan los emails
- Verifica la configuración del servidor de correo en Odoo
- Ve a: Configuración > Técnico > Email > Servidores de Correo Saliente

## 📞 Soporte

Para reportar bugs o solicitar features, contacta al administrador del sistema.

## 📄 Licencia

LGPL-3

## 👨‍💻 Autor

Tu Empresa

---

**Versión**: 16.0.1.0.0
**Compatible con**: Odoo 16.0
**Última actualización**: 2025-12-17
