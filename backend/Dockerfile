FROM python:3.11-slim

WORKDIR /app

# System deps (build tools); wheels for pyproj include PROJ
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    proj-bin \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Enable PROJ network for grid downloads and set data directory
ENV PROJ_NETWORK=ON
ENV PROJ_DATA=/app/proj_data
ENV PROJ_LIB=/app/proj_data
ENV PROJ_USER_WRITABLE_DIRECTORY=/app/proj_data

# Prefetch critical grids into the image (can be disabled via build arg GRID_FETCH=0)
ARG GRID_FETCH=1
RUN mkdir -p /app/proj_data && if [ "$GRID_FETCH" = "1" ]; then \
    projsync -s https://cdn.proj.org -r uk_os_OSTN15_NTv2_OSGBtoETRS.gsb -d /app/proj_data || true && \
    projsync -s https://cdn.proj.org -r uk_os_OSTN15_NTv2_OSGBtoETRS.tif -d /app/proj_data || true && \
    projsync -s https://cdn.proj.org -r uk_os_OSGM15_GB.tif -d /app/proj_data || true ; \
  fi

COPY . .

EXPOSE 3001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3001", "--reload"]
