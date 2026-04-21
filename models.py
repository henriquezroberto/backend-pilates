from sqlalchemy import Column, Integer, String, ForeignKey
from database import Base

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    rol = Column(String, default="cliente") # Puede ser: administrador, profesor, cliente
    membresia = Column(String, default="Basico") # Puede ser: Basico, Intermedio, Premium, Staff

# --- NUEVAS TABLAS ---

class Clase(Base):
    __tablename__ = "clases"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    fecha = Column(String)
    hora = Column(String)
    cupo_maximo = Column(Integer, default=10)
    # NUEVO: ID del profesor asignado
    profesor_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    # NUEVO: ¿Qué nivel de membresía exige esta clase?
    nivel_requerido = Column(String, default="Basico")

class Reserva(Base):
    __tablename__ = "reservas"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    clase_id = Column(Integer, ForeignKey("clases.id"))