FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY crawler_engine ./crawler_engine
COPY main.py .
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
