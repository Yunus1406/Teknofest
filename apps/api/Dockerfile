FROM python:3.12-slim

WORKDIR /app

# fonts-dejavu-core: Faz C.6 PDF üretimi (reportlab) Türkçe karakterleri
# (ğ, ş, ı, İ, ö, ü, ç) doğru göstermek için bir TTF font gerektiriyor —
# reportlab'ın varsayılan Helvetica'sı (WinAnsi/cp1252) bunları taşımıyor.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
