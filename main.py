from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks # <- Agrega BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
import models
from database import engine, SessionLocal
from typing import List, Optional  # <--- ASEGÚRATE DE QUE ESTÉ "Optional"
from datetime import datetime, timedelta

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



# ESTRUCTURAS DE DATOS PARA ADMINISTRADORES
class DatosAdmin(BaseModel):
    nombre: str
    email: str
    password: str

class ReservaCreate(BaseModel):
    usuario_id: int
    clase_id: int

# NUEVO MOLDE PARA EDITAR PROFESOR
class DatosProfesor(BaseModel):
    nombre: Optional[str] = None
    email: Optional[str] = None
    especialidad: Optional[str] = None # Flutter lo envía, pero lo ignoraremos en la BD por ahora

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


# 4. NUEVO: Endpoint para registrar un usuario
@app.post("/registro")
def registrar_usuario(datos: RegistroData, db: Session = Depends(get_db)):
    correo_limpio = datos.email.lower().strip()
    
    usuario_existente = db.query(models.Usuario).filter(models.Usuario.email == correo_limpio).first()
    if usuario_existente:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")
    
    rol_asignado = "administrador" if correo_limpio == "admin@pilates.com" else "cliente"
    # Si es el jefe, es Staff. Si es alumno nuevo, entra como Básico por defecto.
    membresia_asignada = "Staff" if rol_asignado == "administrador" else "Basico"
    
    nuevo_usuario = models.Usuario(
        nombre=datos.nombre, 
        email=correo_limpio, 
        password=datos.password,
        rol=rol_asignado,
        membresia=membresia_asignada # <- NUEVO
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    
    return {"mensaje": "Usuario creado", "usuario": {"nombre": nuevo_usuario.nombre}}

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
                "membresia": usuario.membresia # <- NUEVO: La App ahora sabrá el plan del usuario
            }
        }
    
    raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")

# 6. Estructura para recibir datos de una nueva clase
class ClaseData(BaseModel):
    nombre: str
    fecha: str
    hora: str
    cupo_maximo: int
    profesor_id: int
    nivel_requerido: str # <- NUEVO

# 7. Endpoint para crear una clase nueva (Esto lo usará el Admin/Profesor)
@app.post("/clases")
def crear_clase(datos: ClaseData, db: Session = Depends(get_db)):
    nueva_clase = models.Clase(
        nombre=datos.nombre,
        fecha=datos.fecha,
        hora=datos.hora,
        cupo_maximo=datos.cupo_maximo,
        profesor_id=datos.profesor_id,
        nivel_requerido=datos.nivel_requerido
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
                "nivel_requerido": c.nivel_requerido,
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

# Endpoint para guardar la reserva
@app.post("/reservas")
def agendar_clase(datos: ReservaData, db: Session = Depends(get_db)):
    # 1. Buscar la clase y al usuario (¡Nuevo: Necesitamos al usuario para saber su membresía!)
    clase = db.query(models.Clase).filter(models.Clase.id == datos.clase_id).first()
    usuario = db.query(models.Usuario).filter(models.Usuario.id == datos.usuario_id).first()
    
    if not clase:
        raise HTTPException(status_code=404, detail="Clase no encontrada")
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # --- NUEVA LÓGICA DE JERARQUÍA DE MEMBRESÍAS ---
    # Le damos un valor numérico a cada nivel para poder compararlos
    jerarquia = {"Basico": 1, "Intermedio": 2, "Premium": 3, "Staff": 99}
    
    nivel_alumno = jerarquia.get(usuario.membresia, 1) # Si no tiene, asume 1 (Basico)
    nivel_clase = jerarquia.get(clase.nivel_requerido, 1) # Si la clase no tiene, asume 1 (Basico)
    
    # Si el número del alumno es menor al número que exige la clase, lo bloqueamos
    if nivel_alumno < nivel_clase:
        raise HTTPException(
            status_code=400, # Usamos 400 para que tu app de Flutter muestre la alerta naranja
            detail=f"Tu plan ({usuario.membresia}) no te permite agendar clases de nivel {clase.nivel_requerido}."
        )
    # ------------------------------------------------

    # 2. Contar cuántos alumnos ya están inscritos
    total_inscritos = db.query(models.Reserva).filter(models.Reserva.clase_id == datos.clase_id).count()
    
    # 3. ¡Bloquear si está llena!
    if total_inscritos >= clase.cupo_maximo:
        raise HTTPException(status_code=400, detail="¡Lo sentimos! Esta clase ya está llena")

    # 4. Verificar si el alumno ya la tenía reservada
    reserva_existente = db.query(models.Reserva).filter(
        models.Reserva.usuario_id == datos.usuario_id,
        models.Reserva.clase_id == datos.clase_id
    ).first()
    
    if reserva_existente:
        raise HTTPException(status_code=400, detail="Ya tienes agendada esta clase")
        
    # 5. Si pasa todas las pruebas, lo inscribimos
    nueva_reserva = models.Reserva(usuario_id=datos.usuario_id, clase_id=datos.clase_id)
    db.add(nueva_reserva)
    db.commit()
    return {"mensaje": "¡Clase agendada con éxito!"}

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
                "nivel_requerido": c.nivel_requerido, "profesor_nombre": usuario.nombre
            })
    else:
        reservas = db.query(models.Reserva).filter(models.Reserva.usuario_id == usuario_id).all()
        for r in reservas:
            clase = db.query(models.Clase).filter(models.Clase.id == r.clase_id).first()
            if clase:
                prof = db.query(models.Usuario).filter(models.Usuario.id == clase.profesor_id).first()
                resultado.append({
                    "id": clase.id, "nombre": clase.nombre, "fecha": clase.fecha, "hora": clase.hora, 
                    "nivel_requerido": clase.nivel_requerido, 
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

class ActualizarMembresia(BaseModel):
    membresia: str

# 2. Endpoint para que el Admin registre a un Profesor
@app.post("/crear-profesor")
def registrar_profesor(datos: NuevoProfesor, db: Session = Depends(get_db)):
    correo_limpio = datos.email.lower().strip()
    if db.query(models.Usuario).filter(models.Usuario.email == correo_limpio).first():
        raise HTTPException(status_code=400, detail="El correo ya pertenece a alguien")
    
    nuevo_profesor = models.Usuario(
        nombre=datos.nombre,
        email=correo_limpio,
        password=datos.password,
        rol="profesor", # Rol con poder para crear clases
        membresia="Staff" # No necesita pagar plan
    )
    db.add(nuevo_profesor)
    db.commit()
    return {"mensaje": "Profesor registrado con éxito"}

# 3. Endpoint para ver a todos los alumnos y sus planes
@app.get("/alumnos")
def obtener_alumnos(db: Session = Depends(get_db)):
    # Traemos solo a los clientes para que el admin les gestione la membresía
    return db.query(models.Usuario).filter(models.Usuario.rol == "cliente").all()

# 4. Endpoint para cambiarle el plan a un alumno (Básico -> Premium, etc.)
@app.put("/usuarios/{usuario_id}/membresia")
def asignar_membresia(usuario_id: int, datos: ActualizarMembresia, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    usuario.membresia = datos.membresia
    db.commit()
    return {"mensaje": f"Membresía actualizada a {datos.membresia}"}

# --- ADMIN: GESTIÓN DE PROFESORES ---

# Ver todos los profesores registrados
@app.get("/profesores")
def obtener_profesores(db: Session = Depends(get_db)):
    return db.query(models.Usuario).filter(models.Usuario.rol == "profesor").all()

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
def crear_administrador(datos: DatosAdmin, db: Session = Depends(get_db)):
    # 1. Verificamos que el correo no esté usado
    usuario_existente = db.query(models.Usuario).filter(models.Usuario.email == datos.email).first()
    if usuario_existente:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")
    
    # 2. Creamos al usuario forzando el rol de 'administrador'
    nuevo_admin = models.Usuario(
        nombre=datos.nombre,
        email=datos.email,
        password=datos.password, 
        rol="administrador",
        membresia="Staff"
    )
    
    db.add(nuevo_admin)
    try:
        db.commit()
        return {"mensaje": "Administrador creado exitosamente"}
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

@app.post("/reservar")
def reservar_clase(reserva: ReservaCreate, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == reserva.usuario_id).first()
    clase = db.query(models.Clase).filter(models.Clase.id == reserva.clase_id).first()
    
    # 1. Validaciones básicas
    if not usuario or not clase:
        raise HTTPException(status_code=404, detail="No existe el usuario o la clase")
    
    # 2. VALIDACIÓN DE BILLETERA
    # ¿Tiene un plan activo?
    if not usuario.fecha_vencimiento_plan:
        raise HTTPException(status_code=400, detail="No tienes un plan activo")
    
    # ¿El plan venció?
    fecha_venc = datetime.strptime(usuario.fecha_vencimiento_plan, "%Y-%m-%d")
    if datetime.now() > fecha_venc:
        raise HTTPException(status_code=400, detail="Tu plan ha vencido")
    
    # ¿Le quedan clases? (Si es 999 es ilimitado)
    if usuario.clases_restantes <= 0 and usuario.clases_restantes != 999:
        raise HTTPException(status_code=400, detail="No te quedan clases disponibles")

    # 3. Registrar reserva y descontar clase
    nueva_reserva = models.Reserva(usuario_id=reserva.usuario_id, clase_id=reserva.clase_id)
    db.add(nueva_reserva)
    
    # Descontamos si no es ilimitado
    if usuario.clases_restantes != 999:
        usuario.clases_restantes -= 1
        
    db.commit()
    return {"mensaje": "Reserva exitosa", "clases_restantes": usuario.clases_restantes}

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
