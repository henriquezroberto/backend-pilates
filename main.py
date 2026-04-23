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

class DatosRegistro(BaseModel):
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
def registrar_usuario(datos: DatosRegistro, db: Session = Depends(get_db)):
    usuario_existente = db.query(models.Usuario).filter(models.Usuario.email == datos.email).first()
    if usuario_existente:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")
    
    # Hemos quitado la línea de 'membresia'
    nuevo_usuario = models.Usuario(
        nombre=datos.nombre,
        email=datos.email,
        password=datos.password, 
        rol="cliente"
    )
    
    db.add(nuevo_usuario)
    try:
        db.commit()
        return {"mensaje": "Usuario registrado exitosamente"}
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
        rol="profesor"
    )
    db.add(nuevo_profesor)
    db.commit()
    return {"mensaje": "Profesor registrado con éxito"}

# 3. Endpoint para ver a todos los alumnos y sus planes
@app.get("/alumnos")
def obtener_alumnos(db: Session = Depends(get_db)):
    # Traemos solo a los clientes para que el admin les gestione la membresía
    return db.query(models.Usuario).filter(models.Usuario.rol == "cliente").all()


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
    usuario_existente = db.query(models.Usuario).filter(models.Usuario.email == datos.email).first()
    if usuario_existente:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")
    
    # Hemos quitado la línea de 'membresia="Staff"'
    nuevo_admin = models.Usuario(
        nombre=datos.nombre,
        email=datos.email,
        password=datos.password, 
        rol="administrador"
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

@app.get("/alumnos")
def obtener_alumnos(db: Session = Depends(get_db)):
    # Filtramos solo por el rol de 'cliente'
    alumnos = db.query(models.Usuario).filter(models.Usuario.rol == 'cliente').all()
    resultado = []
    for a in alumnos:
        # Buscamos el nombre del plan si tiene uno asignado
        plan_nombre = "Sin Plan Activo"
        if a.plan_id:
            plan = db.query(models.Plan).filter(models.Plan.id == a.plan_id).first()
            if plan:
                plan_nombre = plan.nombre
        
        resultado.append({
            "id": a.id,
            "nombre": a.nombre,
            "email": a.email,
            "plan_nombre": plan_nombre,
            "clases_restantes": a.clases_restantes,
            "fecha_vencimiento": a.fecha_vencimiento_plan or "N/A"
        })
    return resultado


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
