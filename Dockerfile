FROM python:3.11

COPY pyproject.toml /pyproject.toml

COPY src /src

RUN pip install --no-cache-dir --upgrade -e .

CMD ["python", "-m", "src.main"]
