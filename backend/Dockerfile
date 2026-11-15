# Usamos una imagen oficial de Python ligera
FROM python:3.11-slim

# Directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiamos e instalamos las dependencias necesarias
COPY src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto del código del proyecto
COPY . .

# Comando por defecto para ejecutar tu script principal
CMD ["python", "src/main.py"]