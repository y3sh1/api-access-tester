FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY orders orders
COPY tests tests
USER 65532:65532
CMD ["python", "-m", "orders.demo"]
