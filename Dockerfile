FROM python:3.12

WORKDIR /app

COPY src /app/src
COPY requirements.txt isrgrootx1.crt /app/

RUN pip install -r requirements.txt

CMD ["python", "-m", "src.main"]
