from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from database import Base

# --- 1. NUEVA TABLA: EL CATÁLOGO DE PLANES ---
class Plan(Base):
    __tablename__ = "planes"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True) # Ej: "Mensual Opción 2 (8 Clases)"
    duracion_dias = Column(Integer)     # Ej: 30, 90 o 180
    limite_clases = Column(Integer)     # Ej: 4, 8, 12. (Podemos usar 999 para "Ilimitadas")

# --- 2. TABLA USUARIOS MEJORADA (LA BILLETERA) ---
class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    rol = Column(String, default="cliente") 
    telefono = Column(String, nullable=True) # <-- AGREGAR ESTA LÍNEA
    
    # LA BILLETERA VIRTUAL DEL ALUMNO
    plan_id = Column(Integer, ForeignKey("planes.id"), nullable=True)
    fecha_vencimiento_plan = Column(String, nullable=True) # Ej: "2026-05-23"
    clases_restantes = Column(Integer, default=0) # El contador que bajará con cada reserva
    activo = Column(Boolean, default=True)  # Para marcar si el plan está activo o no (si es False, el alumno no puede reservar)
# --- 3. TABLA CLASES (Se mantiene igual) ---
class Clase(Base):
    __tablename__ = "clases"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    fecha = Column(String)
    hora = Column(String)
    cupo_maximo = Column(Integer, default=10)
    profesor_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    # Ya no necesitamos "nivel_requerido" porque todas las clases aceptan todas las disciplinas de los planes
    disciplina = Column(String, default="General") 

# --- 4. TABLA RESERVAS (Se mantiene igual) ---
class Reserva(Base):
    __tablename__ = "reservas"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    clase_id = Column(Integer, ForeignKey("clases.id"))