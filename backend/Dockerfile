FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-create the data directory used for the SQLite volume mount
RUN mkdir -p /app/data

COPY . .

EXPOSE 5000

CMD ["python", "app.py"]
