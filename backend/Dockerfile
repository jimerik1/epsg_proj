FROM python:3.11-slim

WORKDIR /app

# System deps (build tools); wheels for pyproj include PROJ
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Enable PROJ network for grid downloads
ENV PROJ_NETWORK=ON
ENV PROJ_DATA_DIR=/app/proj_data

COPY . .

EXPOSE 3001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3001", "--reload"]

