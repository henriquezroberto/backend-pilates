from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks # <- Agrega BackgroundTasks
import requests # <--- DEBE ESTAR SOLITO EN SU PROPIA LÍNEA
import os
from pydantic import BaseModel
from sqlalchemy.orm import Session
import models
from database import engine, SessionLocal
from typing import List, Optional  # <--- ASEGÚRATE DE QUE ESTÉ "Optional"
from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, Boolean
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
from urllib import request as urllib_request, error as urllib_error


# Función para crear los planes si la tabla está vacía
def inicializar_planes(db: Session):
    if db.query(models.Plan).count() == 0:
        planes_iniciales = [
            # Mensuales (30 días)
            {"nombre": "Mensual Opción 1 (4 clases)", "duracion": 30, "limite": 4},
            {"nombre": "Mensual Opción 2 (8 clases)", "duracion": 30, "limite": 8},
            {"nombre": "Mensual Opción 3 (12 clases)", "duracion": 30, "limite": 12},
            {"nombre": "Mensual Opción 4 (Ilimitado)", "duracion": 30, "limite": 999},
            # Trimestrales (90 días)
            {"nombre": "Trimestral Opción 1 (12 clases)", "duracion": 90, "limite": 12},
            {"nombre": "Trimestral Opción 2 (24 clases)", "duracion": 90, "limite": 24},
            {"nombre": "Trimestral Opción 3 (36 clases)", "duracion": 90, "limite": 36},
            {"nombre": "Trimestral Opción 4 (Ilimitado)", "duracion": 90, "limite": 999},
            # Semestrales (180 días)
            {"nombre": "Semestral Opción 1 (24 clases)", "duracion": 180, "limite": 24},
            {"nombre": "Semestral Opción 2 (48 clases)", "duracion": 180, "limite": 48},
            {"nombre": "Semestral Opción 3 (72 clases)", "duracion": 180, "limite": 72},
            {"nombre": "Semestral Opción 4 (Ilimitado)", "duracion": 180, "limite": 999},
        ]
        for p in planes_iniciales:
            nuevo_plan = models.Plan(nombre=p["nombre"], duracion_dias=p["duracion"], limite_clases=p["limite"])
            db.add(nuevo_plan)
        db.commit()

## ¡¡IMPORTANTE!!: LLAMA A ESTA FUNCIÓN EN EL EVENTO DE INICIO DE LA APP (Lifespan) PARA QUE SE EJECUTE AUTOMÁTICAMENTE CUANDO LE DES AL BOTÓN DE RUN
def enviar_correo_bienvenida(email_destino: str, nombre: str, contrasena: str, rol: str):
    # Ahora Python buscará la llave en el servidor, no en el código
    api_key = os.getenv("BREVO_API_KEY")

    # --- NUESTRO CHISMOSO ---
    if not api_key:
        print("¡ALERTA! Python dice que la llave de Brevo está vacía o no existe en Render.")
    else:
        print("Python sí leyó una llave, el problema es que a Brevo no le gusta esa llave.")
    # ------------------------
    
    # 2. Configuramos la URL de Brevo y los permisos
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }
    
    # 3. Armamos el correo (ahora usamos HTML para que se vea elegante)
    # Cambia "contactocentropilates@gmail.com" por el correo con el que te registraste en Brevo
    data = {
        "sender": {"name": "Centro Pilates Pilocas", "email": "contactocentropilates@gmail.com"}, 
        "to": [{"email": email_destino, "name": nombre}],
        "subject": "¡Bienvenido a Centro Pilates Pilocas! - Tus accesos",
        "htmlContent": f"""
        <div style="font-family: Arial, sans-serif; color: #333;">
            <h2 style="color: #00796B;">¡Bienvenido a Centro Pilates Pilocas!</h2>
            <p>Hola <b>{nombre}</b>,</p>
            <p>Tu cuenta de <strong>{rol}</strong> ha sido creada exitosamente.</p>
            <p>Descarga nuestra aplicación e ingresa con las siguientes credenciales:</p>
            <div style="background-color: #f5f5f5; padding: 15px; border-radius: 8px;">
                <p><b>Email:</b> {email_destino}</p>
                <p><b>Contraseña temporal:</b> {contrasena}</p>
            </div>
            <p><small>Te recomendamos cambiar tu contraseña una vez que ingreses a la aplicación.</small></p>
            <p>Saludos,<br>El equipo de Centro Pilates Pilocas</p>
        </div>
        """
    }
    
    # 4. Enviamos el correo usando el tráfico web normal (puerto abierto)
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code in [200, 201]:
            print(f"Correo enviado exitosamente a {email_destino} vía Brevo")
        else:
            print(f"Error de Brevo: {response.text}")
    except Exception as e:
        print(f"Excepción al intentar enviar correo a {email_destino}: {e}")

# ESTRUCTURAS DE DATOS PARA ADMINISTRADORES
class DatosAdmin(BaseModel):
    nombre: str
    email: str
    password: str
    telefono: Optional[str] = None # <-- AGREGAR ESTA LÍNEA

class DatosRegistro(BaseModel):
    nombre: str
    email: str
    password: str
    telefono: Optional[str] = None # <-- AGREGAR ESTA LÍNEA

class ReservaCreate(BaseModel):
    usuario_id: int
    clase_id: int

class CambioPassword(BaseModel):
    usuario_id: int
    password_actual: str
    password_nueva: str

# NUEVO MOLDE PARA EDITAR PROFESOR
class DatosProfesor(BaseModel):
    nombre: Optional[str] = None
    email: Optional[str] = None
    especialidad: Optional[str] = None # Flutter lo envía, pero lo ignoraremos en la BD por ahora
    telefono: Optional[str] = None # <-- AGREGAR ESTA LÍNEA

# 1. ¡La magia! Esta línea crea el archivo de la base de datos y las tablas automáticamente
models.Base.metadata.create_all(bind=engine)

# app = FastAPI(title="API Centro Pilates")  # Reemplazado por la versión con lifespan arriba

# 2. Función auxiliar para abrir y cerrar la conexión a la base de datos en cada petición
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 3. Estructuras de datos que esperamos recibir desde la App de Flutter
class LoginData(BaseModel):
    email: str
    password: str

class RegistroData(BaseModel):
    nombre: str
    email: str
    password: str

class ReservaData(BaseModel):
    usuario_id: int
    clase_id: int

# Llama a esta función dentro del evento de inicio usando el nuevo lifespan handler
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    inicializar_planes(db)
    db.close()
    yield

app = FastAPI(title="API Centro Pilates", lifespan=lifespan)

@app.get("/historial/{usuario_id}")
def obtener_historial(usuario_id: int, db: Session = Depends(get_db)):
    reservas = db.query(models.Reserva).filter(models.Reserva.usuario_id == usuario_id).all()
    historial = []
    for r in reservas:
        clase = db.query(models.Clase).filter(models.Clase.id == r.clase_id).first()
        if clase:
            historial.append({
                "nombre": clase.nombre,
                "fecha": clase.fecha,
                "hora": clase.hora,
                "disciplina": clase.disciplina
            })
    return historial

@app.put("/quitar-plan/{usuario_id}")
def quitar_plan(usuario_id: int, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Reseteamos los valores a cero/nulo
    usuario.plan_id = None
    usuario.clases_restantes = 0
    usuario.fecha_vencimiento_plan = None
    
    db.commit()
    return {"mensaje": "Plan removido exitosamente"}

# 4. NUEVO: Endpoint para registrar un usuario
@app.post("/registro")
def registrar_usuario(datos: DatosRegistro, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    usuario_existente = db.query(models.Usuario).filter(models.Usuario.email == datos.email).first()
    if usuario_existente:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")
    
    # Hemos quitado la línea de 'membresia'
    nuevo_usuario = models.Usuario(
        nombre=datos.nombre,
        email=datos.email,
        password=datos.password, 
        rol="alumno",
        telefono=datos.telefono
    )
    
    db.add(nuevo_usuario)
    try:
        db.commit()
        
        # ---> NUEVO: Programamos el envío del correo justo después de guardar exitosamente
        background_tasks.add_task(
            enviar_correo_bienvenida,
            email_destino=datos.email,
            nombre=datos.nombre,
            contrasena=datos.password,
            rol="Alumno"
        )
        
        return {"mensaje": "Usuario registrado exitosamente y correo enviado"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error al crear el usuario")

# 5. ACTUALIZADO: Endpoint de Login conectado a la base de datos
@app.post("/login")
def validar_login(datos: LoginData, db: Session = Depends(get_db)):
    correo_limpio = datos.email.lower().strip()
    
    usuario = db.query(models.Usuario).filter(
        models.Usuario.email == correo_limpio,
        models.Usuario.password == datos.password
    ).first()
    
    if usuario:
        return {
            "mensaje": "Login exitoso", 
            "usuario": {
                "id": usuario.id, 
                "nombre": usuario.nombre, 
                "rol": usuario.rol,
                "plan_id": usuario.plan_id # <- Ahora enviamos de forma segura el ID de su plan
            }
        }
    
    raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")

# 6. Estructura para recibir datos de una nueva clase
# 6. Estructura para recibir datos de una nueva clase
class ClaseData(BaseModel):
    nombre: str
    fecha: str
    hora: str
    cupo_maximo: int
    profesor_id: int
    disciplina: str = "General" # <- Cambiamos nivel_requerido por disciplina

# 7. Endpoint para crear una clase nueva
@app.post("/clases")
def crear_clase(datos: ClaseData, db: Session = Depends(get_db)):
    # 1. Buscamos al profesor en la base de datos
    profe = db.query(models.Usuario).filter(models.Usuario.id == datos.profesor_id).first()
    
    # 2. VALIDACIÓN DE SEGURIDAD: Si existe pero está apagado, frenamos todo
    if profe and not profe.activo:
        raise HTTPException(
            status_code=400, 
            detail=f"El profesor {profe.nombre} está inactivo y no puede dictar clases."
        )

    # 3. Si pasó la validación, creamos la clase (tu código original)
    nueva_clase = models.Clase(
        nombre=datos.nombre,
        fecha=datos.fecha,
        hora=datos.hora,
        cupo_maximo=datos.cupo_maximo,
        profesor_id=datos.profesor_id,
        disciplina=datos.disciplina # <- Corregido aquí
    )
    db.add(nueva_clase)
    db.commit()
    db.refresh(nueva_clase)
    
    return {"mensaje": "Clase creada exitosamente", "clase": nueva_clase}

# 8. Endpoint para que la app lea todas las clases disponibles
# Modificamos para traer el nombre del profesor directamente
# 1. Actualización para ver el nombre del profesor en la lista general
@app.get("/clases")
def obtener_clases(db: Session = Depends(get_db)):
    try:
        clases = db.query(models.Clase).all()
        resultado = []
        for c in clases:
            # Buscamos al profesor en la tabla de Usuarios
            profesor = db.query(models.Usuario).filter(models.Usuario.id == c.profesor_id).first()
            
            resultado.append({
                "id": c.id,
                "nombre": c.nombre,
                "fecha": c.fecha,
                "hora": c.hora,
                "cupo_maximo": c.cupo_maximo,
                "disciplina": c.disciplina,
                "profesor_id": c.profesor_id,
                "profesor_nombre": profesor.nombre if profesor else "Por asignar"
            })
        return resultado
    except Exception as e:
        print(f"Error al listar clases: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener la lista de clases")

# Nuevo endpoint para editar datos de la clase (como el profesor)
@app.put("/clases/{clase_id}")
def actualizar_clase(clase_id: int, datos: dict, db: Session = Depends(get_db)):
    clase = db.query(models.Clase).filter(models.Clase.id == clase_id).first()
    if not clase:
        raise HTTPException(status_code=404, detail="Clase no encontrada")
    
    for clave, valor in datos.items():
        if hasattr(clase, clave):
            setattr(clase, clave, valor)
            
    db.commit()
    return {"mensaje": "Clase actualizada correctamente"}


# 2. Actualización para que el profesor vea SU resumen en "Mis Clases"
# --- 3. MIS CLASES (Lógica ultra-optimizada) ---
@app.get("/mis-clases/{usuario_id}")
def obtener_mis_clases(usuario_id: int, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        return []
    
    resultado = []
    if usuario.rol == 'profesor':
        # ¡Como hay una sola tabla, el ID del profesor es exactamente su ID de usuario!
        clases = db.query(models.Clase).filter(models.Clase.profesor_id == usuario.id).all()
        for c in clases:
            resultado.append({
                "id": c.id, "nombre": c.nombre, "fecha": c.fecha, "hora": c.hora, 
                "disciplina": c.disciplina, "profesor_nombre": usuario.nombre
            })
    else:
        reservas = db.query(models.Reserva).filter(models.Reserva.usuario_id == usuario_id).all()
        for r in reservas:
            clase = db.query(models.Clase).filter(models.Clase.id == r.clase_id).first()
            if clase:
                prof = db.query(models.Usuario).filter(models.Usuario.id == clase.profesor_id).first()
                resultado.append({
                    "id": clase.id, "nombre": clase.nombre, "fecha": clase.fecha, "hora": clase.hora, 
                    "disciplina": clase.disciplina, 
                    "profesor_nombre": prof.nombre if prof else "Por asignar"
                })
                
    return resultado

# Endpoint para que el Admin vea la lista de alumnos de una clase
@app.get("/clases/{clase_id}/asistentes")
def obtener_asistentes(clase_id: int, db: Session = Depends(get_db)):
    # Unimos la tabla Usuarios con la tabla Reservas
    asistentes = db.query(models.Usuario).join(models.Reserva).filter(
        models.Reserva.clase_id == clase_id
    ).all()
    return asistentes

# 1. Estructuras de datos para las nuevas funciones
class NuevoProfesor(BaseModel):
    nombre: str
    email: str
    password: str
    telefono: Optional[str] = None # <-- AGREGAR ESTA LÍNEA

class ActualizarMembresia(BaseModel):
    membresia: str

# 2. Endpoint para que el Admin registre a un Profesor
@app.post("/crear-profesor")
def registrar_profesor(datos: NuevoProfesor, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    correo_limpio = datos.email.lower().strip()
    
    # Verificamos si el correo ya existe
    if db.query(models.Usuario).filter(models.Usuario.email == correo_limpio).first():
        raise HTTPException(status_code=400, detail="El correo ya pertenece a alguien")
    
    nuevo_profesor = models.Usuario(
        nombre=datos.nombre,
        email=correo_limpio,
        password=datos.password,
        rol="profesor",
        telefono=datos.telefono
    )
    
    db.add(nuevo_profesor)
    
    try:
        db.commit()
        
        # Programamos el envío del correo de bienvenida para el profesor
        background_tasks.add_task(
            enviar_correo_bienvenida,
            email_destino=correo_limpio,
            nombre=datos.nombre,
            contrasena=datos.password,
            rol="Profesor" # Especificamos el rol para el cuerpo del mensaje
        )
        
        return {"mensaje": "Profesor registrado con éxito y credenciales enviadas"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al registrar profesor: {str(e)}")

@app.post("/reservar")
def reservar_clase(reserva: ReservaCreate, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == reserva.usuario_id).first()
    clase = db.query(models.Clase).filter(models.Clase.id == reserva.clase_id).first()
    
    if not usuario or not clase:
        raise HTTPException(status_code=404, detail="No existe el usuario o la clase")

    # --- NUEVO: SEGURIDAD ANTI-DUPLICADOS ---
    reserva_previa = db.query(models.Reserva).filter(
        models.Reserva.usuario_id == reserva.usuario_id,
        models.Reserva.clase_id == reserva.clase_id
    ).first()
    
    if reserva_previa:
        raise HTTPException(status_code=400, detail="Ya estás inscrito en esta clase. ¡No gastes tus créditos de más!")
    
    # 2. VALIDACIÓN DE BILLETERA
    # ¿Tiene un plan activo?
    if not usuario.fecha_vencimiento_plan:
        raise HTTPException(status_code=400, detail="No tienes un plan activo. ¡Contrata uno para agendar!")
    
    # ¿El plan venció?
    fecha_venc = datetime.strptime(usuario.fecha_vencimiento_plan, "%Y-%m-%d")
    if datetime.now() > fecha_venc:
        raise HTTPException(status_code=400, detail="Tu plan ha vencido. ¡Renúevalo para seguir entrenando!")
    
    # ¿Le quedan clases? (Si es 999 es ilimitado)
    if usuario.clases_restantes <= 0 and usuario.clases_restantes != 999:
        raise HTTPException(status_code=400, detail="No te quedan clases en tu saldo mensual.")

    # 3. Registrar reserva y descontar clase
    nueva_reserva = models.Reserva(usuario_id=reserva.usuario_id, clase_id=reserva.clase_id)
    db.add(nueva_reserva)
    
    # Descontamos la clase del saldo si no es un plan ilimitado
    if usuario.clases_restantes != 999:
        usuario.clases_restantes -= 1
        
    db.commit()
    return {"mensaje": "Reserva exitosa", "clases_restantes": usuario.clases_restantes}


# 3. Endpoint para ver a todos los alumnos y sus planes
@app.get("/alumnos")
def obtener_alumnos(db: Session = Depends(get_db)):
    # CAMBIO: Filtramos para que solo traiga a quienes tengan el rol "alumno"
    # Usamos .lower() por seguridad por si alguno se guardó con Mayúscula
    usuarios = db.query(models.Usuario).filter(models.Usuario.rol == "alumno").all()
    
    resultado = []
    nombres_planes = {
        1: "Mensual 4 Clases", 2: "Mensual 8 Clases", 3: "Mensual 12 Clases", 4: "Mensual Ilimitado",
        5: "Trimestral 12 Clases", 6: "Trimestral 24 Clases", 7: "Trimestral 36 Clases", 8: "Trimestral Ilimitado",
        9: "Semestral 24 Clases", 10: "Semestral 48 Clases", 11: "Semestral 72 Clases", 12: "Semestral Ilimitado"
    }

    for u in usuarios:
        plan_nombre = nombres_planes.get(u.plan_id, "Sin Plan Activo") if u.plan_id else "Sin Plan Activo"
        
        resultado.append({
            "id": u.id,
            "nombre": u.nombre,
            "email": u.email,
            "telefono": u.telefono, # <--- REVISA ESTA LÍNEA (sin tilde)
            "plan_nombre": plan_nombre,
            "clases_restantes": u.clases_restantes,
            "fecha_vencimiento": u.fecha_vencimiento_plan or "Sin fecha",
            "activo": u.activo if u.activo is not None else True 
        })
    return resultado


# --- ADMIN: GESTIÓN DE PROFESORES ---

# Ver todos los profesores registrados
@app.get("/profesores")
def obtener_profesores(db: Session = Depends(get_db)):
    # Buscamos solo a los que tienen el rol de "profesor"
    profesores = db.query(models.Usuario).filter(models.Usuario.rol == "profesor").all()
    
    resultado = []
    for p in profesores:
        resultado.append({
            "id": p.id,
            "nombre": p.nombre,
            "email": p.email,
            "telefono": p.telefono,
            # Nos aseguramos de enviar el estado activo
            "activo": p.activo if p.activo is not None else True 
        })
    return resultado

# Actualizar datos de cualquier usuario (incluyendo el rol o membresía)
@app.put("/usuarios/{usuario_id}")
def actualizar_usuario(usuario_id: int, datos: dict, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Actualizamos dinámicamente solo lo que nos envíen
    for clave, valor in datos.items():
        if hasattr(usuario, clave):
            setattr(usuario, clave, valor)
            
    db.commit()
    return {"mensaje": "Información actualizada correctamente"}



# NUEVO: Actualizar todos los datos del profesor
# --- SOLUCIÓN PUNTO 4: ACTUALIZAR PROFESOR CON MOLDE EXACTO ---
# --- 2. EDITAR PROFESOR (Buscamos en la tabla Usuario) ---
@app.put("/profesores/{profesor_id}")
def actualizar_profesor(profesor_id: int, datos: DatosProfesor, db: Session = Depends(get_db)):
    # Buscamos que el usuario exista y sea profesor
    profesor = db.query(models.Usuario).filter(models.Usuario.id == profesor_id, models.Usuario.rol == 'profesor').first()
    if not profesor:
        raise HTTPException(status_code=404, detail="Profesor no encontrado")
    
    if datos.nombre is not None: profesor.nombre = datos.nombre
    if datos.email is not None: profesor.email = datos.email
    if datos.telefono is not None: profesor.telefono = datos.telefono
    # Nota: No actualizamos 'especialidad' porque no existe en tu tabla de Base de Datos
    
    try:
        db.commit()
        db.refresh(profesor)
        return {"mensaje": "Profesor actualizado correctamente"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
# --- CLIENTE: CANCELAR RESERVA ---

@app.delete("/reservas/{usuario_id}/{clase_id}")
def cancelar_reserva(
    usuario_id: int, 
    clase_id: int, 
    background_tasks: BackgroundTasks, # <- NUEVO: Pedimos el gestor de tareas
    db: Session = Depends(get_db)
):
    reserva = db.query(models.Reserva).filter(
        models.Reserva.usuario_id == usuario_id,
        models.Reserva.clase_id == clase_id
    ).first()
    
    if not reserva:
        raise HTTPException(status_code=404, detail="No se encontró la reserva")
        
    db.delete(reserva)
    db.commit()

    # --- LÓGICA DE NOTIFICACIÓN ---
    # Buscamos la clase para saber su nombre y quién es el profesor
    clase = db.query(models.Clase).filter(models.Clase.id == clase_id).first()
    if clase and clase.profesor_id:
        profesor = db.query(models.Usuario).filter(models.Usuario.id == clase.profesor_id).first()
        alumno = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
        
        if profesor and alumno:
            # Mandamos a ejecutar el correo en segundo plano
            background_tasks.add_task(
                simular_envio_correo,
                profesor.email,
                "⚠️ Cupo liberado en tu clase",
                f"El alumno {alumno.nombre} ha cancelado su asistencia a '{clase.nombre}'. El cupo está disponible nuevamente en el sistema."
            )

    return {"mensaje": "Reserva cancelada y cupo liberado"}

@app.delete("/clases/{clase_id}")
def eliminar_clase(clase_id: int, db: Session = Depends(get_db)):
    clase = db.query(models.Clase).filter(models.Clase.id == clase_id).first()
    if not clase:
        raise HTTPException(status_code=404, detail="Clase no encontrada")
    
    # IMPORTANTE: Al borrar la clase, borramos también sus reservas
    db.query(models.Reserva).filter(models.Reserva.clase_id == clase_id).delete()
    
    db.delete(clase)
    db.commit()
    return {"mensaje": "Clase eliminada exitosamente"}

# --- NUEVO: CREAR ADMINISTRADOR ---
@app.post("/crear-admin")
def crear_administrador(datos: DatosAdmin, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    usuario_existente = db.query(models.Usuario).filter(models.Usuario.email == datos.email).first()
    if usuario_existente:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")
    
    nuevo_admin = models.Usuario(
        nombre=datos.nombre,
        email=datos.email,
        password=datos.password, 
        rol="administrador",
        telefono=datos.telefono
    )
    
    db.add(nuevo_admin)
    try:
        db.commit()
        
        # --- PROGRAMAR ENVÍO DE CORREO EN SEGUNDO PLANO ---
        background_tasks.add_task(
            enviar_correo_bienvenida,
            email_destino=datos.email,
            nombre=datos.nombre,
            contrasena=datos.password,
            rol="Administrador"
        )
        
        return {"mensaje": "Administrador creado exitosamente y accesos enviados"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error al crear administrador")

@app.post("/asignar-plan/{usuario_id}/{plan_id}")
def asignar_plan(usuario_id: int, plan_id: int, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    plan = db.query(models.Plan).filter(models.Plan.id == plan_id).first()
    
    if not usuario or not plan:
        raise HTTPException(status_code=404, detail="Usuario o Plan no encontrado")
    
    # Calculamos fecha de vencimiento (Hoy + duración del plan)
    vencimiento = datetime.now() + timedelta(days=plan.duracion_dias)
    
    usuario.plan_id = plan.id
    usuario.clases_restantes = plan.limite_clases
    usuario.fecha_vencimiento_plan = vencimiento.strftime("%Y-%m-%d")
    
    db.commit()
    return {"mensaje": f"Plan {plan.nombre} asignado hasta {usuario.fecha_vencimiento_plan}"}



@app.get("/perfil/{usuario_id}")
def obtener_perfil(usuario_id: int, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Buscamos el nombre del plan
    plan_nombre = "Sin Plan Activo"
    if usuario.plan_id:
        plan = db.query(models.Plan).filter(models.Plan.id == usuario.plan_id).first()
        if plan:
            plan_nombre = plan.nombre

    return {
        "nombre": usuario.nombre,
        "email": usuario.email,
        "plan_nombre": plan_nombre,
        "clases_restantes": usuario.clases_restantes,
        "fecha_vencimiento": usuario.fecha_vencimiento_plan or "N/A"
    }

# ELIMINAR USUARIO (Alumno, Profesor o Admin)
@app.delete("/usuarios/{usuario_id}")
def eliminar_usuario(usuario_id: int, db: Session = Depends(get_db)):
    # 1. Buscamos al usuario
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # 2. Limpiamos sus reservas para no dejar basura en la base de datos
    db.query(models.Reserva).filter(models.Reserva.usuario_id == usuario_id).delete()
    
    # (Nota: Si es profesor, las clases que creó seguirán existiendo, 
    # pero es mejor reasignarlas a otro profesor en el futuro)

    # 3. Borramos al usuario definitivamente
    db.delete(usuario)
    db.commit()
    
    return {"mensaje": f"Usuario {usuario.nombre} eliminado correctamente del sistema"}


# CAMBIAR ESTADO DE USUARIO (Inactivar / Reactivar)
@app.put("/usuarios/{usuario_id}/estado")
def cambiar_estado_usuario(usuario_id: int, db: Session = Depends(get_db)):
    # Buscamos al usuario
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Si estaba activo (True), lo pasamos a inactivo (False) y viceversa.
    usuario.activo = not usuario.activo 
    
    # Si lo estamos apagando, le limpiamos las reservas para mayor seguridad
    if not usuario.activo:
        db.query(models.Reserva).filter(models.Reserva.usuario_id == usuario_id).delete()
        
    db.commit()
    
    estado_texto = "Reactivado" if usuario.activo else "Inactivado"
    return {"mensaje": f"El usuario {usuario.nombre} ha sido {estado_texto}", "activo": usuario.activo}

@app.put("/cambiar-password")
def cambiar_password(datos: CambioPassword, db: Session = Depends(get_db)):
    # 1. Buscamos al usuario en la base de datos
    usuario = db.query(models.Usuario).filter(models.Usuario.id == datos.usuario_id).first()
    
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # 2. Verificamos que la contraseña actual sea correcta
    # (Revisa en tu models.py si tu columna se llama 'password' o 'contrasena' y ajusta esta línea)
    if usuario.password != datos.password_actual:
        raise HTTPException(status_code=400, detail="La contraseña actual es incorrecta")
    
    # 3. Guardamos la nueva contraseña
    usuario.password = datos.password_nueva
    
    try:
        db.commit()
        return {"mensaje": "Contraseña actualizada exitosamente"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error al actualizar la contraseña")


# --- SIMULADOR DE NOTIFICACIONES ---
def simular_envio_correo(destinatario: str, asunto: str, mensaje: str):
    # En el futuro, aquí conectarías SendGrid, AWS SES o Twilio (WhatsApp)
    print("\n" + "="*50)
    print(f"📧 [SISTEMA DE ALERTAS] Enviando correo...")
    print(f"Para: {destinatario}")
    print(f"Asunto: {asunto}")
    print(f"Mensaje: {mensaje}")
    print("✔️ Enviado con éxito.")
    print("="*50 + "\n")
